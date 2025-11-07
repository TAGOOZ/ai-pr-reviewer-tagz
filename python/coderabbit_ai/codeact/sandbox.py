"""Secure sandbox for executing LLM-generated code."""

import json
import logging
import re
import subprocess
import tempfile
import textwrap
from pathlib import Path
from typing import Dict, Any, Optional, List

from .. import config

logger = logging.getLogger(__name__)


class CodeSandbox:
    """
    Secure sandbox for executing LLM-generated code.

    Security measures:
    1. Runs in Docker container (isolated filesystem)
    2. CPU/memory limits enforced
    3. Network disabled
    4. Whitelist of allowed imports
    5. Timeout enforcement
    6. Output size limits
    """

    # Allowed Python modules (whitelist)
    ALLOWED_IMPORTS = [
        "ast",
        "re",
        "json",
        "collections",
        "itertools",
        "functools",
        "operator",
        "pandas",
        "numpy",
        "networkx",
        "math",
        "statistics",
        "datetime",
        "typing",
        "asyncio",
    ]

    def __init__(
        self,
        timeout: int = None,
        max_memory_mb: int = None,
        max_cpus: float = None,
        max_output_size: int = None,
    ):
        """
        Initialize sandbox.

        Args:
            timeout: Max execution time in seconds (default from config)
            max_memory_mb: Max memory usage in MB (default from config)
            max_cpus: Max CPU cores (default from config)
            max_output_size: Max output size in bytes (default from config)
        """
        self.timeout = timeout if timeout is not None else config.SANDBOX_EXECUTION_TIMEOUT
        self.max_memory_mb = max_memory_mb if max_memory_mb is not None else config.SANDBOX_MAX_MEMORY_MB
        self.max_cpus = max_cpus if max_cpus is not None else config.SANDBOX_MAX_CPUS
        self.max_output_size = max_output_size if max_output_size is not None else config.SANDBOX_MAX_OUTPUT_SIZE_BYTES

    def execute(
        self,
        code: str,
        context: Dict[str, Any],
        allowed_imports: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Execute code in isolated Docker environment.

        Args:
            code: Python code to execute
            context: Context data available to code (as 'context' variable)
            allowed_imports: Custom import whitelist (default: ALLOWED_IMPORTS)

        Returns:
            dict with 'result' or 'error'
        """
        # Validate imports
        if not self._validate_imports(code, allowed_imports):
            return {
                "error": "Disallowed imports detected",
                "code": code,
                "allowed_imports": allowed_imports or self.ALLOWED_IMPORTS,
            }

        # Create temporary execution environment
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Prepare files
            code_file = tmpdir_path / "analysis.py"
            context_file = tmpdir_path / "context.json"
            output_file = tmpdir_path / "output.json"

            # Write code and context
            code_file.write_text(self._wrap_code(code))
            context_file.write_text(json.dumps(context, default=str))

            # Execute in Docker sandbox
            try:
                result = subprocess.run(
                    [
                        "docker",
                        "run",
                        "--rm",
                        "--network=none",  # No network access
                        f"--memory={self.max_memory_mb}m",
                        f"--cpus={self.max_cpus}",
                        f"--pids-limit={config.SANDBOX_MAX_PROCESSES}",
                        "--security-opt=no-new-privileges",
                        "-v",
                        f"{tmpdir}:/workspace",  # Read-write mount for entire workspace
                        config.SANDBOX_DOCKER_IMAGE,
                        "python3",
                        "/workspace/analysis.py",
                    ],
                    timeout=self.timeout,
                    capture_output=True,
                    text=True,
                )

                if result.returncode != 0:
                    logger.warning(f"Sandbox execution failed: {result.stderr}")
                    return {
                        "error": result.stderr[:config.TRUNCATE_ERROR_OUTPUT],
                        "code": code,
                        "exit_code": result.returncode,
                    }

                # Read output
                if output_file.exists():
                    output_text = output_file.read_text()

                    # Check output size
                    if len(output_text) > self.max_output_size:
                        return {
                            "error": f"Output too large: {len(output_text)} bytes (max: {self.max_output_size})",
                            "output_size": len(output_text),
                        }

                    try:
                        return json.loads(output_text)
                    except json.JSONDecodeError as e:
                        return {
                            "error": f"Invalid JSON output: {e}",
                            "output": output_text[:config.TRUNCATE_SANDBOX_OUTPUT],
                        }

                return {"error": "No output generated"}

            except subprocess.TimeoutExpired:
                logger.warning(f"Sandbox execution timed out after {self.timeout}s")
                return {
                    "error": f"Execution timed out after {self.timeout} seconds",
                    "timeout": self.timeout,
                }
            except Exception as e:
                logger.error(f"Sandbox execution failed: {e}")
                return {"error": f"Sandbox execution failed: {str(e)}"}

    def _validate_imports(
        self, code: str, allowed: Optional[List[str]] = None
    ) -> bool:
        """
        Validate only allowed imports are used using AST parsing.

        Args:
            code: Python code to validate
            allowed: Custom whitelist (default: ALLOWED_IMPORTS)

        Returns:
            True if all imports are allowed
        """
        if allowed is None:
            allowed = self.ALLOWED_IMPORTS

        try:
            import ast
            tree = ast.parse(code)
        except SyntaxError as e:
            logger.warning(f"Syntax error in code validation: {e}")
            return False

        import ast
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name not in allowed:
                        logger.warning(f"Disallowed import detected: {alias.name}")
                        logger.warning(f"Allowed imports: {allowed}")
                        return False
            elif isinstance(node, ast.ImportFrom):
                if node.module and node.module not in allowed:
                    logger.warning(f"Disallowed import detected: {node.module}")
                    logger.warning(f"Allowed imports: {allowed}")
                    return False

        return True

    def _wrap_code(self, code: str) -> str:
        """
        Wrap user code with safety harness and context loading.

        Args:
            code: User code to wrap

        Returns:
            Wrapped code with safety measures
        """
        # Read helper functions
        helpers_path = Path(__file__).parent / "helpers.py"
        helpers_code = ""
        if helpers_path.exists():
            with open(helpers_path, 'r') as f:
                helpers_code = f.read()
                # Remove module docstring and imports to extract just the functions
                helpers_code = re.sub(r'^""".*?"""', '', helpers_code, flags=re.DOTALL)
                helpers_code = re.sub(r'^import .*$', '', helpers_code, flags=re.MULTILINE)
                helpers_code = re.sub(r'^from .*$', '', helpers_code, flags=re.MULTILINE)

        return f"""#!/usr/bin/env python3
import json
import sys
import signal
import traceback
import ast
import re
import textwrap
from typing import List, Dict, Any

# Timeout handler
def timeout_handler(signum, frame):
    raise TimeoutError("Execution exceeded time limit")

signal.signal(signal.SIGALRM, timeout_handler)
signal.alarm({self.timeout})

# Helper functions available to user code
{helpers_code}

try:
    # Load context
    with open('/workspace/context.json', 'r') as f:
        context = json.load(f)

    # User code (indented for safety)
{textwrap.indent(code, '    ')}

    # Validate result exists
    if 'result' not in locals():
        raise ValueError("Code must assign output to 'result' variable")

    # Write output to workspace (wrapped in 'result' key for consistency)
    with open('/workspace/output.json', 'w') as f:
        json.dump({{'result': result}}, f, indent=2, default=str)

except TimeoutError as e:
    with open('/workspace/output.json', 'w') as f:
        json.dump({{
            "error": "Execution timed out",
            "timeout": {self.timeout}
        }}, f)
except Exception as e:
    with open('/workspace/output.json', 'w') as f:
        json.dump({{
            "error": str(e),
            "type": type(e).__name__,
            "traceback": traceback.format_exc()
        }}, f)
finally:
    signal.alarm(0)  # Cancel timeout
"""

    def test_sandbox(self) -> Dict[str, Any]:
        """
        Test sandbox is working correctly.

        Returns:
            dict with test results
        """
        test_code = """
import ast
import json

# Simple test
result = {
    'message': 'Sandbox working!',
    'imports': ['ast', 'json'],
    'context_available': 'test_key' in context,
    'context_value': context.get('test_key')
}
"""

        return self.execute(
            code=test_code, context={"test_key": "test_value"}
        )
