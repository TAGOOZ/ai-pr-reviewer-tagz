# CodeAct Implementation Plan: 3 Phases

## Overview

Implement CodeAct agents for dynamic code analysis in 3 phases:
- **Phase 1**: Requirements validation (3/4 vs 4/4 detection)
- **Phase 2**: Business logic analysis
- **Phase 3**: Custom metrics generation

**Goal**: Add executable code generation to complement DSPy text-based agents.

---

## Phase 1: Requirements Validation (Week 1-2)

### Objectives

Solve your exact problem: "Detect if developer implemented 3/4 or 5/4 features vs requirements"

### Components to Build

#### 1.1 Docker Sandbox (Security Foundation)
**File**: `docker/codeact-sandbox/Dockerfile`

```dockerfile
FROM python:3.11-slim

# Install only allowed packages
RUN pip install --no-cache-dir \
    tree-sitter==0.20.4 \
    pandas==2.0.3 \
    numpy==1.24.3 \
    networkx==3.1

# Create non-root user
RUN useradd -m -u 1000 sandbox
USER sandbox

WORKDIR /workspace
```

**Security features**:
- No network access
- Memory limit: 512MB
- CPU limit: 1 core
- Timeout: 30 seconds
- Read-only filesystem

#### 1.2 CodeSandbox Executor
**File**: `python/coderabbit_ai/codeact/sandbox.py`

**Key methods**:
- `execute(code, context)` - Run code in Docker
- `_validate_imports(code)` - Whitelist check
- `_wrap_code(code)` - Add safety harness

**Security checks**:
1. Import validation (only ast, re, json, pandas, etc.)
2. Timeout enforcement
3. Resource limits
4. Output size limits

#### 1.3 CodeAct Agent Base
**File**: `python/coderabbit_ai/agents/codeact_agent.py`

**Features**:
- Generate Python code via DSPy
- Execute in sandbox
- Self-debugging (retry on errors up to 3 times)
- Return structured results

#### 1.4 Requirements Validation Agent
**File**: `python/coderabbit_ai/agents/requirements_validator_codeact.py`

**Task**: Compare requirements vs implementation

**Input**:
- Requirements text (from README, REQUIREMENTS.md, etc.)
- PR code changes
- PR description

**Generated code example**:
```python
import re
import ast

# Parse requirements (numbered list)
requirements = []
for line in context['requirements'].split('\n'):
    if match := re.match(r'\d+\.\s+(.+)', line):
        requirements.append(match.group(1).lower())

# Parse implemented features
features = []
tree = ast.parse(context['code_changes'])
for node in ast.walk(tree):
    if isinstance(node, ast.FunctionDef):
        if node.name not in ['__init__', 'setUp', 'tearDown']:
            features.append(node.name.lower())

# Compare
missing = [r for r in requirements if not any(f in r or r in f for f in features)]
extra = [f for f in features if not any(f in r or r in f for r in requirements)]

result = {
    'required_count': len(requirements),
    'implemented_count': len(features),
    'missing_features': missing,
    'extra_features': extra,
    'status': 'COMPLETE' if not missing and not extra else 'INCOMPLETE',
    'scope_alignment': 'EXACT' if len(features) == len(requirements) else 'MISMATCH'
}
```

**Output**:
```json
{
  "required_count": 4,
  "implemented_count": 3,
  "missing_features": ["user profile management"],
  "extra_features": [],
  "status": "INCOMPLETE",
  "scope_alignment": "MISMATCH"
}
```

### Testing Strategy

**Test Case 1: Exact match (4/4)**
```python
requirements = """
1. User authentication
2. Password reset
3. OAuth integration
4. Session management
"""

code_changes = """
def authenticate_user(email, password):
    pass

def reset_password(email):
    pass

def oauth_login(provider):
    pass

def manage_session(user_id):
    pass
"""

# Expected: 4/4, COMPLETE
```

**Test Case 2: Missing feature (3/4)**
```python
requirements = """
1. User authentication
2. Password reset
3. OAuth integration
4. Session management
"""

code_changes = """
def authenticate_user(email, password):
    pass

def reset_password(email):
    pass

def oauth_login(provider):
    pass

# Missing: Session management
"""

# Expected: 3/4, INCOMPLETE, missing=['session management']
```

**Test Case 3: Scope creep (5/4)**
```python
requirements = """
1. User authentication
2. Password reset
3. OAuth integration
4. Session management
"""

code_changes = """
def authenticate_user(email, password):
    pass

def reset_password(email):
    pass

def oauth_login(provider):
    pass

def manage_session(user_id):
    pass

def two_factor_auth(user_id):  # Extra!
    pass
"""

# Expected: 5/4, extra=['two_factor_auth']
```

### Integration

**File**: `python/coderabbit_ai/pipeline.py`

```python
# Add to ReviewPipeline
if self._has_requirements(context_response):
    req_validation = self.codeact_agents['requirements'].forward(
        task="Compare requirements vs implementation. Return counts and missing/extra.",
        code_changes=request.code_changes,
        context={
            'requirements': context_response.requirements,
            'pr_description': request.pr_description
        }
    )

    if not req_validation['success']:
        # Fallback to existing RequirementsValidationAgent
        req_validation = self.existing_req_agent.forward(...)
```

### Success Criteria

- ✅ Correctly detects 3/4 scenarios
- ✅ Correctly detects 5/4 scenarios
- ✅ Self-debugs when code fails
- ✅ Executes in <200ms
- ✅ 0 security violations

### Deliverables

1. Docker image: `coderabbit-sandbox:latest`
2. Python modules:
   - `codeact/sandbox.py`
   - `agents/codeact_agent.py`
   - `agents/requirements_validator_codeact.py`
3. Tests: `tests/test_codeact_requirements.py`
4. Documentation: Phase 1 complete guide

---

## Phase 2: Business Logic Analysis (Week 3-4)

### Objectives

Detect deep business logic bugs that simple static analysis misses:
- Race conditions
- State management issues
- Edge case gaps
- Semantic correctness

### Components to Build

#### 2.1 Business Logic Analyzer Agent
**File**: `python/coderabbit_ai/agents/business_logic_codeact.py`

**Task**: Analyze semantic correctness and edge cases

**Generated code example**:
```python
import ast
import networkx as nx

# Build state machine from code
states = {}
transitions = {}

tree = ast.parse(context['code_changes'])

# Extract state variables
for node in ast.walk(tree):
    if isinstance(node, ast.Assign):
        for target in node.targets:
            if isinstance(target, ast.Name):
                states[target.id] = analyze_state_usage(node)

# Check for race conditions
async_functions = [n for n in ast.walk(tree) if isinstance(n, ast.AsyncFunctionDef)]
shared_state = find_shared_state(async_functions, states)

race_risks = []
for state_var in shared_state:
    if not has_lock_protection(state_var, tree):
        race_risks.append({
            'variable': state_var,
            'risk': 'Shared state in async without lock',
            'severity': 'HIGH'
        })

# Check edge cases
edge_case_gaps = []
for func in [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]:
    # Check if handles None
    if not checks_for_none(func):
        edge_case_gaps.append(f"{func.name}: Missing None check")

    # Check if handles empty collections
    if not checks_for_empty(func):
        edge_case_gaps.append(f"{func.name}: Missing empty check")

result = {
    'race_conditions': race_risks,
    'edge_case_gaps': edge_case_gaps,
    'state_complexity': len(states),
    'risk_score': calculate_risk(race_risks, edge_case_gaps)
}
```

**Output**:
```json
{
  "race_conditions": [
    {
      "variable": "user_cache",
      "risk": "Shared state in async without lock",
      "severity": "HIGH"
    }
  ],
  "edge_case_gaps": [
    "process_payment: Missing None check",
    "get_users: Missing empty check"
  ],
  "state_complexity": 12,
  "risk_score": 0.78
}
```

### Testing Strategy

**Test Case 1: Race condition detection**
```python
code_changes = """
user_cache = {}

async def update_cache(user_id, data):
    # No lock!
    user_cache[user_id] = data

async def get_from_cache(user_id):
    return user_cache.get(user_id)
"""

# Expected: race_conditions=[{variable: 'user_cache', ...}]
```

**Test Case 2: Edge case gaps**
```python
code_changes = """
def process_items(items):
    # Missing: if not items check
    total = 0
    for item in items:  # Will fail if items is None
        total += item.price
    return total
"""

# Expected: edge_case_gaps=['process_items: Missing None check']
```

### Success Criteria

- ✅ Detects race conditions in async code
- ✅ Identifies missing edge case handling
- ✅ Calculates accurate risk scores
- ✅ Self-debugs when analysis fails

### Deliverables

1. `agents/business_logic_codeact.py`
2. Tests: `tests/test_codeact_business_logic.py`
3. Integration with pipeline
4. Phase 2 documentation

---

## Phase 3: Custom Metrics (Week 5-6)

### Objectives

Generate PR-specific metrics dynamically:
- Complexity metrics
- Code graph analysis
- Pattern detection
- Quality scores

### Components to Build

#### 3.1 Custom Metrics Agent
**File**: `python/coderabbit_ai/agents/metrics_codeact.py`

**Generated code example**:
```python
import ast
import networkx as nx
import pandas as pd

tree = ast.parse(context['code_changes'])

# Cyclomatic complexity
def calculate_cyclomatic(node):
    complexity = 1
    for child in ast.walk(node):
        if isinstance(child, (ast.If, ast.While, ast.For, ast.ExceptHandler)):
            complexity += 1
    return complexity

# Build call graph
call_graph = nx.DiGraph()
functions = {}

for node in ast.walk(tree):
    if isinstance(node, ast.FunctionDef):
        functions[node.name] = node
        for call in [n for n in ast.walk(node) if isinstance(n, ast.Call)]:
            if hasattr(call.func, 'id'):
                call_graph.add_edge(node.name, call.func.id)

# Calculate metrics
metrics = {
    'function_count': len(functions),
    'avg_cyclomatic_complexity': sum(calculate_cyclomatic(f) for f in functions.values()) / max(len(functions), 1),
    'max_cyclomatic_complexity': max((calculate_cyclomatic(f) for f in functions.values()), default=0),
    'call_graph_depth': nx.dag_longest_path_length(call_graph) if call_graph and nx.is_dag(call_graph) else 0,
    'coupling': call_graph.number_of_edges() / max(call_graph.number_of_nodes(), 1),
    'lines_of_code': len(context['code_changes'].split('\n')),
    'comment_ratio': count_comments(tree) / max(len(context['code_changes'].split('\n')), 1)
}

# Quality score (0-100)
quality_score = 100
if metrics['avg_cyclomatic_complexity'] > 10:
    quality_score -= 20
if metrics['coupling'] > 0.5:
    quality_score -= 15
if metrics['comment_ratio'] < 0.1:
    quality_score -= 10

result = {
    'metrics': metrics,
    'quality_score': max(quality_score, 0),
    'recommendation': 'REFACTOR' if quality_score < 60 else 'GOOD'
}
```

**Output**:
```json
{
  "metrics": {
    "function_count": 8,
    "avg_cyclomatic_complexity": 6.2,
    "max_cyclomatic_complexity": 15,
    "call_graph_depth": 4,
    "coupling": 0.42,
    "lines_of_code": 245,
    "comment_ratio": 0.08
  },
  "quality_score": 65,
  "recommendation": "GOOD"
}
```

### Testing Strategy

**Test Case 1: Simple code (high quality)**
```python
code_changes = """
def add(a, b):
    '''Add two numbers'''
    return a + b

def subtract(a, b):
    '''Subtract two numbers'''
    return a - b
"""

# Expected: quality_score > 80
```

**Test Case 2: Complex code (needs refactor)**
```python
code_changes = """
def complex_function(data):
    result = 0
    for item in data:
        if item.valid:
            for sub in item.children:
                if sub.active:
                    for val in sub.values:
                        if val > 0:
                            result += val
    return result
"""

# Expected: quality_score < 60, cyclomatic_complexity > 10
```

### Success Criteria

- ✅ Generates accurate complexity metrics
- ✅ Builds correct call graphs
- ✅ Produces actionable quality scores
- ✅ Adapts metrics to PR type

### Deliverables

1. `agents/metrics_codeact.py`
2. Tests: `tests/test_codeact_metrics.py`
3. Dashboard integration
4. Phase 3 documentation

---

## Implementation Timeline

| Week | Phase | Tasks | Deliverables |
|------|-------|-------|--------------|
| 1 | Phase 1 | Docker sandbox, CodeSandbox, base agent | Sandbox working |
| 2 | Phase 1 | Requirements validator, tests, integration | Phase 1 complete |
| 3 | Phase 2 | Business logic analyzer, race detection | Core logic working |
| 4 | Phase 2 | Edge case detection, tests, integration | Phase 2 complete |
| 5 | Phase 3 | Metrics agent, complexity analysis | Metrics generation working |
| 6 | Phase 3 | Call graph, quality scoring, integration | Phase 3 complete |

---

## Success Metrics

### Phase 1 (Requirements)
- Detection accuracy: >95% for 3/4 and 5/4 scenarios
- Execution time: <200ms per check
- Self-debug success rate: >90%

### Phase 2 (Business Logic)
- Race condition detection: >80% precision
- Edge case coverage: >75% recall
- False positive rate: <15%

### Phase 3 (Metrics)
- Metric accuracy: ±10% of manual calculation
- Quality score correlation: >0.8 with human reviews
- Execution time: <300ms per analysis

---

## Rollback Plan

If any phase fails:
1. Keep existing DSPy agents as fallback
2. CodeAct agents are additive, not replacements
3. Can disable CodeAct via feature flag
4. Zero impact on current functionality

---

## Security Checklist

- [ ] Docker sandbox tested for escapes
- [ ] Import whitelist enforced
- [ ] Resource limits working (memory, CPU, timeout)
- [ ] No network access verified
- [ ] Output size limits enforced
- [ ] All generated code logged for audit
- [ ] Malicious code injection tests passed

---

## Next Steps

1. Start Phase 1 implementation
2. Build Docker sandbox first (foundation)
3. Implement and test CodeSandbox
4. Build requirements validator
5. Test with real PRs
6. Measure against success criteria
7. Proceed to Phase 2 only if Phase 1 succeeds

**Estimated total time**: 6 weeks for all 3 phases

**Unresolved questions**:
- Should we implement OpenDevin integration instead of custom sandbox?
- What's the acceptable latency increase per phase?
- How to handle multi-language PRs (Rust + Python)?
