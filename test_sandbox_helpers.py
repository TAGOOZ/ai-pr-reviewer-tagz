"""Test if helpers work correctly in sandbox."""

import sys
sys.path.insert(0, 'python')

from coderabbit_ai.codeact.sandbox import CodeSandbox

sandbox = CodeSandbox()

requirements_text = """
## Required Features
1. User authentication
2. Password reset
3. OAuth integration
4. Session management
"""

code_changes_text = """
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

test_code = """
# Get requirements and code from context
requirements_text = context.get('requirements', '')
code_text = context.get('code_changes', '')

print(f"DEBUG: Requirements text length: {len(requirements_text)}")
print(f"DEBUG: Code text length: {len(code_text)}")

# Extract requirements and function names using helper functions
requirements = extract_requirements_list(requirements_text)
functions = extract_function_names(code_text)

print(f"DEBUG: Extracted {len(requirements)} requirements")
print(f"DEBUG: Requirements: {requirements}")
print(f"DEBUG: Extracted {len(functions)} functions")
print(f"DEBUG: Functions: {functions}")

# Match requirements to implemented functions
implemented = []
missing = []

for req in requirements:
    found = False
    for func in functions:
        match_result = keyword_match(req, func)
        print(f"DEBUG: Match '{req}' vs '{func}': {match_result}")
        if match_result:
            implemented.append(req)
            found = True
            break
    if not found:
        missing.append(req)

print(f"DEBUG: Implemented: {implemented}")
print(f"DEBUG: Missing: {missing}")

# Build result dictionary
result = {
    'required_count': len(requirements),
    'implemented_count': len(implemented),
    'missing_features': missing,
    'extra_features': [],
    'status': 'COMPLETE' if len(implemented) == len(requirements) else 'INCOMPLETE',
    'scope_alignment': 'EXACT' if len(implemented) == len(requirements) else 'MISSING'
}
"""

exec_result = sandbox.execute(
    code=test_code,
    context={
        'requirements': requirements_text,
        'code_changes': code_changes_text
    }
)

print("\n=== EXECUTION RESULT ===")
if 'error' in exec_result:
    print(f"ERROR: {exec_result['error']}")
else:
    print("SUCCESS!")
    result = exec_result.get('result', {})
    print(f"Required count: {result.get('required_count')}")
    print(f"Implemented count: {result.get('implemented_count')}")
    print(f"Missing: {result.get('missing_features')}")
