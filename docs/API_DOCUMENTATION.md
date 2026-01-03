# CodeRabbit API Documentation

Complete REST API reference for CodeRabbit services.

---

## Table of Contents

1. [Overview](#overview)
2. [Authentication](#authentication)
3. [Webhook Endpoints](#webhook-endpoints)
4. [Review Endpoints](#review-endpoints)
5. [Configuration Endpoints](#configuration-endpoints)
6. [Health & Monitoring](#health--monitoring)
7. [Error Handling](#error-handling)
8. [Rate Limiting](#rate-limiting)

---

## Overview

**Base URL**: `https://api.coderabbit.ai/api/v1`  
**Protocol**: HTTPS only  
**Format**: JSON  
**Version**: v1 (stable)

---

## Authentication

### API Key Authentication

Include your API key in the `Authorization` header:

```http
Authorization: Bearer YOUR_API_KEY
```

### JWT Token Authentication

For user-specific actions, use JWT tokens:

```http
Authorization: Bearer YOUR_JWT_TOKEN
```

**Obtaining a Token:**
```bash
curl -X POST https://api.coderabbit.ai/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "yourpassword"
  }'
```

---

## Webhook Endpoints

### GitHub Webhook

**Endpoint**: `POST /webhooks/github`

**Description**: Receives webhook events from GitHub.

**Headers:**
```
X-GitHub-Event: pull_request
X-Hub-Signature-256: sha256=...
Content-Type: application/json
```

**Request Body**: GitHub webhook payload (see [GitHub Webhook Documentation](https://docs.github.com/en/webhooks))

**Response:**
```json
{
  "status": "accepted",
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "message": "Review job queued successfully"
}
```

**Status Codes:**
- `202 Accepted` - Webhook received and job queued
- `400 Bad Request` - Invalid webhook payload
- `401 Unauthorized` - Invalid signature
- `500 Internal Server Error` - Server error

### GitLab Webhook

**Endpoint**: `POST /webhooks/gitlab`

**Description**: Receives webhook events from GitLab.

**Headers:**
```
X-Gitlab-Event: Merge Request Hook
X-Gitlab-Token: YOUR_WEBHOOK_SECRET
Content-Type: application/json
```

**Request Body**: GitLab webhook payload

**Response:** Same as GitHub webhook

### Azure DevOps Webhook

**Endpoint**: `POST /webhooks/azure`

**Description**: Receives webhook events from Azure DevOps.

**Headers:**
```
Content-Type: application/json
```

**Request Body**: Azure DevOps webhook payload

**Response:** Same as GitHub webhook

---

## Review Endpoints

### Get Review Status

**Endpoint**: `GET /reviews/{review_id}`

**Description**: Get the status and results of a code review.

**Path Parameters:**
- `review_id` (string, required): Unique review identifier

**Example:**
```bash
curl -X GET https://api.coderabbit.ai/api/v1/reviews/550e8400-e29b-41d4-a716-446655440000 \
  -H "Authorization: Bearer YOUR_API_KEY"
```

**Response:**
```json
{
  "review_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "repository": "owner/repo",
  "pull_request": 123,
  "created_at": "2025-01-03T10:00:00Z",
  "completed_at": "2025-01-03T10:05:23Z",
  "summary": {
    "total_comments": 15,
    "critical_issues": 2,
    "warnings": 8,
    "suggestions": 5
  },
  "results": {
    "comments": [
      {
        "file": "src/main.rs",
        "line": 42,
        "severity": "error",
        "category": "security",
        "message": "Potential SQL injection vulnerability",
        "suggestion": "Use parameterized queries instead"
      }
    ]
  }
}
```

**Status Codes:**
- `200 OK` - Review found
- `404 Not Found` - Review not found
- `401 Unauthorized` - Invalid API key

### Cancel Review

**Endpoint**: `POST /reviews/{review_id}/cancel`

**Description**: Cancel a pending or in-progress review.

**Path Parameters:**
- `review_id` (string, required): Review identifier

**Example:**
```bash
curl -X POST https://api.coderabbit.ai/api/v1/reviews/550e8400-e29b-41d4-a716-446655440000/cancel \
  -H "Authorization: Bearer YOUR_API_KEY"
```

**Response:**
```json
{
  "review_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "cancelled",
  "message": "Review cancelled successfully"
}
```

### List Reviews

**Endpoint**: `GET /reviews`

**Description**: List reviews for the authenticated user/organization.

**Query Parameters:**
- `repository` (string, optional): Filter by repository (format: `owner/repo`)
- `status` (string, optional): Filter by status (`pending`, `in_progress`, `completed`, `failed`)
- `limit` (integer, optional): Number of results per page (default: 20, max: 100)
- `offset` (integer, optional): Pagination offset (default: 0)

**Example:**
```bash
curl -X GET "https://api.coderabbit.ai/api/v1/reviews?repository=owner/repo&status=completed&limit=10" \
  -H "Authorization: Bearer YOUR_API_KEY"
```

**Response:**
```json
{
  "total": 42,
  "limit": 10,
  "offset": 0,
  "reviews": [
    {
      "review_id": "...",
      "status": "completed",
      "repository": "owner/repo",
      "pull_request": 123,
      "created_at": "2025-01-03T10:00:00Z"
    }
  ]
}
```

---

## Configuration Endpoints

### Get Repository Configuration

**Endpoint**: `GET /config/{owner}/{repo}`

**Description**: Get the .coderabbit.yaml configuration for a repository.

**Path Parameters:**
- `owner` (string, required): Repository owner
- `repo` (string, required): Repository name

**Query Parameters:**
- `ref` (string, optional): Git ref (branch/tag), defaults to default branch

**Example:**
```bash
curl -X GET https://api.coderabbit.ai/api/v1/config/owner/repo?ref=main \
  -H "Authorization: Bearer YOUR_API_KEY"
```

**Response:**
```json
{
  "repository": "owner/repo",
  "ref": "main",
  "config": {
    "reviews": {
      "auto_review": true,
      "min_severity": "warning",
      "max_comments": 50
    },
    "ignore": {
      "files": ["*.generated.ts"],
      "directories": ["node_modules", "dist"]
    }
  }
}
```

### Clear Configuration Cache

**Endpoint**: `POST /config/{owner}/{repo}/invalidate`

**Description**: Clear cached configuration for a repository.

**Example:**
```bash
curl -X POST https://api.coderabbit.ai/api/v1/config/owner/repo/invalidate \
  -H "Authorization: Bearer YOUR_API_KEY"
```

**Response:**
```json
{
  "message": "Configuration cache cleared successfully"
}
```

---

## Health & Monitoring

### Health Check

**Endpoint**: `GET /health`

**Description**: Check if the API is healthy.

**Example:**
```bash
curl -X GET https://api.coderabbit.ai/api/v1/health
```

**Response:**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "uptime": 123456,
  "timestamp": "2025-01-03T10:00:00Z"
}
```

### Readiness Check

**Endpoint**: `GET /ready`

**Description**: Check if the API is ready to accept requests.

**Response:**
```json
{
  "ready": true,
  "services": {
    "database": "connected",
    "redis": "connected",
    "ai_pipeline": "ready"
  }
}
```

### Metrics

**Endpoint**: `GET /metrics`

**Description**: Prometheus-compatible metrics endpoint.

**Example:**
```bash
curl -X GET https://api.coderabbit.ai/api/v1/metrics
```

**Response:** Prometheus text format

---

## Error Handling

### Error Response Format

All errors follow a consistent format:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid request parameters",
    "details": {
      "field": "repository",
      "reason": "Repository name is required"
    }
  }
}
```

### Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `VALIDATION_ERROR` | 400 | Invalid request parameters |
| `UNAUTHORIZED` | 401 | Missing or invalid authentication |
| `FORBIDDEN` | 403 | Insufficient permissions |
| `NOT_FOUND` | 404 | Resource not found |
| `RATE_LIMIT_EXCEEDED` | 429 | Too many requests |
| `INTERNAL_ERROR` | 500 | Server error |
| `SERVICE_UNAVAILABLE` | 503 | Service temporarily unavailable |

---

## Rate Limiting

### Limits

- **Anonymous requests**: 10 requests/minute
- **Authenticated requests**: 100 requests/minute
- **Enterprise**: Custom limits

### Headers

Rate limit information is included in response headers:

```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1609459200
```

### Handling Rate Limits

When rate limited, the API returns `429 Too Many Requests`:

```json
{
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Rate limit exceeded. Try again in 45 seconds.",
    "retry_after": 45
  }
}
```

---

## Best Practices

1. **Use API Keys**: Store API keys securely (environment variables, secret managers)
2. **Handle Rate Limits**: Implement exponential backoff
3. **Validate Webhooks**: Always verify webhook signatures
4. **Monitor Health**: Poll `/health` endpoint periodically
5. **Cache Responses**: Cache review results when appropriate
6. **Error Handling**: Handle all error codes gracefully

---

## SDKs and Libraries

- **JavaScript/TypeScript**: `@coderabbit/sdk-js`
- **Python**: `coderabbit-sdk`
- **Go**: `github.com/coderabbitai/coderabbit-go`
- **Rust**: `coderabbit-sdk` (crates.io)

---

## Support

- **Documentation**: https://docs.coderabbit.ai
- **API Status**: https://status.coderabbit.ai
- **Support Email**: support@coderabbit.ai
- **Community**: https://community.coderabbit.ai
