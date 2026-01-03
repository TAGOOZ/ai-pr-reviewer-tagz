use crate::metrics::MetricsCalculator;
use crate::parser::LanguageParser;
use crate::rules::RuleEngine;
use crate::static_analysis::StaticAnalyzer;
use coderabbit_shared::{FileChange, Result};
use rayon::prelude::*;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Issue {
    pub rule_id: String,
    pub message: String,
    pub severity: String,
    pub line: u32,
    pub column: u32,
    pub suggestion: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CodeMetrics {
    pub lines_of_code: u32,
    pub cyclomatic_complexity: u32,
    pub maintainability_index: f32,
    pub technical_debt_minutes: u32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ASTFeatures {
    pub function_count: u32,
    pub class_count: u32,
    pub import_count: u32,
    pub complexity_score: f32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CodeAnalysisResult {
    pub file_path: String,
    pub language: String,
    pub issues: Vec<Issue>,
    pub metrics: CodeMetrics,
    pub embeddings: Vec<f32>,
    pub ast_features: ASTFeatures,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DiffAnalysis {
    pub added_lines: u32,
    pub removed_lines: u32,
    pub modified_functions: Vec<String>,
    pub risk_score: f32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RepoContext {
    pub repository_id: String,
    pub branch: String,
    pub commit_hash: String,
    pub metadata: HashMap<String, String>,
}

pub struct CodeAnalyzer {
    rule_engine: RuleEngine,
}

impl CodeAnalyzer {
    pub fn new() -> Self {
        Self {
            rule_engine: RuleEngine::new(),
            static_analyzer: StaticAnalyzer::new(),
        }
    }

    pub async fn analyze_files(&self, files: Vec<FileChange>) -> Result<Vec<CodeAnalysisResult>> {
        // Use Rayon for parallel processing
        let results: Result<Vec<_>> = files
            .into_par_iter()
            .map(|file| self.analyze_single_file(file))
            .collect();

        results
    }

    pub async fn analyze_file_batch(
        &self,
        files: Vec<FileChange>,
    ) -> Result<Vec<CodeAnalysisResult>> {
        // Thin wrapper to provide a clear batch API surface
        self.analyze_files(files).await
    }

    pub async fn analyze_diff(&self, diff: &str, context: &RepoContext) -> Result<DiffAnalysis> {
        tracing::info!("Analyzing diff for repo: {}", context.repository_id);

        let mut added_lines = 0;
        let mut removed_lines = 0;
        let mut modified_functions = Vec::new();
        let mut current_function = None;

        // Parse diff line by line
        for line in diff.lines() {
            if line.starts_with("+++") || line.starts_with("---") {
                // Skip file markers
                continue;
            } else if line.starts_with("+") && !line.starts_with("+++") {
                added_lines += 1;

                // Check if this is a function definition
                if line.contains("fn ")
                    || line.contains("def ")
                    || line.contains("function ")
                    || line.contains("func ")
                {
                    // Extract function name
                    if let Some(func_name) = self.extract_function_name(line) {
                        current_function = Some(func_name.clone());
                        if !modified_functions.contains(&func_name) {
                            modified_functions.push(func_name);
                        }
                    }
                }
            } else if line.starts_with("-") && !line.starts_with("---") {
                removed_lines += 1;

                // Check if this is a function definition being removed
                if line.contains("fn ")
                    || line.contains("def ")
                    || line.contains("function ")
                    || line.contains("func ")
                {
                    if let Some(func_name) = self.extract_function_name(line) {
                        if !modified_functions.contains(&func_name) {
                            modified_functions.push(func_name);
                        }
                    }
                }
            } else if line.starts_with("@@") {
                // Parse function context from diff hunk header
                if let Some(func_name) = self.extract_function_from_hunk(line) {
                    current_function = Some(func_name.clone());
                    if !modified_functions.contains(&func_name) {
                        modified_functions.push(func_name);
                    }
                }
            }
        }

        // Calculate risk score based on changes
        let risk_score = self.calculate_risk_score(added_lines, removed_lines, &modified_functions);

        tracing::info!(
            "Diff analysis complete: +{} -{} lines, {} functions modified, risk score: {:.2}",
            added_lines,
            removed_lines,
            modified_functions.len(),
            risk_score
        );

        Ok(DiffAnalysis {
            added_lines,
            removed_lines,
            modified_functions,
            risk_score,
        })
    }

    fn extract_function_name(&self, line: &str) -> Option<String> {
        // Remove leading +/- and whitespace
        let trimmed = line.trim_start_matches(['+', '-', ' ', '\t']);

        // Try different function patterns
        let patterns = [
            (r"fn\s+(\w+)", "fn "),
            (r"def\s+(\w+)", "def "),
            (r"function\s+(\w+)", "function "),
            (r"func\s+(\w+)", "func "),
            (r"(\w+)\s*\(", ""), // Generic pattern: name(
        ];

        for (_, keyword) in patterns {
            if let Some(pos) = trimmed.find(keyword) {
                let after_keyword = &trimmed[pos + keyword.len()..];
                if let Some(name_end) =
                    after_keyword.find(|c: char| !c.is_alphanumeric() && c != '_')
                {
                    let name = after_keyword[..name_end].trim();
                    if !name.is_empty() {
                        return Some(name.to_string());
                    }
                }
            }
        }

        None
    }

    fn extract_function_from_hunk(&self, hunk_header: &str) -> Option<String> {
        // Hunk headers often contain function context like: @@ -10,7 +10,7 @@ fn main() {
        if let Some(pos) = hunk_header.rfind("@@") {
            let context = hunk_header[pos + 2..].trim();
            if !context.is_empty() {
                // Extract function name from context
                return self.extract_function_name(context);
            }
        }
        None
    }

    fn calculate_risk_score(&self, added: u32, removed: u32, functions: &[String]) -> f32 {
        // Risk scoring factors:
        // 1. Large number of changes (lines added/removed)
        // 2. Number of functions modified
        // 3. Balance of additions vs deletions

        let line_risk = ((added + removed) as f32 / 100.0).min(5.0); // Max 5 points for lines
        let function_risk = (functions.len() as f32 / 10.0).min(3.0); // Max 3 points for functions

        // Imbalanced changes (lots of additions or lots of deletions) are riskier
        let imbalance = if added + removed > 0 {
            (added as f32 - removed as f32).abs() / (added + removed) as f32
        } else {
            0.0
        };
        let balance_risk = imbalance * 2.0; // Max 2 points for imbalance

        // Total risk score (0-10 scale)
        (line_risk + function_risk + balance_risk).min(10.0)
    }

    pub async fn extract_embeddings(&self, code: &str) -> Result<Vec<f32>> {
        tracing::info!("Extracting embeddings for code snippet");

        // Call Python embedding service via HTTP
        let client = reqwest::Client::new();

        #[derive(serde::Serialize)]
        struct EmbeddingRequest {
            text: String,
        }

        #[derive(serde::Deserialize)]
        struct EmbeddingResponse {
            embedding: Vec<f32>,
        }

        // Try to call the embedding service
        let embedding_url = std::env::var("EMBEDDING_SERVICE_URL")
            .unwrap_or_else(|_| "http://localhost:8081/embed".to_string());

        match client
            .post(&embedding_url)
            .json(&EmbeddingRequest {
                text: code.to_string(),
            })
            .timeout(std::time::Duration::from_secs(10))
            .send()
            .await
        {
            Ok(response) => {
                if response.status().is_success() {
                    match response.json::<EmbeddingResponse>().await {
                        Ok(data) => {
                            tracing::debug!(
                                "Successfully extracted embeddings: {} dimensions",
                                data.embedding.len()
                            );
                            Ok(data.embedding)
                        }
                        Err(e) => {
                            tracing::warn!("Failed to parse embedding response: {}", e);
                            Ok(vec![]) // Return empty on parse error
                        }
                    }
                } else {
                    tracing::warn!("Embedding service returned status: {}", response.status());
                    Ok(vec![])
                }
            }
            Err(e) => {
                tracing::warn!("Failed to call embedding service: {}", e);
                // Return empty vector as fallback
                Ok(vec![])
            }
        }
    }

    fn analyze_single_file(&self, file: FileChange) -> Result<CodeAnalysisResult> {
        tracing::info!("Analyzing file: {}", file.path);

        // Apply static analysis rules
        let issues = self.rule_engine.apply_rules(&file.content, &file.language);

        // Calculate code metrics
        let metrics = MetricsCalculator::calculate_metrics(&file.content, &file.language);

        // Extract AST features using tree-sitter
        let ast_features = self.extract_ast_features(&file.content, &file.language);

        Ok(CodeAnalysisResult {
            file_path: file.path,
            language: file.language,
            issues,
            metrics,
            embeddings: vec![], // Embeddings are extracted separately via async method
            ast_features,
        })
    }

    fn extract_ast_features(&self, code: &str, language: &str) -> ASTFeatures {
        // Try tree-sitter parsing first, fall back to heuristics if it fails
        match self.extract_ast_features_with_treesitter(code, language) {
            Ok(features) => {
                tracing::debug!(
                    "Successfully extracted AST features using tree-sitter for {}",
                    language
                );
                features
            }
            Err(e) => {
                tracing::debug!(
                    "Tree-sitter parsing failed for {}: {}. Using heuristic fallback.",
                    language,
                    e
                );
                self.extract_ast_features_heuristic(code, language)
            }
        }
    }

    fn extract_ast_features_with_treesitter(
        &self,
        code: &str,
        language: &str,
    ) -> Result<ASTFeatures> {
        let mut parser = LanguageParser::new()?;
        let tree = parser.parse(language, code)?;
        let root_node = tree.root_node();

        let mut function_count = 0;
        let mut class_count = 0;
        let mut import_count = 0;
        let mut decision_points = 0;

        // Walk the tree and count different node types
        let mut cursor = root_node.walk();
        let mut visit_children = true;

        loop {
            let node = cursor.node();
            let kind = node.kind();

            // Count functions based on language-specific node types
            match language {
                "rust" => match kind {
                    "function_item" => function_count += 1,
                    "struct_item" | "enum_item" | "impl_item" => class_count += 1,
                    "use_declaration" => import_count += 1,
                    "if_expression" | "match_expression" | "while_expression"
                    | "for_expression" | "loop_expression" => decision_points += 1,
                    _ => {}
                },
                "python" => match kind {
                    "function_definition" => function_count += 1,
                    "class_definition" => class_count += 1,
                    "import_statement" | "import_from_statement" => import_count += 1,
                    "if_statement" | "while_statement" | "for_statement" | "match_statement" => {
                        decision_points += 1
                    }
                    _ => {}
                },
                "javascript" | "typescript" => match kind {
                    "function_declaration"
                    | "function"
                    | "arrow_function"
                    | "method_definition" => function_count += 1,
                    "class_declaration" => class_count += 1,
                    "import_statement" => import_count += 1,
                    "if_statement" | "while_statement" | "for_statement" | "switch_statement" => {
                        decision_points += 1
                    }
                    _ => {}
                },
                "java" => match kind {
                    "method_declaration" => function_count += 1,
                    "class_declaration" | "interface_declaration" => class_count += 1,
                    "import_declaration" => import_count += 1,
                    "if_statement" | "while_statement" | "for_statement" | "switch_expression" => {
                        decision_points += 1
                    }
                    _ => {}
                },
                "go" => match kind {
                    "function_declaration" | "method_declaration" => function_count += 1,
                    "type_declaration" => class_count += 1,
                    "import_declaration" => import_count += 1,
                    "if_statement" | "for_statement" | "switch_statement" => decision_points += 1,
                    _ => {}
                },
                _ => {}
            }

            // Navigate the tree
            if visit_children && cursor.goto_first_child() {
                continue;
            }
            visit_children = true;

            if cursor.goto_next_sibling() {
                continue;
            }

            loop {
                if !cursor.goto_parent() {
                    // Reached root, done
                    let complexity_score = 1.0 + (decision_points as f32);
                    return Ok(ASTFeatures {
                        function_count,
                        class_count,
                        import_count,
                        complexity_score,
                    });
                }

                if cursor.goto_next_sibling() {
                    break;
                }
            }
        }
    }

    fn extract_ast_features_heuristic(&self, code: &str, language: &str) -> ASTFeatures {
        // Fallback heuristic-based AST feature extraction for unsupported languages
        let mut function_count = 0;
        let mut class_count = 0;
        let mut import_count = 0;

        // Simple heuristic-based counting (language-specific)
        match language {
            "rust" => {
                function_count = code.matches("fn ").count();
                class_count = code.matches("struct ").count() + code.matches("enum ").count();
                import_count = code.matches("use ").count();
            }
            "python" => {
                function_count = code.matches("def ").count();
                class_count = code.matches("class ").count();
                import_count = code.matches("import ").count() + code.matches("from ").count();
            }
            "javascript" | "typescript" => {
                function_count = code.matches("function ").count() + code.matches("const ").count();
                class_count = code.matches("class ").count();
                import_count = code.matches("import ").count() + code.matches("require(").count();
            }
            _ => {
                // Generic counting for other languages
                function_count = code
                    .lines()
                    .filter(|l| l.contains("function") || l.contains("def"))
                    .count();
                class_count = code.matches("class ").count();
            }
        }

        // Calculate cyclomatic complexity (simplified)
        let complexity_score = self.calculate_cyclomatic_complexity(code, language);

        ASTFeatures {
            function_count: function_count as u32,
            class_count: class_count as u32,
            import_count: import_count as u32,
            complexity_score,
        }
    }

    fn calculate_cyclomatic_complexity(&self, code: &str, language: &str) -> f32 {
        // Simplified cyclomatic complexity calculation
        // Count decision points: if, else, while, for, case, match, etc.

        let decision_keywords = match language {
            "rust" => vec!["if ", "else", "while ", "for ", "match ", "loop "],
            "python" => vec!["if ", "elif ", "else:", "while ", "for ", "try:", "except:"],
            "javascript" | "typescript" => {
                vec!["if ", "else", "while ", "for ", "switch ", "case "]
            }
            _ => vec!["if ", "else", "while ", "for "],
        };

        let mut decision_count = 1; // Base complexity is 1
        for keyword in decision_keywords {
            decision_count += code.matches(keyword).count();
        }

        // Normalize by lines of code
        let loc = code.lines().count() as f32;
        if loc > 0.0 {
            decision_count as f32 / loc * 100.0
        } else {
            0.0
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use coderabbit_shared::{ChangeType, FileChange};

    #[tokio::test]
    async fn batch_analysis_returns_same_count_as_input() {
        let analyzer = CodeAnalyzer::new();
        let files = vec![
            FileChange {
                path: "a.rs".into(),
                change_type: ChangeType::Modified,
                content: "fn main() {}".into(),
                diff: "".into(),
                language: "rust".into(),
            },
            FileChange {
                path: "b.ts".into(),
                change_type: ChangeType::Added,
                content: "export const x=1".into(),
                diff: "".into(),
                language: "typescript".into(),
            },
            FileChange {
                path: "c.py".into(),
                change_type: ChangeType::Deleted,
                content: "print('x')".into(),
                diff: "".into(),
                language: "python".into(),
            },
        ];
        let results = analyzer
            .analyze_file_batch(files.clone())
            .await
            .expect("analyze_file_batch");
        assert_eq!(results.len(), files.len());
    }
}
