# System Integration Test Report

**Run ID:** `2af9ff84`
**Started:** 2026-01-03 22:32:17 UTC
**Duration:** 0.0 seconds

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

#### [37086b7a] health_phase

- **Component:** health
- **Category:** unknown
- **Message:** No module named 'httpx'

<details>
<summary>Stack Trace</summary>

```
Traceback (most recent call last):
  File "/media/mustafa-tag-eldeen/563CBB613CBB3B373/graduationProject/codeRabbit/ai-pr-reviewer-tagz/tests/system/orchestrator.py", line 80, in _run_phase
    passed, failed, skipped = await test_func()
                              ^^^^^^^^^^^^^^^^^
  File "/media/mustafa-tag-eldeen/563CBB613CBB3B373/graduationProject/codeRabbit/ai-pr-reviewer-tagz/tests/system/orchestrator.py", line 112, in _run_health_tests
    from .health import test_health
  File "/media/mustafa-tag-eldeen/563CBB613CBB3B373/graduationProject/codeRabbit/ai-pr-reviewer-tagz/tests/system/health/test_health.py", line 6, in <module>
    import httpx
ModuleNotFoundError: No module named 'httpx'

```
</details>
