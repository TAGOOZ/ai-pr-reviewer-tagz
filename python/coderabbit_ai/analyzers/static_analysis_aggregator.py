"""Static analysis aggregator - orchestrates all static analysis tools."""

import logging
from typing import List, Dict, Any, Optional
from pathlib import Path

from .astgrep_scanner import AstGrepScanner
from ..models import SecurityFinding, SecuritySummary
from .. import config

logger = logging.getLogger(__name__)


class StaticAnalysisAggregator:
    """
    Aggregates results from multiple static analysis tools.

    Features:
    - Runs traditional linters (flake8, eslint, pylint, etc.)
    - Runs security scanners (ast-grep)
    - Consolidates results into structured format
    - Handles errors gracefully
    """

    def __init__(
        self,
        enable_astgrep: bool = None,
        enable_linters: bool = True
    ):
        """
        Initialize static analysis aggregator.

        Args:
            enable_astgrep: Enable ast-grep scanning (defaults to config.ASTGREP_ENABLED)
            enable_linters: Enable traditional linters
        """
        self.enable_astgrep = enable_astgrep if enable_astgrep is not None else config.ASTGREP_ENABLED
        self.enable_linters = enable_linters

        # Initialize ast-grep scanner
        self.astgrep_scanner = None
        if self.enable_astgrep:
            try:
                self.astgrep_scanner = AstGrepScanner(
                    rules_repo=config.ASTGREP_RULES_REPO,
                    rules_path=config.ASTGREP_RULES_PATH,
                    cache_ttl=config.ASTGREP_CACHE_TTL,
                    auto_update=config.ASTGREP_AUTO_UPDATE,
                    use_sandbox=config.get_env_bool("ASTGREP_USE_SANDBOX", False)
                )
                logger.info("AST-Grep scanner initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize ast-grep scanner: {e}")
                self.astgrep_scanner = None

    def analyze(
        self,
        changed_files: List[str],
        project_root: str,
        language: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Run all static analysis tools on changed files.

        Args:
            changed_files: List of changed file paths (relative to project_root)
            project_root: Root directory of the project
            language: Optional language filter

        Returns:
            Dictionary containing all analysis results:
            {
                "linter_results": [...],  # Traditional linter output
                "security_findings": [...],  # SecurityFinding objects
                "security_summary": {...},  # SecuritySummary object
                "stats": {...}
            }
        """
        logger.info(f"Running static analysis on {len(changed_files)} files")

        # Results containers
        linter_results = []
        security_findings = []
        stats = {
            "files_analyzed": len(changed_files),
            "tools_run": [],
            "total_issues": 0,
            "scan_time_ms": 0
        }

        # Run traditional linters
        if self.enable_linters:
            try:
                linter_results = self._run_linters(changed_files, project_root)
                stats["tools_run"].extend([r["tool"] for r in linter_results])
                stats["total_issues"] += sum(
                    len(r.get("issues", [])) for r in linter_results
                )
            except Exception as e:
                logger.error(f"Linter execution failed: {e}", exc_info=True)

        # Run ast-grep security scanner
        if self.enable_astgrep and self.astgrep_scanner:
            try:
                astgrep_result = self._run_astgrep(
                    changed_files,
                    project_root,
                    language
                )

                if astgrep_result:
                    # Extract security findings
                    for finding_dict in astgrep_result.get("findings", []):
                        try:
                            finding = SecurityFinding(**finding_dict)
                            security_findings.append(finding)
                        except Exception as e:
                            logger.warning(f"Failed to parse security finding: {e}")

                    # Update stats
                    stats["tools_run"].append("ast-grep")
                    stats["total_issues"] += len(security_findings)
                    stats["scan_time_ms"] += astgrep_result.get("stats", {}).get("scan_time_ms", 0)

            except Exception as e:
                logger.error(f"AST-Grep execution failed: {e}", exc_info=True)

        # Generate security summary
        security_summary = self._generate_security_summary(security_findings)

        return {
            "linter_results": linter_results,
            "security_findings": [f.dict() for f in security_findings],
            "security_summary": security_summary.dict(),
            "stats": stats
        }

    def _run_linters(
        self,
        changed_files: List[str],
        project_root: str
    ) -> List[Dict[str, Any]]:
        """
        Run traditional linters (flake8, eslint, etc.).

        Args:
            changed_files: Files to analyze
            project_root: Project root directory

        Returns:
            List of linter results in standard format
        """
        results = []

        # Group files by language
        python_files = [f for f in changed_files if f.endswith('.py')]
        js_ts_files = [f for f in changed_files if f.endswith(('.js', '.jsx', '.ts', '.tsx'))]

        # Run Python linters
        if python_files:
            # Flake8
            flake8_result = self._run_flake8(python_files, project_root)
            if flake8_result:
                results.append(flake8_result)

            # Pylint (optional, can be slow)
            # pylint_result = self._run_pylint(python_files, project_root)
            # if pylint_result:
            #     results.append(pylint_result)

        # Run JavaScript/TypeScript linters
        if js_ts_files:
            eslint_result = self._run_eslint(js_ts_files, project_root)
            if eslint_result:
                results.append(eslint_result)

        return results

    def _run_flake8(
        self,
        files: List[str],
        project_root: str
    ) -> Optional[Dict[str, Any]]:
        """Run flake8 on Python files."""
        try:
            import subprocess

            # Build command
            cmd = ["flake8", "--format=json"] + files

            result = subprocess.run(
                cmd,
                cwd=project_root,
                capture_output=True,
                text=True,
                timeout=config.STATIC_ANALYZER_TIMEOUT
            )

            # Parse output
            issues = []
            if result.stdout:
                try:
                    import json
                    flake8_output = json.loads(result.stdout)

                    for file_path, file_issues in flake8_output.items():
                        for issue in file_issues:
                            issues.append({
                                "file": file_path,
                                "line": issue.get("line_number"),
                                "column": issue.get("column_number"),
                                "severity": "warning" if issue.get("code", "").startswith("W") else "error",
                                "message": issue.get("text"),
                                "code": issue.get("code")
                            })
                except json.JSONDecodeError:
                    # Fallback: parse line-by-line format
                    logger.warning("Failed to parse flake8 JSON output")

            return {
                "tool": "flake8",
                "issues": issues
            }

        except subprocess.TimeoutExpired:
            logger.warning("Flake8 timed out")
            return None
        except FileNotFoundError:
            logger.debug("Flake8 not installed, skipping")
            return None
        except Exception as e:
            logger.warning(f"Flake8 execution failed: {e}")
            return None

    def _run_eslint(
        self,
        files: List[str],
        project_root: str
    ) -> Optional[Dict[str, Any]]:
        """Run ESLint on JavaScript/TypeScript files."""
        try:
            import subprocess

            # Build command
            cmd = ["eslint", "--format=json"] + files

            result = subprocess.run(
                cmd,
                cwd=project_root,
                capture_output=True,
                text=True,
                timeout=config.STATIC_ANALYZER_TIMEOUT
            )

            # Parse output
            issues = []
            if result.stdout:
                try:
                    import json
                    eslint_output = json.loads(result.stdout)

                    for file_result in eslint_output:
                        file_path = file_result.get("filePath", "")
                        # Make path relative
                        if file_path.startswith(project_root):
                            file_path = file_path[len(project_root):].lstrip("/")

                        for message in file_result.get("messages", []):
                            issues.append({
                                "file": file_path,
                                "line": message.get("line"),
                                "column": message.get("column"),
                                "severity": message.get("severity", 1),  # 1=warning, 2=error
                                "message": message.get("message"),
                                "rule": message.get("ruleId")
                            })
                except json.JSONDecodeError:
                    logger.warning("Failed to parse ESLint JSON output")

            return {
                "tool": "eslint",
                "issues": issues
            }

        except subprocess.TimeoutExpired:
            logger.warning("ESLint timed out")
            return None
        except FileNotFoundError:
            logger.debug("ESLint not installed, skipping")
            return None
        except Exception as e:
            logger.warning(f"ESLint execution failed: {e}")
            return None

    def _run_astgrep(
        self,
        changed_files: List[str],
        project_root: str,
        language: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Run ast-grep scanner.

        Args:
            changed_files: Files to scan
            project_root: Project root directory
            language: Optional language filter

        Returns:
            AST-Grep scan results
        """
        if not self.astgrep_scanner:
            logger.debug("AST-Grep scanner not available")
            return None

        try:
            return self.astgrep_scanner.scan(
                changed_files=changed_files,
                project_root=project_root,
                language=language
            )
        except Exception as e:
            logger.error(f"AST-Grep scan failed: {e}", exc_info=True)
            return None

    def _generate_security_summary(
        self,
        findings: List[SecurityFinding]
    ) -> SecuritySummary:
        """
        Generate security summary from findings.

        Args:
            findings: List of SecurityFinding objects

        Returns:
            SecuritySummary object
        """
        if not findings:
            return SecuritySummary()

        by_severity = {}
        by_category = {}
        critical_files = set()
        tools_used = set()

        for finding in findings:
            # Count by severity
            by_severity[finding.severity] = by_severity.get(finding.severity, 0) + 1

            # Count by category
            by_category[finding.category] = by_category.get(finding.category, 0) + 1

            # Track critical files
            if finding.severity in ["critical", "high"]:
                critical_files.add(finding.file)

            # Track tools
            tools_used.add(finding.tool)

        return SecuritySummary(
            total_findings=len(findings),
            by_severity=by_severity,
            by_category=by_category,
            critical_files=list(critical_files),
            tools_used=list(tools_used)
        )

    def check_tools_installed(self) -> Dict[str, bool]:
        """
        Check which static analysis tools are installed.

        Returns:
            Dictionary mapping tool name to installation status
        """
        tools_status = {}

        # Check ast-grep
        if self.astgrep_scanner:
            tools_status["ast-grep"] = self.astgrep_scanner.check_installation()
        else:
            tools_status["ast-grep"] = False

        # Check flake8
        try:
            import subprocess
            result = subprocess.run(
                ["flake8", "--version"],
                capture_output=True,
                timeout=5
            )
            tools_status["flake8"] = result.returncode == 0
        except Exception:
            tools_status["flake8"] = False

        # Check eslint
        try:
            import subprocess
            result = subprocess.run(
                ["eslint", "--version"],
                capture_output=True,
                timeout=5
            )
            tools_status["eslint"] = result.returncode == 0
        except Exception:
            tools_status["eslint"] = False

        return tools_status
