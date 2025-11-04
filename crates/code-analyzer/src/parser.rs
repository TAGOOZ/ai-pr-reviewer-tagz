use tree_sitter::{Language, Parser, Tree};
use coderabbit_shared::{Result, CodeRabbitError};

pub struct LanguageParser {
    parser: Parser,
}

impl LanguageParser {
    pub fn new() -> Result<Self> {
        let parser = Parser::new();
        Ok(Self { parser })
    }

    pub fn parse(&mut self, language: &str, source_code: &str) -> Result<Tree> {
        let language = self.get_language(language)?;
        self.parser.set_language(language)
            .map_err(|e| CodeRabbitError::AnalysisError(format!("Failed to set language: {}", e)))?;

        self.parser.parse(source_code, None)
            .ok_or_else(|| CodeRabbitError::AnalysisError("Failed to parse source code".to_string()))
    }

    fn get_language(&self, language: &str) -> Result<Language> {
        match language.to_lowercase().as_str() {
            "rust" => Ok(tree_sitter_rust::language()),
            "typescript" | "javascript" => Ok(tree_sitter_typescript::language_typescript()),
            "python" => Ok(tree_sitter_python::language()),
            "java" => Ok(tree_sitter_java::language()),
            "go" => Ok(tree_sitter_go::language()),
            _ => Err(CodeRabbitError::AnalysisError(format!("Unsupported language: {}", language))),
        }
    }
}