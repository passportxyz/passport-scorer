use anyhow::{Context, Result};
use colored::*;
use jsonwebtoken::{encode, EncodingKey, Header};
use reqwest::Client;
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::collections::BTreeMap;
use std::path::PathBuf;
use std::process::Stdio;
use std::time::Duration;
use tokio::io::{AsyncBufReadExt, BufReader};
use tokio::process::{Child, Command};
use tokio::time::sleep;
use clap::Parser;

/// Command line arguments
#[derive(Parser, Debug)]
#[command(name = "comparison-tests")]
#[command(about = "Compare Python and Rust scorer implementations", long_about = None)]
struct Args {
    /// Print Rust responses in verbose mode
    #[arg(short, long)]
    verbose: bool,
}

/// Test configuration loaded from test_config.json
#[derive(Debug, Deserialize, Serialize)]
struct TestConfig {
    test_address: String,
    scorer_id: i32,
    api_key: String,
    issuer_did: String,
    providers: Vec<String>,
    expected_score_above: f64,
    #[serde(default)]
    credentials: Vec<Value>,
}

const PYTHON_PORT: u16 = 8002;
const RUST_PORT: u16 = 3000;
const PYTHON_BASE: &str = "http://localhost:8002";
const RUST_BASE: &str = "http://localhost:3000";

/// JWT Claims for ceramic cache authentication
/// Matches Python's ninja_jwt RefreshToken format
#[derive(Debug, Serialize, Deserialize)]
struct JwtClaims {
    did: String,
    token_type: String,
    exp: usize,
    iat: usize,  // Issued at timestamp
    jti: String, // JWT ID (unique identifier)
}

/// Generate a test JWT token for ceramic cache endpoints
/// Mimics Python's DbCacheToken behavior
fn generate_test_jwt(address: &str) -> Result<String> {
    let did = format!("did:pkh:eip155:1:{}", address.to_lowercase());

    let now = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)?
        .as_secs() as usize;

    // Token expires in 7 days (matching Python's DbCacheToken lifetime)
    let exp = now + (7 * 24 * 60 * 60);

    let claims = JwtClaims {
        did,
        token_type: "access".to_string(),
        exp,
        iat: now,  // Issued at current timestamp
        jti: format!("test-jti-{}", now), // Simple unique ID for testing
    };

    // Use SECRET_KEY from environment (must match Django's SECRET_KEY for JWT validation)
    // Django stores it with quotes in .env but they are stripped when loaded
    let secret = std::env::var("SECRET_KEY")
        .unwrap_or_else(|_| "dev-secret-key-not-for-production".to_string())
        .trim_matches('"')
        .to_string();

    let token = encode(
        &Header::default(),
        &claims,
        &EncodingKey::from_secret(secret.as_bytes()),
    )?;

    Ok(token)
}

/// Check if a port is in use
fn check_port_available(port: u16) -> Result<()> {
    use std::net::TcpListener;
    match TcpListener::bind(("127.0.0.1", port)) {
        Ok(_) => Ok(()),
        Err(_) => anyhow::bail!(
            "Port {} is already in use!\n\
             Kill existing processes with: fuser -k {}/tcp\n\
             Or run: fuser -k 3000/tcp 8002/tcp",
            port, port
        ),
    }
}

/// Ensure required ports are available before starting
fn ensure_ports_available() -> Result<()> {
    check_port_available(PYTHON_PORT).context("Python server port check failed")?;
    check_port_available(RUST_PORT).context("Rust server port check failed")?;
    println!("{}", "Ports 3000 and 8002 are available".green());
    Ok(())
}

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

// Ensure cleanup happens even on error/panic (like a finally block)
impl Drop for ServerManager {
    fn drop(&mut self) {
        println!("{}", "\nShutting down servers...".cyan());

        // Kill Python process group (Django spawns child processes)
        if let Some(child) = self.python_process.take() {
            let pid = child.id();
            if let Some(pid) = pid {
                // Kill the entire process group
                unsafe {
                    libc::kill(-(pid as i32), libc::SIGKILL);
                }
            }
        }

        // Kill Rust process
        if let Some(mut child) = self.rust_process.take() {
            let _ = child.start_kill();
        }
    }
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
            // Make this its own process group so we can kill all children
            .process_group(0)
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

        // Filter out cargo-specific env vars that cause fingerprint mismatches
        let filtered_env: Vec<(String, String)> = std::env::vars()
            .filter(|(k, _)| {
                !k.starts_with("CARGO_")
                && k != "RUSTFLAGS"
                && k != "RUSTC"
                && k != "RUSTDOC"
            })
            .collect();

        let mut child = Command::new("cargo")
            .args(["run", "--release"])
            .current_dir(&rust_dir)
            .env_clear()
            .envs(filtered_env)
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
                        eprintln!("{} {}", "[Rust ERROR]".red(), line.red());
                    } else {
                        eprintln!("{} {}", "[Rust]".blue(), line.green());
                    }
                }
            });
        }

        // Spawn task to drain stdout (server logs go here) - prevents pipe buffer from blocking
        if let Some(stdout) = child.stdout.take() {
            tokio::spawn(async move {
                let reader = BufReader::new(stdout);
                let mut lines = reader.lines();
                // Just drain the output to prevent blocking - uncomment below to see logs
                while let Ok(Some(_line)) = lines.next_line().await {
                    // Uncomment to see server JSON logs:
                    // eprintln!("{} {}", "[Rust LOG]".dimmed(), _line);
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

        // Wait for Rust (120s timeout for didkit compilation)
        let rust_health = format!("{}/health", RUST_BASE);
        for i in 0..120 {
            match client.get(&rust_health).send().await {
                Ok(resp) if resp.status().is_success() => {
                    println!("{}", format!("  Rust server ready ({}s)", i).green());
                    return Ok(());
                }
                _ if i == 119 => {
                    anyhow::bail!("Rust server failed to start after 120s");
                }
                _ => sleep(Duration::from_secs(1)).await,
            }
        }

        Ok(())
    }
}

struct TestRunner {
    client: Client,
    passed: usize,
    failed: usize,
    verbose: bool,
}

impl TestRunner {
    fn new(verbose: bool) -> Self {
        Self {
            client: Client::builder()
                .timeout(Duration::from_secs(30))
                .build()
                .unwrap(),
            passed: 0,
            failed: 0,
            verbose,
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

    async fn compare_post_internal(&mut self, name: &str, path: &str, body: &Value, internal_key: &str) -> Result<bool> {
        print!("Testing {} ... ", name.bold());

        let python_url = format!("{}{}", PYTHON_BASE, path);
        let rust_url = format!("{}{}", RUST_BASE, path);

        // Make POST requests with internal Authorization header
        let python_resp = self.client.post(&python_url)
            .header("AUTHORIZATION", internal_key)
            .header("Content-Type", "application/json")
            .json(body)
            .send().await
            .context("Python request failed")?;
        let rust_resp = self.client.post(&rust_url)
            .header("AUTHORIZATION", internal_key)
            .header("Content-Type", "application/json")
            .json(body)
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

        // Print Rust response if verbose mode is enabled
        if self.verbose {
            println!("\n{}", "  Rust Response:".blue().bold());
            println!("{}", serde_json::to_string_pretty(&rust_json).unwrap_or_default());
        }

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

    /// Compare error responses (just status codes, not body content)
    async fn compare_error(&mut self, name: &str, path: &str, expected_status: u16) -> Result<bool> {
        print!("Testing {} ... ", name.bold());

        let python_url = format!("{}{}", PYTHON_BASE, path);
        let rust_url = format!("{}{}", RUST_BASE, path);

        // Make requests without auth
        let python_resp = self.client.get(&python_url)
            .send().await
            .context("Python request failed")?;
        let rust_resp = self.client.get(&rust_url)
            .send().await
            .context("Rust request failed")?;

        let python_status = python_resp.status().as_u16();
        let rust_status = rust_resp.status().as_u16();

        // Check that both match expected status
        if python_status != expected_status || rust_status != expected_status {
            println!("{}", "FAIL".red());
            println!("  Expected: {}, Python: {}, Rust: {}", expected_status, python_status, rust_status);
            self.failed += 1;
            Ok(false)
        } else if python_status != rust_status {
            println!("{}", "FAIL".red());
            println!("  Status mismatch: Python={}, Rust={}", python_status, rust_status);
            self.failed += 1;
            Ok(false)
        } else {
            println!("{}", "PASS".green());
            self.passed += 1;
            Ok(true)
        }
    }

    /// Compare GET requests with JWT authentication
    async fn compare_get_with_jwt(&mut self, name: &str, path: &str, jwt_token: &str) -> Result<bool> {
        print!("Testing {} ... ", name.bold());

        let python_url = format!("{}{}", PYTHON_BASE, path);
        let rust_url = format!("{}{}", RUST_BASE, path);

        // Make requests with JWT Bearer token
        let python_resp = self.client.get(&python_url)
            .header("Authorization", format!("Bearer {}", jwt_token))
            .send().await
            .context("Python request failed")?;
        let rust_resp = self.client.get(&rust_url)
            .header("Authorization", format!("Bearer {}", jwt_token))
            .header("X-Use-Rust-Scorer", "true") // Required for Rust routing
            .send().await
            .context("Rust request failed")?;

        self.compare_responses(name, python_resp, rust_resp).await
    }

    /// Compare POST requests with JWT authentication
    async fn compare_post_with_jwt(&mut self, name: &str, path: &str, body: &Value, jwt_token: &str) -> Result<bool> {
        print!("Testing {} ... ", name.bold());

        let python_url = format!("{}{}", PYTHON_BASE, path);
        let rust_url = format!("{}{}", RUST_BASE, path);

        // Make requests with JWT Bearer token
        let python_resp = self.client.post(&python_url)
            .header("Authorization", format!("Bearer {}", jwt_token))
            .header("Content-Type", "application/json")
            .json(body)
            .send().await
            .context("Python request failed")?;
        let rust_resp = self.client.post(&rust_url)
            .header("Authorization", format!("Bearer {}", jwt_token))
            .header("X-Use-Rust-Scorer", "true") // Required for Rust routing
            .header("Content-Type", "application/json")
            .json(body)
            .send().await
            .context("Rust request failed")?;

        self.compare_responses(name, python_resp, rust_resp).await
    }

    /// Compare PATCH requests with JWT authentication
    async fn compare_patch_with_jwt(&mut self, name: &str, path: &str, body: &Value, jwt_token: &str) -> Result<bool> {
        print!("Testing {} ... ", name.bold());

        let python_url = format!("{}{}", PYTHON_BASE, path);
        let rust_url = format!("{}{}", RUST_BASE, path);

        // Make requests with JWT Bearer token
        let python_resp = self.client.patch(&python_url)
            .header("Authorization", format!("Bearer {}", jwt_token))
            .header("Content-Type", "application/json")
            .json(body)
            .send().await
            .context("Python request failed")?;
        let rust_resp = self.client.patch(&rust_url)
            .header("Authorization", format!("Bearer {}", jwt_token))
            .header("X-Use-Rust-Scorer", "true") // Required for Rust routing
            .header("Content-Type", "application/json")
            .json(body)
            .send().await
            .context("Rust request failed")?;

        self.compare_responses(name, python_resp, rust_resp).await
    }

    /// Compare DELETE requests with JWT authentication
    async fn compare_delete_with_jwt(&mut self, name: &str, path: &str, body: &Value, jwt_token: &str) -> Result<bool> {
        print!("Testing {} ... ", name.bold());

        let python_url = format!("{}{}", PYTHON_BASE, path);
        let rust_url = format!("{}{}", RUST_BASE, path);

        // Make requests with JWT Bearer token
        let python_resp = self.client.delete(&python_url)
            .header("Authorization", format!("Bearer {}", jwt_token))
            .header("Content-Type", "application/json")
            .json(body)
            .send().await
            .context("Python request failed")?;
        let rust_resp = self.client.delete(&rust_url)
            .header("Authorization", format!("Bearer {}", jwt_token))
            .header("X-Use-Rust-Scorer", "true") // Required for Rust routing
            .header("Content-Type", "application/json")
            .json(body)
            .send().await
            .context("Rust request failed")?;

        self.compare_responses(name, python_resp, rust_resp).await
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

/// Fields that will naturally differ between sequential Python and Rust calls
const IGNORED_FIELDS: &[&str] = &["last_score_timestamp", "id"];

/// Remove fields that will naturally differ between calls
fn strip_ignored_fields(value: &mut Value) {
    if let Value::Object(map) = value {
        for field in IGNORED_FIELDS {
            map.remove(*field);
        }
        for (_, v) in map.iter_mut() {
            strip_ignored_fields(v);
        }
    } else if let Value::Array(arr) = value {
        for item in arr.iter_mut() {
            strip_ignored_fields(item);
        }
    }
}

/// Compare two JSON values, returning an error with diff if they don't match
fn compare_json(python: &Value, rust: &Value) -> Result<(), String> {
    let mut python_cleaned = python.clone();
    let mut rust_cleaned = rust.clone();

    strip_ignored_fields(&mut python_cleaned);
    strip_ignored_fields(&mut rust_cleaned);

    let python_sorted = sort_json(&python_cleaned);
    let rust_sorted = sort_json(&rust_cleaned);

    if python_sorted == rust_sorted {
        return Ok(());
    }

    // Generate diff
    let python_pretty = serde_json::to_string_pretty(&python_sorted).unwrap();
    let rust_pretty = serde_json::to_string_pretty(&rust_sorted).unwrap();

    // Find actual difference by comparing lines
    let python_lines: Vec<&str> = python_pretty.lines().collect();
    let rust_lines: Vec<&str> = rust_pretty.lines().collect();

    let mut diff = String::new();
    diff.push_str("  Difference found:\n");

    // Find first differing line
    for (i, (p, r)) in python_lines.iter().zip(rust_lines.iter()).enumerate() {
        if p != r {
            diff.push_str(&format!("  First difference at line {}:\n", i + 1));
            diff.push_str(&format!("    Python: {}\n", p.yellow()));
            diff.push_str(&format!("    Rust:   {}\n", r.blue()));
            // Show surrounding context
            if i > 0 {
                diff.push_str(&format!("    Context before: {}\n", python_lines[i-1]));
            }
            break;
        }
    }

    // Check for length difference
    if python_lines.len() != rust_lines.len() {
        diff.push_str(&format!("  Length difference: Python={}, Rust={}\n",
            python_lines.len(), rust_lines.len()));
    }

    Err(diff)
}

/// Sort JSON objects by key for consistent comparison
/// Also sorts arrays by their JSON representation for order-independent comparison
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
            // First recursively sort each element
            let mut sorted_elements: Vec<Value> = arr.iter().map(sort_json).collect();
            // Then sort the array by string representation for order-independent comparison
            sorted_elements.sort_by(|a, b| {
                let a_str = serde_json::to_string(a).unwrap_or_default();
                let b_str = serde_json::to_string(b).unwrap_or_default();
                a_str.cmp(&b_str)
            });
            Value::Array(sorted_elements)
        }
        _ => value.clone(),
    }
}

#[tokio::main]
async fn main() -> Result<()> {
    // Parse command line arguments
    let args = Args::parse();

    println!("{}", "\n========================================".bold());
    println!("{}", "  Python <-> Rust Comparison Tests".bold());
    println!("{}", "========================================\n".bold());

    if args.verbose {
        println!("{}", "Verbose mode: Will print Rust responses".cyan());
    }

    // Check ports are available first
    ensure_ports_available()?;

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
    let mut test_runner = TestRunner::new(args.verbose);

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

    // Phase 2: Additional internal endpoints

    // Check bans endpoint - test with credential data
    let check_bans_body = json!([{
        "credentialSubject": {
            "hash": "v0.0.0:test_hash_123",
            "provider": "Google",
            "id": format!("did:pkh:eip155:1:{}", config.test_address)
        }
    }]);
    test_runner
        .compare_post_internal("Check Bans endpoint", "/internal/check-bans", &check_bans_body, &internal_key)
        .await?;

    // Check revocations endpoint - test with proof values (mix of revoked and non-revoked)
    let check_revocations_body = json!({
        "proof_values": [
            "revoked_proof_1",      // Should be found (revoked)
            "revoked_proof_2",      // Should be found (revoked)
            "non_revoked_proof"     // Should NOT be found (not revoked)
        ]
    });
    test_runner
        .compare_post_internal("Check Revocations endpoint", "/internal/check-revocations", &check_revocations_body, &internal_key)
        .await?;

    // GTC stake endpoint - test with test address
    let stake_path = format!("/internal/stake/gtc/{}", config.test_address);
    test_runner
        .compare_get_internal("GTC Stake endpoint", &stake_path, &internal_key)
        .await?;

    // Allow list endpoint - test with a list name and address
    let allow_list_path = format!("/internal/allow-list/testlist/{}", config.test_address);
    test_runner
        .compare_get_internal("Allow List endpoint", &allow_list_path, &internal_key)
        .await?;

    // CGrants contributor statistics endpoint
    let cgrants_path = format!("/internal/cgrants/contributor_statistics?address={}", config.test_address);
    test_runner
        .compare_get_internal("CGrants Contributor Statistics endpoint", &cgrants_path, &internal_key)
        .await?;

    // Phase 2.5: Error test cases

    // NOTE: Skipping auth error tests for internal endpoints in dev mode
    // - Python dev server checks internal_api_key auth
    // - Rust assumes ALB handles auth (production behavior)
    // - In production, internal ALB will enforce auth at infrastructure level
    // - These tests would pass in production but fail in local dev

    // TODO: Consider adding optional auth middleware for dev mode parity

    // Other error cases to test (with proper auth):
    // - Invalid address format (needs Rust validation improvement)
    // - Non-existent scorer (needs better 404 handling)

    // Phase 3: Embed endpoints

    // GET embed score endpoint - returns stamps + score
    let embed_score_path = format!("/internal/embed/score/{}/{}", config.scorer_id, config.test_address);
    test_runner
        .compare_get_internal("Embed Score endpoint", &embed_score_path, &internal_key)
        .await?;

    // POST embed stamps endpoint - adds stamps and returns new score
    // Now using production-format EthereumEip712Signature2021 credentials
    if !config.credentials.is_empty() {
        let embed_stamps_body = json!({
            "scorer_id": config.scorer_id,
            "stamps": config.credentials
        });
        let embed_stamps_path = format!("/internal/embed/stamps/{}", config.test_address);
        test_runner
            .compare_post_internal("Embed Stamps POST endpoint", &embed_stamps_path, &embed_stamps_body, &internal_key)
            .await?;
    } else {
        println!("{}", "  Skipping Embed Stamps test (no credentials in config)".yellow());
    }

    // Phase 4: Ceramic Cache endpoints (with JWT authentication)
    println!("\n{}", "Ceramic Cache Endpoints (JWT auth):".bold());

    // Generate JWT token for ceramic cache endpoints
    let jwt_token = generate_test_jwt(&config.test_address)
        .context("Failed to generate JWT token")?;

    // GET /ceramic-cache/score/{address} - Get score with stamps and human points
    let ceramic_score_path = format!("/ceramic-cache/score/{}", config.test_address);
    test_runner
        .compare_get_with_jwt("Ceramic Cache GET score endpoint", &ceramic_score_path, &jwt_token)
        .await?;

    // POST /ceramic-cache/stamps/bulk - Add stamps and return score with human points
    if !config.credentials.is_empty() {
        // Build CacheStampPayload array from credentials
        let cache_stamps_body: Vec<Value> = config.credentials.iter().map(|cred| {
            let provider = cred.get("credentialSubject")
                .and_then(|cs| cs.get("provider"))
                .and_then(|p| p.as_str())
                .unwrap_or("Unknown");

            json!({
                "provider": provider,
                "stamp": cred
            })
        }).collect();

        test_runner
            .compare_post_with_jwt("Ceramic Cache POST stamps endpoint", "/ceramic-cache/stamps/bulk", &json!(cache_stamps_body), &jwt_token)
            .await?;

        // PATCH /ceramic-cache/stamps/bulk - Update stamps (soft delete + recreate for stamps with stamp field)
        // For PATCH test, we'll modify one stamp and remove another
        let patch_stamps_body: Vec<Value> = vec![
            // Update Google stamp (include stamp field - will be recreated)
            json!({
                "provider": "Google",
                "stamp": config.credentials.get(0).unwrap()
            }),
            // Remove Twitter stamp (no stamp field - will be soft deleted only)
            json!({
                "provider": "Twitter"
            })
        ];

        test_runner
            .compare_patch_with_jwt("Ceramic Cache PATCH stamps endpoint", "/ceramic-cache/stamps/bulk", &json!(patch_stamps_body), &jwt_token)
            .await?;

        // DELETE /ceramic-cache/stamps/bulk - Delete stamps (soft delete only, no recreation)
        // For DELETE test, we'll delete the Github stamp
        let delete_stamps_body: Vec<Value> = vec![
            json!({
                "provider": "Github"
            })
        ];

        test_runner
            .compare_delete_with_jwt("Ceramic Cache DELETE stamps endpoint", "/ceramic-cache/stamps/bulk", &json!(delete_stamps_body), &jwt_token)
            .await?;
    } else {
        println!("{}", "  Skipping Ceramic Cache POST/PATCH/DELETE tests (no credentials in config)".yellow());
    }

    // Summary
    test_runner.summary();

    // Drop will handle shutdown automatically (even on error)
    // Need to drop before exit to ensure cleanup
    let failed = test_runner.failed;
    drop(server_manager);

    // Exit with appropriate code
    if failed > 0 {
        std::process::exit(1);
    }

    Ok(())
}
