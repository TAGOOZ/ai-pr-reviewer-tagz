# System Integration Test Report

**Run ID:** `dda58d31`
**Started:** 2026-01-03 23:43:32 UTC
**Duration:** 1.8 seconds

## Summary

| Metric | Value |
|--------|-------|
| Total Tests | 6 |
| Passed | 5 ✅ |
| Failed | 1 ❌ |
| Skipped | 0 ⏭️ |
| Pass Rate | 83.3% |

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
| health | 6 | 5 | 1 | 83% ❌ |

## Issue Details

### 🔴 Critical Issues

#### [66d2ba67] test_api_gateway_health

- **Component:** api_gateway
- **Category:** connectivity
- **Message:** All connection attempts failed

<details>
<summary>Stack Trace</summary>

```
Traceback (most recent call last):
  File "/home/zeus/miniconda3/envs/cloudspace/lib/python3.12/site-packages/httpx/_transports/default.py", line 67, in map_httpcore_exceptions
    yield
  File "/home/zeus/miniconda3/envs/cloudspace/lib/python3.12/site-packages/httpx/_transports/default.py", line 371, in handle_async_request
    resp = await self._pool.handle_async_request(req)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/zeus/miniconda3/envs/cloudspace/lib/python3.12/site-packages/httpcore/_async/connection_pool.py", line 256, in handle_async_request
    raise exc from None
  File "/home/zeus/miniconda3/envs/cloudspace/lib/python3.12/site-packages/httpcore/_async/connection_pool.py", line 236, in handle_async_request
    response = await connection.handle_async_request(
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/zeus/miniconda3/envs/cloudspace/lib/python3.12/site-packages/httpcore/_async/connection.py", line 101, in handle_async_request

```
</details>
