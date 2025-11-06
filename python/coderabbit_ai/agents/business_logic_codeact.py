"""Business Logic Analysis using CodeAct - Phase 2."""

import logging
from typing import Dict, Any
from ..codeact.agent import CodeActAgent
from ..codeact.sandbox import CodeSandbox

logger = logging.getLogger(__name__)


class BusinessLogicAnalyzerCodeAct:
    """Detect business logic bugs using executable code analysis."""

    def __init__(self, sandbox: CodeSandbox = None, max_retries: int = 3):
        self.agent = CodeActAgent(sandbox=sandbox, max_retries=max_retries)

    def analyze(self, code_changes: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Analyze business logic for race conditions, edge cases, state issues."""

        task = """
Analyze code for business logic issues:

1. Race conditions: Find shared state accessed in async/concurrent code without locks
2. Edge case gaps: Missing None checks, empty collection checks, boundary conditions
3. State management: Complex state machines, inconsistent state updates

Return:
{
    'race_conditions': [{'variable': str, 'risk': str, 'severity': str}],
    'edge_case_gaps': [str],
    'state_issues': [str],
    'risk_score': float (0-1)
}
"""

        result = self.agent.forward(
            task=task,
            code_changes=code_changes,
            context=context or {}
        )

        if not result['success']:
            return {'success': False, 'error': result.get('error')}

        return {'success': True, **result['result']}
