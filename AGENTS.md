# AGENTS.md - Ralph's Signs for CodeRabbit

## CRITICAL: Read this BEFORE each task

This file contains "signs" that Ralph has learned about this codebase. When something fails, update this file first - do NOT just fix code blindly.

---

## RUST COMPILATION PATTERNS

### When cargo check fails with "unresolved module or crate"
**Sign**: You probably forgot to add a dependency to Cargo.toml

**Pattern from analysis**:
```toml
# File: crates/api-gateway/Cargo.toml
# ADD THIS LINE if you see coderabbit_cache_layer errors:
coderabbit-cache-layer = { path = "../cache-layer" }
```

**Action**: Check error message for missing crate name, add to Cargo.toml under [dependencies], run `cargo check` again.

### When IndexingService::new() fails with wrong number of arguments
**Sign**: Function signature changed but call site wasn't updated

**Pattern from analysis**:
```rust
// File: crates/api-gateway/src/handlers/indexing.rs:48-51
// WRONG (2 args):
let indexing_service = IndexingService::new(
    orchestrator_arc.clone(),
    github_token,
);

// CORRECT (3 args):
let indexing_service = IndexingService::new(
    orchestrator_arc.clone(),
    github_token,
    None,  // static_context_cache: Option<...>
);
```

**Action**: Match the number of arguments to the function signature in indexing_service.rs:34-37

### Verification Commands (MUST PASS before any Rust commit)
```bash
cargo fmt --all
cargo clippy --all-targets --all-features -- -D warnings
cargo check --workspace
```

---

## PYTHON SECURITY PATTERNS

### Path Traversal Vulnerabilities

#### Pattern 1: review_id in file paths (server.py:39)
**Sign**: Using untrusted string directly in os.path.join()

```python
# VULNERABLE:
path = os.path.join(store, f"{review_id}.json")

# SAFE:
# Validate review_id first
import re
if not re.match(r'^[a-zA-Z0-9\-_]+$', review_id):
    raise ValueError("Invalid review_id")
path = os.path.join(store, f"{review_id}.json")
```

#### Pattern 2: shm_path in file operations (server.py:199, 262)
**Sign**: User-controlled path used in file operations

```python
# VULNERABLE:
with open(shm_path, "rb") as f:
    raw = f.read(byte_len)
response_path = shm_path + ".response"

# SAFE:
import pathlib
shm_path = pathlib.Path(shm_path).resolve()
if not str(shm_path).startswith("/tmp/coderabbit_shm/"):
    raise ValueError("Invalid shm_path")
with open(shm_path, "rb") as f:
    raw = f.read(byte_len)
```

**Action**: ALWAYS validate paths before filesystem operations. Restrict to safe directories.

### Command Injection Vulnerabilities

#### Pattern: test_command.split() (pr_test_runner.py:251, 332)
**Sign**: Using .split() on user input for subprocess

```python
# VULNERABLE:
result = subprocess.run(
    test_command.split(),  # Malicious: "; rm -rf /"
    cwd=tmpdir,
    capture_output=True,
    text=True,
    timeout=self.timeout,
)

# SAFE:
import shlex
import subprocess
result = subprocess.run(
    shlex.split(test_command),  # Properly escaped
    cwd=tmpdir,
    capture_output=True,
    text=True,
    timeout=self.timeout,
)
```

**Action**: ALWAYS use shlex.split() for shell commands, never .split() on untrusted input.

### MessagePack Deserialization (server.py:202)
**Sign**: No size limits on deserialization

```python
# VULNERABLE:
files_changed = msgpack.unpackb(raw, raw=False)

# SAFE:
MAX_MSGPACK_SIZE = 10 * 1024 * 1024  # 10MB
if byte_len > MAX_MSGPACK_SIZE:
    raise ValueError("MessagePack payload too large")
files_changed = msgpack.unpackb(raw, raw=False)
```

**Action**: ALWAYS validate payload size before deserialization.

### CORS Configuration (server.py:143)
**Sign**: allow_origins=["*"] allows all origins

```python
# INSECURE:
allow_origins=["*"],  # Any site can make requests

# SECURE:
from os import getenv
allowed_origins = getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,  # Specific origins only
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**Action**: NEVER use allow_origins=["*"] in production. Use environment variable with specific origins.

---

## CODE QUALITY PATTERNS

### Duplicate Imports
**Sign**: Same import appears multiple times

**Detection command**:
```bash
grep -n "^import\|^from" file.py | sort | uniq -d
```

**Examples found**:
- `python/coderabbit_ai/analyzers/astgrep_scanner.py:530` - duplicate `import re`
- `python/coderabbit_ai/codeact/sandbox.py:6,35,193` - duplicate `import ast`
- `python/coderabbit_ai/agents/context_engineering.py:4,342` - duplicate `import ast`
- `python/coderabbit_ai/pr_test_runner.py:234,280` - duplicate `import subprocess`

**Action**: Remove duplicate imports, keep first occurrence.

### Bare Exception Handlers
**Sign**: `except:` or `except Exception:` with just `pass`

**Anti-pattern**:
```python
# BAD:
try:
    risky_operation()
except:
    pass  # Swallows all errors
```

**Better**:
```python
try:
    risky_operation()
except ValueError as e:
    logger.warning(f"Invalid value: {e}")
except IOError as e:
    logger.error(f"IO error: {e}")
```

**Action**: Catch specific exceptions, handle appropriately, log errors.

---

## TESTING PATTERNS

### Verification Commands (MUST PASS before commit)
```bash
# Rust:
cargo fmt --all -- --check
cargo clippy --all-targets --all-features -- -D warnings
cargo test --workspace

# Python:
poetry run black --check python/
poetry run isort --check-only python/
poetry run flake8 python/
poetry run mypy python/
poetry run pytest tests/ -v
```

### When Tests Fail
1. DO NOT just comment out the test
2. Check if the test is outdated (code changed, test didn't)
3. Check if the test is testing wrong behavior
4. If test needs update: understand WHY, document it
5. Update AGENTS.md if pattern should be avoided

### Common Test Failures
- **ImportError**: Dependency missing, add to pyproject.toml or Cargo.toml
- **AttributeError**: API changed, update test to match
- **AssertionError**: Logic changed, update expected values
- **TimeoutError**: Performance regression, investigate

---

## GIT WORKFLOW PATTERNS

### Commit Messages (Geoffrey Huntley style)
```
fix: add missing coderabbit-cache-layer dependency
feat: implement path validation for review_id
security: replace .split() with shlex.split() for subprocess
refactor: remove duplicate imports in astgrep_scanner.py
```

**Format**: `<type>: <description>`
- `fix`: Bug fix
- `feat`: New feature
- `security`: Security fix
- `refactor`: Code cleanup
- `test`: Test changes
- `docs`: Documentation

### Before Each Commit
1. Run verification commands (above)
2. Check git status: `git status`
3. Review diff: `git diff`
4. Stage changes: `git add <files>`
5. Commit: `git commit -m "<message>"`
6. DO NOT push (human-in-the-loop approach)

---

## WHEN TO UPDATE THIS FILE

Update AGENTS.md when:
1. ❌ Ralph makes the same mistake twice
2. ❌ A pattern of errors emerges
3. ❌ A "sign" would have prevented an error
4. ❌ Discovery of a better practice for this codebase

Do NOT update for:
- ✅ One-off typos
- ✅ Simple logic fixes
- ✅ Normal development

---

## SUMMARY: Ralph's Golden Rules

1. **One task per loop** - Complete, verify, commit, exit
2. **Signs over fixes** - When something fails, update AGENTS.md first
3. **Always verify** - Never commit without running verification commands
4. **Security first** - Path validation, shlex.split(), no allow_origins=["*"]
5. **Human in loop** - Commit locally, let human review before push
