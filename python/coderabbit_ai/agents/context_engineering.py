"""Context Engineering Agent for comprehensive context gathering."""

import dspy
import ast
import hashlib
import time
from typing import Dict, Any, List, Optional, Tuple
from ..models import ContextData, ContextEngineeringResponse, ContextEngineeringSignature
from collections import defaultdict, Counter
import re
import json


class ContextEngineeringAgent(dspy.Module):
    """Enhanced Agent for gathering and enriching context for code review."""
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__()
        self.config = config or {}
        self.context_generator = dspy.ChainOfThought(ContextEngineeringSignature)
        self.language_patterns = self._load_language_patterns()
        
    def forward(self, context_data: ContextData) -> ContextEngineeringResponse:
        """
        Process repository data and generate enriched context.

        Args:
            context_data: Input context data containing repo info, changes, and history

        Returns:
            ContextEngineeringResponse with enriched context and relationships
        """
        start_time = time.time()

        # Convert static analysis results to string format
        static_analysis_str = self._format_static_analysis(context_data.static_analysis_results)

        # Generate AST features for code relationships
        ast_features = self._extract_ast_features(context_data.code_changes)

        # Format RAG context if available
        rag_context_str = self._format_rag_context(context_data.rag_context)

        # Generate enriched context using DSPy
        result = self.context_generator(
            repo_structure=context_data.repo_structure,
            code_changes=context_data.code_changes,
            historical_data=context_data.historical_data,
            static_analysis_results=static_analysis_str,
            ast_features=ast_features,
            rag_context=rag_context_str
        )

        processing_time = int((time.time() - start_time) * 1000)

        return ContextEngineeringResponse(
            agent_id="context_engineering",
            confidence_score=self._calculate_confidence_score(context_data, result),
            processing_time_ms=processing_time,
            enriched_context=result.enriched_context,
            code_relationships=result.code_relationships,
            relevant_patterns=result.relevant_patterns,
            metadata={
                "risk_assessment": result.risk_assessment,
                "ast_complexity": len(ast_features),
                "static_analysis_tools": len(context_data.static_analysis_results),
                "historical_prs_analyzed": self._count_historical_prs(context_data.historical_data),
                "rag_enabled": context_data.rag_context is not None,
                "rag_patterns_found": len(context_data.rag_context.similar_patterns) if context_data.rag_context else 0,
                "rag_issues_found": len(context_data.rag_context.related_issues) if context_data.rag_context else 0,
                "rag_practices_found": len(context_data.rag_context.best_practices) if context_data.rag_context else 0
            }
        )
    
    def _format_static_analysis(self, results: List[Dict[str, Any]]) -> str:
        """Format static analysis results into a readable string."""
        if not results:
            return "No static analysis results available."

        formatted_results = []
        total_issues = 0

        for result in results:
            tool_name = result.get("tool", "Unknown")
            issues = result.get("issues", [])
            total_issues += len(issues)

            # Categorize issues by severity
            severity_counts = Counter()
            for issue in issues:
                severity = issue.get("severity", "unknown")
                severity_counts[severity] += 1

            # Format tool summary
            summary = f"{tool_name}: {len(issues)} issues"
            if severity_counts:
                severity_summary = ", ".join([f"{count} {sev}" for sev, count in severity_counts.items()])
                summary += f" ({severity_summary})"
            formatted_results.append(summary)

            # Show top 3 most critical issues
            critical_issues = [issue for issue in issues if issue.get("severity") == "critical"][:3]
            for issue in critical_issues:
                message = issue.get("message", "No message")[:100]
                file_path = issue.get("file", "unknown file")
                formatted_results.append(f"  CRITICAL: {message} in {file_path}")

        # Add summary header
        header = f"Static Analysis Summary: {total_issues} total issues across {len(results)} tools\n"
        return header + "\n".join(formatted_results)

    def _format_rag_context(self, rag_context) -> str:
        """Format RAG context data into a readable string for DSPy."""
        if not rag_context:
            return "No RAG context available."

        formatted_sections = []

        # Format similar code patterns
        if rag_context.similar_patterns:
            formatted_sections.append("=== Similar Code Patterns from Codebase ===")
            for i, pattern in enumerate(rag_context.similar_patterns[:5], 1):  # Top 5
                formatted_sections.append(
                    f"{i}. File: {pattern.file_path} (Similarity: {pattern.similarity_score:.2f})\n"
                    f"   Language: {pattern.language}\n"
                    f"   Snippet: {pattern.content_snippet[:200]}..."
                )

        # Format related issues
        if rag_context.related_issues:
            formatted_sections.append("\n=== Related Issues from History ===")
            for i, issue in enumerate(rag_context.related_issues[:3], 1):  # Top 3
                formatted_sections.append(
                    f"{i}. Issue: {issue.issue_id} - {issue.title} (Similarity: {issue.similarity_score:.2f})\n"
                    f"   Description: {issue.description[:150]}..."
                )

        # Format best practices
        if rag_context.best_practices:
            formatted_sections.append("\n=== Recommended Best Practices ===")
            for i, practice in enumerate(rag_context.best_practices[:3], 1):  # Top 3
                formatted_sections.append(
                    f"{i}. [{practice.category}] (Relevance: {practice.relevance_score:.2f})\n"
                    f"   {practice.description}"
                )

        # Summary
        summary = (
            f"RAG Context Summary: {len(rag_context.similar_patterns)} patterns, "
            f"{len(rag_context.related_issues)} issues, {len(rag_context.best_practices)} practices\n\n"
        )

        return summary + "\n".join(formatted_sections)

    def _extract_ast_features(self, code_changes: str) -> str:
        """Extract AST-based features from code changes."""
        features = []
        
        try:
            # Parse code changes to extract AST information
            lines = code_changes.split('\n')
            for line in lines[:50]:  # Limit to first 50 lines for efficiency
                if line.strip().startswith('+') or line.strip().startswith('-'):
                    code_content = line.strip()[1:].strip()
                    if code_content and len(code_content) > 10:
                        try:
                            tree = ast.parse(code_content)
                            features.append(f"AST Node: {type(tree.body[0]).__name__ if tree.body else 'Empty'}")
                            
                            # Extract function/method definitions
                            for node in ast.walk(tree):
                                if isinstance(node, ast.FunctionDef):
                                    features.append(f"Function: {node.name} ({len(node.args.args)} params)")
                                elif isinstance(node, ast.ClassDef):
                                    features.append(f"Class: {node.name} ({len(node.body)} methods)")
                                elif isinstance(node, ast.Import):
                                    features.append(f"Import: {node.names[0].name if node.names else 'unknown'}")
                                    
                        except SyntaxError:
                            # Skip syntax errors
                            continue
                            
        except Exception as e:
            features.append(f"AST parsing error: {str(e)}")
        
        return f"AST Analysis:\n" + "\n".join(features[:20])  # Limit output
    
    def _analyze_code_graph(self, file_changes: List[Dict[str, Any]]) -> str:
        """Analyze code relationships and dependencies."""
        relationships = []
        
        # Extract imports and dependencies
        imports = defaultdict(list)
        function_calls = defaultdict(set)
        
        for file_change in file_changes:
            file_path = file_change.get("path", "unknown")
            content = file_change.get("content", "")
            
            try:
                tree = ast.parse(content)
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            imports[file_path].append(alias.name)
                    elif isinstance(node, ast.ImportFrom):
                        module = node.module or ""
                        for alias in node.names:
                            imports[file_path].append(f"{module}.{alias.name}")
                    elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                        function_calls[file_path].add(node.func.id)
                        
            except SyntaxError:
                continue
        
        # Build relationship analysis
        relationships.append("Code Relationship Analysis:")
        relationships.append(f"Files analyzed: {len(file_changes)}")
        relationships.append(f"Dependencies found: {sum(len(deps) for deps in imports.values())}")
        
        # Find circular dependencies
        all_imports = set()
        for deps in imports.values():
            all_imports.update(deps)
        
        relationships.append(f"Unique modules: {len(all_imports)}")
        
        return "\n".join(relationships)
    
    def _extract_historical_patterns(self, historical_data: str) -> str:
        """Extract relevant patterns from historical data."""
        patterns = []
        
        # Extract PR patterns
        pr_pattern = r"PR #(\d+): ([^\n]+)"
        pr_matches = re.findall(pr_pattern, historical_data)
        
        if pr_matches:
            patterns.append(f"Historical PRs: {len(pr_matches)} patterns found")
            # Analyze common issue types
            common_issues = self._analyze_common_issues(pr_matches)
            patterns.append(f"Common issues: {common_issues}")
        
        # Extract recurring themes
        if "security" in historical_data.lower():
            patterns.append("Security patterns: Multiple security-related reviews detected")
        if "performance" in historical_data.lower():
            patterns.append("Performance patterns: Performance optimization requests found")
        if "refactor" in historical_data.lower():
            patterns.append("Refactoring patterns: Code quality improvement trends detected")
        
        return "\n".join(patterns) if patterns else "No historical patterns detected"
    
    def _analyze_common_issues(self, pr_matches: List[Tuple[str, str]]) -> str:
        """Analyze common issues from PR titles."""
        issues = []
        title_lower = [title.lower() for _, title in pr_matches]
        
        # Count common keywords
        keywords = ["bug", "fix", "performance", "security", "refactor", "test", "docs"]
        for keyword in keywords:
            count = sum(1 for title in title_lower if keyword in title)
            if count > 0:
                issues.append(f"{keyword}: {count} occurrences")
        
        return ", ".join(issues) if issues else "no common patterns"
    
    def _calculate_confidence_score(self, context_data: ContextData, result) -> float:
        """Calculate confidence score based on input quality and completeness."""
        score = 0.7  # Base score
        
        # Boost score based on available data
        if context_data.static_analysis_results:
            score += 0.1
        if len(context_data.static_analysis_results) > 5:
            score += 0.05
        if context_data.historical_data and len(context_data.historical_data) > 100:
            score += 0.1
        if context_data.repo_structure and len(context_data.repo_structure) > 200:
            score += 0.05
        
        # Ensure score stays within bounds
        return min(1.0, score)
    
    def _count_historical_prs(self, historical_data: str) -> int:
        """Count number of historical PRs in the data."""
        pr_pattern = r"PR #(\d+)"
        matches = re.findall(pr_pattern, historical_data)
        return len(matches)
    
    def _load_language_patterns(self) -> Dict[str, Dict[str, str]]:
        """Load language-specific patterns for analysis."""
        return {
            "python": {
                "test_patterns": ["def test_", "class Test", "assert", "pytest"],
                "security_patterns": ["eval(", "exec(", "os.system", "subprocess.call"],
                "performance_patterns": ["for i in range", "append(", "list("],
            },
            "rust": {
                "test_patterns": ["#[test]", "fn test_", "assert!"],
                "security_patterns": ["unwrap()", "expect()", "unsafe"],
                "performance_patterns": ["vec![", "String::new", ".clone()"],
            },
            "javascript": {
                "test_patterns": ["describe(", "it(", "expect(", "test("],
                "security_patterns": ["eval(", "innerHTML", "document.write"],
                "performance_patterns": ["for(", "forEach", "map("],
            }
        }
    
    def get_risk_assessment(self, context_data: ContextData) -> Dict[str, Any]:
        """Generate risk assessment for the code changes."""
        risk_factors = {
            "complexity": "medium",
            "security_risk": "low",
            "performance_risk": "low",
            "test_coverage": "unknown"
        }
        
        # Analyze code complexity
        if "complex" in context_data.code_changes.lower():
            risk_factors["complexity"] = "high"
        
        # Analyze security patterns
        security_keywords = ["eval", "exec", "sql", "command", "shell"]
        if any(keyword in context_data.code_changes.lower() for keyword in security_keywords):
            risk_factors["security_risk"] = "medium"
        
        # Analyze test coverage
        if "test" in context_data.code_changes.lower():
            risk_factors["test_coverage"] = "present"
        else:
            risk_factors["test_coverage"] = "missing"
        
        return risk_factors
    
    def extract_code_metrics(self, code_changes: str) -> Dict[str, int]:
        """Extract code metrics from changes."""
        metrics = {
            "lines_added": 0,
            "lines_deleted": 0,
            "files_changed": 0,
            "functions_defined": 0,
            "classes_defined": 0
        }
        
        lines = code_changes.split('\n')
        for line in lines:
            if line.strip().startswith('+'):
                metrics["lines_added"] += 1
            elif line.strip().startswith('-'):
                metrics["lines_deleted"] += 1
        
        # Count AST elements
        for line in lines[:100]:  # Limit for performance
            if line.strip().startswith('+') or line.strip().startswith('-'):
                code_content = line.strip()[1:].strip()
                try:
                    tree = ast.parse(code_content)
                    for node in ast.walk(tree):
                        if isinstance(node, ast.FunctionDef):
                            metrics["functions_defined"] += 1
                        elif isinstance(node, ast.ClassDef):
                            metrics["classes_defined"] += 1
                except:
                    pass
        
        return metrics
