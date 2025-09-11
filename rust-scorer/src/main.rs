
use passport_scorer::api::server;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    server::run_server().await
}
