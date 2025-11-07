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
IMPORTANT: Get code from context['code_changes'], do NOT hard-code it!

Use the provided helper functions to calculate code quality metrics.

**CRITICAL**: Extract the code to analyze from the context dictionary:
```python
code_to_analyze = context.get('code_changes', '')
```

Then use these helper functions:
- count_functions(code_to_analyze)
- calculate_cyclomatic_complexity(code_to_analyze)
- count_lines_of_code(code_to_analyze)

Create the result dict with this exact structure:
```python
result = {
    'metrics': {
        'function_count': <use count_functions()>,
        'avg_cyclomatic_complexity': <calculate average>,
        'max_cyclomatic_complexity': <calculate max>,
        'call_graph_depth': 0,
        'coupling': 0.0,
        'lines_of_code': <use count_lines_of_code()>
    },
    'quality_score': <calculate 0-100>,
    'recommendation': <'GOOD' or 'REFACTOR' or 'CRITICAL'>
}
```
"""

        result = self.agent.forward(
            task=task,
            code_changes=code_changes,
            context={}
        )

        if not result['success']:
            return {'success': False, 'error': result.get('error')}

        # Ensure result has the expected structure with defaults
        analysis = result.get('result') or {}

        # Add defaults for missing fields
        if not isinstance(analysis, dict):
            analysis = {}

        return {
            'success': True,
            'metrics': analysis.get('metrics', {
                'function_count': 0,
                'avg_cyclomatic_complexity': 0.0,
                'max_cyclomatic_complexity': 0,
                'call_graph_depth': 0,
                'coupling': 0.0,
                'lines_of_code': 0
            }),
            'quality_score': analysis.get('quality_score', 50),
            'recommendation': analysis.get('recommendation', 'UNKNOWN')
        }
