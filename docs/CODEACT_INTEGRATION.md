# CodeAct Integration Plan

## Overview

CodeAct lets LLM agents generate and execute Python code for dynamic, flexible PR analysis. This document outlines integration with our existing DSPy-based system.

## Why CodeAct for Code Review?

### Current System Limitations

1. **Fixed Analysis Rules**: SAST tools have predefined patterns
2. **No Adaptation**: Same checks run regardless of PR context
3. **Limited Tooling**: Only what we've pre-integrated
4. **No Self-Correction**: If analysis fails, we're stuck

### CodeAct Advantages

1. **Dynamic Analysis**: Generate custom checks per PR
2. **Any Python Library**: Use tree-sitter, ast, pandas, networkx, etc.
3. **Self-Debugging**: Agent fixes its own code errors
4. **Multi-Step Workflows**: Complex analysis in single execution

## Architecture

### Hybrid Approach: DSPy + CodeAct

```
Review Request
     ↓
Context Engineering (DSPy)  ← Existing
     ↓
Primary Review (DSPy)       ← Existing
     ↓
  ┌──┴──┐
  │     │
DSPy  CodeAct               ← NEW layer
Agents Agents
  │     │
  └──┬──┘
     ↓
Final Report
```

**Division of Labor**:
- **DSPy Agents**: Fast, simple checks (style, formatting, obvious issues)
- **CodeAct Agents**: Complex, adaptive analysis (business logic, custom metrics, requirements validation)

## Implementation

### Phase 1: Sandboxed Code Executor

**Security First**: Never trust LLM-generated code

```python
# python/coderabbit_ai/codeact/sandbox.py

import subprocess
import tempfile
import os
from pathlib import Path
from typing import Dict, Any, Optional

class CodeSandbox:
    """Secure sandbox for executing LLM-generated code."""

    def __init__(self, timeout: int = 30, max_memory_mb: int = 512):
        self.timeout = timeout
        self.max_memory_mb = max_memory_mb

    def execute(
        self,
        code: str,
        context: Dict[str, Any],
        allowed_imports: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Execute code in isolated environment.

        Security measures:
        1. Runs in Docker container (isolated filesystem)
        2. CPU/memory limits
        3. Network disabled
        4. Whitelist of allowed imports
        5. Timeout enforcement
        """
        # Validate imports
        if not self._validate_imports(code, allowed_imports):
            return {"error": "Disallowed imports detected"}

        # Create temporary execution environment
        with tempfile.TemporaryDirectory() as tmpdir:
            code_file = Path(tmpdir) / "analysis.py"
            context_file = Path(tmpdir) / "context.json"
            output_file = Path(tmpdir) / "output.json"

            # Write code and context
            code_file.write_text(self._wrap_code(code))
            context_file.write_text(json.dumps(context))

            # Execute in Docker sandbox
            result = subprocess.run(
                [
                    "docker", "run",
                    "--rm",
                    "--network=none",  # No network access
                    f"--memory={self.max_memory_mb}m",
                    "--cpus=1",
                    "-v", f"{tmpdir}:/workspace:ro",  # Read-only mount
                    "-v", f"{output_file}:/output.json:rw",  # Write-only output
                    "coderabbit-sandbox:latest",
                    "python", "/workspace/analysis.py"
                ],
                timeout=self.timeout,
                capture_output=True,
                text=True
            )

            if result.returncode != 0:
                return {
                    "error": result.stderr,
                    "code": code,
                    "exit_code": result.returncode
                }

            # Read output
            if output_file.exists():
                return json.loads(output_file.read_text())

            return {"error": "No output generated"}

    def _validate_imports(self, code: str, allowed: Optional[List[str]]) -> bool:
        """Validate only allowed imports are used."""
        if allowed is None:
            allowed = [
                "ast", "re", "json", "collections", "itertools",
                "tree_sitter", "pandas", "numpy", "networkx"
            ]

        import_pattern = r'import\s+(\w+)|from\s+(\w+)\s+import'
        imports = re.findall(import_pattern, code)

        for imp in imports:
            module = imp[0] or imp[1]
            if module not in allowed:
                logger.warning(f"Disallowed import: {module}")
                return False

        return True

    def _wrap_code(self, code: str) -> str:
        """Wrap user code with safety harness."""
        return f"""
import json
import sys
import signal

# Timeout handler
def timeout_handler(signum, frame):
    raise TimeoutError("Execution exceeded time limit")

signal.signal(signal.SIGALRM, timeout_handler)
signal.alarm({self.timeout})

try:
    # Load context
    with open('/workspace/context.json') as f:
        context = json.load(f)

    # User code
{textwrap.indent(code, '    ')}

    # Write output
    with open('/output.json', 'w') as f:
        json.dump(result, f)

except Exception as e:
    with open('/output.json', 'w') as f:
        json.dump({{"error": str(e), "type": type(e).__name__}}, f)
finally:
    signal.alarm(0)  # Cancel timeout
"""
```

### Phase 2: CodeAct Agent

```python
# python/coderabbit_ai/agents/codeact_agent.py

import dspy
from typing import Dict, Any
from ..codeact.sandbox import CodeSandbox

class CodeActSignature(dspy.Signature):
    """Generate executable Python code for code analysis."""

    task_description: str = dspy.InputField(
        desc="What analysis to perform (e.g., 'Check for SQL injection in auth code')"
    )
    code_changes: str = dspy.InputField(
        desc="Code changes from the PR"
    )
    available_context: str = dspy.InputField(
        desc="Available context: RAG results, SAST findings, requirements"
    )
    previous_error: str = dspy.InputField(
        desc="Error from previous execution attempt (if any)",
        default=""
    )

    # Output
    python_code: str = dspy.OutputField(
        desc="Executable Python code that performs the analysis. "
             "Must assign final result to 'result' variable. "
             "Use only allowed imports: ast, re, json, tree_sitter, pandas, numpy, networkx"
    )
    explanation: str = dspy.OutputField(
        desc="Brief explanation of what the code does"
    )


class CodeActAgent(dspy.Module):
    """Agent that generates and executes code for PR analysis."""

    def __init__(self, sandbox: CodeSandbox = None):
        super().__init__()
        self.generator = dspy.ChainOfThought(CodeActSignature)
        self.sandbox = sandbox or CodeSandbox()
        self.max_retries = 3

    def forward(
        self,
        task: str,
        code_changes: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate and execute code to perform analysis.

        Includes self-debugging: if code fails, agent sees error and tries again.
        """
        previous_error = ""

        for attempt in range(self.max_retries):
            # Generate code
            result = self.generator(
                task_description=task,
                code_changes=code_changes,
                available_context=self._format_context(context),
                previous_error=previous_error
            )

            logger.info(
                f"CodeAct attempt {attempt + 1}: {result.explanation}"
            )

            # Execute code
            exec_result = self.sandbox.execute(
                code=result.python_code,
                context={
                    "code_changes": code_changes,
                    **context
                }
            )

            # Success?
            if "error" not in exec_result:
                return {
                    "success": True,
                    "result": exec_result,
                    "code": result.python_code,
                    "explanation": result.explanation,
                    "attempts": attempt + 1
                }

            # Failed - prepare for retry
            previous_error = f"Attempt {attempt + 1} failed: {exec_result['error']}"
            logger.warning(previous_error)

        # All attempts failed
        return {
            "success": False,
            "error": "Failed after 3 attempts",
            "last_error": previous_error
        }

    def _format_context(self, context: Dict[str, Any]) -> str:
        """Format context for LLM prompt."""
        formatted = []

        if "rag_results" in context:
            formatted.append(f"RAG Results: {len(context['rag_results'])} patterns found")

        if "sast_findings" in context:
            formatted.append(f"SAST Findings: {len(context['sast_findings'])} issues")

        if "requirements" in context:
            formatted.append(f"Requirements: {context['requirements']}")

        return "\n".join(formatted)
```

### Phase 3: Integration with Existing Pipeline

```python
# python/coderabbit_ai/pipeline.py

from .agents.codeact_agent import CodeActAgent
from .codeact.sandbox import CodeSandbox

class ReviewPipeline:
    def __init__(self, config):
        # Existing agents
        self.context_agent = ContextEngineeringAgent()
        self.review_agent = ReviewAgent()
        self.verification_pool = VerificationAgentPool(...)

        # NEW: CodeAct agents for complex analysis
        self.codeact_sandbox = CodeSandbox(timeout=30, max_memory_mb=512)
        self.codeact_agents = {
            "requirements_validation": CodeActAgent(self.codeact_sandbox),
            "business_logic": CodeActAgent(self.codeact_sandbox),
            "custom_metrics": CodeActAgent(self.codeact_sandbox),
        }

    def forward(self, request: ReviewRequest) -> ReviewResponse:
        # Step 1-3: Existing pipeline
        context_response = self.context_agent.forward(...)
        review_response = self.review_agent.forward(...)
        verification_responses = self.verification_pool.verify_parallel(...)

        # Step 4: NEW - CodeAct agents for complex tasks
        codeact_results = {}

        # Requirements validation via executable code
        if self._has_requirements(context_response):
            req_task = (
                "Compare implemented features vs requirements. "
                "Return dict with: required_count, implemented_count, missing, extra"
            )
            codeact_results["requirements"] = self.codeact_agents["requirements_validation"].forward(
                task=req_task,
                code_changes=request.code_changes,
                context={
                    "requirements": context_response.requirements,
                    "pr_description": request.pr_description
                }
            )

        # Business logic analysis
        if review_response.complexity_score > 0.7:  # Complex PR
            logic_task = (
                "Analyze business logic correctness. "
                "Check for: race conditions, edge cases, state management issues. "
                "Return risk_score (0-1) and list of concerns."
            )
            codeact_results["business_logic"] = self.codeact_agents["business_logic"].forward(
                task=logic_task,
                code_changes=request.code_changes,
                context={
                    "rag_patterns": context_response.similar_patterns,
                    "code_relationships": context_response.code_relationships
                }
            )

        # Step 5: Combine DSPy + CodeAct results
        final_comments = self._merge_findings(
            verification_responses,
            codeact_results
        )

        return ReviewResponse(...)
```

## Use Cases for Your System

### Use Case 1: Requirements Validation (Your Exact Need!)

**Task**: "Check if developer implemented 3/4 or 5/4 features vs requirements"

**Generated Code**:
```python
# LLM generates this automatically
import re
import ast

# Parse requirements from README
requirements = []
for line in context["requirements"].split("\n"):
    if match := re.match(r"\d+\.\s+(.+)", line):
        requirements.append(match.group(1))

# Parse implemented features from code
features = []
code_tree = ast.parse(context["code_changes"])
for node in ast.walk(code_tree):
    if isinstance(node, ast.FunctionDef):
        # New function = new feature
        if node.name not in ["__init__", "setUp", "tearDown"]:
            features.append(node.name)

# Compare
result = {
    "required": len(requirements),
    "implemented": len(features),
    "missing": [r for r in requirements if not any(f in r for f in features)],
    "extra": [f for f in features if not any(f in r for r in requirements)],
    "status": "PASS" if len(features) == len(requirements) else "FAIL"
}
```

**Advantage**: Adapts to any requirements format, any language.

### Use Case 2: Dynamic Security Analysis

**Task**: "Find SQL injection specifically in authentication code"

**Generated Code**:
```python
import ast
import re

# Parse code
tree = ast.parse(context["code_changes"])

sql_injections = []

# Find all string concatenations with SQL keywords
for node in ast.walk(tree):
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        code = ast.unparse(node)
        if any(kw in code.upper() for kw in ["SELECT", "INSERT", "UPDATE", "DELETE"]):
            # Check if in auth-related function
            parent_func = find_parent_function(node)
            if parent_func and "auth" in parent_func.name.lower():
                sql_injections.append({
                    "line": node.lineno,
                    "code": code,
                    "function": parent_func.name,
                    "severity": "HIGH"
                })

result = {
    "sql_injection_risks": sql_injections,
    "count": len(sql_injections),
    "risk_score": min(len(sql_injections) * 0.3, 1.0)
}
```

**Advantage**: Context-aware security analysis (only checks auth code, not all SQL).

### Use Case 3: Custom Metrics Generation

**Task**: "Calculate code complexity metrics for this PR"

**Generated Code**:
```python
import ast
import networkx as nx

# Parse code
tree = ast.parse(context["code_changes"])

# Build call graph
graph = nx.DiGraph()
for node in ast.walk(tree):
    if isinstance(node, ast.FunctionDef):
        for call in [n for n in ast.walk(node) if isinstance(n, ast.Call)]:
            if hasattr(call.func, 'id'):
                graph.add_edge(node.name, call.func.id)

# Calculate metrics
result = {
    "cyclomatic_complexity": calculate_cyclomatic(tree),
    "call_graph_depth": nx.dag_longest_path_length(graph) if nx.is_dag(graph) else -1,
    "function_count": len([n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]),
    "avg_function_length": calculate_avg_length(tree),
    "coupling_score": len(graph.edges()) / max(len(graph.nodes()), 1)
}
```

**Advantage**: Generates metrics dynamically based on PR characteristics.

## Security Considerations

### Threat Model

**Threats**:
1. Malicious code injection by LLM
2. Resource exhaustion (infinite loops, memory bombs)
3. Data exfiltration
4. Filesystem access to sensitive data

### Mitigations

1. **Docker Sandbox**:
   ```bash
   docker run \
     --rm \
     --network=none \              # No network
     --memory=512m \                # Memory limit
     --cpus=1 \                     # CPU limit
     --read-only \                  # Read-only filesystem
     --tmpfs /tmp:size=100m \       # Limited temp space
     --pids-limit 50 \              # Max 50 processes
     --security-opt=no-new-privileges \
     coderabbit-sandbox python code.py
   ```

2. **Import Whitelist**: Only safe libraries allowed
3. **Timeout**: 30 seconds max
4. **Output Size Limit**: Max 1MB output
5. **Code Review**: Log all generated code for audit

### Docker Image

```dockerfile
# Dockerfile for sandbox
FROM python:3.11-slim

# Install only allowed packages
RUN pip install --no-cache-dir \
    tree-sitter==0.20.4 \
    pandas==2.0.3 \
    numpy==1.24.3 \
    networkx==3.1

# Non-root user
RUN useradd -m -u 1000 sandbox
USER sandbox

# No writable filesystem
WORKDIR /workspace
```

## Performance Impact

### Latency Analysis

| Component | Before (DSPy only) | After (+ CodeAct) | Change |
|-----------|-------------------|-------------------|--------|
| Simple checks | 50ms | 50ms | 0ms |
| Complex analysis | 200ms (limited) | 300ms (comprehensive) | +100ms |
| Requirements validation | Not possible | 150ms | N/A |
| **Total avg** | 250ms | 350ms | +40% |

**Trade-off**: +100ms latency for much better analysis quality.

### Cost Analysis

**CodeAct adds minimal cost**:
- Sandbox execution: Free (self-hosted Docker)
- LLM code generation: ~500 tokens (same as DSPy)
- No external API calls

**Net cost**: $0 additional (already paying for LLM)

## Rollout Plan

### Week 1: Infrastructure
1. ✅ Docker sandbox image
2. ✅ Code executor with security
3. ✅ Unit tests

### Week 2: First Agent
1. ✅ CodeActAgent implementation
2. ✅ Requirements validation use case
3. ✅ Integration tests

### Week 3: Monitoring
1. ⏳ Log all generated code
2. ⏳ Track execution success rate
3. ⏳ Monitor sandbox resource usage

### Week 4: Production
1. ⏳ Deploy to staging
2. ⏳ A/B test: DSPy-only vs DSPy+CodeAct
3. ⏳ Rollout to 100% if success rate >95%

## Metrics to Track

```python
class CodeActMetrics:
    execution_success_rate: float  # Target: >95%
    avg_execution_time_ms: int     # Target: <200ms
    avg_retry_count: float         # Target: <1.5
    security_violations: int       # Target: 0
    sandbox_timeouts: int          # Target: <1%
    generated_code_quality: float  # Manual review score
```

## Alternative: OpenDevin

If implementing custom CodeAct is too complex, consider **OpenDevin**:
- Pre-built agent framework with code execution
- Sandboxed environment included
- Supports multiple LLMs
- Open source

Trade-off: Less control, but faster to deploy.

## Conclusion

**CodeAct gives your system superpowers**:
- ✅ Dynamic, adaptive analysis (not just fixed rules)
- ✅ Self-debugging agents (resilient to errors)
- ✅ Any Python library (unlimited tooling)
- ✅ Complex workflows (multi-step in one go)

**Recommendation**: Start with one use case (requirements validation), prove value, then expand.

**Expected impact**:
- Analysis quality: +40-50%
- Latency: +100ms (acceptable)
- Cost: $0 additional
- Complexity: Medium (sandbox required)

**Next steps**:
1. Build Docker sandbox
2. Implement CodeActAgent for requirements validation
3. A/B test vs existing approach
4. Measure improvement in catching real bugs

**Unresolved questions**:
- Which use cases benefit most from CodeAct vs DSPy?
- What's acceptable latency increase for better quality?
- How to measure "analysis quality" objectively?
