"""Context Engineering Agent for comprehensive context gathering."""

import dspy
import hashlib
import time
import logging
from typing import Dict, Any, List, Optional, Tuple
from ..models import ContextData, ContextEngineeringResponse, ContextEngineeringSignature
from collections import defaultdict, Counter
import re
import json

# Import new integration components
from ..integrations.hybrid_context_provider import HybridContextProvider
from ..integrations.context_adapter import ContextAdapter

logger = logging.getLogger(__name__)


class ContextEngineeringAgent(dspy.Module):
    """Enhanced Agent for gathering and enriching context for code review."""

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__()
        self.config = config or {}
        self.context_generator = dspy.ChainOfThought(ContextEngineeringSignature)
        self.language_patterns = self._load_language_patterns()

        # New: Hybrid context provider for multi-layer analysis
        self.hybrid_provider = None  # Initialized on-demand per repository
        
    def forward(self, context_data: ContextData) -> ContextEngineeringResponse:
        """
        Process repository data and generate enriched context.

        Args:
            context_data: Input context data containing repo info, changes, and history

        Returns:
            ContextEngineeringResponse with enriched context and relationships
        """
        start_time = time.time()

        # NEW: Enrich with hybrid context (Graph + DeepWiki) if available
        hybrid_context_str = ""
        if context_data.project_root:
            try:
                hybrid_context_str = self._enrich_with_hybrid_context(context_data)
                logger.info("Successfully enriched context with graph and DeepWiki analysis")
            except Exception as e:
                logger.warning(f"Failed to enrich with hybrid context: {e}")
                hybrid_context_str = ""

        # NEW: Format security findings from ast-grep and other scanners
        security_context_str = ""
        if context_data.security_findings:
            try:
                security_context_str = self._format_security_findings(context_data.security_findings)
                logger.info(f"Formatted {len(context_data.security_findings)} security findings")
            except Exception as e:
                logger.warning(f"Failed to format security findings: {e}")
                security_context_str = ""

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

        # Calculate enhanced confidence score
        confidence = self._calculate_confidence_score(context_data, result)

        # Merge hybrid context and security context into enriched_context
        enriched_context = result.enriched_context
        if hybrid_context_str:
            enriched_context = f"{hybrid_context_str}\n\n{enriched_context}"
        if security_context_str:
            enriched_context = f"{security_context_str}\n\n{enriched_context}"

        return ContextEngineeringResponse(
            agent_id="context_engineering",
            confidence_score=confidence,
            processing_time_ms=processing_time,
            enriched_context=enriched_context,
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
                "rag_practices_found": len(context_data.rag_context.best_practices) if context_data.rag_context else 0,
                # Hybrid context metadata
                "hybrid_context_enabled": context_data.hybrid_context is not None,
                "context_sources": context_data.hybrid_context.context_sources if context_data.hybrid_context else [],
                "graph_risk_level": context_data.hybrid_context.graph_context.risk_level if context_data.hybrid_context else "UNKNOWN",
                "deepwiki_available": context_data.hybrid_context.deepwiki_context.available if context_data.hybrid_context and context_data.hybrid_context.deepwiki_context else False,
                # NEW: Security findings metadata
                "security_findings_count": len(context_data.security_findings),
                "critical_security_issues": sum(1 for f in context_data.security_findings if f.severity == "critical"),
                "high_security_issues": sum(1 for f in context_data.security_findings if f.severity == "high"),
                "security_tools_used": list(set(f.tool for f in context_data.security_findings)) if context_data.security_findings else []
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

    def _format_security_findings(self, findings: List) -> str:
        """
        Format security findings from ast-grep and other security scanners.

        Args:
            findings: List of SecurityFinding objects

        Returns:
            Formatted string for LLM consumption
        """
        if not findings:
            return ""

        # Import here to avoid circular dependency
        from ..models import SecurityFinding

        # Convert dicts to SecurityFinding objects if needed
        finding_objects = []
        for f in findings:
            if isinstance(f, dict):
                try:
                    finding_objects.append(SecurityFinding(**f))
                except Exception:
                    continue
            else:
                finding_objects.append(f)

        if not finding_objects:
            return ""

        formatted_sections = []
        formatted_sections.append("=" * 80)
        formatted_sections.append("🔒 SECURITY ANALYSIS")
        formatted_sections.append("=" * 80)

        # Group by severity
        by_severity = defaultdict(list)
        for finding in finding_objects:
            by_severity[finding.severity].append(finding)

        # Count statistics
        total = len(finding_objects)
        critical_count = len(by_severity.get("critical", []))
        high_count = len(by_severity.get("high", []))
        medium_count = len(by_severity.get("medium", []))
        low_count = len(by_severity.get("low", []))

        # Summary
        formatted_sections.append(f"\n📊 SUMMARY: {total} security findings detected")
        formatted_sections.append(f"   • CRITICAL: {critical_count}")
        formatted_sections.append(f"   • HIGH: {high_count}")
        formatted_sections.append(f"   • MEDIUM: {medium_count}")
        formatted_sections.append(f"   • LOW: {low_count}")

        # Format findings by severity (highest first)
        for severity in ["critical", "high", "medium", "low"]:
            items = by_severity.get(severity, [])
            if not items:
                continue

            formatted_sections.append(f"\n{'─' * 80}")
            formatted_sections.append(f"{severity.upper()} SEVERITY ({len(items)} findings)")
            formatted_sections.append('─' * 80)

            # Show top 10 per severity
            for i, finding in enumerate(items[:10], 1):
                formatted_sections.append(f"\n{i}. [{finding.tool}] {finding.rule_id}")
                formatted_sections.append(f"   📄 File: {finding.file}:{finding.line}")
                formatted_sections.append(f"   ⚠️  Issue: {finding.message}")

                if finding.code_snippet:
                    snippet = finding.code_snippet[:200]
                    formatted_sections.append(f"   💻 Code: {snippet}")

                if finding.suggestion:
                    formatted_sections.append(f"   💡 Fix: {finding.suggestion}")

                if finding.cwe_id:
                    formatted_sections.append(f"   🔗 {finding.cwe_id}")

                if finding.confidence < 1.0:
                    formatted_sections.append(f"   📈 Confidence: {finding.confidence:.0%}")

            if len(items) > 10:
                formatted_sections.append(f"\n   ... and {len(items) - 10} more {severity} issues")

        # Critical files section
        critical_files = set()
        for finding in finding_objects:
            if finding.severity in ["critical", "high"]:
                critical_files.add(finding.file)

        if critical_files:
            formatted_sections.append(f"\n{'─' * 80}")
            formatted_sections.append(f"🚨 CRITICAL FILES ({len(critical_files)} files with high-risk issues)")
            formatted_sections.append('─' * 80)
            for file in sorted(critical_files)[:20]:  # Top 20
                file_findings = [f for f in finding_objects if f.file == file and f.severity in ["critical", "high"]]
                formatted_sections.append(f"   • {file} ({len(file_findings)} issues)")

        # Recommendations
        formatted_sections.append(f"\n{'─' * 80}")
        formatted_sections.append("📋 RECOMMENDATIONS")
        formatted_sections.append('─' * 80)

        if critical_count > 0:
            formatted_sections.append("   ❌ BLOCK MERGE: Critical security vulnerabilities must be fixed before merging")
        elif high_count >= 3:
            formatted_sections.append("   ⚠️  CAUTION: Multiple high-severity issues found - review and fix recommended")
        elif high_count > 0:
            formatted_sections.append("   ⚠️  WARNING: High-severity issues detected - consider fixing before merge")
        else:
            formatted_sections.append("   ✅ No critical security issues detected")

        formatted_sections.append("\n" + "=" * 80)

        return "\n".join(formatted_sections)

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

        # NEW: Boost score based on hybrid context availability
        if context_data.hybrid_context:
            # Base boost for having graph context
            score += 0.05

            # Additional boost if DeepWiki is available
            if (context_data.hybrid_context.deepwiki_context and
                context_data.hybrid_context.deepwiki_context.available):
                score += 0.10

                # Extra boost for rich DeepWiki content
                if context_data.hybrid_context.deepwiki_context.architectural_overview:
                    score += 0.03
                if context_data.hybrid_context.deepwiki_context.patterns_and_conventions:
                    score += 0.02

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

    def _enrich_with_hybrid_context(self, context_data: ContextData) -> str:
        """
        Enrich context with graph-based and DeepWiki analysis.

        Args:
            context_data: Context data with project_root and optional repository_name

        Returns:
            Formatted hybrid context string for LLM
        """
        # Extract changed files from code_changes
        changed_files = self._extract_changed_files(context_data.code_changes)

        if not changed_files:
            logger.warning("No changed files detected, skipping hybrid context")
            return ""

        # Initialize or reuse hybrid provider
        if not self.hybrid_provider or self.hybrid_provider.project_root != context_data.project_root:
            from .. import config

            self.hybrid_provider = HybridContextProvider(
                project_root=context_data.project_root,
                repo_name=context_data.repository_name,
                enable_deepwiki=config.DEEPWIKI_ENABLED,
                cache_ttl=config.GRAPH_CACHE_TTL
            )
            logger.info(
                f"Initialized HybridContextProvider for {context_data.project_root}"
            )

        # Get hybrid context
        hybrid_context = self.hybrid_provider.enrich_pr_context(
            changed_files=changed_files
        )

        # Convert to Pydantic model and store in context_data
        hybrid_context_data = ContextAdapter.hybrid_to_hybrid_context_data(
            hybrid_context
        )
        context_data.hybrid_context = hybrid_context_data

        # Format for LLM
        formatted = ContextAdapter.format_hybrid_context_for_llm(hybrid_context_data)

        logger.info(
            f"Hybrid context enriched - Sources: {hybrid_context.get_context_sources()}, "
            f"Risk: {hybrid_context_data.graph_context.risk_level}"
        )

        return formatted

    def _extract_changed_files(self, code_changes: str) -> List[str]:
        """
        Extract list of changed files from code_changes string.

        Args:
            code_changes: Diff or code changes string

        Returns:
            List of file paths
        """
        changed_files = []

        # Try to parse diff format
        lines = code_changes.split('\n')
        for line in lines:
            # Match diff headers: +++ b/path/to/file or --- a/path/to/file
            if line.startswith('+++') or line.startswith('---'):
                # Extract file path
                parts = line.split(maxsplit=1)
                if len(parts) > 1:
                    file_path = parts[1]
                    # Remove a/ or b/ prefix
                    if file_path.startswith(('a/', 'b/')):
                        file_path = file_path[2:]
                    if file_path and file_path != '/dev/null':
                        changed_files.append(file_path)

            # Also try File: format
            elif line.startswith('File:'):
                file_path = line.replace('File:', '').strip()
                if file_path:
                    changed_files.append(file_path)

        # Remove duplicates while preserving order
        seen = set()
        unique_files = []
        for f in changed_files:
            if f not in seen:
                seen.add(f)
                unique_files.append(f)

        return unique_files
