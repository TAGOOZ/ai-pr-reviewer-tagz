"""CodeAct Agent: Generates and executes code for analysis."""

import dspy
import logging
from typing import Dict, Any, Optional
from .sandbox import CodeSandbox

logger = logging.getLogger(__name__)


class CodeActSignature(dspy.Signature):
    """Generate executable Python code for code analysis."""

    task_description: str = dspy.InputField(
        desc="What analysis to perform (e.g., 'Check for SQL injection in auth code')"
    )
    code_changes: str = dspy.InputField(
        desc="Code changes from the PR (diff format or full content)"
    )
    available_context: str = dspy.InputField(
        desc="Available context: RAG results, SAST findings, requirements, PR description"
    )
    previous_error: str = dspy.InputField(
        desc="Error from previous execution attempt (empty on first attempt)",
        default="",
    )

    # Output fields
    python_code: str = dspy.OutputField(
        desc=(
            "Executable Python code that performs the analysis. "
            "IMPORTANT: Must assign final result to 'result' variable. "
            "Available imports: ast, re, json, collections, pandas, numpy, networkx. "
            "Context data accessible via 'context' dict. "
            "Example: result = {'status': 'PASS', 'issues': []}"
        )
    )
    explanation: str = dspy.OutputField(
        desc="Brief explanation of what the code does (1-2 sentences)"
    )


class CodeActAgent(dspy.Module):
    """
    Agent that generates and executes code for PR analysis.

    Features:
    - Generates Python code via DSPy
    - Executes in secure sandbox
    - Self-debugging (retries on errors)
    - Returns structured results
    """

    def __init__(
        self,
        sandbox: Optional[CodeSandbox] = None,
        max_retries: int = 3,
    ):
        """
        Initialize CodeAct agent.

        Args:
            sandbox: CodeSandbox instance (default: creates new)
            max_retries: Max retry attempts on execution errors
        """
        super().__init__()
        self.generator = dspy.ChainOfThought(CodeActSignature)
        self.sandbox = sandbox or CodeSandbox(timeout=30, max_memory_mb=512)
        self.max_retries = max_retries

    def forward(
        self, task: str, code_changes: str, context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate and execute code to perform analysis.

        Self-debugging: If code fails, agent sees error and tries again.

        Args:
            task: Description of what to analyze
            code_changes: PR code changes
            context: Additional context (requirements, RAG results, etc.)

        Returns:
            dict with 'success', 'result', 'code', 'explanation', 'attempts'
        """
        previous_error = ""

        for attempt in range(self.max_retries):
            logger.info(f"CodeAct attempt {attempt + 1}/{self.max_retries}")

            # Generate code
            try:
                from .. import config
                generated = self.generator(
                    task_description=task,
                    code_changes=code_changes[:config.TRUNCATE_CODE_CHANGES],
                    available_context=self._format_context(context),
                    previous_error=previous_error,
                )
            except Exception as e:
                logger.error(f"Code generation failed: {e}")
                return {
                    "success": False,
                    "error": f"Code generation failed: {str(e)}",
                    "attempts": attempt + 1,
                }

            logger.info(f"Generated code: {generated.explanation}")
            logger.debug(f"Code:\n{generated.python_code}")

            # Execute code
            exec_result = self.sandbox.execute(
                code=generated.python_code,
                context={
                    "code_changes": code_changes,
                    **context,
                },
            )

            # Success?
            if "error" not in exec_result:
                logger.info(f"Execution succeeded on attempt {attempt + 1}")
                return {
                    "success": True,
                    "result": exec_result.get("result", exec_result),
                    "code": generated.python_code,
                    "explanation": generated.explanation,
                    "attempts": attempt + 1,
                }

            # Failed - prepare for retry
            error_msg = exec_result.get("error", "Unknown error")
            previous_error = f"Attempt {attempt + 1} failed: {error_msg}"
            logger.warning(previous_error)

        # All attempts failed
        return {
            "success": False,
            "error": "Failed after maximum retries",
            "last_error": previous_error,
            "attempts": self.max_retries,
        }

    def _format_context(self, context: Dict[str, Any]) -> str:
        """
        Format context for LLM prompt.

        Args:
            context: Context dictionary

        Returns:
            Formatted string summary
        """
        formatted = []

        if "requirements" in context:
            req_text = str(context["requirements"])[:500]
            formatted.append(f"Requirements:\n{req_text}")

        if "pr_description" in context:
            pr_desc = str(context["pr_description"])[:300]
            formatted.append(f"PR Description:\n{pr_desc}")

        if "rag_results" in context:
            rag_count = len(context.get("rag_results", []))
            formatted.append(f"RAG Results: {rag_count} similar patterns found")

        if "sast_findings" in context:
            sast_count = len(context.get("sast_findings", []))
            formatted.append(f"SAST Findings: {sast_count} issues detected")

        return "\n\n".join(formatted) if formatted else "No additional context"
