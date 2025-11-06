"""Requirements Validation using CodeAct - Phase 1 Implementation."""

import logging
from typing import Dict, Any
from ..codeact.agent import CodeActAgent
from ..codeact.sandbox import CodeSandbox

logger = logging.getLogger(__name__)


class RequirementsValidatorCodeAct:
    """
    Validate PR implementation against documented requirements using executable code.

    Solves the "3/4 vs 4/4" problem:
    - Detects if developer implemented 3 features when 4 were required
    - Detects if developer implemented 5 features (scope creep)
    - Provides precise counts and missing/extra features
    """

    def __init__(self, sandbox: CodeSandbox = None):
        """
        Initialize requirements validator.

        Args:
            sandbox: CodeSandbox instance (default: creates new)
        """
        self.agent = CodeActAgent(sandbox=sandbox, max_retries=3)

    def validate(
        self,
        requirements_text: str,
        code_changes: str,
        pr_description: str = "",
    ) -> Dict[str, Any]:
        """
        Validate implementation vs requirements.

        Args:
            requirements_text: Requirements from README, REQUIREMENTS.md, etc.
            code_changes: PR code changes (diff or full content)
            pr_description: PR description (optional)

        Returns:
            dict with:
                - success: bool
                - required_count: int
                - implemented_count: int
                - missing_features: List[str]
                - extra_features: List[str]
                - status: "COMPLETE" | "INCOMPLETE" | "SCOPE_CREEP"
                - scope_alignment: "EXACT" | "MISSING" | "EXTRA"
        """
        task = """
Analyze requirements vs implementation to detect feature count mismatches.

Your code should:
1. Parse requirements from requirements_text (look for numbered lists, bullet points, "must have" statements)
2. Extract implemented features from code_changes (new functions, classes, endpoints)
3. Compare and return:
   - required_count: Total requirements found
   - implemented_count: Total features implemented
   - missing_features: List of requirements not implemented
   - extra_features: List of features not in requirements
   - status: "COMPLETE" if all requirements met, "INCOMPLETE" if missing, "SCOPE_CREEP" if extra
   - scope_alignment: "EXACT" if counts match, "MISSING" if under, "EXTRA" if over

Example output:
result = {
    'required_count': 4,
    'implemented_count': 3,
    'missing_features': ['session management'],
    'extra_features': [],
    'status': 'INCOMPLETE',
    'scope_alignment': 'MISSING'
}
"""

        result = self.agent.forward(
            task=task,
            code_changes=code_changes,
            context={
                "requirements": requirements_text,
                "pr_description": pr_description,
            },
        )

        if not result["success"]:
            logger.warning(f"Requirements validation failed: {result.get('error')}")
            # Fallback to basic analysis
            return {
                "success": False,
                "error": result.get("error"),
                "fallback": True,
            }

        return {
            "success": True,
            **result["result"],
            "code": result.get("code"),
            "explanation": result.get("explanation"),
            "attempts": result.get("attempts"),
        }

    def format_report(self, validation_result: Dict[str, Any]) -> str:
        """
        Format validation result as human-readable report.

        Args:
            validation_result: Result from validate()

        Returns:
            Formatted report string
        """
        if not validation_result.get("success"):
            return f"**Requirements Validation Failed**: {validation_result.get('error')}"

        report = ["## Requirements Validation Report\n"]

        # Summary
        status = validation_result.get("status", "UNKNOWN")
        req_count = validation_result.get("required_count", 0)
        impl_count = validation_result.get("implemented_count", 0)

        if status == "COMPLETE":
            report.append(f"✅ **Status**: {status}")
            report.append(f"- All {req_count} requirements implemented")
        elif status == "INCOMPLETE":
            report.append(f"⚠️ **Status**: {status}")
            report.append(
                f"- Implemented {impl_count}/{req_count} requirements"
            )
        elif status == "SCOPE_CREEP":
            report.append(f"⚠️ **Status**: {status}")
            report.append(
                f"- Implemented {impl_count} features but only {req_count} required"
            )

        # Missing features
        missing = validation_result.get("missing_features", [])
        if missing:
            report.append(f"\n### Missing Features ({len(missing)})")
            for feature in missing:
                report.append(f"- {feature}")

        # Extra features
        extra = validation_result.get("extra_features", [])
        if extra:
            report.append(f"\n### Extra Features ({len(extra)})")
            for feature in extra:
                report.append(f"- {feature}")

        return "\n".join(report)


# Example usage for testing
if __name__ == "__main__":
    validator = RequirementsValidatorCodeAct()

    # Test case: 3/4 implementation
    requirements = """
    ## Required Features
    1. User authentication
    2. Password reset
    3. OAuth integration
    4. Session management
    """

    code_changes = """
    def authenticate_user(email, password):
        '''Authenticate user with email and password'''
        pass

    def reset_password(email):
        '''Send password reset email'''
        pass

    def oauth_login(provider):
        '''Login via OAuth provider'''
        pass

    # Missing: Session management
    """

    result = validator.validate(requirements, code_changes)
    print(validator.format_report(result))
