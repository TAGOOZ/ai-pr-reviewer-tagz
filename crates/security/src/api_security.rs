use coderabbit_shared::{Result, CodeRabbitError};
use std::collections::HashMap;
use serde::{Deserialize, Serialize};
use serde_json::json;
use std::sync::Arc;
use tokio::sync::RwLock;
use std::time::{Duration, SystemTime, UNIX_EPOCH};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SecurityConfig {
    pub jwt_secret: String,
    pub jwt_issuer: String,
    pub jwt_audience: String,
    pub jwt_expiration_hours: u64,
    pub rate_limit_requests_per_minute: u64,
    pub rate_limit_burst_size: u64,
    pub enable_cors: bool,
    pub allowed_origins: Vec<String>,
    pub api_key_header: String,
    pub enable_api_key_auth: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct JWTPayload {
    pub sub: String,        // Subject (user ID)
    pub iss: String,        // Issuer
    pub aud: String,        // Audience
    pub exp: u64,          // Expiration time (timestamp)
    pub iat: u64,          // Issued at (timestamp)
    pub scope: Vec<String>, // Permissions/scopes (NOTE: singular "scope")
    pub roles: Vec<String>, // User roles
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RateLimitInfo {
    pub requests_per_minute: u64,
    pub burst_size: u64,
    pub window_start: SystemTime,
    pub request_count: u64,
    pub blocked_until: Option<SystemTime>,
}

#[derive(Debug)]
pub struct SecurityManager {
    config: SecurityConfig,
    rate_limits: Arc<RwLock<HashMap<String, RateLimitInfo>>>,
    active_tokens: Arc<RwLock<HashMap<String, JWTPayload>>>,
    api_keys: Arc<RwLock<HashMap<String, ApiKeyInfo>>>,
    security_stats: Arc<RwLock<SecurityStats>>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ApiKeyInfo {
    pub key_id: String,
    pub name: String,
    pub scopes: Vec<String>,
    pub created_at: SystemTime,
    pub last_used: Option<SystemTime>,
    pub expires_at: Option<SystemTime>,
    pub rate_limit_multiplier: f32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SecurityStats {
    pub total_requests: u64,
    pub authenticated_requests: u64,
    pub blocked_requests: u64,
    pub rate_limited_requests: u64,
    pub invalid_tokens: u64,
    pub successful_logins: u64,
    pub failed_logins: u64,
    pub jwt_tokens_issued: u64,
    pub api_keys_used: u64,
    pub active_sessions: u64,
}

impl SecurityManager {
    pub async fn new(config: SecurityConfig) -> Result<Self> {
        tracing::info!("Initializing API security manager");
        
        let manager = Self {
            config: config.clone(),
            rate_limits: Arc::new(RwLock::new(HashMap::new())),
            active_tokens: Arc::new(RwLock::new(HashMap::new())),
            api_keys: Arc::new(RwLock::new(HashMap::new())),
            security_stats: Arc::new(RwLock::new(SecurityStats {
                total_requests: 0,
                authenticated_requests: 0,
                blocked_requests: 0,
                rate_limited_requests: 0,
                invalid_tokens: 0,
                successful_logins: 0,
                failed_logins: 0,
                jwt_tokens_issued: 0,
                api_keys_used: 0,
                active_sessions: 0,
            })),
        };
        
        manager.initialize_default_api_keys().await?;
        manager.start_maintenance_tasks().await?;
        
        Ok(manager)
    }

    /// Initialize default API keys for system access
    async fn initialize_default_api_keys(&self) -> Result<()> {
        tracing::info!("Initializing default API keys");
        
        let mut api_keys = self.api_keys.write().await;
        
        // System API key for internal services
        let system_key = ApiKeyInfo {
            key_id: "system_internal_001".to_string(),
            name: "System Internal API".to_string(),
            scopes: vec!["admin".to_string(), "system".to_string(), "read".to_string(), "write".to_string()],
            created_at: SystemTime::now(),
            last_used: None,
            expires_at: None, // No expiration for system key
            rate_limit_multiplier: 10.0, // Higher rate limit for system
        };
        
        api_keys.insert("sk-system-internal-001".to_string(), system_key);
        
        tracing::info!("Initialized system API key");
        Ok(())
    }

    /// Generate JWT token for user
    pub async fn generate_jwt_token(&self, user_id: &str, scopes: Vec<String>, roles: Vec<String>) -> Result<String> {
        let now = SystemTime::now();
        let expiration = now + Duration::from_secs(self.config.jwt_expiration_hours * 3600);
        
        let payload = JWTPayload {
            sub: user_id.to_string(),
            iss: self.config.jwt_issuer.clone(),
            aud: self.config.jwt_audience.clone(),
            exp: expiration.duration_since(UNIX_EPOCH).unwrap().as_secs(),
            iat: now.duration_since(UNIX_EPOCH).unwrap().as_secs(),
            scope: scopes, // FIXED: Use singular "scope"
            roles,
        };
        
        // Sign the token (simplified - in production use proper JWT library)
        let token = self.sign_jwt_payload(&payload)?;
        
        // Store active token
        {
            let mut active_tokens = self.active_tokens.write().await;
            active_tokens.insert(token.clone(), payload.clone());
        }
        
        // Update statistics
        {
            let mut stats = self.security_stats.write().await;
            stats.jwt_tokens_issued += 1;
            stats.active_sessions += 1;
        }
        
        tracing::info!("Generated JWT token for user: {}", user_id);
        Ok(token)
    }

    /// Validate JWT token
    pub async fn validate_jwt_token(&self, token: &str) -> Result<Option<JWTPayload>> {
        // Update statistics
        {
            let mut stats = self.security_stats.write().await;
            stats.total_requests += 1;
        }
        
        // Check if token exists in active tokens
        {
            let active_tokens = self.active_tokens.read().await;
            if let Some(payload) = active_tokens.get(token) {
                // Check expiration
                let now = SystemTime::now().duration_since(UNIX_EPOCH).unwrap().as_secs();
                if payload.exp > now {
                    // Update statistics
                    {
                        let mut stats = self.security_stats.write().await;
                        stats.authenticated_requests += 1;
                    }
                    
                    tracing::debug!("Valid JWT token found for user: {}", payload.sub);
                    return Ok(Some(payload.clone()));
                } else {
                    // Token expired, remove it
                    drop(active_tokens);
                    let mut active_tokens = self.active_tokens.write().await;
                    active_tokens.remove(token);
                }
            }
        }
        
        // Validate signature
        let payload = match self.verify_jwt_signature(token) {
            Ok(payload) => payload,
            Err(_) => {
                let mut stats = self.security_stats.write().await;
                stats.invalid_tokens += 1;
                return Ok(None);
            }
        };
        
        // Check expiration
        let now = SystemTime::now().duration_since(UNIX_EPOCH).unwrap().as_secs();
        if payload.exp <= now {
            tracing::warn!("JWT token expired for user: {}", payload.sub);
            return Ok(None);
        }
        
        // Update statistics
        {
            let mut stats = self.security_stats.write().await;
            stats.authenticated_requests += 1;
        }
        
        // Store active token
        {
            let mut active_tokens = self.active_tokens.write().await;
            active_tokens.insert(token.to_string(), payload.clone());
        }
        
        Ok(Some(payload))
    }

    /// Revoke JWT token
    pub async fn revoke_jwt_token(&self, token: &str) -> Result<()> {
        let mut active_tokens = self.active_tokens.write().await;
        active_tokens.remove(token);
        
        // Update statistics
        {
            let mut stats = self.security_stats.write().await;
            stats.active_sessions = stats.active_sessions.saturating_sub(1);
        }
        
        tracing::info!("Revoked JWT token");
        Ok(())
    }

    /// Check rate limit for IP address
    pub async fn check_rate_limit(&self, identifier: &str) -> Result<bool> {
        let mut rate_limits = self.rate_limits.write().await;
        let now = SystemTime::now();
        
        let rate_info = rate_limits.entry(identifier.to_string()).or_insert(RateLimitInfo {
            requests_per_minute: self.config.rate_limit_requests_per_minute,
            burst_size: self.config.rate_limit_burst_size,
            window_start: now,
            request_count: 0,
            blocked_until: None,
        });
        
        // Check if currently blocked
        if let Some(blocked_until) = rate_info.blocked_until {
            if now < blocked_until {
                let mut stats = self.security_stats.write().await;
                stats.rate_limited_requests += 1;
                tracing::warn!("Request blocked due to rate limit: {}", identifier);
                return Ok(false);
            } else {
                rate_info.blocked_until = None;
            }
        }
        
        // Check if we need to reset the window (1 minute window)
        let window_duration = Duration::from_secs(60);
        if now.duration_since(rate_info.window_start).unwrap_or_default() > window_duration {
            rate_info.window_start = now;
            rate_info.request_count = 0;
        }
        
        // Check rate limit
        if rate_info.request_count >= rate_info.requests_per_minute {
            // Block for a period
            rate_info.blocked_until = Some(now + Duration::from_secs(60));
            
            let mut stats = self.security_stats.write().await;
            stats.rate_limited_requests += 1;
            
            tracing::warn!("Rate limit exceeded for: {} (count: {})", identifier, rate_info.request_count);
            return Ok(false);
        }
        
        // Allow request and increment counter
        rate_info.request_count += 1;
        
        // Additional burst check
        if rate_info.request_count > rate_info.burst_size {
            rate_info.blocked_until = Some(now + Duration::from_secs(30));
            
            let mut stats = self.security_stats.write().await;
            stats.rate_limited_requests += 1;
            
            tracing::warn!("Burst limit exceeded for: {} (count: {})", identifier, rate_info.request_count);
            return Ok(false);
        }
        
        Ok(true)
    }

    /// Validate API key
    pub async fn validate_api_key(&self, api_key: &str) -> Result<Option<ApiKeyInfo>> {
        let api_keys = self.api_keys.read().await;
        
        if let Some(key_info) = api_keys.get(api_key) {
            let key_info_cloned = key_info.clone();
            // Check expiration
            if let Some(expires_at) = key_info_cloned.expires_at {
                if SystemTime::now() > expires_at {
                    tracing::warn!("Expired API key used: {}", key_info_cloned.key_id);
                    return Ok(None);
                }
            }
            // Update last used
            drop(api_keys);
            let mut api_keys = self.api_keys.write().await;
            if let Some(key_info_mut) = api_keys.get_mut(api_key) {
                key_info_mut.last_used = Some(SystemTime::now());
            }
            // Update statistics
            {
                let mut stats = self.security_stats.write().await;
                stats.api_keys_used += 1;
            }
            tracing::debug!("Valid API key used: {}", key_info_cloned.key_id);
            return Ok(Some(key_info_cloned));
        }
        
        Ok(None)
    }

    /// Check if user has required scope
    pub fn has_scope(&self, payload: &JWTPayload, required_scope: &str) -> bool {
        payload.scope.contains(&required_scope.to_string()) || 
        payload.scope.contains(&"admin".to_string())
    }

    /// Check if user has required role
    pub fn has_role(&self, payload: &JWTPayload, required_role: &str) -> bool {
        payload.roles.contains(&required_role.to_string()) || 
        payload.roles.contains(&"admin".to_string())
    }

    /// Get security statistics
    pub async fn get_security_stats(&self) -> SecurityStats {
        let stats = self.security_stats.read().await;
        stats.clone()
    }

    /// Generate API key
    pub async fn generate_api_key(&self, name: String, scopes: Vec<String>, 
                                expires_in_days: Option<u32>) -> Result<String> {
        let key_id = format!("ak_{}", uuid::Uuid::new_v4());
        let api_key = format!("sk-{}-{}-{}", name.to_lowercase().replace(' ', "-"), 
                            key_id, chrono::Utc::now().timestamp());
        
        let expires_at = expires_in_days.map(|days| {
            SystemTime::now() + Duration::from_secs(days as u64 * 24 * 3600)
        });
        
        let key_info = ApiKeyInfo {
            key_id: key_id.clone(),
            name,
            scopes,
            created_at: SystemTime::now(),
            last_used: None,
            expires_at,
            rate_limit_multiplier: 1.0,
        };
        
        let mut api_keys = self.api_keys.write().await;
        api_keys.insert(api_key.clone(), key_info);
        
        tracing::info!("Generated API key: {}", key_id);
        Ok(api_key)
    }

    /// Revoke API key
    pub async fn revoke_api_key(&self, api_key: &str) -> Result<()> {
        let mut api_keys = self.api_keys.write().await;
        api_keys.remove(api_key);
        
        tracing::info!("Revoked API key: {}", api_key);
        Ok(())
    }

    /// Get active sessions count
    pub async fn get_active_sessions_count(&self) -> u64 {
        let active_tokens = self.active_tokens.read().await;
        active_tokens.len() as u64
    }

    // Private helper methods

    /// Sign JWT payload (simplified implementation)
    fn sign_jwt_payload(&self, payload: &JWTPayload) -> Result<String> {
        use base64::{Engine as _, engine::general_purpose};
        use hmac::{Hmac, Mac};
        use sha2::Sha256;
        
        type HmacSha256 = Hmac<Sha256>;
        
        // Create HMAC
        let mut mac = HmacSha256::new_from_slice(self.config.jwt_secret.as_bytes())
            .map_err(|e| CodeRabbitError::ConfigError(format!("HMAC creation failed: {}", e)))?;
        
        // Encode header and payload
        let header = json!({
            "alg": "HS256",
            "typ": "JWT"
        });
        
        let header_b64 = general_purpose::STANDARD.encode(serde_json::to_string(&header).unwrap());
        let payload_b64 = general_purpose::STANDARD.encode(serde_json::to_string(payload).unwrap());
        
        let message = format!("{}.{}", header_b64, payload_b64);
        
        // Update HMAC with message
        mac.update(message.as_bytes());
        
        // Get signature
        let signature_bytes = mac.finalize().into_bytes();
        let signature_b64 = general_purpose::STANDARD.encode(signature_bytes);
        
        // Return complete token
        Ok(format!("{}.{}.{}", header_b64, payload_b64, signature_b64))
    }

    /// Verify JWT signature
    fn verify_jwt_signature(&self, token: &str) -> Result<JWTPayload> {
        use base64::{Engine as _, engine::general_purpose};
        use hmac::{Hmac, Mac};
        use sha2::Sha256;
        
        type HmacSha256 = Hmac<Sha256>;
        
        let parts: Vec<&str> = token.split('.').collect();
        if parts.len() != 3 {
            return Err(CodeRabbitError::ConfigError("Invalid JWT token format".to_string()));
        }
        
        let (_header_b64, payload_b64, signature_b64) = (parts[0], parts[1], parts[2]);
        
        // Create HMAC
        let mut mac = HmacSha256::new_from_slice(self.config.jwt_secret.as_bytes())
            .map_err(|e| CodeRabbitError::ConfigError(format!("HMAC creation failed: {}", e)))?;
        
        let message = format!("{}.{}", parts[0], parts[1]);
        mac.update(message.as_bytes());
        
        // Verify signature
        let expected_signature = general_purpose::STANDARD.decode(signature_b64)
            .map_err(|e| CodeRabbitError::ConfigError(format!("Signature decode failed: {}", e)))?;
        
        mac.verify_slice(&expected_signature)
            .map_err(|_| CodeRabbitError::ConfigError("JWT signature verification failed".to_string()))?;
        
        // Decode payload
        let payload_json = general_purpose::STANDARD.decode(payload_b64)
            .map_err(|e| CodeRabbitError::ConfigError(format!("Payload decode failed: {}", e)))?;
        
        let payload_str = String::from_utf8(payload_json)
            .map_err(|e| CodeRabbitError::ConfigError(format!("Payload UTF-8 decode failed: {}", e)))?;
        
        let payload: JWTPayload = serde_json::from_str(&payload_str)
            .map_err(|e| CodeRabbitError::ConfigError(format!("Payload JSON decode failed: {}", e)))?;
        
        Ok(payload)
    }

    /// Start background maintenance tasks
    async fn start_maintenance_tasks(&self) -> Result<()> {
        // Start token cleanup task
        let security_manager = Arc::new(self.clone());
        tokio::spawn(async move {
            let mut interval = tokio::time::interval(Duration::from_secs(300)); // Every 5 minutes
            
            loop {
                interval.tick().await;
                if let Err(e) = security_manager.cleanup_expired_tokens().await {
                    tracing::warn!("Token cleanup failed: {}", e);
                }
            }
        });
        
        // Start rate limit cleanup task
        let security_manager = Arc::new(self.clone());
        tokio::spawn(async move {
            let mut interval = tokio::time::interval(Duration::from_secs(60)); // Every minute
            
            loop {
                interval.tick().await;
                if let Err(e) = security_manager.cleanup_rate_limits().await {
                    tracing::warn!("Rate limit cleanup failed: {}", e);
                }
            }
        });
        
        tracing::info!("Security maintenance tasks started");
        Ok(())
    }

    /// Cleanup expired JWT tokens
    async fn cleanup_expired_tokens(&self) -> Result<()> {
        let now = SystemTime::now().duration_since(UNIX_EPOCH).unwrap().as_secs();
        
        let mut active_tokens = self.active_tokens.write().await;
        let expired_tokens: Vec<String> = active_tokens.iter()
            .filter(|(_, payload)| payload.exp <= now)
            .map(|(token, _)| token.clone())
            .collect();
        
        for token in expired_tokens.iter() {
            active_tokens.remove(token);
        }
        
        if !expired_tokens.is_empty() {
            tracing::info!("Cleaned up {} expired JWT tokens", expired_tokens.len());
        }
        
        Ok(())
    }

    /// Cleanup old rate limit entries
    async fn cleanup_rate_limits(&self) -> Result<()> {
        let now = SystemTime::now();
        let cutoff = now - Duration::from_secs(3600); // 1 hour ago
        
        let mut rate_limits = self.rate_limits.write().await;
        let old_entries: Vec<String> = rate_limits.iter()
            .filter(|(_, info)| info.window_start < cutoff && info.request_count == 0)
            .map(|(key, _)| key.clone())
            .collect();
        
        for key in old_entries.iter() {
            rate_limits.remove(key);
        }
        
        if !old_entries.is_empty() {
            tracing::debug!("Cleaned up {} old rate limit entries", old_entries.len());
        }
        
        Ok(())
    }
}

// Implement Clone for SecurityManager
impl Clone for SecurityManager {
    fn clone(&self) -> Self {
        Self {
            config: self.config.clone(),
            rate_limits: Arc::clone(&self.rate_limits),
            active_tokens: Arc::clone(&self.active_tokens),
            api_keys: Arc::clone(&self.api_keys),
            security_stats: Arc::clone(&self.security_stats),
        }
    }
}
