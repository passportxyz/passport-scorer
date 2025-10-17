use std::env;
use std::collections::HashMap;
use tracing::info;

/// Load secrets from AWS Secrets Manager and set them as environment variables
///
/// This mimics the behavior of the Python Lambda in api/aws_lambdas/utils.py:36-54
///
/// If SCORER_SERVER_SSM_ARN is set, it:
/// 1. Fetches the secret from AWS Secrets Manager
/// 2. Parses the JSON secret string
/// 3. Sets all key-value pairs as environment variables
///
/// This is called during Lambda cold start initialization, before the first request.
pub async fn load_secrets_from_manager() -> Result<(), Box<dyn std::error::Error>> {
    // Check if SCORER_SERVER_SSM_ARN is set (matches Python's check)
    let secret_arn = match env::var("SCORER_SERVER_SSM_ARN") {
        Ok(arn) => arn,
        Err(_) => {
            info!("SCORER_SERVER_SSM_ARN not set, skipping secrets loading");
            return Ok(());
        }
    };

    info!("Loading secrets from AWS Secrets Manager: {}", secret_arn);

    // Create AWS config and Secrets Manager client
    let config = aws_config::load_from_env().await;
    let client = aws_sdk_secretsmanager::Client::new(&config);

    // Fetch the secret value
    let response = client
        .get_secret_value()
        .secret_id(&secret_arn)
        .send()
        .await
        .map_err(|e| {
            format!("Failed to fetch secret from Secrets Manager: {}", e)
        })?;

    // Get the secret string
    let secret_string = response
        .secret_string()
        .ok_or("Secret does not contain a string value")?;

    // Parse JSON and set environment variables
    let secrets: HashMap<String, String> = serde_json::from_str(secret_string)
        .map_err(|e| format!("Failed to parse secret JSON: {}", e))?;

    info!("Loaded {} secrets from Secrets Manager", secrets.len());

    // Set each secret as an environment variable
    // SAFETY: This is safe because:
    // 1. We're in Lambda cold start (single-threaded initialization)
    // 2. No other threads are running yet
    // 3. This happens before any requests are processed
    for (key, value) in secrets {
        unsafe {
            env::set_var(&key, &value);
        }
        info!("Set environment variable: {}", key);
    }

    Ok(())
}

