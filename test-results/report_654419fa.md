# System Integration Test Report

**Run ID:** `654419fa`
**Started:** 2026-01-03 23:18:21 UTC
**Duration:** 0.4 seconds

## Summary

| Metric | Value |
|--------|-------|
| Total Tests | 6 |
| Passed | 3 ✅ |
| Failed | 3 ❌ |
| Skipped | 0 ⏭️ |
| Pass Rate | 50.0% |

## Issues Summary

| Severity | Count |
|----------|-------|
| 🔴 Critical | 2 |
| 🟠 High | 1 |
| 🟡 Medium | 0 |
| 🟢 Low | 0 |

## Component Results

| Component | Tests | Passed | Failed | Pass Rate |
|-----------|-------|--------|--------|-----------|
| health | 6 | 3 | 3 | 50% ❌ |

## Issue Details

### 🔴 Critical Issues

#### [e60e57d2] test_api_gateway_health

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

#### [96cd01ce] test_python_service_health

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

### 🟠 High Issues

#### [1764cedf] test_database_schema

- **Component:** database
- **Category:** data_integrity
- **Message:** Missing tables: review_comments, organizations, file_changes, pull_requests, jobs, ai_models, vector_index, analysis_results, job_progress, dspy_signatures, users, repositories
