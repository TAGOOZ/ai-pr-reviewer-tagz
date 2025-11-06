"""Custom Metrics Generation using CodeAct - Phase 3."""

import logging
from typing import Dict, Any
from ..codeact.agent import CodeActAgent
from ..codeact.sandbox import CodeSandbox

logger = logging.getLogger(__name__)


class MetricsGeneratorCodeAct:
    """Generate custom code metrics dynamically."""

    def __init__(self, sandbox: CodeSandbox = None, max_retries: int = 3):
        self.agent = CodeActAgent(sandbox=sandbox, max_retries=max_retries)

    def generate_metrics(self, code_changes: str) -> Dict[str, Any]:
        """Generate complexity, coupling, and quality metrics."""

        task = """
Calculate code metrics:

1. Cyclomatic complexity (avg and max)
2. Function count
3. Call graph depth
4. Coupling (edges/nodes in call graph)
5. Lines of code
6. Quality score (0-100 based on above)

Return:
{
    'metrics': {
        'function_count': int,
        'avg_cyclomatic_complexity': float,
        'max_cyclomatic_complexity': int,
        'call_graph_depth': int,
        'coupling': float,
        'lines_of_code': int
    },
    'quality_score': int (0-100),
    'recommendation': 'GOOD' | 'REFACTOR' | 'CRITICAL'
}
"""

        result = self.agent.forward(
            task=task,
            code_changes=code_changes,
            context={}
        )

        if not result['success']:
            return {'success': False, 'error': result.get('error')}

        return {'success': True, **result['result']}
