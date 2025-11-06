"""Tests for CodeSandbox."""

import pytest
from coderabbit_ai.codeact.sandbox import CodeSandbox


def test_sandbox_basic_execution():
    """Test basic code execution."""
    sandbox = CodeSandbox(timeout=10)

    code = """
result = {
    'status': 'success',
    'value': 42,
    'message': 'Hello from sandbox!'
}
"""

    result = sandbox.execute(code, context={})

    assert result.get('result') is not None
    assert result['result']['status'] == 'success'
    assert result['result']['value'] == 42


def test_sandbox_context_access():
    """Test code can access context data."""
    sandbox = CodeSandbox()

    code = """
result = {
    'has_context': 'test_key' in context,
    'context_value': context.get('test_key'),
    'context_number': context.get('number') * 2
}
"""

    result = sandbox.execute(
        code,
        context={'test_key': 'test_value', 'number': 21}
    )

    assert result['result']['has_context'] is True
    assert result['result']['context_value'] == 'test_value'
    assert result['result']['context_number'] == 42


def test_sandbox_import_validation():
    """Test import whitelist enforcement."""
    sandbox = CodeSandbox()

    # Allowed import
    code_allowed = """
import ast
import json
result = {'imports': 'allowed'}
"""

    result = sandbox.execute(code_allowed, context={})
    assert result.get('result') is not None

    # Disallowed import
    code_disallowed = """
import requests  # Not in whitelist!
result = {'imports': 'disallowed'}
"""

    result = sandbox.execute(code_disallowed, context={})
    assert 'error' in result
    assert 'Disallowed' in result['error']


def test_sandbox_missing_result_variable():
    """Test error when code doesn't assign 'result'."""
    sandbox = CodeSandbox()

    code = """
# Forgot to assign result!
x = 42
"""

    result = sandbox.execute(code, context={})
    assert 'error' in result
    assert 'result' in result['error'].lower()


def test_sandbox_ast_analysis():
    """Test actual code analysis scenario."""
    sandbox = CodeSandbox()

    code = """
import ast

# Parse code from context
tree = ast.parse(context['code_to_analyze'])

# Count functions
function_count = sum(1 for node in ast.walk(tree) if isinstance(node, ast.FunctionDef))

# Find function names
function_names = [
    node.name
    for node in ast.walk(tree)
    if isinstance(node, ast.FunctionDef)
]

result = {
    'function_count': function_count,
    'function_names': function_names,
    'has_classes': any(isinstance(node, ast.ClassDef) for node in ast.walk(tree))
}
"""

    test_code = """
def foo():
    pass

def bar():
    pass

class MyClass:
    pass
"""

    result = sandbox.execute(code, context={'code_to_analyze': test_code})

    assert result['result']['function_count'] == 2
    assert set(result['result']['function_names']) == {'foo', 'bar'}
    assert result['result']['has_classes'] is True


def test_sandbox_test():
    """Test sandbox self-test."""
    sandbox = CodeSandbox()
    result = sandbox.test_sandbox()

    assert result.get('result') is not None
    assert result['result']['message'] == 'Sandbox working!'
    assert result['result']['context_available'] is True
    assert result['result']['context_value'] == 'test_value'
