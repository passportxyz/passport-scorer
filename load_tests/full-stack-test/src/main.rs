use anyhow::{Error, Result};
use async_process::Command;
use std::{process::Stdio, time::SystemTime};

// Steps

// Function to execute a command with parameters and return the output
async fn execute_command(command: &str, args: &[&str]) -> Result<String, Error> {
    let output = Command::new(command).args(args).output().await?;

    String::from_utf8(output.stdout).map_err(Error::from)
}

// Function to run the k6 script for the scorer API with environment variables
async fn run_k6_script(
    script_path: &str,
    api_key: &str,
    scorer_id: &str,
    vus: u32,
    duration: &str,
    output: &str,
) -> Result<String> {
    let args = [
        "run",
        "-e",
        &format!("SCORER_API_KEY={}", api_key),
        "-e",
        &format!("SCORER_ID={}", scorer_id),
        "--vus",
        &vus.to_string(),
        "--duration",
        duration,
        script_path,
        "--out",
        &format!("csv={}", output),
    ];

    execute_command("k6", &args).await
}

// Function to run the IAM k6 test script
async fn run_iam_script(
    script_path: &str,
    vus: u32,
    duration: &str,
    output: &str,
) -> Result<String> {
    let args = [
        "run",
        "--vus",
        &vus.to_string(),
        "--duration",
        duration,
        script_path,
        "--out",
        &format!("csv={}", output),
    ];

    execute_command("k6", &args).await
}

#[tokio::main]
async fn main() -> Result<()> {
    // Example parameters for the scorer API script
    let scorer_api_script_path = "../test_scripts/scorer_api_script.js";
    let api_key = "iE7QwgX9.rx9XIXdkPwZUYAHditFMgFVKvDp428OH";
    let scorer_id = "24";
    let scorer_vus = 500;
    let scorer_duration = "15m";
    let scorer_output = "scorer_load_test_1500_15min.csv";

    // Parameters for the IAM test script
    let iam_script_path = "../test_scripts/iam_script.js";
    let iam_vus = 500;
    let iam_duration = "15m";
    let iam_output = "iam_load_test_1500_15min.csv";

    let start = SystemTime::now();

    // Run both scripts concurrently
    let (scorer_results, iam_results) = tokio::join!(
        run_k6_script(
            scorer_api_script_path,
            api_key,
            scorer_id,
            scorer_vus,
            scorer_duration,
            scorer_output
        ),
        run_iam_script(iam_script_path, iam_vus, iam_duration, iam_output)
    );

    let end = SystemTime::now();

    dbg!(scorer_results, iam_results);
    dbg!(start, end, end.duration_since(start).unwrap());
    Ok(())
}
