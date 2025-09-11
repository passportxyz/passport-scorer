
#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    rust_scorer::api::server::run_server().await
}
