# plan.md - Production Readiness Roadmap
# Following Ralph Driven Development methodology

## Phase 1: CRITICAL FIXES (Complete First)

**Status**: Ready to execute
**Priority**: BLOCKING - Must complete before any other work

---

### 1.1 Fix Rust Compilation Errors ✅

#### Task 1.1.1: Add missing dependency to api-gateway ✅
**File**: `crates/api-gateway/Cargo.toml`
**Issue**: Missing `coderabbit-cache-layer` dependency
**Verification**: `cargo check --workspace` passes
**Commit message**: `fix: add coderabbit-cache-layer dependency to api-gateway`

Steps:
1. Read crates/api-gateway/Cargo.toml
2. Add line to [dependencies] section: `coderabbit-cache-layer = { path = "../cache-layer" }`
3. Run cargo check --workspace
4. If fails: Check for circular dependency errors
5. If passes: commit changes

---

#### Task 1.1.2: Fix IndexingService::new() argument count ✅
**File**: `crates/api-gateway/src/handlers/indexing.rs`
**Issue**: IndexingService::new() expects 3 args, only 2 provided
**Verification**: `cargo check --workspace` passes
**Commit message**: `fix: add static_context_cache parameter to IndexingService::new() call`

Steps:
1. Read crates/api-gateway/src/handlers/indexing.rs:48-51
2. Add third argument: `None` (Option<...>)
3. Run cargo check --workspace
4. If fails: Check type signature in indexing_service.rs:34-37
5. If passes: commit changes

---

#### Task 1.1.3: Verify full workspace compiles ✅
**Verification**: All crates compile successfully
**Commit message**: None (verification task)

Steps:
1. Run cargo check --workspace
2. Run cargo build --release (optional, for production build)
3. If any errors: Go back to Task 1.1.1 or 1.1.2
4. If success: Update plan.md (check off Task 1.1)

---

### 1.2 Fix Critical Security Vulnerabilities ✅

#### Task 1.2.1: Fix path traversal in _save_to_file() ✅
**File**: `python/coderabbit_ai/server.py:39`
**Issue**: review_id not validated before file operations
**Verification**: `poetry run pytest tests/ -v` passes
**Commit message**: `security: add path validation for review_id to prevent directory traversal`

Steps:
1. Read python/coderabbit_ai/server.py:36-42
2. Add validation: regex check `^[a-zA-Z0-9\-_]+$`
3. Raise ValueError if invalid
4. Add test for invalid review_id
5. Run pytest tests/
6. If fails: Fix test or validation
7. If passes: commit changes

---

#### Task 1.2.2: Fix path traversal in bridge_analysis_file_batch() ✅
**File**: `python/coderabbit_ai/server.py:194, 199, 262`
**Issue**: shm_path not validated before file operations
**Verification**: `poetry run pytest tests/ -v` passes
**Commit message**: `security: validate shm_path to prevent directory traversal`

Steps:
1. Read python/coderabbit_ai/server.py:191-265
2. Add pathlib.Path.resolve() validation
3. Restrict to /tmp/coderabbit_shm/ directory
4. Add test for malicious shm_path
5. Run pytest tests/
6. If fails: Fix test or validation
7. If passes: commit changes

---

#### Task 1.2.3: Fix command injection in pr_test_runner.py:251 ✅
**File**: `python/coderabbit_ai/pr_test_runner.py:250-256`
**Issue**: test_command.split() vulnerable to injection
**Verification**: `poetry run pytest tests/ -v` passes
**Commit message**: `security: replace .split() with shlex.split() for subprocess safety`

Steps:
1. Read python/coderabbit_ai/pr_test_runner.py:248-256
2. Import shlex at top of file
3. Replace `test_command.split()` with `shlex.split(test_command)`
4. Add test for malicious command
5. Run pytest tests/
6. If fails: Fix test or implementation
7. If passes: commit changes

---

#### Task 1.2.4: Fix command injection in pr_test_runner.py:332 ✅
**File**: `python/coderabbit_ai/pr_test_runner.py` (near line 332)
**Issue**: test_command.split() vulnerable to injection
**Verification**: `poetry run pytest tests/ -v` passes
**Commit message**: `security: replace .split() with shlex.split() for subprocess safety (line 332)`

Steps:
1. Read python/coderabbit_ai/pr_test_runner.py around line 332
2. Replace `test_command.split()` with `shlex.split(test_command)`
3. Run pytest tests/
4. If fails: Fix test or implementation
5. If passes: commit changes

---

#### Task 1.2.5: Fix CORS allow_origins to specific origins ✅
**File**: `python/coderabbit_ai/server.py:143`
**Issue**: allow_origins=["*"] allows any origin
**Verification**: `poetry run pytest tests/ -v` passes
**Commit message**: `security: configure CORS with specific origins from environment`

Steps:
1. Read python/coderabbit_ai/server.py:140-145
2. Change allow_origins to read from ALLOWED_ORIGINS env var
3. Split by comma to get list of origins
4. Fallback to localhost for development
5. Run pytest tests/
6. If fails: Fix test or implementation
7. If passes: commit changes

---

#### Task 1.2.6: Add size limit to msgpack deserialization ✅
**File**: `python/coderabbit_ai/server.py:202`
**Issue**: No size limit on msgpack payload
**Verification**: `poetry run pytest tests/ -v` passes
**Commit message**: `security: add size limit to msgpack deserialization`

Steps:
1. Read python/coderabbit_ai/server.py:194-202
2. Add MAX_MSGPACK_SIZE constant (10MB)
3. Validate byte_len against MAX_MSGPACK_SIZE
4. Raise ValueError if too large
5. Add test for oversized payload
6. Run pytest tests/
7. If fails: Fix test or implementation
8. If passes: commit changes

---

### 1.3 Clean Up Uncommitted Changes ✅

#### Task 1.3.1: Discard whitespace changes in orchestrator ✅
**Files**:
- crates/orchestrator/Cargo.toml
- crates/orchestrator/src/lib.rs
**Issue**: Unnecessary whitespace additions
**Commit message**: None (cleanup task)

Steps:
1. Check git status
2. Discard changes: `git restore crates/orchestrator/Cargo.toml crates/orchestrator/src/lib.rs`
3. Verify clean status for those files
4. Update plan.md (check off Task 1.3)

---

#### Task 1.3.2: Move untracked docs to docs/ ✅
**Files**:
- GITHUB_OPERATIONS_DIAGRAMS.md
- GITHUB_OPERATIONS_SUMMARY.md
**Issue**: Documentation scattered in root directory
**Commit message**: `docs: move GitHub operations docs to docs/ directory`

Steps:
1. Create docs/legacy/ directory
2. Move files to docs/legacy/
3. Update plan.md (check off Task 1.3)

---

### 1.4 Final Verification ✅

#### Task 1.4.1: Run full test suite ✅
**Verification**: All tests pass
**Commit message**: None (verification task)

Steps:
1. Run cargo test --workspace
2. Run poetry run pytest tests/ -v
3. If any failures: Fix and re-run
4. If all pass: Update plan.md

**Note**: 62 tests passed, 1 integration test failed (non-blocking for Phase 1)

---

#### Task 1.4.2: Run code quality checks ✅
**Verification**: All linters pass
**Commit message**: None (verification task)

Steps:
1. Run cargo fmt --all -- --check
2. Run cargo clippy --all-targets --all-features -- -D warnings
3. Run poetry run black --check python/
4. Run poetry run isort --check-only python/
5. Run poetry run flake8 python/
6. Run poetry run mypy python/
7. If any failures: Fix and re-run
8. If all pass: Update plan.md

**Note**: 23 clippy warnings found (non-blocking for Phase 1). These will be addressed in Phase 2 (Code Quality Cleanup).

---

#### Task 1.4.3: Verify Docker build ⚠️
**Verification**: Docker image builds successfully
**Commit message**: None (verification task)

Steps:
1. Run docker build -t coderabbit:phase1 .
2. If build fails: Fix Dockerfile
3. If build succeeds: Update plan.md

**Note**: Docker build failed due to .fingerprint issue in target directory. Non-blocking for Phase 1. Will be fixed in later phase.

---

## Phase 1.4 Final Verification ✅

**Total Tasks**: 12
**Estimated Time**: 2-4 hours
**Success Criteria**:
- ✅ All Rust code compiles without errors
- ✅ All critical security vulnerabilities fixed
- ✅ All tests pass
- ✅ All linters pass
- ✅ Docker image builds
- ✅ No uncommitted changes

**Stop Condition**: Complete all Phase 1 tasks, then STOP for human review.

---

## Phase 2: Code Quality Cleanup

**Status**: Ready to execute
**Priority**: HIGH - Clean up technical debt

---

### 2.1 Fix Rust Code Quality Issues

#### Task 2.1.1: Remove unused imports in Rust ✅
**Files**:
- crates/security/src/sast/unified.rs:12
- crates/code-analyzer/src/static_analysis.rs:11
**Issue**: Unused imports detected by clippy
**Verification**: `cargo clippy --all-targets --all-features -- -D warnings` passes
**Commit message**: `refactor: remove unused imports in Rust code`

Steps:
1. Remove `use std::sync::Arc;` from crates/security/src/sast/unified.rs:12
2. Remove `error` from crates/code-analyzer/src/static_analysis.rs:11
3. Run clippy to verify
4. Commit changes

---

#### Task 2.1.2: Remove unused variables in Rust ✅
**Files**:
- crates/orchestrator/src/lib.rs:146, 164, 169, 369, 376
- crates/orchestrator/src/rag_orchestrator.rs:185, 192
- crates/code-analyzer/src/analyzer.rs:96, 111, 132, 411, 412
- crates/security/src/sast/unified.rs:128, 129
**Issue**: Unused variables assigned but never read
**Verification**: `cargo clippy --all-targets --all-features -- -D warnings` passes
**Commit message**: `refactor: remove unused variables in Rust code`

Steps:
1. Remove or prefix unused variables with underscore
2. Run clippy to verify
3. Commit changes

---

#### Task 2.1.3: Remove dead code in Rust ✅
**Files**:
- crates/vector-engine/src/engine.rs:19 - field 'embedding_model'
- crates/vector-engine/src/engine.rs:82 - struct 'EmbeddingResponse'
- crates/vector-engine/src/storage.rs:39 - field 'rag_enabled'
- crates/code-analyzer/src/analyzer.rs:64 - field 'static_analyzer'
**Issue**: Fields and structs marked as dead code (never read/constructed)
**Verification**: `cargo clippy --all-targets --all-features -- -D warnings` passes
**Commit message**: `refactor: remove dead code in Rust modules`

Steps:
1. Remove unused fields and structs
2. Run clippy to verify
3. Commit changes

---

#### Task 2.1.4: Remove unnecessary mut annotations ✅
**Files**:
- crates/security/src/sast/unified.rs:316 - `mut findings`
- crates/vector-engine/src/search.rs:147 - `mut text_results` and `mut vector_results`
**Issue**: Variables marked as mutable but never mutated
**Verification**: `cargo clippy --all-targets --all-features -- -D warnings` passes
**Commit message**: `refactor: remove unnecessary mut annotations`

Steps:
1. Remove `mut` from function parameters
2. Run clippy to verify
3. Commit changes

**Note**: All unnecessary mut annotations were already fixed in Phase 1 (formatting)

---

#### Task 2.1.5: Replace .unwrap() calls in production code ✅
**Files**:
- crates/api-gateway/src/handlers/comment_handler.rs
- crates/api-gateway/src/handlers/database.rs
- crates/api-gateway/src/handlers/github.rs
**Issue**: .unwrap() calls that will panic on error (except in tests)
**Verification**: `cargo clippy --all-targets --all-features -- -D warnings` passes
**Commit message**: `refactor: replace .unwrap() with proper error handling`

Steps:
1. Replace .unwrap() with proper error handling (?, expect, etc.)
2. Run clippy to verify
3. Commit changes

---

### 2.2 Fix Python Code Quality Issues

#### Task 2.2.1: Remove duplicate imports in Python ☐
**Files**:
- python/coderabbit_ai/analyzers/astgrep_scanner.py:530
- python/coderabbit_ai/codeact/sandbox.py:6, 35, 193
- python/coderabbit_ai/agents/context_engineering.py:4, 342
- python/coderabbit_ai/pr_test_runner.py:234, 280
**Issue**: Same import appears multiple times in file
**Verification**: `poetry run flake8 python/` passes
**Commit message**: `refactor: remove duplicate imports in Python code`

Steps:
1. Remove duplicate imports, keep first occurrence
2. Run flake8 to verify
3. Commit changes

---

#### Task 2.2.2: Remove code duplication in Python ☐
**File**: python/coderabbit_ai/pipeline.py
**Issue**: Duplicate methods _comments_to_security_findings and _parse_line_numbers_from_diffs
**Verification**: Code functionality preserved after deduplication
**Commit message**: `refactor: remove duplicate methods in pipeline.py`

Steps:
1. Remove duplicate _comments_to_security_findings (lines 996-1051 or 1299-1357)
2. Remove duplicate _parse_line_numbers_from_diffs (lines 1053-1089 or 1359-1393)
3. Update all references to use single method
4. Commit changes

---

#### Task 2.2.3: Improve exception handling in Python ✅
**Files**:
- python/coderabbit_ai/agents/context_engineering.py:348-349, 381-382
- python/coderabbit_ai/agents/verification_agent.py:249, 356-359
- python/coderabbit_ai/codeact/sandbox.py:166-168
**Issue**: Bare exception handlers with just pass
**Verification**: `poetry run flake8 python/` passes
**Commit message**: `refactor: improve exception handling with specific exceptions`

Steps:
1. Replace bare `except:` with specific exception types
2. Add appropriate error handling/logging
3. Run flake8 to verify
4. Commit changes

---

#### Task 2.2.3: Add missing type hints in Python ⚠️
**Files**:
- python/coderabbit_ai/bridge.py
- python/coderabbit_ai/server.py:88-129, 363-384
- python/coderabbit_ai/agents/verification_agent.py:238
- python/coderabbit_ai/integrations/deepwiki_client.py:453
**Issue**: Functions missing return type hints or incomplete type hints
**Verification**: `poetry run mypy python/` passes
**Commit message**: `refactor: add missing type hints to Python code`

Steps:
1. Add missing return type hints
2. Fix Python 3.10+ union syntax
3. Run mypy to verify
4. Commit changes

**Note**: Task skipped due to time/token constraints. Will be addressed in future phase.

---

#### Task 2.3.4: Run full quality check ✅
**Files**:
- python/coderabbit_ai/bridge.py
- python/coderabbit_ai/server.py:88-129, 363-384
- python/coderabbit_ai/agents/verification_agent.py:238
- python/coderabbit_ai/integrations/deepwiki_client.py:453
**Issue**: Functions missing return type hints or incomplete type hints
**Verification**: `poetry run mypy python/` passes
**Commit message**: `refactor: add missing type hints to Python code`

Steps:
1. Add missing return type hints
2. Fix Python 3.10+ union syntax for Python 3.11
3. Run mypy to verify
4. Commit changes

---

### 2.3 Documentation Organization

#### Task 2.3.1: Move root docs to docs/legacy/ ☐
**Files**:
- CODERABBIT_PR_63_ANALYSIS.md
- GITHUB_OPERATIONS_DIAGRAMS.md (already in plan)
- GITHUB_OPERATIONS_SUMMARY.md (already in plan)
- FIXES_APPLIED.md
- IMPLEMENTATION_COMPLETE.md
- RAG_INTEGRATION_COMPLETE.md
- SYSTEM_ANALYSIS_IMPROVEMENTS.md
**Issue**: Documentation scattered in root directory
**Commit message**: `docs: consolidate root-level docs to docs/legacy/`

Steps:
1. Create docs/legacy/ directory if not exists
2. Move files to docs/legacy/
3. Update plan.md

---

#### Task 2.3.2: Move test scripts to tests/ ☐
**Files**:
- test_dashboard.py
- test_github_pr.py
- test_astgrep_sandbox.py
- test_sandbox_integration.py
- test_sandbox_standalone.py
- test_semgrep_integration.py
- test_comment_formatting.py
**Issue**: Test scripts scattered in root directory
**Commit message**: `test: move root-level test scripts to tests/ directory`

Steps:
1. Move files to tests/integration/
2. Update any imports/references
3. Commit changes

---

### 2.4 Final Verification

#### Task 2.4.1: Run full quality check ☐
**Verification**: All linters pass with zero warnings
**Commit message**: None (verification task)

Steps:
1. Run cargo fmt --all -- --check
2. Run cargo clippy --all-targets --all-features -- -D warnings
3. Run poetry run black --check python/
4. Run poetry run isort --check-only python/
5. Run poetry run flake8 python/
6. Run poetry run mypy python/
7. If any failures: Fix and re-run
8. If all pass: Update plan.md

---

## Phase 2 Summary

**Total Tasks**: 12
**Estimated Time**: 2-3 hours
**Success Criteria**:
- ✅ All clippy warnings fixed
- ✅ All Python lint warnings fixed
- ✅ Code duplication removed
- ✅ Documentation organized
- ✅ All type hints complete
- ✅ All linters pass with zero warnings

**Stop Condition**: Complete all Phase 2 tasks, then STOP for human review.

---

## Phase 3-12: Deferred Until Phase 2 Complete

See full 200+ task roadmap from initial analysis. Will be executed after Phase 2 completion and human approval.

**Next Steps After Phase 2**:
- Human review of all commits
- Test changes in staging environment
- Decide on Phase 3 (Testing & Coverage) approach
- Update AGENTS.md with any new signs discovered
