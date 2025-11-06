"""Tests for Requirements Validation - Phase 1."""

import pytest
from coderabbit_ai.agents.requirements_validator_codeact import RequirementsValidatorCodeAct


@pytest.fixture
def validator():
    """Create validator instance."""
    return RequirementsValidatorCodeAct()


def test_exact_match_4_of_4(validator):
    """Test exact match: 4 requirements, 4 implemented."""
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

    result = validator.validate(requirements, code_changes)

    assert result['success'] is True
    assert result['required_count'] == 4
    assert result['implemented_count'] == 4
    assert result['status'] == 'COMPLETE'
    assert result['scope_alignment'] == 'EXACT'
    assert len(result.get('missing_features', [])) == 0
    assert len(result.get('extra_features', [])) == 0


def test_missing_feature_3_of_4(validator):
    """Test missing feature: 4 requirements, only 3 implemented."""
    requirements = """
    ## Required Features
    1. User authentication
    2. Password reset
    3. OAuth integration
    4. Session management
    """

    code_changes = """
    def authenticate_user(email, password):
        '''Authenticate user'''
        return True

    def reset_password(email):
        '''Reset password'''
        return True

    def oauth_login(provider):
        '''OAuth login'''
        return True

    # Missing: Session management!
    """

    result = validator.validate(requirements, code_changes)

    assert result['success'] is True
    assert result['required_count'] == 4
    assert result['implemented_count'] == 3
    assert result['status'] == 'INCOMPLETE'
    assert result['scope_alignment'] == 'MISSING'
    assert len(result['missing_features']) > 0


def test_scope_creep_5_of_4(validator):
    """Test scope creep: 4 requirements, but 5 features implemented."""
    requirements = """
    ## Required Features
    1. User authentication
    2. Password reset
    3. OAuth integration
    4. Session management
    """

    code_changes = """
    def authenticate_user(email, password):
        return True

    def reset_password(email):
        return True

    def oauth_login(provider):
        return True

    def manage_session(user_id):
        return True

    def two_factor_authentication(user_id):
        '''Extra feature not in requirements!'''
        return True
    """

    result = validator.validate(requirements, code_changes)

    assert result['success'] is True
    assert result['required_count'] == 4
    assert result['implemented_count'] >= 4  # Should detect extra
    # May be COMPLETE (all requirements met) or SCOPE_CREEP depending on implementation
    assert len(result.get('extra_features', [])) > 0  # Should detect extra feature


def test_bullet_point_requirements(validator):
    """Test requirements as bullet points instead of numbered list."""
    requirements = """
    Required features:
    - User login
    - Password recovery
    - API authentication
    - Rate limiting
    """

    code_changes = """
    def user_login(username, password):
        pass

    def recover_password(email):
        pass

    def api_auth(token):
        pass

    def rate_limit(user_id):
        pass
    """

    result = validator.validate(requirements, code_changes)

    assert result['success'] is True
    assert result['required_count'] >= 3  # Should detect bullet requirements
    assert result['status'] in ['COMPLETE', 'INCOMPLETE']


def test_must_have_statements(validator):
    """Test requirements expressed as 'must have' statements."""
    requirements = """
    The system must have:
    - Authentication mechanism
    - Password reset functionality
    - OAuth support

    The system must support session management.
    """

    code_changes = """
    class AuthenticationManager:
        def authenticate(self, user):
            pass

    def reset_password(user):
        pass

    def oauth_handler(provider):
        pass

    class SessionManager:
        def create_session(self, user):
            pass
    """

    result = validator.validate(requirements, code_changes)

    assert result['success'] is True
    assert result['required_count'] >= 3


def test_pr_description_helps(validator):
    """Test that PR description provides additional context."""
    requirements = """
    Features:
    1. Authentication
    2. Authorization
    3. Session handling
    """

    code_changes = """
    def auth_function():
        pass
    """

    pr_description = """
    This PR implements authentication, authorization, and session handling.

    Implemented:
    - auth_function: Handles both authentication and authorization
    - Session handling is delegated to existing SessionManager class
    """

    result = validator.validate(requirements, code_changes, pr_description)

    assert result['success'] is True
    # PR description should help agent understand that 1 function covers multiple features


def test_format_report(validator):
    """Test report formatting."""
    result = {
        'success': True,
        'required_count': 4,
        'implemented_count': 3,
        'missing_features': ['session management'],
        'extra_features': [],
        'status': 'INCOMPLETE',
        'scope_alignment': 'MISSING'
    }

    report = validator.format_report(result)

    assert '⚠️' in report  # Warning emoji
    assert 'INCOMPLETE' in report
    assert '3/4' in report
    assert 'session management' in report


def test_real_world_scenario(validator):
    """Test real-world scenario from issue tracker."""
    requirements = """
    # GitHub Issue #123: User Management Features

    We need the following features for v2.0:

    1. User registration with email verification
    2. Profile management (update name, avatar, bio)
    3. Account deletion with data export
    4. Two-factor authentication setup

    Acceptance criteria:
    - All features must work with OAuth users
    - Data export must include all user data
    - 2FA should support TOTP apps
    """

    code_changes = """
    class UserService:
        def register_user(self, email, password):
            '''Register new user and send verification email'''
            pass

        def update_profile(self, user_id, profile_data):
            '''Update user profile'''
            pass

        def delete_account(self, user_id):
            '''Delete account and export data'''
            pass

        # Missing: Two-factor authentication setup!
    """

    pr_description = """
    Implements user management features from #123.

    Completed:
    - User registration with email verification
    - Profile updates
    - Account deletion with full data export

    Still TODO:
    - 2FA setup (will be in next PR)
    """

    result = validator.validate(requirements, code_changes, pr_description)

    assert result['success'] is True
    assert result['required_count'] == 4
    assert result['implemented_count'] == 3
    assert result['status'] == 'INCOMPLETE'
    # Should detect that 2FA is missing
    assert any('two' in feature.lower() or '2fa' in feature.lower()
               for feature in result.get('missing_features', []))
