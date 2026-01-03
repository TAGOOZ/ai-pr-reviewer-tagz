#!/usr/bin/env python3
"""Standalone test for CodeSandbox import validation (no dependencies required)."""

import ast
import sys
import json
from pathlib import Path

# Add python directory to path
sys.path.insert(0, str(Path(__file__).parent / "python"))


def validate_imports(code: str, allowed: list = None) -> bool:
    """
    Validate only allowed imports are used using AST parsing.
    This is a standalone version of CodeSandbox._validate_imports for testing.
    """
    ALLOWED_IMPORTS = [
        "ast", "re", "json", "collections", "itertools", "functools",
        "operator", "pandas", "numpy", "networkx", "math", "statistics",
        "datetime", "typing",
    ]

    if allowed is None:
        allowed = ALLOWED_IMPORTS

    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        print(f"  ❌ Syntax error: {e}")
        return False

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name not in allowed:
                    print(f"  ❌ Disallowed import: {alias.name}")
                    return False
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.module not in allowed:
                print(f"  ❌ Disallowed import from: {node.module}")
                return False

    return True


def run_tests():
    """Run all import validation tests."""
    print("="*60)
    print("SANDBOX IMPORT VALIDATION TESTS (Standalone)")
    print("="*60)
    print()

    tests_passed = 0
    tests_failed = 0

    # Test 1: Allowed imports
    print("Test 1: Allowed imports (ast, json, pandas)")
    code = """
import ast
import json
import pandas
result = 1
"""
    if validate_imports(code):
        print("  ✓ PASS")
        tests_passed += 1
    else:
        print("  ✗ FAIL")
        tests_failed += 1
    print()

    # Test 2: Disallowed import
    print("Test 2: Disallowed import (os)")
    code = """
import os
result = 1
"""
    if not validate_imports(code):
        print("  ✓ PASS (correctly rejected)")
        tests_passed += 1
    else:
        print("  ✗ FAIL (should have been rejected)")
        tests_failed += 1
    print()

    # Test 3: Mixed imports
    print("Test 3: Mixed imports (ast + requests)")
    code = """
import ast
import requests
result = 1
"""
    if not validate_imports(code):
        print("  ✓ PASS (correctly rejected)")
        tests_passed += 1
    else:
        print("  ✗ FAIL (should have been rejected)")
        tests_failed += 1
    print()

    # Test 4: From imports
    print("Test 4: From imports (ast, datetime)")
    code = """
from ast import parse
from datetime import datetime
result = 1
"""
    if validate_imports(code):
        print("  ✓ PASS")
        tests_passed += 1
    else:
        print("  ✗ FAIL")
        tests_failed += 1
    print()

    # Test 5: Custom allowed list
    print("Test 5: Custom whitelist (requests allowed)")
    code = """
import requests
result = 1
"""
    if validate_imports(code, allowed=['requests']):
        print("  ✓ PASS")
        tests_passed += 1
    else:
        print("  ✗ FAIL")
        tests_failed += 1
    print()

    # Test 6: Disallowed from import
    print("Test 6: Disallowed from import (from subprocess)")
    code = """
from subprocess import run
result = 1
"""
    if not validate_imports(code):
        print("  ✓ PASS (correctly rejected)")
        tests_passed += 1
    else:
        print("  ✗ FAIL (should have been rejected)")
        tests_failed += 1
    print()

    # Test 7: Multiple allowed imports
    print("Test 7: Multiple allowed imports")
    code = """
import ast
import re
import json
import collections
from itertools import chain
from functools import reduce
result = 1
"""
    if validate_imports(code):
        print("  ✓ PASS")
        tests_passed += 1
    else:
        print("  ✗ FAIL")
        tests_failed += 1
    print()

    # Summary
    print("="*60)
    print(f"RESULTS: {tests_passed} passed, {tests_failed} failed")
    print("="*60)

    return tests_failed == 0


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
