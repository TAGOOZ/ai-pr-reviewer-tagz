# Security Concerns & AST-Grep Integration

## 1. ❌ Hardcoded API Keys - FIXED

### Problem
API keys were hardcoded directly in test files:
```python
os.environ['ANTHROPIC_API_KEY'] = "sk-ant-api03-..."
os.environ['GITHUB_TOKEN'] = "ghp_..."
```

### Solution
✅ **Fixed in test_github_pr.py:**
- Now loads from `.env` file using `python-dotenv`
- Validates required environment variables on startup
- Fails fast with clear error message if keys are missing
- Added `.env` file with your credentials
- Updated `.env.example` with all required variables

### Files Changed
- [.env](.env) - Created with your API keys
- [.env.example](.env.example) - Added ANTHROPIC_API_KEY, COHERE_API_KEY, AST-Grep config
- [test_github_pr.py](test_github_pr.py#L14-L31) - Now uses environment variables

---

## 2. 🔓 AST-Grep Sandbox Status

### Current Implementation: **NOT SANDBOXED** ⚠️

**Location**: [python/coderabbit_ai/analyzers/astgrep_scanner.py:276-282](python/coderabbit_ai/analyzers/astgrep_scanner.py#L276-L282)

```python
result = subprocess.run(
    cmd,
    capture_output=True,
    text=True,
    timeout=30,  # 30 seconds per file
    cwd=project_root  # Runs directly on host filesystem
)
```

### Security Implications

**Risk Level: MEDIUM-HIGH for untrusted code**

1. **Direct Filesystem Access**: AST-Grep runs on the actual filesystem, not in isolation
2. **Process Execution**: Spawns `ast-grep` process with full host privileges
3. **Working Directory**: Uses `project_root` as cwd, which could be anywhere
4. **No Resource Limits**: Beyond 30s timeout, no CPU/memory constraints

### Recommended Solutions

#### Option A: Use CodeSandbox (Recommended)
Integrate with the existing `CodeSandbox` class:

```python
from ..codeact import CodeSandbox

# In AstGrepScanner.__init__
self.sandbox = CodeSandbox(...)

# In _scan_file
with self.sandbox as sb:
    result = sb.run_command(
        cmd=['ast-grep', 'scan', '--json', ...],
        timeout=30
    )
```

**Pros:**
- Isolated Docker container
- Resource limits enforced
- File system isolation
- Network isolation possible

**Cons:**
- Slower (container startup overhead)
- Requires Docker
- More complex setup

#### Option B: Use Firejail/Bubblewrap (Lighter)
```python
cmd = [
    "firejail",
    "--noprofile",
    "--private=/tmp/scan",
    "--read-only=/",
    "ast-grep", "scan", "--json", ...
]
```

**Pros:**
- Lightweight
- Faster than Docker
- Still provides isolation

**Cons:**
- Requires firejail installation
- Less comprehensive than containers

#### Option C: Keep Current + Add Restrictions
```python
result = subprocess.run(
    cmd,
    capture_output=True,
    text=True,
    timeout=30,
    cwd=safe_project_root,
    env={},  # Empty environment
    user='nobody',  # Lower privilege user
    # Add ulimits via preexec_fn
)
```

### When Does AST-Grep Scan Run?

**Triggered on:**
1. Every PR review via `CodeRabbitMultiAgentPipeline.forward()`
2. Phase 1: Static Analysis step
3. Only on **PR-changed files**, not entire codebase

**Current Status:**
- ✅ Runs on file diffs only (limited scope)
- ✅ 30-second timeout per file
- ❌ No sandbox isolation
- ❌ No resource limits beyond timeout

---

## 3. 📦 AST-Grep Repository Clarification

### Two Repositories Explained

#### [coderabbitai/ast-grep](https://github.com/coderabbitai/ast-grep)
**What it is:** CodeRabbit's FORK of the ast-grep tool itself

**Purpose:**
- Customized version of the core ast-grep CLI tool
- Contains CodeRabbit-specific modifications
- Upstream contributions (PR #1584 mentioned)
- Rust source code + build tooling

**Do we need it?**
❌ **NO** - We can use the official `ast-grep` binary from the main project

---

#### [coderabbitai/ast-grep-essentials](https://github.com/coderabbitai/ast-grep-essentials) ✅
**What it is:** Security RULES for ast-grep

**Purpose:**
- Collection of `.yml` rule files
- 50+ security patterns for Python
- 17 programming languages supported
- Organized by: `rules/<language>/security/*.yml`

**Do we need it?**
✅ **YES** - This is what we're using correctly!

**Current Status:**
- ✅ Cloned to `/tmp/ast-grep-rules`
- ✅ Auto-updates enabled (24hr TTL)
- ✅ Rules discovered recursively via `rglob()`
- ✅ Properly integrated

**Rule Structure:**
```
/tmp/ast-grep-rules/
├── rules/
│   ├── python/
│   │   └── security/
│   │       ├── sql-injection-python.yml
│   │       ├── hardcoded-secrets-python.yml
│   │       └── ... (50+ rules)
│   ├── javascript/
│   │   └── security/
│   │       ├── express-jwt-hardcoded-secret.yml
│   │       └── ...
│   └── ... (17 languages total)
```

---

## 4. Installation Requirements

### What You Need Installed

#### 1. AST-Grep Binary (the tool itself)
```bash
# Option A: Install from official source (recommended)
cargo install ast-grep

# Option B: Download binary
# https://github.com/ast-grep/ast-grep/releases

# Option C: Use package manager
brew install ast-grep  # macOS
```

**Not needed:**
- ❌ Don't need to install from coderabbitai/ast-grep fork
- ✅ Official ast-grep binary works fine

#### 2. AST-Grep Rules (essentials repo)
✅ **Already handled automatically**
- Auto-clones on first run
- Updates every 24 hours
- Path: `/tmp/ast-grep-rules`

---

## 5. Security Checklist

### Current Security Posture

| Security Control | Status | Risk |
|------------------|--------|------|
| API Keys in .env | ✅ Fixed | Low |
| Credentials in .gitignore | ✅ Yes | Low |
| AST-Grep sandboxed | ❌ No | Medium-High |
| Resource limits | ⚠️ Partial (timeout only) | Medium |
| File scope limited | ✅ Yes (PR diffs only) | Low |
| Input validation | ✅ Yes (file paths validated) | Low |
| Network isolation | ❌ No | Low |

### Recommended Actions

**Priority 1 (High):**
1. ❌ **Implement AST-Grep sandboxing** if analyzing untrusted PRs
2. ✅ Keep credentials in .env (done)
3. ✅ Validate `.env` is in `.gitignore` (already is)

**Priority 2 (Medium):**
4. Add resource limits (CPU, memory) to AST-Grep execution
5. Consider running entire Python service in container
6. Add rate limiting for API calls

**Priority 3 (Nice to have):**
7. Implement audit logging for all scans
8. Add metrics/monitoring for AST-Grep performance
9. Cache AST-Grep results by file hash

---

## 6. Testing with New .env Setup

```bash
# 1. Verify .env file exists
ls -la .env

# 2. Test environment loading
python -c "from dotenv import load_dotenv; import os; load_dotenv(); print('ANTHROPIC_API_KEY:', 'SET' if os.getenv('ANTHROPIC_API_KEY') else 'MISSING')"

# 3. Run the test
python test_github_pr.py
```

**Expected output:**
```
✅ Environment variables loaded
🌐 GITHUB PR ANALYZER - Full System Test
...
```

**If you get an error:**
```
❌ ERROR: Missing required environment variables: ANTHROPIC_API_KEY, GITHUB_TOKEN
```
→ Check that `.env` file exists and contains the keys

---

## Summary

### What We Fixed ✅
1. API keys moved from hardcoded to `.env`
2. AST-Grep rules now discovered recursively
3. Environment validation added to test scripts
4. `.env.example` updated with all config options

### What Needs Attention ⚠️
1. **AST-Grep runs without sandbox** - consider adding isolation for untrusted code
2. Decision needed: Which sandboxing approach to use?

### Repository Clarification ✅
- **Use official ast-grep binary** (not the CodeRabbit fork)
- **Use coderabbitai/ast-grep-essentials** for rules (already doing this)
