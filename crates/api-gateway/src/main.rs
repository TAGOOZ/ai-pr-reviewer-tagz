use coderabbit_api_gateway::ApiGateway;
use coderabbit_shared::AppConfig;
use tracing_subscriber::{layer::SubscriberExt, util::SubscriberInitExt};

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    // Initialize tracing
    tracing_subscriber::registry()
        .with(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| "coderabbit_api_gateway=debug,tower_http=debug".into()),
        )
        .with(tracing_subscriber::fmt::layer())
        .init();

    // Load configuration from environment
    let config = AppConfig::from_env()
        .map_err(|e| format!("Failed to load configuration: {}", e))?;

    tracing::info!("Starting CodeRabbit API Gateway");
    tracing::info!("Environment: {}", config.environment);
    tracing::info!("Server: {}:{}", config.server.host, config.server.port);

    // Create and start the API gateway
    let gateway = ApiGateway::new(config);
    
    if let Err(e) = gateway.start().await {
        tracing::error!("Failed to start API Gateway: {}", e);
        std::process::exit(1);
    }

    Ok(())
}