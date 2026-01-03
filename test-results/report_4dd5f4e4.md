# System Integration Test Report

**Run ID:** `4dd5f4e4`
**Started:** 2026-01-03 22:31:41 UTC
**Duration:** 0.3 seconds

## Summary

| Metric | Value |
|--------|-------|
| Total Tests | 1 |
| Passed | 0 ✅ |
| Failed | 1 ❌ |
| Skipped | 0 ⏭️ |
| Pass Rate | 0.0% |

## Issues Summary

| Severity | Count |
|----------|-------|
| 🔴 Critical | 1 |
| 🟠 High | 0 |
| 🟡 Medium | 0 |
| 🟢 Low | 0 |

## Component Results

| Component | Tests | Passed | Failed | Pass Rate |
|-----------|-------|--------|--------|-----------|
| health | 1 | 0 | 1 | 0% ❌ |

## Issue Details

### 🔴 Critical Issues

#### [c1f6e8d6] health_phase

- **Component:** health
- **Category:** unknown
- **Message:** No module named 'asyncpg'

<details>
<summary>Stack Trace</summary>

```
Traceback (most recent call last):
  File "/media/mustafa-tag-eldeen/563CBB613CBB3B373/graduationProject/codeRabbit/ai-pr-reviewer-tagz/tests/system/orchestrator.py", line 80, in _run_phase
    passed, failed, skipped = await test_func()
                              ^^^^^^^^^^^^^^^^^
  File "/media/mustafa-tag-eldeen/563CBB613CBB3B373/graduationProject/codeRabbit/ai-pr-reviewer-tagz/tests/system/orchestrator.py", line 112, in _run_health_tests
    from .health import test_health
  File "/media/mustafa-tag-eldeen/563CBB613CBB3B373/graduationProject/codeRabbit/ai-pr-reviewer-tagz/tests/system/health/test_health.py", line 7, in <module>
    import asyncpg
ModuleNotFoundError: No module named 'asyncpg'

```
</details>
