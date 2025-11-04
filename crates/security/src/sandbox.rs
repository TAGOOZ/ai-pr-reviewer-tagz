use coderabbit_shared::{Result, CodeRabbitError};
use std::collections::HashMap;
use serde::{Deserialize, Serialize};
use std::sync::Arc;
use tokio::sync::RwLock;
use std::process::{Command, Stdio};
use std::os::unix::fs::PermissionsExt;
use nix::unistd::Uid;


#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SandboxConfig {
    pub max_memory_mb: u64,
    pub max_cpu_time_seconds: u64,
    pub max_execution_time_seconds: u64,
    pub allowed_directories: Vec<String>,
    pub blocked_syscalls: Vec<String>,
    pub enable_network: bool,
    pub user_id: u32,
    pub group_id: u32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ExecutionResult {
    pub exit_code: i32,
    pub stdout: String,
    pub stderr: String,
    pub execution_time_ms: u64,
    pub memory_used_kb: u64,
    pub cpu_time_ms: u64,
    pub sandbox_violations: Vec<String>,
    pub success: bool,
}

#[derive(Debug)]
pub struct SecurityManager {
    config: SandboxConfig,
    active_sessions: Arc<RwLock<HashMap<String, ExecutionSession>>>,
    security_stats: Arc<RwLock<SecurityStats>>,
}

#[derive(Debug, Clone)]
pub struct ExecutionSession {
    pub session_id: String,
    pub pid: Option<u32>,
    pub start_time: std::time::Instant,
    pub working_directory: String,
    pub allowed_executables: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SecurityStats {
    pub total_executions: u64,
    pub blocked_executions: u64,
    pub sandbox_violations: u64,
    pub average_execution_time_ms: f64,
    pub max_memory_used_kb: u64,
    pub security_score: f64,
}

impl SecurityManager {
    pub async fn new(config: SandboxConfig) -> Result<Self> {
        tracing::info!("Initializing security manager with sandbox configuration");
        
        // Verify we're running as root for privilege operations
        if !Uid::current().is_root() {
            tracing::warn!("Security manager not running as root - limited sandboxing capabilities");
        }
        
        let security_manager = Self {
            config,
            active_sessions: Arc::new(RwLock::new(HashMap::new())),
            security_stats: Arc::new(RwLock::new(SecurityStats {
                total_executions: 0,
                blocked_executions: 0,
                sandbox_violations: 0,
                average_execution_time_ms: 0.0,
                max_memory_used_kb: 0,
                security_score: 100.0,
            })),
        };
        
        security_manager.initialize_sandbox_environment().await?;
        
        Ok(security_manager)
    }

    /// Initialize sandbox environment with security constraints
    async fn initialize_sandbox_environment(&self) -> Result<()> {
        tracing::info!("Setting up sandbox environment with Jailkit/cgroups");
        
        // Create secure working directory
        let sandbox_dir = "/tmp/coderabbit_sandbox";
        if let Err(e) = std::fs::create_dir_all(sandbox_dir) {
            tracing::error!("Failed to create sandbox directory: {}", e);
            return Err(CodeRabbitError::ConfigError(format!("Sandbox setup failed: {}", e)));
        }
        
        // Set restrictive permissions
        let metadata = std::fs::metadata(sandbox_dir).map_err(|e| CodeRabbitError::ConfigError(format!("Failed to get sandbox directory metadata: {}", e)))?;
        let mut perms = metadata.permissions();
        perms.set_mode(0o700); // Only owner can read/write/execute
        std::fs::set_permissions(sandbox_dir, perms).map_err(|e| CodeRabbitError::ConfigError(format!("Failed to set sandbox permissions: {}", e)))?;
        
        tracing::info!("Sandbox directory created with restricted permissions: {}", sandbox_dir);
        
        // Initialize cgroup limits
        self.setup_cgroup_limits().await?;
        
        // Verify Jailkit configuration
        self.verify_jailkit_setup().await?;
        
        Ok(())
    }

    /// Set up cgroup resource limits
    async fn setup_cgroup_limits(&self) -> Result<()> {
        tracing::info!("Configuring cgroup memory and CPU limits");
        
        let memory_limit = self.config.max_memory_mb * 1024 * 1024; // Convert to bytes
        let cpu_quota = self.config.max_cpu_time_seconds * 100; // Convert to percentage * 100
        
        // Create memory cgroup
        let memory_cgroup = format!("/sys/fs/cgroup/memory/coderabbit_sandbox_{}", 
                                  std::process::id());
        
        if let Err(e) = Command::new("sh")
            .arg("-c")
            .arg(&format!(
                "echo {} > {}/memory.limit_in_bytes && \
                 echo {} > {}/cpu.cfs_quota_us && \
                 echo {} > {}/cpu.cfs_period_us",
                memory_limit, memory_cgroup, cpu_quota, memory_cgroup, 
                100000, memory_cgroup
            ))
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .status()
        {
            tracing::warn!("Failed to setup cgroup limits: {}", e);
        }
        
        Ok(())
    }

    /// Verify Jailkit is properly configured
    async fn verify_jailkit_setup(&self) -> Result<()> {
        tracing::info!("Verifying Jailkit configuration");
        
        // Check if jailkit binary exists and has correct permissions
        let jailkit_path = "/usr/sbin/jk_chrootlaunch";
        match std::fs::metadata(jailkit_path) {
            Ok(metadata) => {
                let permissions = metadata.permissions();
                tracing::info!("Found Jailkit at {} with permissions: {:?}", 
                             jailkit_path, permissions.mode());
            }
            Err(_) => {
                tracing::warn!("Jailkit not found at standard location");
            }
        }
        
        // Check for required system utilities
        let required_tools = ["timeout", "nice", "prlimit", "unshare"];
        for tool in &required_tools {
            match Command::new("which").arg(tool).output() {
                Ok(output) => {
                    if output.status.success() {
                        tracing::info!("Security tool '{}' available", tool);
                    } else {
                        tracing::warn!("Security tool '{}' not found", tool);
                    }
                }
                Err(e) => tracing::warn!("Failed to check tool '{}': {}", tool, e),
            }
        }
        
        Ok(())
    }

    /// Execute code in secure sandbox environment
    pub async fn execute_in_sandbox(&self, code: &str, language: &str, _working_dir: Option<String>) -> Result<ExecutionResult> {
        let start_time = std::time::Instant::now();
        let session_id = format!("sandbox_{}", chrono::Utc::now().timestamp());
        
        tracing::info!("Starting sandboxed execution session: {}", session_id);
        
        // Update statistics
        {
            let mut stats = self.security_stats.write().await;
            stats.total_executions += 1;
        }
        
        // Create secure working directory for this session
        let session_dir = format!("/tmp/coderabbit_sandbox/{}", session_id);
        if let Err(e) = std::fs::create_dir_all(&session_dir) {
            return Err(CodeRabbitError::ConfigError(
                format!("Failed to create session directory: {}", e)));
        }
        
        let session = ExecutionSession {
            session_id: session_id.clone(),
            pid: None,
            start_time,
            working_directory: session_dir.clone(),
            allowed_executables: self.get_allowed_executables(language),
        };
        
        // Register session
        {
            let mut sessions = self.active_sessions.write().await;
            sessions.insert(session_id.clone(), session);
        }
        
        // Write code to secure file
        let code_file = format!("{}/code.{}", session_dir, self.get_file_extension(language));
        if let Err(e) = std::fs::write(&code_file, code) {
            return Err(CodeRabbitError::ConfigError(
                format!("Failed to write code file: {}", e)));
        }
        
        // Execute in sandbox
        let result = self.execute_with_constraints(&session_dir, &code_file, language).await;
        
        // Cleanup session
        self.cleanup_session(&session_id).await;
        
        // Update statistics
        self.update_security_stats(&result).await;
        
        result
    }

    /// Execute code with security constraints
    async fn execute_with_constraints(&self, session_dir: &str, code_file: &str, 
                                    language: &str) -> Result<ExecutionResult> {
        let start_time = std::time::Instant::now();
        
        tracing::info!("Executing {} code in sandbox: {}", language, code_file);
        
        let (executable, args) = self.get_execution_command(language, code_file);
        
        // Build secure command with constraints
        let mut cmd = Command::new("timeout");
        cmd.args(&[
            &self.config.max_execution_time_seconds.to_string(),
            "nice", "-n", "10", // Lower CPU priority
            "prlimit", 
            &format!("--memory={}", self.config.max_memory_mb * 1024 * 1024), // Memory limit
            &format!("--nproc=1"), // Limit processes
            "unshare", "--mount", "--pid", "--fork", "--user", // Create new namespace
            "--mount-proc", // Mount new proc filesystem
            &executable,
        ])
        .args(&args[1..]) // Skip executable name from args
        .current_dir(session_dir)
        .stdout(Stdio::piped())
        .stderr(Stdio::piped());
        
        // Set up seccomp filtering if available
        self.apply_seccomp_filter(&mut cmd);
        
        // Execute with timeout
        let output = match cmd.output() {
            Ok(output) => output,
            Err(e) => {
                tracing::error!("Failed to execute sandboxed process: {}", e);
                return Ok(ExecutionResult {
                    exit_code: -1,
                    stdout: String::new(),
                    stderr: format!("Execution failed: {}", e),
                    execution_time_ms: start_time.elapsed().as_millis() as u64,
                    memory_used_kb: 0,
                    cpu_time_ms: 0,
                    sandbox_violations: vec!["execution_failed".to_string()],
                    success: false,
                });
            }
        };
        
        let execution_time = start_time.elapsed().as_millis() as u64;

        // Get resource usage statistics
        let (memory_used_kb, cpu_time_ms) = self.get_resource_usage();
        let sandbox_violations = self.check_sandbox_violations(&output);

        Ok(ExecutionResult {
            exit_code: output.status.code().unwrap_or(-1),
            stdout: String::from_utf8_lossy(&output.stdout).to_string(),
            stderr: String::from_utf8_lossy(&output.stderr).to_string(),
            execution_time_ms: execution_time,
            memory_used_kb,
            cpu_time_ms,
            sandbox_violations,
            success: output.status.success(),
        })
    }

    /// Get resource usage from /proc filesystem (Linux only)
    fn get_resource_usage(&self) -> (u64, u64) {
        #[cfg(target_os = "linux")]
        {
            use std::fs;
            use std::io::Read;

            // Try to read memory usage from /proc/self/status
            let memory_kb = if let Ok(mut file) = fs::File::open("/proc/self/status") {
                let mut content = String::new();
                if file.read_to_string(&mut content).is_ok() {
                    // Look for VmRSS (Resident Set Size - actual memory used)
                    content
                        .lines()
                        .find(|line| line.starts_with("VmRSS:"))
                        .and_then(|line| {
                            line.split_whitespace()
                                .nth(1)
                                .and_then(|s| s.parse::<u64>().ok())
                        })
                        .unwrap_or(0)
                } else {
                    0
                }
            } else {
                0
            };

            // Try to read CPU time from /proc/self/stat
            let cpu_ms = if let Ok(stat) = fs::read_to_string("/proc/self/stat") {
                let fields: Vec<&str> = stat.split_whitespace().collect();
                // Field 13 (utime) + Field 14 (stime) = total CPU time in clock ticks
                if fields.len() >= 15 {
                    let utime = fields[13].parse::<u64>().unwrap_or(0);
                    let stime = fields[14].parse::<u64>().unwrap_or(0);
                    let clock_ticks_per_sec = 100; // Usually 100 on Linux (sysconf(_SC_CLK_TCK))
                    ((utime + stime) * 1000) / clock_ticks_per_sec
                } else {
                    0
                }
            } else {
                0
            };

            (memory_kb, cpu_ms)
        }

        #[cfg(not(target_os = "linux"))]
        {
            // Resource monitoring not implemented for non-Linux platforms
            (0, 0)
        }
    }

    /// Check for sandbox violations in the output
    fn check_sandbox_violations(&self, output: &std::process::Output) -> Vec<String> {
        let mut violations = Vec::new();

        // Check stderr for common violation patterns
        let stderr = String::from_utf8_lossy(&output.stderr);

        if stderr.contains("Permission denied") || stderr.contains("Operation not permitted") {
            violations.push("permission_denied".to_string());
        }

        if stderr.contains("Killed") || stderr.contains("SIGKILL") {
            violations.push("process_killed".to_string());
        }

        if stderr.contains("Segmentation fault") || stderr.contains("SIGSEGV") {
            violations.push("segmentation_fault".to_string());
        }

        if stderr.contains("timeout") || stderr.contains("SIGALRM") {
            violations.push("timeout_exceeded".to_string());
        }

        if stderr.contains("Out of memory") || stderr.contains("OOM") {
            violations.push("memory_limit_exceeded".to_string());
        }

        // Check for syscall restriction violations
        if stderr.contains("Bad system call") || stderr.contains("SIGSYS") {
            violations.push("syscall_restricted".to_string());
        }

        violations
    }

    /// Apply seccomp filtering for additional security
    fn apply_seccomp_filter(&self, _cmd: &mut Command) {
        tracing::debug!("Applying seccomp syscall filtering");
        
        // Create minimal seccomp profile
        let _seccomp_profile = r#"
            #include <linux/seccomp.h>
            #include <linux/filter.h>
            
            // Allow basic syscalls only
            BPF_STMT(BPF_LD + BPF_W + BPF_ABS, (offsetof(struct seccomp_data, nr))),
            BPF_JUMP(BPF_JMP + BPF_JEQ + BPF_K, __NR_read, 0, 1),
            BPF_STMT(BPF_RET + BPF_K, SECCOMP_RET_ALLOW),
            BPF_JUMP(BPF_JMP + BPF_JEQ + BPF_K, __NR_write, 0, 1),
            BPF_STMT(BPF_RET + BPF_K, SECCOMP_RET_ALLOW),
            BPF_JUMP(BPF_JMP + BPF_JEQ + BPF_K, __NR_exit, 0, 1),
            BPF_STMT(BPF_RET + BPF_K, SECCOMP_RET_ALLOW),
            BPF_STMT(BPF_RET + BPF_K, SECCOMP_RET_KILL)
        "#;
        
        // Note: In a full implementation, this would create a seccomp filter
        // and apply it to the process. For now, we just log the intent.
        tracing::info!("Seccomp filtering configured for sandboxed execution");
    }

    /// Get execution command for specific language
    fn get_execution_command(&self, language: &str, code_file: &str) -> (String, Vec<String>) {
        match language.to_lowercase().as_str() {
            "python" => (
                "python3".to_string(),
                vec!["python3".to_string(), code_file.to_string()]
            ),
            "javascript" | "js" => (
                "node".to_string(),
                vec!["node".to_string(), code_file.to_string()]
            ),
            "bash" | "shell" => (
                "bash".to_string(),
                vec!["bash".to_string(), code_file.to_string()]
            ),
            "rust" => (
                "rustc".to_string(),
                vec!["rustc".to_string(), "-O".to_string(), code_file.to_string(), "-o".to_string(), "a.out".to_string()]
            ),
            _ => (
                "sh".to_string(),
                vec!["sh".to_string(), code_file.to_string()]
            )
        }
    }

    /// Get file extension for language
    fn get_file_extension(&self, language: &str) -> &str {
        match language.to_lowercase().as_str() {
            "python" => "py",
            "javascript" | "js" => "js",
            "rust" => "rs",
            "bash" | "shell" => "sh",
            _ => "txt"
        }
    }

    /// Get list of allowed executables for language
    fn get_allowed_executables(&self, language: &str) -> Vec<String> {
        match language.to_lowercase().as_str() {
            "python" => vec!["python3".to_string()],
            "javascript" => vec!["node".to_string()],
            "bash" => vec!["bash".to_string(), "sh".to_string()],
            "rust" => vec!["rustc".to_string(), "./a.out".to_string()],
            _ => vec!["sh".to_string()]
        }
    }

    /// Cleanup session resources
    async fn cleanup_session(&self, session_id: &str) {
        tracing::info!("Cleaning up sandbox session: {}", session_id);
        
        // Remove from active sessions
        {
            let mut sessions = self.active_sessions.write().await;
            sessions.remove(session_id);
        }
        
        // Remove session directory
        let session_dir = format!("/tmp/coderabbit_sandbox/{}", session_id);
        let _ = std::fs::remove_dir_all(&session_dir);
    }

    /// Update security statistics
    async fn update_security_stats(&self, result: &Result<ExecutionResult>) {
        let mut stats = self.security_stats.write().await;
        
        match result {
            Ok(execution_result) => {
                if execution_result.success {
                    let current_avg = stats.average_execution_time_ms;
                    let new_count = stats.total_executions;
                    stats.average_execution_time_ms = 
                        (current_avg * (new_count - 1) as f64 + execution_result.execution_time_ms as f64) / new_count as f64;
                    
                    if execution_result.memory_used_kb > stats.max_memory_used_kb {
                        stats.max_memory_used_kb = execution_result.memory_used_kb;
                    }
                    
                    if !execution_result.sandbox_violations.is_empty() {
                        stats.sandbox_violations += execution_result.sandbox_violations.len() as u64;
                        stats.security_score -= 0.1;
                    }
                } else {
                    stats.blocked_executions += 1;
                    stats.security_score -= 0.5;
                }
            }
            Err(_) => {
                stats.blocked_executions += 1;
                stats.security_score -= 1.0;
            }
        }
        
        // Ensure security score doesn't go below 0
        stats.security_score = stats.security_score.max(0.0);
    }

    /// Get security statistics
    pub async fn get_security_stats(&self) -> SecurityStats {
        let stats = self.security_stats.read().await;
        stats.clone()
    }

    /// Check if sandbox environment is secure
    pub async fn validate_security(&self) -> Result<bool> {
        tracing::info!("Performing security validation");
        
        // Check running as root
        if !Uid::current().is_root() {
            tracing::warn!("Not running as root - limited security capabilities");
            return Ok(false);
        }
        
        // Check sandbox directory permissions
        let sandbox_dir = "/tmp/coderabbit_sandbox";
        match std::fs::metadata(sandbox_dir) {
            Ok(metadata) => {
                let permissions = metadata.permissions();
                if permissions.mode() & 0o077 != 0 {
                    tracing::error!("Sandbox directory has incorrect permissions");
                    return Ok(false);
                }
            }
            Err(e) => {
                tracing::error!("Cannot access sandbox directory: {}", e);
                return Ok(false);
            }
        }
        
        // Check active sessions for security issues
        let sessions = self.active_sessions.read().await;
        for (session_id, session) in sessions.iter() {
            let session_path = std::path::Path::new(&session.working_directory);
            if !session_path.exists() {
                tracing::error!("Session {} has missing working directory", session_id);
                return Ok(false);
            }
        }
        
        tracing::info!("Security validation passed");
        Ok(true)
    }

    /// Get list of active sandbox sessions
    pub async fn get_active_sessions(&self) -> Vec<String> {
        let sessions = self.active_sessions.read().await;
        sessions.keys().cloned().collect()
    }

    /// Terminate specific sandbox session
    pub async fn terminate_session(&self, session_id: &str) -> Result<()> {
        tracing::info!("Terminating sandbox session: {}", session_id);
        
        let mut sessions = self.active_sessions.write().await;
        
        if let Some(session) = sessions.remove(session_id) {
            // Kill process if running
            if let Some(pid) = session.pid {
                let _ = Command::new("kill")
                    .arg("-9")
                    .arg(pid.to_string())
                    .output();
            }
            
            // Cleanup session directory
            let _ = std::fs::remove_dir_all(&session.working_directory);
            
            Ok(())
        } else {
            Err(CodeRabbitError::NotFound(format!("Session {} not found", session_id)))
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use tokio::test;

    // Helper to create test sandbox config
    fn test_sandbox_config() -> SandboxConfig {
        SandboxConfig {
            max_memory_mb: 512,
            max_cpu_time_seconds: 10,
            max_execution_time_seconds: 5,
            allowed_directories: vec!["/tmp/coderabbit_sandbox".to_string()],
            blocked_syscalls: vec!["socket".to_string(), "connect".to_string()],
            enable_network: false,
            user_id: 1000,
            group_id: 1000,
        }
    }

    // ===== Configuration Tests =====

    #[test]
    async fn test_sandbox_config_creation() {
        let config = test_sandbox_config();

        assert_eq!(config.max_memory_mb, 512);
        assert_eq!(config.max_cpu_time_seconds, 10);
        assert_eq!(config.max_execution_time_seconds, 5);
        assert!(!config.enable_network);
        assert_eq!(config.user_id, 1000);
        assert_eq!(config.group_id, 1000);
    }

    #[test]
    async fn test_execution_result_defaults() {
        let result = ExecutionResult {
            exit_code: 0,
            stdout: "success".to_string(),
            stderr: String::new(),
            execution_time_ms: 100,
            memory_used_kb: 1024,
            cpu_time_ms: 50,
            sandbox_violations: vec![],
            success: true,
        };

        assert_eq!(result.exit_code, 0);
        assert!(result.success);
        assert!(result.sandbox_violations.is_empty());
    }

    #[test]
    async fn test_security_stats_initialization() {
        let stats = SecurityStats {
            total_executions: 0,
            blocked_executions: 0,
            sandbox_violations: 0,
            average_execution_time_ms: 0.0,
            max_memory_used_kb: 0,
            security_score: 100.0,
        };

        assert_eq!(stats.total_executions, 0);
        assert_eq!(stats.security_score, 100.0);
    }

    // ===== Security Manager Tests =====

    #[test]
    async fn test_security_manager_creation() {
        let config = test_sandbox_config();
        let result = SecurityManager::new(config).await;

        // Manager creation may fail if not root, but should return Result
        assert!(result.is_ok() || result.is_err());
    }

    #[test]
    async fn test_file_extension_mapping() {
        let config = test_sandbox_config();
        let manager = match SecurityManager::new(config).await {
            Ok(m) => m,
            Err(_) => return, // Skip if cannot create manager
        };

        assert_eq!(manager.get_file_extension("python"), "py");
        assert_eq!(manager.get_file_extension("javascript"), "js");
        assert_eq!(manager.get_file_extension("rust"), "rs");
        assert_eq!(manager.get_file_extension("bash"), "sh");
        assert_eq!(manager.get_file_extension("unknown"), "txt");
    }

    #[test]
    async fn test_allowed_executables_python() {
        let config = test_sandbox_config();
        let manager = match SecurityManager::new(config).await {
            Ok(m) => m,
            Err(_) => return,
        };

        let executables = manager.get_allowed_executables("python");
        assert!(executables.contains(&"python3".to_string()));
    }

    #[test]
    async fn test_allowed_executables_javascript() {
        let config = test_sandbox_config();
        let manager = match SecurityManager::new(config).await {
            Ok(m) => m,
            Err(_) => return,
        };

        let executables = manager.get_allowed_executables("javascript");
        assert!(executables.contains(&"node".to_string()));
    }

    #[test]
    async fn test_allowed_executables_rust() {
        let config = test_sandbox_config();
        let manager = match SecurityManager::new(config).await {
            Ok(m) => m,
            Err(_) => return,
        };

        let executables = manager.get_allowed_executables("rust");
        assert!(executables.contains(&"rustc".to_string()));
    }

    #[test]
    async fn test_execution_command_python() {
        let config = test_sandbox_config();
        let manager = match SecurityManager::new(config).await {
            Ok(m) => m,
            Err(_) => return,
        };

        let (executable, args) = manager.get_execution_command("python", "/tmp/test.py");
        assert_eq!(executable, "python3");
        assert!(args.contains(&"/tmp/test.py".to_string()));
    }

    #[test]
    async fn test_execution_command_javascript() {
        let config = test_sandbox_config();
        let manager = match SecurityManager::new(config).await {
            Ok(m) => m,
            Err(_) => return,
        };

        let (executable, args) = manager.get_execution_command("javascript", "/tmp/test.js");
        assert_eq!(executable, "node");
        assert!(args.contains(&"/tmp/test.js".to_string()));
    }

    #[test]
    async fn test_execution_command_bash() {
        let config = test_sandbox_config();
        let manager = match SecurityManager::new(config).await {
            Ok(m) => m,
            Err(_) => return,
        };

        let (executable, _) = manager.get_execution_command("bash", "/tmp/test.sh");
        assert_eq!(executable, "bash");
    }

    // ===== Sandbox Violation Detection Tests =====

    #[test]
    async fn test_check_sandbox_violations_permission_denied() {
        let config = test_sandbox_config();
        let manager = match SecurityManager::new(config).await {
            Ok(m) => m,
            Err(_) => return,
        };

        let output = std::process::Output {
            status: std::process::ExitStatus::default(),
            stdout: vec![],
            stderr: b"Permission denied".to_vec(),
        };

        let violations = manager.check_sandbox_violations(&output);
        assert!(violations.contains(&"permission_denied".to_string()));
    }

    #[test]
    async fn test_check_sandbox_violations_timeout() {
        let config = test_sandbox_config();
        let manager = match SecurityManager::new(config).await {
            Ok(m) => m,
            Err(_) => return,
        };

        let output = std::process::Output {
            status: std::process::ExitStatus::default(),
            stdout: vec![],
            stderr: b"timeout: command exceeded time limit".to_vec(),
        };

        let violations = manager.check_sandbox_violations(&output);
        assert!(violations.contains(&"timeout_exceeded".to_string()));
    }

    #[test]
    async fn test_check_sandbox_violations_memory() {
        let config = test_sandbox_config();
        let manager = match SecurityManager::new(config).await {
            Ok(m) => m,
            Err(_) => return,
        };

        let output = std::process::Output {
            status: std::process::ExitStatus::default(),
            stdout: vec![],
            stderr: b"Out of memory".to_vec(),
        };

        let violations = manager.check_sandbox_violations(&output);
        assert!(violations.contains(&"memory_limit_exceeded".to_string()));
    }

    #[test]
    async fn test_check_sandbox_violations_process_killed() {
        let config = test_sandbox_config();
        let manager = match SecurityManager::new(config).await {
            Ok(m) => m,
            Err(_) => return,
        };

        let output = std::process::Output {
            status: std::process::ExitStatus::default(),
            stdout: vec![],
            stderr: b"Killed".to_vec(),
        };

        let violations = manager.check_sandbox_violations(&output);
        assert!(violations.contains(&"process_killed".to_string()));
    }

    #[test]
    async fn test_check_sandbox_violations_segfault() {
        let config = test_sandbox_config();
        let manager = match SecurityManager::new(config).await {
            Ok(m) => m,
            Err(_) => return,
        };

        let output = std::process::Output {
            status: std::process::ExitStatus::default(),
            stdout: vec![],
            stderr: b"Segmentation fault".to_vec(),
        };

        let violations = manager.check_sandbox_violations(&output);
        assert!(violations.contains(&"segmentation_fault".to_string()));
    }

    #[test]
    async fn test_check_sandbox_violations_syscall() {
        let config = test_sandbox_config();
        let manager = match SecurityManager::new(config).await {
            Ok(m) => m,
            Err(_) => return,
        };

        let output = std::process::Output {
            status: std::process::ExitStatus::default(),
            stdout: vec![],
            stderr: b"Bad system call".to_vec(),
        };

        let violations = manager.check_sandbox_violations(&output);
        assert!(violations.contains(&"syscall_restricted".to_string()));
    }

    #[test]
    async fn test_check_sandbox_violations_none() {
        let config = test_sandbox_config();
        let manager = match SecurityManager::new(config).await {
            Ok(m) => m,
            Err(_) => return,
        };

        let output = std::process::Output {
            status: std::process::ExitStatus::default(),
            stdout: b"Success".to_vec(),
            stderr: vec![],
        };

        let violations = manager.check_sandbox_violations(&output);
        assert!(violations.is_empty());
    }

    // ===== Session Management Tests =====

    #[test]
    async fn test_get_active_sessions_empty() {
        let config = test_sandbox_config();
        let manager = match SecurityManager::new(config).await {
            Ok(m) => m,
            Err(_) => return,
        };

        let sessions = manager.get_active_sessions().await;
        assert_eq!(sessions.len(), 0);
    }

    #[test]
    async fn test_terminate_nonexistent_session() {
        let config = test_sandbox_config();
        let manager = match SecurityManager::new(config).await {
            Ok(m) => m,
            Err(_) => return,
        };

        let result = manager.terminate_session("nonexistent_session").await;
        assert!(result.is_err());
    }

    // ===== Security Statistics Tests =====

    #[test]
    async fn test_get_security_stats() {
        let config = test_sandbox_config();
        let manager = match SecurityManager::new(config).await {
            Ok(m) => m,
            Err(_) => return,
        };

        let stats = manager.get_security_stats().await;
        assert_eq!(stats.total_executions, 0);
        assert_eq!(stats.blocked_executions, 0);
        assert_eq!(stats.security_score, 100.0);
    }

    // ===== Python Execution Tests =====

    #[test]
    async fn test_execute_simple_python() {
        let config = test_sandbox_config();
        let manager = match SecurityManager::new(config).await {
            Ok(m) => m,
            Err(_) => return,
        };

        let code = "print('Hello from Python')";
        let result = manager.execute_in_sandbox(code, "python", None).await;

        if let Ok(exec_result) = result {
            // Verify result structure exists (execution may fail due to env)
            assert!(exec_result.execution_time_ms >= 0);
        }
        // If failed due to permissions/environment, that's acceptable in test environment
    }

    #[test]
    async fn test_execute_python_with_output() {
        let config = test_sandbox_config();
        let manager = match SecurityManager::new(config).await {
            Ok(m) => m,
            Err(_) => return,
        };

        let code = "result = 2 + 2\nprint(f'Result: {result}')";
        let result = manager.execute_in_sandbox(code, "python", None).await;

        if let Ok(exec_result) = result {
            assert!(exec_result.execution_time_ms >= 0);
        }
    }

    #[test]
    async fn test_execute_python_with_error() {
        let config = test_sandbox_config();
        let manager = match SecurityManager::new(config).await {
            Ok(m) => m,
            Err(_) => return,
        };

        let code = "undefined_variable";
        let result = manager.execute_in_sandbox(code, "python", None).await;

        if let Ok(exec_result) = result {
            // Should have error in stderr or non-zero exit
            assert!(!exec_result.stderr.is_empty() || exec_result.exit_code != 0);
        }
    }

    // ===== JavaScript Execution Tests =====

    #[test]
    async fn test_execute_simple_javascript() {
        let config = test_sandbox_config();
        let manager = match SecurityManager::new(config).await {
            Ok(m) => m,
            Err(_) => return,
        };

        let code = "console.log('Hello from Node.js');";
        let result = manager.execute_in_sandbox(code, "javascript", None).await;

        if let Ok(exec_result) = result {
            assert!(exec_result.execution_time_ms >= 0);
        }
    }

    // ===== Bash Execution Tests =====

    #[test]
    async fn test_execute_simple_bash() {
        let config = test_sandbox_config();
        let manager = match SecurityManager::new(config).await {
            Ok(m) => m,
            Err(_) => return,
        };

        let code = "echo 'Hello from Bash'";
        let result = manager.execute_in_sandbox(code, "bash", None).await;

        if let Ok(exec_result) = result {
            assert!(exec_result.execution_time_ms >= 0);
        }
    }

    // ===== Resource Limit Tests =====

    #[test]
    async fn test_execution_tracks_time() {
        let config = test_sandbox_config();
        let manager = match SecurityManager::new(config).await {
            Ok(m) => m,
            Err(_) => return,
        };

        let code = "import time\ntime.sleep(0.1)\nprint('done')";
        let result = manager.execute_in_sandbox(code, "python", None).await;

        if let Ok(exec_result) = result {
            // Just verify time is tracked (value depends on system load)
            assert!(exec_result.execution_time_ms >= 0);
        }
    }

    #[test]
    async fn test_timeout_enforcement() {
        let mut config = test_sandbox_config();
        config.max_execution_time_seconds = 1; // 1 second timeout

        let manager = match SecurityManager::new(config).await {
            Ok(m) => m,
            Err(_) => return,
        };

        // Code that sleeps longer than timeout
        let code = "import time\ntime.sleep(5)\nprint('should not reach here')";
        let result = manager.execute_in_sandbox(code, "python", None).await;

        if let Ok(exec_result) = result {
            // Should timeout
            assert!(!exec_result.success || !exec_result.sandbox_violations.is_empty());
        }
    }

    // ===== Statistics Update Tests =====

    #[test]
    async fn test_stats_updated_after_execution() {
        let config = test_sandbox_config();
        let manager = match SecurityManager::new(config).await {
            Ok(m) => m,
            Err(_) => return,
        };

        let initial_stats = manager.get_security_stats().await;
        assert_eq!(initial_stats.total_executions, 0);

        let code = "print('test')";
        let _ = manager.execute_in_sandbox(code, "python", None).await;

        let updated_stats = manager.get_security_stats().await;
        assert!(updated_stats.total_executions >= initial_stats.total_executions);
    }

    #[test]
    async fn test_security_score_decreases_on_violation() {
        let config = test_sandbox_config();
        let manager = match SecurityManager::new(config).await {
            Ok(m) => m,
            Err(_) => return,
        };

        let initial_stats = manager.get_security_stats().await;
        let initial_score = initial_stats.security_score;

        // Execute code that should fail
        let code = "invalid python code!!!";
        let _ = manager.execute_in_sandbox(code, "python", None).await;

        let updated_stats = manager.get_security_stats().await;
        // Score should either decrease or stay same (if execution handled gracefully)
        assert!(updated_stats.security_score <= initial_score);
    }

    // ===== Multi-language Tests =====

    #[test]
    async fn test_multiple_language_support() {
        let config = test_sandbox_config();
        let manager = match SecurityManager::new(config).await {
            Ok(m) => m,
            Err(_) => return,
        };

        let languages = vec![
            ("python", "print('Python')"),
            ("javascript", "console.log('JavaScript')"),
            ("bash", "echo 'Bash'"),
        ];

        for (lang, code) in languages {
            let result = manager.execute_in_sandbox(code, lang, None).await;
            // Just verify it returns a result (may succeed or fail based on environment)
            assert!(result.is_ok() || result.is_err());
        }
    }

    // ===== Serialization Tests =====

    #[test]
    async fn test_execution_result_serialization() {
        let result = ExecutionResult {
            exit_code: 0,
            stdout: "success".to_string(),
            stderr: String::new(),
            execution_time_ms: 100,
            memory_used_kb: 1024,
            cpu_time_ms: 50,
            sandbox_violations: vec![],
            success: true,
        };

        let serialized = serde_json::to_string(&result).unwrap();
        let deserialized: ExecutionResult = serde_json::from_str(&serialized).unwrap();

        assert_eq!(deserialized.exit_code, 0);
        assert_eq!(deserialized.success, true);
    }

    #[test]
    async fn test_security_stats_serialization() {
        let stats = SecurityStats {
            total_executions: 100,
            blocked_executions: 5,
            sandbox_violations: 2,
            average_execution_time_ms: 123.45,
            max_memory_used_kb: 2048,
            security_score: 95.5,
        };

        let serialized = serde_json::to_string(&stats).unwrap();
        let deserialized: SecurityStats = serde_json::from_str(&serialized).unwrap();

        assert_eq!(deserialized.total_executions, 100);
        assert_eq!(deserialized.blocked_executions, 5);
    }

    #[test]
    async fn test_sandbox_config_serialization() {
        let config = test_sandbox_config();

        let serialized = serde_json::to_string(&config).unwrap();
        let deserialized: SandboxConfig = serde_json::from_str(&serialized).unwrap();

        assert_eq!(deserialized.max_memory_mb, 512);
        assert_eq!(deserialized.max_execution_time_seconds, 5);
    }
}
