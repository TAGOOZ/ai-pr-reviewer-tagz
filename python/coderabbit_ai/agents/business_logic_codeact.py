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
Analyze code for business logic issues using the provided helper functions.

**AVAILABLE HELPER FUNCTIONS** (already imported, just call them):
- find_async_functions(code) -> List[str]: Returns list of async function names
- find_global_variables(code) -> List[str]: Returns list of global variable names

**YOUR TASK:**

1. **Race conditions**: Find shared mutable state accessed in async code
   - Use find_async_functions() to get async functions
   - Use find_global_variables() to get global variables
   - If there are globals AND async functions, it's a potential race condition
   - Return format: [{'variable': 'user_cache', 'risk': 'concurrent writes without lock', 'severity': 'HIGH'}]

2. **Edge case gaps**: Find attribute access or operations that could fail
   - Parse code with ast.parse() and ast.walk()
   - Look for ast.Attribute nodes without None checks
   - Return format: ['Missing None check before accessing attribute']

3. **Risk score**: Calculate based on issues found
   - 0.0-0.3: No race conditions, good error handling
   - 0.4-0.6: Some issues
   - 0.7-1.0: Race conditions or multiple critical issues

**Example Code:**
```python
# Get the code to analyze
code_to_analyze = context['code_changes']

# Use helpers
async_funcs = find_async_functions(code_to_analyze)
globals_found = find_global_variables(code_to_analyze)

# Check for race conditions
race_conditions = []
if globals_found and async_funcs:
    for var in globals_found:
        race_conditions.append({
            'variable': var,
            'risk': 'concurrent writes without lock',
            'severity': 'HIGH'
        })

# Calculate risk
risk_score = 0.8 if race_conditions else 0.2

result = {
    'race_conditions': race_conditions,
    'edge_case_gaps': [],
    'state_issues': [],
    'risk_score': risk_score
}
```
"""

        result = self.agent.forward(
            task=task,
            code_changes=code_changes,
            context=context or {}
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
            'race_conditions': analysis.get('race_conditions', []),
            'edge_case_gaps': analysis.get('edge_case_gaps', []),
            'state_issues': analysis.get('state_issues', []),
            'risk_score': analysis.get('risk_score', 0.0)
        }
