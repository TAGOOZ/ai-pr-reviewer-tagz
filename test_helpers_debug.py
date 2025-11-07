"""Debug script to test helper functions."""

import sys
sys.path.insert(0, 'python')

from coderabbit_ai.codeact.helpers import (
    extract_requirements_list,
    extract_function_names,
    keyword_match
)

requirements = """
## Required Features
1. User authentication
2. Password reset
3. OAuth integration
4. Session management
"""

code_changes = """
def authenticate_user(email, password):
    '''Authenticate user with email and password'''
    return True

def reset_password(email):
    '''Send password reset email'''
    return True

def oauth_login(provider):
    '''Login via OAuth provider'''
    return True

def manage_session(user_id):
    '''Manage user session'''
    return True
"""

print("=== Testing Helper Functions ===\n")

# Test extract_requirements_list
reqs = extract_requirements_list(requirements)
print(f"Requirements extracted ({len(reqs)}):")
for i, req in enumerate(reqs, 1):
    print(f"  {i}. {req}")

# Test extract_function_names
funcs = extract_function_names(code_changes)
print(f"\nFunctions extracted ({len(funcs)}):")
for i, func in enumerate(funcs, 1):
    print(f"  {i}. {func}")

# Test keyword matching
print("\n=== Testing Keyword Matching ===")
for req in reqs:
    print(f"\nRequirement: '{req}'")
    for func in funcs:
        match = keyword_match(req, func)
        print(f"  vs '{func}': {match}")
