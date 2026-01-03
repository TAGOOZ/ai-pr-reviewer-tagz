# System Integration Test Report

**Run ID:** `e2355c88`
**Started:** 2026-01-03 23:26:09 UTC
**Duration:** 1.5 seconds

## Summary

| Metric | Value |
|--------|-------|
| Total Tests | 6 |
| Passed | 4 ✅ |
| Failed | 2 ❌ |
| Skipped | 0 ⏭️ |
| Pass Rate | 66.7% |

## Issues Summary

| Severity | Count |
|----------|-------|
| 🔴 Critical | 2 |
| 🟠 High | 0 |
| 🟡 Medium | 0 |
| 🟢 Low | 0 |

## Component Results

| Component | Tests | Passed | Failed | Pass Rate |
|-----------|-------|--------|--------|-----------|
| health | 6 | 4 | 2 | 67% ❌ |

## Issue Details

### 🔴 Critical Issues

#### [acbd12ce] test_api_gateway_health

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

#### [f19bff06] test_python_service_health

- **Component:** ai_pipeline
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
