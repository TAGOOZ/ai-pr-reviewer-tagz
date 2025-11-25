"""
Semgrep-based security scanner with optional Docker sandbox execution.

Semgrep provides comprehensive security scanning with 2000+ rules covering:
- OWASP Top 10 vulnerabilities
- CWE (Common Weakness Enumeration) patterns
- Framework-specific security issues
- Best practice violations
"""

import json
import logging
import subprocess
import time
from pathlib import Path
from typing import List, Dict, Any, Optional

from ..models import SecurityFinding
from .. import config

logger = logging.getLogger(__name__)


class SemgrepScanner:
    """
    Semgrep security scanner with sandbox support.

    Semgrep is a fast, open-source static analysis tool that finds bugs and
    enforces code standards. It uses patterns that look like source code.

    Features:
    - 2000+ security rules (OWASP, CWE, framework-specific)
    - Multi-language support (40+ languages)
    - Fast scanning (uses tree-sitter)
    - Optional Docker sandbox execution for untrusted code
    """

    SEVERITY_MAP = {
        "ERROR": "critical",
        "WARNING": "high",
        "INFO": "medium"
    }

    def __init__(
        self,
        rulesets: Optional[List[str]] = None,
        timeout: int = 60,
        max_findings_per_file: int = 50,
        use_sandbox: bool = False
    ):
        """
        Initialize Semgrep scanner.

        Args:
            rulesets: List of Semgrep rulesets to use (e.g., ["p/security-audit", "p/owasp-top-ten"])
                     Default: ["auto"] (automatically detect rules)
            timeout: Maximum time in seconds for scanning
            max_findings_per_file: Maximum findings to report per file
            use_sandbox: Run Semgrep in Docker sandbox (recommended for untrusted code)
        """
        self.rulesets = rulesets or ["auto"]
        self.timeout = timeout
        self.max_findings_per_file = max_findings_per_file
        self.use_sandbox = use_sandbox

        # Initialize sandbox if enabled
        self.sandbox = None
        if self.use_sandbox:
            try:
                from ..codeact import CodeSandbox
                self.sandbox = CodeSandbox(
                    timeout=self.timeout,
                    max_memory_mb=512,  # Semgrep needs more memory than ast-grep
                    max_cpus=2.0
                )
                logger.info("Semgrep will run in sandboxed mode")
            except ImportError:
                logger.warning("CodeSandbox not available, falling back to direct execution")
                self.use_sandbox = False

        # Check if semgrep is available (when not using sandbox)
        if not self.use_sandbox:
            self._verify_semgrep_installed()

    def _verify_semgrep_installed(self) -> bool:
        """Verify Semgrep is installed and accessible."""
        try:
            result = subprocess.run(
                ["semgrep", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                logger.info(f"Semgrep version: {result.stdout.strip()}")
                return True
            else:
                logger.warning("Semgrep is not properly installed")
                return False
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            logger.warning(f"Semgrep not found: {e}")
            return False

    def scan(
        self,
        changed_files: List[str],
        project_root: str,
        language: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Scan changed files with Semgrep.

        Args:
            changed_files: List of file paths to scan (relative to project_root)
            project_root: Root directory of the project
            language: Optional language filter (not used - Semgrep auto-detects)

        Returns:
            Dictionary containing findings and statistics
        """
        start_time = time.time()

        try:
            if self.use_sandbox and self.sandbox:
                findings = self._scan_sandboxed(changed_files, project_root)
            else:
                findings = self._scan_direct(changed_files, project_root)

            scan_time = time.time() - start_time

            return {
                "tool": "semgrep",
                "findings": findings,
                "files_scanned": len(changed_files),
                "scan_time_seconds": round(scan_time, 2),
                "rules_used": self.rulesets
            }

        except Exception as e:
            logger.error(f"Semgrep scan failed: {e}", exc_info=True)
            return self._empty_result()

    def _scan_direct(self, changed_files: List[str], project_root: str) -> List[SecurityFinding]:
        """Scan files directly on host (faster but less secure)."""
        findings = []
        project_path = Path(project_root)

        # Build file paths
        file_paths = []
        for file in changed_files:
            file_path = project_path / file
            if file_path.exists() and file_path.is_file():
                file_paths.append(str(file_path))

        if not file_paths:
            logger.warning("No valid files to scan")
            return []

        # Build Semgrep command
        cmd = ["semgrep", "--json", "--quiet"]

        # Add rulesets
        for ruleset in self.rulesets:
            if ruleset == "auto":
                cmd.append("--config=auto")
            else:
                cmd.append(f"--config={ruleset}")

        # Add file paths
        cmd.extend(file_paths)

        logger.info(f"Running Semgrep: {' '.join(cmd[:5])}... on {len(file_paths)} files")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                cwd=project_root
            )

            if result.stdout:
                semgrep_output = json.loads(result.stdout)
                findings.extend(self._parse_semgrep_output(semgrep_output, project_root))

            if result.returncode != 0 and result.stderr:
                logger.warning(f"Semgrep stderr: {result.stderr[:500]}")

        except subprocess.TimeoutExpired:
            logger.error(f"Semgrep scan timed out after {self.timeout}s")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Semgrep JSON output: {e}")
        except Exception as e:
            logger.error(f"Semgrep scan error: {e}", exc_info=True)

        return findings

    def _scan_sandboxed(self, changed_files: List[str], project_root: str) -> List[SecurityFinding]:
        """Scan files in Docker sandbox (secure, isolated)."""
        findings = []
        project_path = Path(project_root)

        # Read file contents
        file_contents = {}
        for file in changed_files:
            file_path = project_path / file
            if file_path.exists() and file_path.is_file():
                try:
                    file_contents[file] = file_path.read_text(encoding='utf-8', errors='ignore')
                except Exception as e:
                    logger.warning(f"Could not read {file}: {e}")

        if not file_contents:
            logger.warning("No valid files to scan")
            return []

        # Generate sandbox code to run Semgrep
        # Build config args list
        config_args = [f"--config={r}" if r != "auto" else "--config=auto" for r in self.rulesets]
        config_args_repr = repr(config_args)

        code = f'''
import subprocess
import json
from pathlib import Path

# Write files to scan
files_written = []
for file_path, content in context["files"].items():
    target_path = Path(file_path)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(content, encoding='utf-8')
    files_written.append(str(target_path))

# Build command
cmd = ["semgrep", "--json", "--quiet"] + {config_args_repr} + files_written

# Run Semgrep
try:
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout={self.timeout}
    )

    if result.stdout:
        semgrep_data = json.loads(result.stdout)
        result = semgrep_data
    else:
        result = {{"results": [], "errors": []}}
except subprocess.TimeoutExpired:
    result = {{"error": "Semgrep scan timed out"}}
except Exception as e:
    result = {{"error": str(e)}}
'''

        try:
            # Execute in sandbox
            sandbox_result = self.sandbox.execute(
                code=code,
                context={"files": file_contents},
                allowed_imports=["subprocess", "json", "pathlib"]
            )

            if "error" in sandbox_result:
                logger.warning(f"Sandbox Semgrep failed: {sandbox_result['error']}")
                return []

            semgrep_output = sandbox_result.get("result", {})
            if semgrep_output and "results" in semgrep_output:
                findings.extend(self._parse_semgrep_output(semgrep_output, project_root))

        except Exception as e:
            logger.error(f"Sandboxed Semgrep scan failed: {e}", exc_info=True)

        return findings

    def _parse_semgrep_output(self, semgrep_data: Dict[str, Any], project_root: str) -> List[SecurityFinding]:
        """Parse Semgrep JSON output into SecurityFinding objects."""
        findings = []
        project_path = Path(project_root)

        results = semgrep_data.get("results", [])

        for result in results:
            try:
                # Extract file path (make it relative to project root)
                file_path = result.get("path", "")
                if file_path.startswith(str(project_path)):
                    file_path = str(Path(file_path).relative_to(project_path))

                # Extract line number
                line = result.get("start", {}).get("line", 0)

                # Extract severity
                severity_str = result.get("extra", {}).get("severity", "WARNING").upper()
                severity = self.SEVERITY_MAP.get(severity_str, "medium")

                # Extract rule info
                check_id = result.get("check_id", "semgrep-unknown")
                message = result.get("extra", {}).get("message", "Security issue detected")

                # Extract metadata
                metadata = result.get("extra", {}).get("metadata", {})
                category = metadata.get("category", "security")
                cwe_ids = metadata.get("cwe", [])
                cwe_id = cwe_ids[0] if cwe_ids else None
                owasp_category = metadata.get("owasp", None)
                confidence = metadata.get("confidence", "MEDIUM")

                # Map confidence to float
                confidence_map = {"HIGH": 0.9, "MEDIUM": 0.7, "LOW": 0.5}
                confidence_score = confidence_map.get(confidence.upper(), 0.7)

                # Extract code snippet
                code_snippet = result.get("extra", {}).get("lines", "")

                # Extract fix suggestion
                fix = result.get("extra", {}).get("fix", None)
                suggestion = fix if fix else None

                # Extract references
                references = metadata.get("references", [])

                finding = SecurityFinding(
                    file=file_path,
                    line=line,
                    severity=severity,
                    rule_id=check_id,
                    category=category,
                    message=message[:200] if len(message) > 200 else message,
                    tool="semgrep",
                    confidence=confidence_score,
                    code_snippet=code_snippet[:300] if code_snippet else None,
                    suggestion=suggestion,
                    cwe_id=cwe_id,
                    owasp_category=owasp_category,
                    references=references[:5] if references else []
                )

                findings.append(finding)

            except Exception as e:
                logger.warning(f"Failed to parse Semgrep result: {e}")
                continue

        # Limit findings per file
        if self.max_findings_per_file > 0:
            file_counts = {}
            filtered_findings = []
            for finding in findings:
                count = file_counts.get(finding.file, 0)
                if count < self.max_findings_per_file:
                    filtered_findings.append(finding)
                    file_counts[finding.file] = count + 1
            findings = filtered_findings

        return findings

    def _empty_result(self) -> Dict[str, Any]:
        """Return empty result structure."""
        return {
            "tool": "semgrep",
            "findings": [],
            "files_scanned": 0,
            "scan_time_seconds": 0,
            "rules_used": self.rulesets
        }
