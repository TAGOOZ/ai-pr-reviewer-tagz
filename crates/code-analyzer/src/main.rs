use coderabbit_code_analyzer::CodeAnalyzer;
use coderabbit_shared::{FileChange, ChangeType};
use tracing_subscriber::{layer::SubscriberExt, util::SubscriberInitExt};

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    // Initialize tracing
    tracing_subscriber::registry()
        .with(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| "coderabbit_code_analyzer=debug".into()),
        )
        .with(tracing_subscriber::fmt::layer())
        .init();

    tracing::info!("Starting CodeRabbit Code Analyzer");

    // Create analyzer instance
    let analyzer = CodeAnalyzer::new();

    // Example usage - analyze some sample files
    let sample_files = vec![
        FileChange {
            path: "src/main.rs".to_string(),
            change_type: ChangeType::Modified,
            content: r#"
fn main() {
    println!("Hello, world!");
    let x = 42;
    println!("The answer is {}", x);
}
"#.to_string(),
            diff: r#"
+fn main() {
+    println!("Hello, world!");
+    let x = 42;
+    println!("The answer is {}", x);
+}
"#.to_string(),
            language: "rust".to_string(),
        },
        FileChange {
            path: "src/lib.rs".to_string(),
            change_type: ChangeType::Added,
            content: r#"
pub fn add(a: i32, b: i32) -> i32 {
    a + b
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_add() {
        assert_eq!(add(2, 2), 4);
    }
}
"#.to_string(),
            diff: r#"
+pub fn add(a: i32, b: i32) -> i32 {
+    a + b
+}
+
+#[cfg(test)]
+mod tests {
+    use super::*;
+
+    #[test]
+    fn test_add() {
+        assert_eq!(add(2, 2), 4);
+    }
+}
"#.to_string(),
            language: "rust".to_string(),
        },
    ];

    // Analyze the files
    match analyzer.analyze_files(sample_files).await {
        Ok(results) => {
            tracing::info!("Analysis completed successfully");
            for result in results {
                tracing::info!(
                    "File: {}, Language: {}, Issues: {}, LOC: {}",
                    result.file_path,
                    result.language,
                    result.issues.len(),
                    result.metrics.lines_of_code
                );
            }
        }
        Err(e) => {
            tracing::error!("Analysis failed: {}", e);
            std::process::exit(1);
        }
    }

    tracing::info!("CodeRabbit Code Analyzer completed");
    Ok(())
}