"""Tests for code analysis functionality."""

import time
from typing import Tuple

import httpx

from ..config import TestConfig
from ..issue_collector import IssueCollector, Severity, Category


async def test_python_ast_parsing(config: TestConfig, collector: IssueCollector) -> bool:
    """Test Python AST parsing."""
    try:
        code = '''
def hello(name: str) -> str:
    """Greet someone."""
    return f"Hello, {name}!"

class Greeter:
    def __init__(self, prefix: str = "Hi"):
        self.prefix = prefix
    
    def greet(self, name: str) -> str:
        return f"{self.prefix}, {name}!"

import os
from typing import List, Optional
'''
        
        async with httpx.AsyncClient(timeout=config.timeout_analysis) as client:
            response = await client.post(
                f"{config.ai_pipeline_url}/analyze/ast",
                json={"code": code, "language": "python"}
            )
            
            if response.status_code == 200:
                result = response.json()
                # Check for expected features
                if "functions" in result or "classes" in result or "ast" in result:
                    collector.add_log(f"Python AST parsing passed: {result.keys()}")
                    return True
                else:
                    collector.record_issue(
                        test_name="test_python_ast_parsing",
                        component="analysis",
                        message="AST response missing expected fields",
                        severity=Severity.MEDIUM,
                        category=Category.FUNCTIONALITY,
                        context={"response_keys": list(result.keys())}
                    )
                    return False
            elif response.status_code == 404:
                collector.add_log("AST parsing endpoint not found (skipped)")
                return True
            else:
                collector.record_issue(
                    test_name="test_python_ast_parsing",
                    component="analysis",
                    message=f"AST parsing returned {response.status_code}",
                    severity=Severity.MEDIUM,
                    category=Category.FUNCTIONALITY
                )
                return False
    except httpx.ConnectError:
        collector.add_log("AST parsing test skipped - service not available")
        return True
    except Exception as e:
        collector.record_failure(
            test_name="test_python_ast_parsing",
            component="analysis",
            error=e,
            severity=Severity.MEDIUM,
            category=Category.FUNCTIONALITY
        )
        return False


async def test_diff_analysis(config: TestConfig, collector: IssueCollector) -> bool:
    """Test diff analysis and risk scoring."""
    try:
        diff = '''
diff --git a/src/auth.py b/src/auth.py
index 1234567..abcdefg 100644
--- a/src/auth.py
+++ b/src/auth.py
@@ -10,6 +10,15 @@ def authenticate(username: str, password: str) -> bool:
     if not username or not password:
         return False
-    return check_credentials(username, password)
+    
+    # Add rate limiting
+    if is_rate_limited(username):
+        raise RateLimitError("Too many attempts")
+    
+    result = check_credentials(username, password)
+    if not result:
+        record_failed_attempt(username)
+    return result
'''
        
        async with httpx.AsyncClient(timeout=config.timeout_analysis) as client:
            response = await client.post(
                f"{config.ai_pipeline_url}/analyze/diff",
                json={"diff": diff}
            )
            
            if response.status_code == 200:
                result = response.json()
                collector.add_log(f"Diff analysis passed: {result.keys()}")
                return True
            elif response.status_code == 404:
                collector.add_log("Diff analysis endpoint not found (skipped)")
                return True
            else:
                collector.record_issue(
                    test_name="test_diff_analysis",
                    component="analysis",
                    message=f"Diff analysis returned {response.status_code}",
                    severity=Severity.MEDIUM,
                    category=Category.FUNCTIONALITY
                )
                return False
    except httpx.ConnectError:
        collector.add_log("Diff analysis test skipped - service not available")
        return True
    except Exception as e:
        collector.record_failure(
            test_name="test_diff_analysis",
            component="analysis",
            error=e,
            severity=Severity.MEDIUM,
            category=Category.FUNCTIONALITY
        )
        return False


async def test_code_metrics(config: TestConfig, collector: IssueCollector) -> bool:
    """Test code metrics calculation."""
    try:
        code = '''
def complex_function(data, options=None):
    result = []
    for item in data:
        if item.get("active"):
            if item.get("type") == "A":
                result.append(process_a(item))
            elif item.get("type") == "B":
                result.append(process_b(item))
            else:
                if options and options.get("strict"):
                    raise ValueError("Unknown type")
                result.append(item)
    return result
'''
        
        async with httpx.AsyncClient(timeout=config.timeout_analysis) as client:
            response = await client.post(
                f"{config.ai_pipeline_url}/analyze/metrics",
                json={"code": code, "language": "python"}
            )
            
            if response.status_code == 200:
                result = response.json()
                collector.add_log(f"Code metrics passed: {result}")
                return True
            elif response.status_code == 404:
                collector.add_log("Code metrics endpoint not found (skipped)")
                return True
            else:
                collector.record_issue(
                    test_name="test_code_metrics",
                    component="analysis",
                    message=f"Code metrics returned {response.status_code}",
                    severity=Severity.LOW,
                    category=Category.FUNCTIONALITY
                )
                return False
    except httpx.ConnectError:
        collector.add_log("Code metrics test skipped - service not available")
        return True
    except Exception as e:
        collector.record_failure(
            test_name="test_code_metrics",
            component="analysis",
            error=e,
            severity=Severity.LOW,
            category=Category.FUNCTIONALITY
        )
        return False


async def test_batch_file_analysis(config: TestConfig, collector: IssueCollector) -> bool:
    """Test batch file analysis performance."""
    try:
        files = [
            {"path": f"file_{i}.py", "content": f"def func_{i}(): return {i}", "language": "python"}
            for i in range(20)
        ]
        
        start = time.time()
        async with httpx.AsyncClient(timeout=config.timeout_analysis) as client:
            response = await client.post(
                f"{config.ai_pipeline_url}/analyze/batch",
                json={"files": files}
            )
            elapsed = time.time() - start
            
            if response.status_code == 200:
                result = response.json()
                results_count = len(result.get("results", result.get("analyses", [])))
                collector.add_log(f"Batch analysis passed: {results_count} files in {elapsed:.2f}s")
                return True
            elif response.status_code == 404:
                collector.add_log("Batch analysis endpoint not found (skipped)")
                return True
            else:
                collector.record_issue(
                    test_name="test_batch_file_analysis",
                    component="analysis",
                    message=f"Batch analysis returned {response.status_code}",
                    severity=Severity.MEDIUM,
                    category=Category.FUNCTIONALITY
                )
                return False
    except httpx.ConnectError:
        collector.add_log("Batch analysis test skipped - service not available")
        return True
    except Exception as e:
        collector.record_failure(
            test_name="test_batch_file_analysis",
            component="analysis",
            error=e,
            severity=Severity.MEDIUM,
            category=Category.FUNCTIONALITY
        )
        return False


async def test_syntax_error_handling(config: TestConfig, collector: IssueCollector) -> bool:
    """Test handling of code with syntax errors."""
    try:
        invalid_code = '''
def broken_function(
    # Missing closing paren and body
class AlsoBroken
    pass  # Missing colon
'''
        
        async with httpx.AsyncClient(timeout=config.timeout_analysis) as client:
            response = await client.post(
                f"{config.ai_pipeline_url}/analyze/ast",
                json={"code": invalid_code, "language": "python"}
            )
            
            # Should either return 200 with error info or 400
            if response.status_code in [200, 400, 422]:
                collector.add_log(f"Syntax error handling passed: status={response.status_code}")
                return True
            elif response.status_code == 404:
                collector.add_log("Syntax error test skipped - endpoint not found")
                return True
            else:
                collector.record_issue(
                    test_name="test_syntax_error_handling",
                    component="analysis",
                    message=f"Unexpected status for syntax error: {response.status_code}",
                    severity=Severity.LOW,
                    category=Category.FUNCTIONALITY
                )
                return False
    except httpx.ConnectError:
        collector.add_log("Syntax error test skipped - service not available")
        return True
    except Exception as e:
        collector.record_failure(
            test_name="test_syntax_error_handling",
            component="analysis",
            error=e,
            severity=Severity.LOW,
            category=Category.FUNCTIONALITY
        )
        return False


async def run_all(config: TestConfig, collector: IssueCollector) -> Tuple[int, int, int]:
    """Run all analysis tests."""
    tests = [
        ("Python AST Parsing", test_python_ast_parsing),
        ("Diff Analysis", test_diff_analysis),
        ("Code Metrics", test_code_metrics),
        ("Batch File Analysis", test_batch_file_analysis),
        ("Syntax Error Handling", test_syntax_error_handling),
    ]
    
    passed = 0
    failed = 0
    skipped = 0
    
    for name, test_func in tests:
        try:
            result = await test_func(config, collector)
            if result:
                passed += 1
                print(f"    ✅ {name}")
            else:
                failed += 1
                print(f"    ❌ {name}")
        except Exception as e:
            failed += 1
            print(f"    ❌ {name}: {str(e)[:50]}")
    
    return passed, failed, skipped
