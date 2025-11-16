# Sandbox Integration Guide

## You Already Have a CodeSandbox! ✅

**Location**: [python/coderabbit_ai/codeact/sandbox.py](python/coderabbit_ai/codeact/sandbox.py)

### Current Features

| Feature | Status | Details |
|---------|--------|---------|
| Docker Isolation | ✅ | Runs in isolated container |
| Network Disabled | ✅ | `--network=none` |
| Memory Limits | ✅ | Default: 512MB |
| CPU Limits | ✅ | Default: 1.0 cores |
| Process Limits | ✅ | Max: 50 processes |
| Timeout | ✅ | Default: 30s |
| Import Whitelist | ✅ | Only safe Python modules |
| Output Size Limit | ✅ | Max: 10KB |
| Non-root User | ✅ | Runs as `sandbox` user |

### Already Using Sandbox

The CodeSandbox is **already integrated** in:

1. **CodeAct Agents** - LLM-generated code execution
   - [Requirements Validator](python/coderabbit_ai/agents/requirements_validator_codeact.py)
   - [Business Logic Analyzer](python/coderabbit_ai/agents/business_logic_codeact.py)
   - [Metrics Generator](python/coderabbit_ai/agents/metrics_codeact.py)

2. **Pipeline** - Main review flow
   - [CodeRabbitMultiAgentPipeline](python/coderabbit_ai/pipeline.py)

### Security Architecture

```
┌─────────────────────────────────────────────┐
│          Host System (Your Server)          │
│                                             │
│  ┌───────────────────────────────────────┐ │
│  │  Docker Container (Isolated)          │ │
│  │  ┌─────────────────────────────────┐  │ │
│  │  │  Sandbox Process                │  │ │
│  │  │  • User: sandbox (non-root)     │  │ │
│  │  │  • Network: DISABLED            │  │ │
│  │  │  • Memory: 512MB max            │  │ │
│  │  │  • CPU: 1.0 core                │  │ │
│  │  │  • Timeout: 30s                 │  │ │
│  │  │  • Imports: WHITELISTED         │  │ │
│  │  └─────────────────────────────────┘  │ │
│  │                                       │ │
│  │  Volumes (isolated):                 │ │
│  │  /workspace → temp directory         │ │
│  └───────────────────────────────────────┘ │
└─────────────────────────────────────────────┘
```

---

## What You Asked For: PR Test Runner 🎯

You said: **"when PR happens i need to run the code in a sandbox to test and check"**

This is **different** from static analysis. You want to:
1. ✅ Fetch PR code
2. ✅ Install dependencies
3. ✅ **RUN** tests in sandbox
4. ✅ Check if code works/breaks
5. ✅ Report results

### Current Gap

**What we have:**
- ✅ CodeSandbox for executing LLM-generated analysis code
- ✅ AST-Grep for static security scanning (NO sandbox yet)
- ❌ **NO PR Test Runner** - doesn't execute actual PR code

**What we need:**
```python
class PRTestRunner:
    """Run PR code and tests in isolated sandbox."""

    def run_pr_tests(self, pr_code, test_files):
        # 1. Clone PR into sandbox
        # 2. Install dependencies (package.json, requirements.txt)
        # 3. Run tests (pytest, npm test, etc.)
        # 4. Capture results
        # 5. Return pass/fail + logs
```

---

## Implementation Plan

### Phase 1: Integrate AST-Grep with Sandbox ⚡ (Quick Win)

**Current:** AST-Grep runs unsandboxed on host
**Goal:** Run AST-Grep inside CodeSandbox

**Changes needed:**

#### 1. Update `.env` with sandbox config:
```bash
# Sandbox Configuration
SANDBOX_EXECUTION_TIMEOUT=30
SANDBOX_MAX_MEMORY_MB=512
SANDBOX_MAX_CPUS=1.0
SANDBOX_DOCKER_IMAGE=coderabbit-sandbox:latest
```

#### 2. Modify `astgrep_scanner.py`:

```python
from ..codeact import CodeSandbox

class AstGrepScanner:
    def __init__(self, ..., use_sandbox=True):
        self.use_sandbox = use_sandbox
        if use_sandbox:
            self.sandbox = CodeSandbox(
                timeout=60,  # AST-Grep needs more time
                max_memory_mb=256  # Lighter than code execution
            )

    def _scan_file(self, file_path, project_root, rule_files):
        if self.use_sandbox:
            return self._scan_file_sandboxed(...)
        else:
            return self._scan_file_direct(...)  # Current implementation

    def _scan_file_sandboxed(self, ...):
        # Run ast-grep inside Docker container
        code = f'''
import subprocess
import json

result = subprocess.run(
    ["ast-grep", "scan", "--json", "--config", "{rule_file}", "{file_path}"],
    capture_output=True,
    text=True,
    timeout=30
)

# Parse and return findings
result = json.loads(result.stdout) if result.stdout else []
'''
        return self.sandbox.execute(code, context={...})
```

**Pros:**
- ✅ Fast to implement (2-3 hours)
- ✅ Uses existing infrastructure
- ✅ Adds security layer to AST-Grep

**Cons:**
- ⚠️ Slower (Docker overhead ~100-200ms per scan)
- ⚠️ Requires Docker to be running

---

### Phase 2: Build PR Test Runner 🚀 (What You Really Need)

**Goal:** Run actual PR code (tests, build, etc.) in sandbox

#### Use Cases

1. **Python PR:**
   - Install from `requirements.txt`
   - Run `pytest`
   - Check coverage
   - Lint with `ruff`/`black`

2. **JavaScript PR:**
   - Install from `package.json`
   - Run `npm test`
   - Check build `npm run build`
   - Lint with `eslint`

3. **Any Language:**
   - Clone PR files into sandbox
   - Run language-specific tests
   - Capture stdout/stderr
   - Return pass/fail

#### Architecture

```python
class PRTestRunner:
    """Execute PR tests in isolated Docker sandbox."""

    def __init__(self):
        self.sandbox = CodeSandbox(
            timeout=300,  # 5 minutes for tests
            max_memory_mb=2048,  # More memory for builds
            max_cpus=2.0  # More CPU for compilation
        )

    def run_tests(
        self,
        pr_files: List[FileChange],
        language: str,
        test_command: Optional[str] = None
    ) -> TestResult:
        """
        Run PR tests in sandbox.

        Returns:
            TestResult with:
            - passed: bool
            - output: str (stdout/stderr)
            - coverage: Optional[float]
            - failed_tests: List[str]
            - build_errors: List[str]
        """
        # 1. Detect test framework
        test_cmd = test_command or self._detect_test_command(pr_files, language)

        # 2. Prepare sandbox code
        setup_code = self._generate_setup_code(pr_files, language)
        test_code = self._generate_test_code(test_cmd)

        # 3. Execute in sandbox
        result = self.sandbox.execute(
            code=setup_code + test_code,
            context={"files": [f.to_dict() for f in pr_files]}
        )

        # 4. Parse results
        return self._parse_test_results(result)

    def _detect_test_command(self, pr_files, language):
        """Auto-detect test command based on files."""
        file_names = [f.path for f in pr_files]

        if language == "python":
            if "pytest.ini" in file_names or any("test_" in f for f in file_names):
                return "pytest --tb=short"
            elif "tox.ini" in file_names:
                return "tox"

        elif language == "javascript":
            if "package.json" in file_names:
                return "npm test"

        elif language == "go":
            return "go test ./..."

        return None

    def _generate_setup_code(self, pr_files, language):
        """Generate code to setup PR environment in sandbox."""
        return f'''
import os
import json
import subprocess
from pathlib import Path

# Create file structure
for file_data in context["files"]:
    file_path = Path(file_data["path"])
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(file_data["content"])

# Install dependencies
if "{language}" == "python":
    if Path("requirements.txt").exists():
        subprocess.run(["pip", "install", "-r", "requirements.txt"], check=True)
    if Path("setup.py").exists():
        subprocess.run(["pip", "install", "-e", "."], check=True)

elif "{language}" == "javascript":
    if Path("package.json").exists():
        subprocess.run(["npm", "install"], check=True)
'''

    def _generate_test_code(self, test_command):
        """Generate code to run tests."""
        return f'''
# Run tests
test_result = subprocess.run(
    {test_command.split()},
    capture_output=True,
    text=True
)

result = {{
    "passed": test_result.returncode == 0,
    "stdout": test_result.stdout,
    "stderr": test_result.stderr,
    "exit_code": test_result.returncode
}}
'''
```

#### Integration with Pipeline

Add to [pipeline.py](python/coderabbit_ai/pipeline.py):

```python
def forward(self, request):
    # ... existing code ...

    # NEW: Phase 4 - Run PR Tests
    if config.ENABLE_PR_TEST_RUNNER:
        pr_test_runner = PRTestRunner()
        test_results = pr_test_runner.run_tests(
            pr_files=request.pull_request.files_changed,
            language=self._detect_language(request),
            test_command=request.config.test_command
        )

        # Add test results to comments
        if not test_results.passed:
            final_comments.append(ReviewComment(
                file_path="tests",
                line_number=0,
                severity="critical",
                message=f"❌ Tests failed: {test_results.failed_tests}",
                comment_type=CommentType.ISSUE
            ))
```

---

## Quick Start

### 1. Build Sandbox Docker Image

```bash
cd docker/codeact-sandbox
docker build -t coderabbit-sandbox:latest .
```

**Test it works:**
```bash
docker run --rm coderabbit-sandbox:latest python3 -c "print('Sandbox OK!')"
```

### 2. Update `.env`

Add to your [.env](.env):

```bash
# Sandbox Configuration
SANDBOX_EXECUTION_TIMEOUT=30
SANDBOX_MAX_MEMORY_MB=512
SANDBOX_MAX_CPUS=1.0
SANDBOX_MAX_PROCESSES=50
SANDBOX_DOCKER_IMAGE=coderabbit-sandbox:latest
SANDBOX_MAX_OUTPUT_SIZE_BYTES=10240

# PR Test Runner
ENABLE_PR_TEST_RUNNER=true
PR_TEST_TIMEOUT=300
PR_TEST_MAX_MEMORY_MB=2048
PR_TEST_MAX_CPUS=2.0
```

### 3. Test Sandbox

```python
from coderabbit_ai.codeact import CodeSandbox

sandbox = CodeSandbox()
result = sandbox.test_sandbox()
print(result)
# {'result': {'message': 'Sandbox working!', ...}}
```

---

## Docker Image Requirements

To support PR tests, the sandbox image needs:

### Current Image
```dockerfile
FROM python:3.11-slim
# Only has: pandas, numpy, networkx
```

### Enhanced Image (for PR testing)
```dockerfile
FROM python:3.11-slim

# Install multiple language runtimes
RUN apt-get update && apt-get install -y \
    nodejs npm \
    golang \
    ast-grep \  # For static analysis
    git \
    && rm -rf /var/lib/apt/lists/*

# Install Python tools
RUN pip install --no-cache-dir \
    pytest pytest-cov \
    ruff black mypy \
    pandas numpy networkx

# Install Node.js tools
RUN npm install -g \
    eslint \
    @typescript-eslint/parser

# Non-root user
RUN useradd -m -u 1000 sandbox
WORKDIR /workspace
USER sandbox
```

**Build command:**
```bash
docker build -t coderabbit-sandbox:pr-runner -f docker/pr-sandbox/Dockerfile .
```

---

## Decision Time 🤔

### Option A: Just AST-Grep Sandbox (Quick)
**Effort:** 2-3 hours
**Benefit:** Secure AST-Grep scanning
**Limitation:** Still no PR test execution

### Option B: Full PR Test Runner (Complete Solution)
**Effort:** 1-2 days
**Benefit:** Actually runs and tests PR code
**Limitation:** More complex, needs enhanced Docker image

### Option C: Both (Recommended)
**Phase 1:** AST-Grep sandbox (today)
**Phase 2:** PR Test Runner (this week)

---

## What Do You Want?

1. ✅ **AST-Grep in sandbox** - Secure static analysis
2. ✅ **PR Test Runner** - Actually execute PR code
3. ✅ **Both** - Complete solution

Let me know and I'll implement it!

---

## Current Status

| Component | Sandbox Status | Notes |
|-----------|----------------|-------|
| CodeAct Agents | ✅ Sandboxed | Already using CodeSandbox |
| AST-Grep Scanner | ❌ Not sandboxed | Runs directly on host |
| PR Code Execution | ❌ Doesn't exist | Need to build PRTestRunner |
| LLM-generated code | ✅ Sandboxed | Via CodeAct agents |

**Your sandbox infrastructure is ready - we just need to use it!**
