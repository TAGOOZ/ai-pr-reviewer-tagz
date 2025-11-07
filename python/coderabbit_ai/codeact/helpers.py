"""Helper functions for CodeAct agents to use in generated code.

These helpers provide reliable implementations of common parsing tasks,
reducing the complexity of LLM-generated code and improving reliability.
"""

import ast
import re
import textwrap
from typing import List, Dict, Any


def count_functions(code: str) -> int:
    """Count function definitions in Python code."""
    try:
        # Dedent to handle indented code from test strings
        code = textwrap.dedent(code)
        tree = ast.parse(code)
        return sum(1 for node in ast.walk(tree) if isinstance(node, ast.FunctionDef))
    except:
        return 0


def find_async_functions(code: str) -> List[str]:
    """Find all async function names in code."""
    try:
        code = textwrap.dedent(code)
        tree = ast.parse(code)
        return [node.name for node in ast.walk(tree) if isinstance(node, ast.AsyncFunctionDef)]
    except:
        return []


def find_global_variables(code: str) -> List[str]:
    """Find global variable assignments at module level."""
    try:
        code = textwrap.dedent(code)
        tree = ast.parse(code)
        globals_found = []
        for node in tree.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        globals_found.append(target.id)
        return globals_found
    except:
        return []


def calculate_cyclomatic_complexity(code: str) -> Dict[str, int]:
    """Calculate cyclomatic complexity for each function.

    Returns:
        dict: {function_name: complexity}
    """
    try:
        code = textwrap.dedent(code)
        tree = ast.parse(code)
        complexities = {}

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                complexity = 1  # Base complexity
                for child in ast.walk(node):
                    # Count decision points
                    if isinstance(child, (ast.If, ast.For, ast.While, ast.ExceptHandler)):
                        complexity += 1
                    elif isinstance(child, ast.BoolOp):
                        complexity += len(child.values) - 1
                complexities[node.name] = complexity

        return complexities
    except:
        return {}


def count_lines_of_code(code: str) -> int:
    """Count non-empty, non-comment lines."""
    lines = code.split('\n')
    count = 0
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith('#'):
            count += 1
    return count


def extract_requirements_list(text: str) -> List[str]:
    """Extract requirements from numbered or bulleted lists.

    Looks for patterns like:
    - 1. Requirement
    - * Requirement
    - - Requirement
    """
    requirements = []

    # Pattern for numbered lists (1., 2., etc.)
    numbered = re.findall(r'^\s*\d+\.\s+(.+)$', text, re.MULTILINE)
    requirements.extend(numbered)

    # Pattern for bullet points (-, *, etc.)
    bulleted = re.findall(r'^\s*[-*]\s+(.+)$', text, re.MULTILINE)
    requirements.extend(bulleted)

    # Remove duplicates while preserving order
    seen = set()
    unique_requirements = []
    for req in requirements:
        req_clean = req.strip()
        if req_clean and req_clean not in seen:
            seen.add(req_clean)
            unique_requirements.append(req_clean)

    return unique_requirements


def extract_function_names(code: str) -> List[str]:
    """Extract all function names from code."""
    try:
        code = textwrap.dedent(code)
        tree = ast.parse(code)
        return [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
    except:
        return []


def keyword_match(requirement: str, implementation_name: str) -> bool:
    """Check if implementation name matches requirement using keyword matching.

    Examples:
        "User authentication" matches "authenticate_user"
        "Password reset" matches "reset_password"
    """
    req_lower = requirement.lower()
    impl_lower = implementation_name.lower()

    # Extract keywords from requirement (words longer than 2 chars)
    req_keywords = [w for w in re.findall(r'\w+', req_lower) if len(w) > 2]

    # Check if any keyword appears in implementation name
    return any(keyword in impl_lower for keyword in req_keywords)
