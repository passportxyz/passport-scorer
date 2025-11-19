use anyhow::{Context, Result};
use colored::*;
use reqwest::Client;
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::collections::BTreeMap;
use std::path::PathBuf;
use std::process::Stdio;
use std::time::Duration;
use tokio::io::{AsyncBufReadExt, BufReader};
use tokio::process::{Child, Command};
use tokio::time::sleep;

/// Test configuration loaded from test_config.json
#[derive(Debug, Deserialize, Serialize)]
struct TestConfig {
    test_address: String,
    scorer_id: i32,
    api_key: String,
    issuer_did: String,
    providers: Vec<String>,
    expected_score_above: f64,
}

const PYTHON_BASE: &str = "http://localhost:8002";
const RUST_BASE: &str = "http://localhost:3000";

/// Load environment variables from .env.development file
fn load_env_file(project_root: &PathBuf) -> Result<()> {
    let env_file = project_root.join(".env.development");

    if !env_file.exists() {
        anyhow::bail!(
            "Could not find .env.development at {}\nPlease create it following dev-setup/DEV_SETUP.md",
            env_file.display()
        );
    }

    // Use dotenvy to load the env file (override existing vars)
    dotenvy::from_path_override(&env_file)
        .context("Failed to load .env.development")?;

    println!("{}", "Loaded environment from .env.development".green());
    Ok(())
}

struct ServerManager {
    python_process: Option<Child>,
    rust_process: Option<Child>,
    project_root: PathBuf,
}

impl ServerManager {
    fn new() -> Result<Self> {
        // Find project root (parent of rust-scorer)
        let current = std::env::current_dir()?;
        let project_root = if current.ends_with("comparison-tests") {
            current.parent().unwrap().parent().unwrap().to_path_buf()
        } else if current.ends_with("rust-scorer") {
            current.parent().unwrap().to_path_buf()
        } else {
            current
        };

        Ok(Self {
            python_process: None,
            rust_process: None,
            project_root,
        })
    }

    async fn start_python(&mut self) -> Result<()> {
        println!("{}", "Starting Python server...".cyan());

        let api_dir = self.project_root.join("api");

        // Verify required env vars are set
        std::env::var("DATABASE_URL").context("DATABASE_URL not set")?;
        std::env::var("CERAMIC_CACHE_SCORER_ID").context("CERAMIC_CACHE_SCORER_ID not set")?;

        let mut child = Command::new("poetry")
            .args(["run", "python", "manage.py", "runserver", "0.0.0.0:8002"])
            .current_dir(&api_dir)
            // Inherit all env vars from parent process
            .envs(std::env::vars())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .kill_on_drop(true)
            .spawn()
            .context("Failed to start Python server")?;

        // Spawn task to forward stderr (where Django logs go)
        if let Some(stderr) = child.stderr.take() {
            tokio::spawn(async move {
                let reader = BufReader::new(stderr);
                let mut lines = reader.lines();
                while let Ok(Some(line)) = lines.next_line().await {
                    if line.contains("Error") || line.contains("Exception") {
                        eprintln!("{} {}", "[Python]".yellow(), line.red());
                    }
                }
            });
        }

        self.python_process = Some(child);
        Ok(())
    }

    async fn start_rust(&mut self) -> Result<()> {
        println!("{}", "Starting Rust server...".cyan());

        let rust_dir = self.project_root.join("rust-scorer");

        // Verify required env vars are set
        std::env::var("DATABASE_URL").context("DATABASE_URL not set - source .env.development first")?;
        std::env::var("CERAMIC_CACHE_SCORER_ID").context("CERAMIC_CACHE_SCORER_ID not set - source .env.development first")?;

        let mut child = Command::new("cargo")
            .args(["run", "--release"])
            .current_dir(&rust_dir)
            // Inherit all env vars from parent process
            .envs(std::env::vars())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .kill_on_drop(true)
            .spawn()
            .context("Failed to start Rust server")?;

        // Spawn task to forward stderr
        if let Some(stderr) = child.stderr.take() {
            tokio::spawn(async move {
                let reader = BufReader::new(stderr);
                let mut lines = reader.lines();
                while let Ok(Some(line)) = lines.next_line().await {
                    if line.contains("error") || line.contains("Error") {
                        eprintln!("{} {}", "[Rust]".blue(), line.red());
                    }
                }
            });
        }

        self.rust_process = Some(child);
        Ok(())
    }

    async fn wait_for_healthy(&self, client: &Client) -> Result<()> {
        println!("{}", "Waiting for servers to be healthy...".cyan());

        // Wait for Python - use weights endpoint since no /health exists
        let python_health = format!("{}/internal/embed/weights", PYTHON_BASE);
        for i in 0..60 {
            match client.get(&python_health).send().await {
                Ok(resp) if resp.status().is_success() => {
                    println!("{}", format!("  Python server ready ({}s)", i).green());
                    break;
                }
                _ if i == 59 => {
                    anyhow::bail!("Python server failed to start after 60s");
                }
                _ => sleep(Duration::from_secs(1)).await,
            }
        }

        // Wait for Rust
        let rust_health = format!("{}/health", RUST_BASE);
        for i in 0..60 {
            match client.get(&rust_health).send().await {
                Ok(resp) if resp.status().is_success() => {
                    println!("{}", format!("  Rust server ready ({}s)", i).green());
                    return Ok(());
                }
                _ if i == 59 => {
                    anyhow::bail!("Rust server failed to start after 60s");
                }
                _ => sleep(Duration::from_secs(1)).await,
            }
        }

        Ok(())
    }

    async fn shutdown(&mut self) {
        println!("{}", "\nShutting down servers...".cyan());

        if let Some(mut child) = self.python_process.take() {
            let _ = child.kill().await;
        }
        if let Some(mut child) = self.rust_process.take() {
            let _ = child.kill().await;
        }
    }
}

struct TestRunner {
    client: Client,
    passed: usize,
    failed: usize,
}

impl TestRunner {
    fn new() -> Self {
        Self {
            client: Client::builder()
                .timeout(Duration::from_secs(30))
                .build()
                .unwrap(),
            passed: 0,
            failed: 0,
        }
    }

    async fn compare_get(&mut self, name: &str, path: &str) -> Result<bool> {
        print!("Testing {} ... ", name.bold());

        let python_url = format!("{}{}", PYTHON_BASE, path);
        let rust_url = format!("{}{}", RUST_BASE, path);

        // Make requests
        let python_resp = self.client.get(&python_url).send().await
            .context("Python request failed")?;
        let rust_resp = self.client.get(&rust_url).send().await
            .context("Rust request failed")?;

        // Check status codes
        let python_status = python_resp.status();
        let rust_status = rust_resp.status();

        if python_status != rust_status {
            println!("{}", "FAIL".red());
            println!("  Status mismatch: Python={}, Rust={}", python_status, rust_status);
            self.failed += 1;
            return Ok(false);
        }

        // Parse JSON
        let python_json: Value = python_resp.json().await
            .context("Failed to parse Python response as JSON")?;
        let rust_json: Value = rust_resp.json().await
            .context("Failed to parse Rust response as JSON")?;

        // Compare
        if let Err(diff) = compare_json(&python_json, &rust_json) {
            println!("{}", "FAIL".red());
            println!("{}", diff);
            self.failed += 1;
            Ok(false)
        } else {
            println!("{}", "PASS".green());
            self.passed += 1;
            Ok(true)
        }
    }

    async fn compare_get_with_api_key(&mut self, name: &str, path: &str, api_key: &str) -> Result<bool> {
        print!("Testing {} ... ", name.bold());

        let python_url = format!("{}{}", PYTHON_BASE, path);
        let rust_url = format!("{}{}", RUST_BASE, path);

        // Make requests with API key
        let python_resp = self.client.get(&python_url)
            .header("X-API-Key", api_key)
            .send().await
            .context("Python request failed")?;
        let rust_resp = self.client.get(&rust_url)
            .header("X-API-Key", api_key)
            .send().await
            .context("Rust request failed")?;

        self.compare_responses(name, python_resp, rust_resp).await
    }

    async fn compare_get_internal(&mut self, name: &str, path: &str, internal_key: &str) -> Result<bool> {
        print!("Testing {} ... ", name.bold());

        let python_url = format!("{}{}", PYTHON_BASE, path);
        let rust_url = format!("{}{}", RUST_BASE, path);

        // Make requests with internal Authorization header
        let python_resp = self.client.get(&python_url)
            .header("AUTHORIZATION", internal_key)
            .send().await
            .context("Python request failed")?;
        let rust_resp = self.client.get(&rust_url)
            .header("AUTHORIZATION", internal_key)
            .send().await
            .context("Rust request failed")?;

        self.compare_responses(name, python_resp, rust_resp).await
    }

    async fn compare_responses(&mut self, _name: &str, python_resp: reqwest::Response, rust_resp: reqwest::Response) -> Result<bool> {

        // Check status codes
        let python_status = python_resp.status();
        let rust_status = rust_resp.status();

        if python_status != rust_status {
            println!("{}", "FAIL".red());
            println!("  Status mismatch: Python={}, Rust={}", python_status, rust_status);
            self.failed += 1;
            return Ok(false);
        }

        // Ensure we got a successful response
        if !python_status.is_success() {
            let python_body = python_resp.text().await.unwrap_or_default();
            let rust_body = rust_resp.text().await.unwrap_or_default();
            println!("{}", "FAIL".red());
            println!("  Both returned error status: {}", python_status);
            println!("  Python response: {}", python_body);
            println!("  Rust response: {}", rust_body);
            self.failed += 1;
            return Ok(false);
        }

        // Parse JSON
        let python_json: Value = python_resp.json().await
            .context("Failed to parse Python response as JSON")?;
        let rust_json: Value = rust_resp.json().await
            .context("Failed to parse Rust response as JSON")?;

        // Compare
        if let Err(diff) = compare_json(&python_json, &rust_json) {
            println!("{}", "FAIL".red());
            println!("{}", diff);
            self.failed += 1;
            Ok(false)
        } else {
            println!("{}", "PASS".green());
            self.passed += 1;
            Ok(true)
        }
    }

    fn summary(&self) {
        println!("\n{}", "=".repeat(50));
        println!(
            "Results: {} passed, {} failed",
            self.passed.to_string().green(),
            if self.failed > 0 {
                self.failed.to_string().red()
            } else {
                self.failed.to_string().green()
            }
        );
        println!("{}", "=".repeat(50));
    }
}

/// Compare two JSON values, returning an error with diff if they don't match
fn compare_json(python: &Value, rust: &Value) -> Result<(), String> {
    let python_sorted = sort_json(python);
    let rust_sorted = sort_json(rust);

    if python_sorted == rust_sorted {
        return Ok(());
    }

    // Generate diff
    let python_pretty = serde_json::to_string_pretty(&python_sorted).unwrap();
    let rust_pretty = serde_json::to_string_pretty(&rust_sorted).unwrap();

    let mut diff = String::new();
    diff.push_str("  Difference found:\n");
    diff.push_str(&format!("  {}\n", "Python:".yellow()));
    for line in python_pretty.lines().take(20) {
        diff.push_str(&format!("    {}\n", line));
    }
    diff.push_str(&format!("  {}\n", "Rust:".blue()));
    for line in rust_pretty.lines().take(20) {
        diff.push_str(&format!("    {}\n", line));
    }

    Err(diff)
}

/// Sort JSON objects by key for consistent comparison
fn sort_json(value: &Value) -> Value {
    match value {
        Value::Object(map) => {
            let sorted: BTreeMap<String, Value> = map
                .iter()
                .map(|(k, v)| (k.clone(), sort_json(v)))
                .collect();
            Value::Object(sorted.into_iter().collect())
        }
        Value::Array(arr) => {
            Value::Array(arr.iter().map(sort_json).collect())
        }
        _ => value.clone(),
    }
}

#[tokio::main]
async fn main() -> Result<()> {
    println!("{}", "\n========================================".bold());
    println!("{}", "  Python <-> Rust Comparison Tests".bold());
    println!("{}", "========================================\n".bold());

    // Find project root and load environment
    let current = std::env::current_dir()?;
    let project_root = if current.ends_with("comparison-tests") {
        current.parent().unwrap().parent().unwrap().to_path_buf()
    } else if current.ends_with("rust-scorer") {
        current.parent().unwrap().to_path_buf()
    } else {
        current
    };

    load_env_file(&project_root)?;

    // Load test configuration
    let config_path = project_root.join("rust-scorer/comparison-tests/test_config.json");
    let config: TestConfig = if config_path.exists() {
        let config_str = std::fs::read_to_string(&config_path)
            .context("Failed to read test_config.json")?;
        serde_json::from_str(&config_str)
            .context("Failed to parse test_config.json")?
    } else {
        anyhow::bail!(
            "test_config.json not found at {}\nRun: poetry run python ../dev-setup/create_test_credentials.py",
            config_path.display()
        );
    };

    println!("{}", format!("Loaded test config: address={}, scorer_id={}",
        &config.test_address[..10], config.scorer_id).green());

    let mut server_manager = ServerManager::new()?;
    let mut test_runner = TestRunner::new();

    // Start servers
    server_manager.start_python().await?;
    server_manager.start_rust().await?;

    // Wait for health
    server_manager.wait_for_healthy(&test_runner.client).await?;

    println!("\n{}", "Running comparison tests...".bold());
    println!("{}", "-".repeat(50));

    // Run tests
    test_runner
        .compare_get("Weights endpoint", "/internal/embed/weights")
        .await?;

    // Internal scoring endpoint test (available in Django dev server)
    let internal_key = std::env::var("CGRANTS_API_TOKEN")
        .unwrap_or_else(|_| "dev-internal-api-key".to_string());
    let score_path = format!("/internal/score/v2/{}/{}", config.scorer_id, config.test_address);
    test_runner
        .compare_get_internal("Internal Score endpoint", &score_path, &internal_key)
        .await?;

    // Summary
    test_runner.summary();

    // Shutdown
    server_manager.shutdown().await;

    // Exit with appropriate code
    if test_runner.failed > 0 {
        std::process::exit(1);
    }

    Ok(())
}
