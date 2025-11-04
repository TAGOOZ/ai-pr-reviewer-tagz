use axum::{Router, serve};
use tokio::net::TcpListener;
use tower::ServiceBuilder;
use tower_http::{
    cors::CorsLayer,
    trace::TraceLayer,
    timeout::TimeoutLayer,
};
use std::time::Duration;
use coderabbit_shared::{Result, CodeRabbitError, AppConfig};

use crate::routes::create_routes;
use crate::middleware::auth::AuthLayer;
use crate::handlers::database::{DatabaseState, DatabaseConfig};

pub struct ApiGateway {
    config: AppConfig,
}

impl ApiGateway {
    pub fn new(config: AppConfig) -> Self {
        Self { config }
    }

    pub async fn start(&self) -> Result<()> {
        let app = self.create_app().await?;
        
        let addr = format!("{}:{}", self.config.server.host, self.config.server.port);
        let listener = TcpListener::bind(&addr)
            .await
            .map_err(|e| CodeRabbitError::InternalError(format!("Failed to bind to {}: {}", addr, e)))?;

        tracing::info!("API Gateway listening on {}", addr);

        serve(listener, app)
            .await
            .map_err(|e| CodeRabbitError::InternalError(format!("Server error: {}", e)))?;

        Ok(())
    }

    async fn create_app(&self) -> Result<Router> {
        let middleware = ServiceBuilder::new()
            .layer(TraceLayer::new_for_http())
            .layer(CorsLayer::permissive())
            .layer(TimeoutLayer::new(Duration::from_secs(30)))
            .layer(AuthLayer::from_env());

        // Initialize database state
        let db_config = DatabaseConfig {
            url: self.config.database.url.clone(),
            max_connections: self.config.database.max_connections,
            connection_timeout: Duration::from_secs(self.config.database.connection_timeout as u64),
            idle_timeout: Duration::from_secs(300), // 5 minutes
        };
        let db_state = DatabaseState::new(db_config).await;

        let routes = create_routes();

        Ok(Router::new()
            .nest("/api/v1", routes)
            .with_state(db_state)
            .layer(middleware))
    }
}