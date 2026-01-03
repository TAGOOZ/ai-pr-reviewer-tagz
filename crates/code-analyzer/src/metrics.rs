use crate::analyzer::CodeMetrics;

pub struct MetricsCalculator;

impl MetricsCalculator {
    pub fn calculate_metrics(content: &str, language: &str) -> CodeMetrics {
        let lines_of_code = Self::count_lines_of_code(content);
        let cyclomatic_complexity = Self::calculate_complexity(content, language);
        let maintainability_index =
            Self::calculate_maintainability_index(lines_of_code, cyclomatic_complexity);
        let technical_debt_minutes =
            Self::estimate_technical_debt(lines_of_code, cyclomatic_complexity);

        CodeMetrics {
            lines_of_code,
            cyclomatic_complexity,
            maintainability_index,
            technical_debt_minutes,
        }
    }

    fn count_lines_of_code(content: &str) -> u32 {
        content
            .lines()
            .filter(|line| !line.trim().is_empty() && !line.trim().starts_with("//"))
            .count() as u32
    }

    fn calculate_complexity(content: &str, language: &str) -> u32 {
        // Simplified complexity calculation based on control flow keywords
        let keywords = match language {
            "rust" => vec!["if", "else", "match", "for", "while", "loop"],
            "javascript" | "typescript" => vec!["if", "else", "switch", "for", "while", "do"],
            "python" => vec!["if", "elif", "else", "for", "while", "try", "except"],
            "java" => vec!["if", "else", "switch", "for", "while", "do", "try", "catch"],
            "go" => vec!["if", "else", "switch", "for", "select"],
            _ => vec!["if", "else", "for", "while"],
        };

        let mut complexity = 1; // Base complexity
        for keyword in keywords {
            complexity += content.matches(keyword).count() as u32;
        }

        complexity
    }

    fn calculate_maintainability_index(loc: u32, complexity: u32) -> f32 {
        // Simplified maintainability index calculation
        let halstead_volume = (loc as f32) * 2.0; // Simplified Halstead volume
        let mi = 171.0
            - 5.2 * (halstead_volume.ln())
            - 0.23 * (complexity as f32)
            - 16.2 * ((loc as f32).ln());
        mi.max(0.0).min(100.0)
    }

    fn estimate_technical_debt(loc: u32, complexity: u32) -> u32 {
        // Simplified technical debt estimation in minutes
        let base_debt = loc / 10; // 1 minute per 10 lines
        let complexity_debt = complexity * 2; // 2 minutes per complexity point
        base_debt + complexity_debt
    }
}
