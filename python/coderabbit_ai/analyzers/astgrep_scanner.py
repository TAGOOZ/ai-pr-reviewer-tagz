"""AST-Grep security scanner with local rule caching."""

import json
import logging
import subprocess
import os
import time
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

from ..models import SecurityFinding, SecuritySummary
from .. import config

logger = logging.getLogger(__name__)


class AstGrepScanner:
    """
    AST-Grep scanner for structural code pattern analysis.

    Features:
    - Local rule caching (clones ast-grep-essentials repository)
    - Automatic rule updates (checks daily)
    - Incremental scanning (only changed files)
    - Structured output parsing
    """

    def __init__(
        self,
        rules_repo: str = "coderabbitai/ast-grep-essentials",
        rules_path: Optional[str] = None,
        cache_ttl: int = 86400,  # 24 hours in seconds
        auto_update: bool = True
    ):
        """
        Initialize AST-Grep scanner.

        Args:
            rules_repo: GitHub repository containing ast-grep rules (format: "owner/repo")
            rules_path: Local path to cache rules (defaults to config.ASTGREP_RULES_PATH)
            cache_ttl: Cache TTL in seconds (default: 24 hours)
            auto_update: Automatically update rules if cache is stale
        """
        self.rules_repo = rules_repo
        self.rules_path = Path(rules_path or config.ASTGREP_RULES_PATH)
        self.cache_ttl = cache_ttl
        self.auto_update = auto_update

        # Ensure rules are available
        self._ensure_rules_available()

    def _ensure_rules_available(self) -> None:
        """Ensure ast-grep rules are available locally."""
        if not self.rules_path.exists():
            logger.info(f"Rules not found at {self.rules_path}, cloning repository...")
            self._clone_rules_repo()
        elif self.auto_update and self._is_cache_stale():
            logger.info("Rules cache is stale, updating...")
            self._update_rules_repo()
        else:
            logger.debug(f"Using cached rules from {self.rules_path}")

    def _clone_rules_repo(self) -> None:
        """Clone ast-grep-essentials repository."""
        try:
            # Create parent directory
            self.rules_path.parent.mkdir(parents=True, exist_ok=True)

            # Clone repository
            repo_url = f"https://github.com/{self.rules_repo}.git"
            cmd = ["git", "clone", "--depth", "1", repo_url, str(self.rules_path)]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5 minutes timeout
            )

            if result.returncode != 0:
                raise RuntimeError(f"Failed to clone rules repository: {result.stderr}")

            logger.info(f"Successfully cloned rules from {repo_url}")

            # Write timestamp file
            self._write_cache_timestamp()

        except subprocess.TimeoutExpired:
            raise RuntimeError("Timeout while cloning rules repository")
        except Exception as e:
            logger.error(f"Failed to clone rules repository: {e}")
            raise

    def _update_rules_repo(self) -> None:
        """Update ast-grep-essentials repository (git pull)."""
        try:
            cmd = ["git", "-C", str(self.rules_path), "pull", "--rebase"]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60  # 1 minute timeout
            )

            if result.returncode != 0:
                logger.warning(f"Failed to update rules repository: {result.stderr}")
                logger.info("Continuing with cached rules")
            else:
                logger.info("Successfully updated rules repository")
                self._write_cache_timestamp()

        except subprocess.TimeoutExpired:
            logger.warning("Timeout while updating rules repository, using cached version")
        except Exception as e:
            logger.warning(f"Failed to update rules repository: {e}, using cached version")

    def _is_cache_stale(self) -> bool:
        """Check if rules cache is stale based on TTL."""
        timestamp_file = self.rules_path / ".cache_timestamp"

        if not timestamp_file.exists():
            return True

        try:
            with open(timestamp_file, "r") as f:
                timestamp_str = f.read().strip()
                cache_time = datetime.fromisoformat(timestamp_str)
                age = datetime.now() - cache_time
                return age.total_seconds() > self.cache_ttl
        except Exception as e:
            logger.warning(f"Failed to read cache timestamp: {e}")
            return True

    def _write_cache_timestamp(self) -> None:
        """Write current timestamp to cache file."""
        timestamp_file = self.rules_path / ".cache_timestamp"
        try:
            with open(timestamp_file, "w") as f:
                f.write(datetime.now().isoformat())
        except Exception as e:
            logger.warning(f"Failed to write cache timestamp: {e}")

    def _find_rule_files(self, language: Optional[str] = None) -> List[Path]:
        """
        Find ast-grep rule files.

        Args:
            language: Optional language filter (e.g., "python", "javascript", "go")

        Returns:
            List of rule file paths
        """
        rule_files = []

        # ast-grep-essentials structure: rules/<language>/*.yml
        rules_dir = self.rules_path / "rules"

        if not rules_dir.exists():
            logger.warning(f"Rules directory not found: {rules_dir}")
            return []

        if language:
            # Search specific language directory
            lang_dir = rules_dir / language
            if lang_dir.exists():
                rule_files.extend(lang_dir.glob("*.yml"))
                rule_files.extend(lang_dir.glob("*.yaml"))
        else:
            # Search all language directories
            for lang_dir in rules_dir.iterdir():
                if lang_dir.is_dir():
                    rule_files.extend(lang_dir.glob("*.yml"))
                    rule_files.extend(lang_dir.glob("*.yaml"))

        return rule_files

    def scan(
        self,
        changed_files: List[str],
        project_root: str,
        language: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Scan changed files with ast-grep.

        Args:
            changed_files: List of file paths to scan (relative to project_root)
            project_root: Root directory of the project
            language: Optional language filter

        Returns:
            Dictionary containing findings and statistics
        """
        start_time = time.time()

        try:
            # Find applicable rule files
            rule_files = self._find_rule_files(language)

            if not rule_files:
                logger.warning("No ast-grep rules found")
                return self._empty_result()

            logger.info(f"Found {len(rule_files)} ast-grep rule files")

            # Run ast-grep for each file
            all_findings = []
            for file_path in changed_files:
                full_path = Path(project_root) / file_path

                if not full_path.exists() or not full_path.is_file():
                    continue

                # Determine file language
                file_lang = self._detect_language(file_path)
                if language and file_lang != language:
                    continue

                # Run ast-grep on this file
                findings = self._scan_file(full_path, project_root, rule_files)
                all_findings.extend(findings)

            # Generate summary
            summary = self._generate_summary(all_findings)

            elapsed_time = int((time.time() - start_time) * 1000)

            return {
                "tool": "ast-grep",
                "findings": [f.dict() for f in all_findings],
                "summary": summary.dict(),
                "stats": {
                    "files_scanned": len(changed_files),
                    "rules_applied": len(rule_files),
                    "scan_time_ms": elapsed_time
                }
            }

        except Exception as e:
            logger.error(f"AST-Grep scan failed: {e}", exc_info=True)
            return self._empty_result()

    def _scan_file(
        self,
        file_path: Path,
        project_root: str,
        rule_files: List[Path]
    ) -> List[SecurityFinding]:
        """
        Scan a single file with ast-grep.

        Args:
            file_path: Absolute path to file
            project_root: Project root directory
            rule_files: List of rule file paths

        Returns:
            List of SecurityFinding objects
        """
        findings = []

        for rule_file in rule_files:
            try:
                # Run ast-grep command
                # ast-grep --json --rule-file <rule> <file>
                cmd = [
                    "ast-grep",
                    "scan",
                    "--json",
                    "--config", str(rule_file),
                    str(file_path)
                ]

                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=30,  # 30 seconds per file
                    cwd=project_root
                )

                if result.returncode == 0 and result.stdout:
                    # Parse JSON output
                    matches = json.loads(result.stdout)
                    findings.extend(self._parse_astgrep_output(
                        matches,
                        file_path,
                        project_root,
                        rule_file
                    ))

            except subprocess.TimeoutExpired:
                logger.warning(f"Timeout scanning {file_path} with {rule_file.name}")
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse ast-grep output: {e}")
            except Exception as e:
                logger.warning(f"Error scanning {file_path} with {rule_file.name}: {e}")

        return findings

    def _parse_astgrep_output(
        self,
        matches: List[Dict[str, Any]],
        file_path: Path,
        project_root: str,
        rule_file: Path
    ) -> List[SecurityFinding]:
        """
        Parse ast-grep JSON output into SecurityFinding objects.

        Args:
            matches: List of matches from ast-grep
            file_path: File that was scanned
            project_root: Project root directory
            rule_file: Rule file used

        Returns:
            List of SecurityFinding objects
        """
        findings = []

        # Get relative file path
        try:
            rel_path = str(file_path.relative_to(project_root))
        except ValueError:
            rel_path = str(file_path)

        for match in matches:
            try:
                # Extract rule metadata
                rule_id = self._extract_rule_id(rule_file)
                severity = self._extract_severity(match, rule_file)
                category = self._extract_category(rule_file)

                # Create SecurityFinding
                finding = SecurityFinding(
                    tool="ast-grep",
                    rule_id=rule_id,
                    severity=severity,
                    category=category,
                    file=rel_path,
                    line=match.get("range", {}).get("start", {}).get("line", 0),
                    column=match.get("range", {}).get("start", {}).get("column"),
                    message=match.get("message", f"Pattern matched: {rule_id}"),
                    code_snippet=match.get("text"),
                    suggestion=match.get("fix"),
                    cwe_id=self._extract_cwe(match, rule_file),
                    confidence=0.9,  # ast-grep has high precision
                    references=self._extract_references(match, rule_file)
                )

                findings.append(finding)

            except Exception as e:
                logger.warning(f"Failed to parse ast-grep match: {e}")

        return findings

    def _extract_rule_id(self, rule_file: Path) -> str:
        """Extract rule ID from rule file path."""
        # Example: rules/python/security/sql-injection.yml -> python/security/sql-injection
        try:
            parts = rule_file.relative_to(self.rules_path / "rules").with_suffix("").parts
            return "/".join(parts)
        except Exception:
            return rule_file.stem

    def _extract_severity(self, match: Dict[str, Any], rule_file: Path) -> str:
        """Extract severity from match or rule file."""
        # Check match metadata
        if "severity" in match:
            return match["severity"].lower()

        # Infer from rule path
        rule_path = str(rule_file).lower()
        if "critical" in rule_path:
            return "critical"
        elif "high" in rule_path or "security" in rule_path:
            return "high"
        elif "medium" in rule_path:
            return "medium"
        else:
            return "low"

    def _extract_category(self, rule_file: Path) -> str:
        """Extract category from rule file path."""
        rule_path = str(rule_file).lower()

        if "security" in rule_path:
            return "security"
        elif "performance" in rule_path:
            return "performance"
        elif "best-practice" in rule_path or "practice" in rule_path:
            return "best-practice"
        else:
            return "code-quality"

    def _extract_cwe(self, match: Dict[str, Any], rule_file: Path) -> Optional[str]:
        """Extract CWE ID from match or rule metadata."""
        # Check match metadata
        if "cwe" in match:
            cwe = match["cwe"]
            if isinstance(cwe, str) and not cwe.startswith("CWE-"):
                return f"CWE-{cwe}"
            return cwe

        # Try to read from rule file
        try:
            with open(rule_file, "r") as f:
                content = f.read()
                # Look for CWE reference in comments or metadata
                if "CWE-" in content:
                    import re
                    cwe_match = re.search(r"CWE-(\d+)", content)
                    if cwe_match:
                        return f"CWE-{cwe_match.group(1)}"
        except Exception:
            pass

        return None

    def _extract_references(self, match: Dict[str, Any], rule_file: Path) -> List[str]:
        """Extract reference URLs from match or rule metadata."""
        refs = []

        # Check match metadata
        if "references" in match:
            refs.extend(match["references"])

        # Add OWASP reference if security-related
        if "security" in str(rule_file).lower():
            refs.append("https://owasp.org/www-project-top-ten/")

        return refs

    def _detect_language(self, file_path: str) -> Optional[str]:
        """Detect programming language from file extension."""
        ext_map = {
            ".py": "python",
            ".js": "javascript",
            ".ts": "typescript",
            ".jsx": "javascript",
            ".tsx": "typescript",
            ".go": "go",
            ".rs": "rust",
            ".java": "java",
            ".rb": "ruby",
            ".php": "php",
            ".c": "c",
            ".cpp": "cpp",
            ".cs": "csharp"
        }

        ext = Path(file_path).suffix.lower()
        return ext_map.get(ext)

    def _generate_summary(self, findings: List[SecurityFinding]) -> SecuritySummary:
        """Generate summary statistics from findings."""
        by_severity = {}
        by_category = {}
        critical_files = set()

        for finding in findings:
            # Count by severity
            by_severity[finding.severity] = by_severity.get(finding.severity, 0) + 1

            # Count by category
            by_category[finding.category] = by_category.get(finding.category, 0) + 1

            # Track critical files
            if finding.severity in ["critical", "high"]:
                critical_files.add(finding.file)

        return SecuritySummary(
            total_findings=len(findings),
            by_severity=by_severity,
            by_category=by_category,
            critical_files=list(critical_files),
            tools_used=["ast-grep"]
        )

    def _empty_result(self) -> Dict[str, Any]:
        """Return empty result structure."""
        return {
            "tool": "ast-grep",
            "findings": [],
            "summary": SecuritySummary().dict(),
            "stats": {
                "files_scanned": 0,
                "rules_applied": 0,
                "scan_time_ms": 0
            }
        }

    def check_installation(self) -> bool:
        """Check if ast-grep is installed."""
        try:
            result = subprocess.run(
                ["ast-grep", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except Exception:
            return False
