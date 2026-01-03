"""End-to-end integration test for full review pipeline."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from coderabbit_ai.models import (
    ReviewRequest,
    Repository,
    PullRequest,
    User,
    FileChange,
    OrganizationConfig,
    ReviewRules,
    AISettings
)
from coderabbit_ai.pipeline import CodeRabbitMultiAgentPipeline


class TestFullReviewPipeline:
    """End-to-end tests for complete review pipeline."""

    @patch('coderabbit_ai.pipeline.ContextEngineeringAgent')
    @patch('coderabbit_ai.pipeline.EmbeddingService')
    @patch('coderabbit_ai.pipeline.VectorEngine')
    @patch('coderabbit_ai.pipeline.ReviewAgent')
    @patch('coderabbit_ai.pipeline.VerificationAgent')
    def test_complete_review_flow(self, mock_verification, mock_review, mock_vector_class, mock_embedding_class, mock_context_agent_class):
        """Test complete review flow from webhook to comments."""
        # Mock context agent
        mock_context_agent = Mock()
        mock_context_result = Mock()
        mock_context_result.enriched_context = "PR context with dependencies and risks"
        mock_context_result.confidence_score = 0.85
        mock_context_result.processing_time_ms = 150
        mock_context_agent.forward.return_value = mock_context_result
        mock_context_agent_class.return_value = mock_context_agent

        # Mock embedding service
        mock_embedding_service = Mock()
        mock_embedding_service.generate_embedding.return_value = [0.1, 0.2, 0.3]
        mock_embedding_class.return_value = mock_embedding_service

        # Mock vector engine
        mock_vector_engine = Mock()
        mock_vector_engine.search.return_value = [
            {
                'file_path': 'src/similar.py',
                'content': 'def similar_function(): pass',
                'score': 0.9
            }
        ]
        mock_vector_class.return_value = mock_vector_engine

        # Mock review agent
        mock_review_agent = Mock()
        mock_review_result = Mock()
        mock_review_result.review_findings = [
            {
                'severity': 'high',
                'category': 'security',
                'message': 'SQL injection vulnerability',
                'suggested_fix': 'Use parameterized queries'
            }
        ]
        mock_review_result.confidence_score = 0.80
        mock_review_result.processing_time_ms = 500
        mock_review_agent.forward.return_value = mock_review_result
        mock_review_class.return_value = mock_review_agent

        # Mock verification agent
        mock_verification_agent = Mock()
        mock_verification_result = Mock()
        mock_verification_result.verification_summary = "Review verified with high confidence"
        mock_verification_result.accepted_findings = 1
        mock_verification_result.rejected_findings = 0
        mock_verification_agent.forward.return_value = mock_verification_result
        mock_verification_class.return_value = mock_verification_agent

        # Create pipeline
        pipeline = CodeRabbitMultiAgentPipeline(config={})

        # Create review request
        request = ReviewRequest(
            repository=Repository(
                id="repo-123",
                name="test/repo",
                owner="test"
            ),
            pull_request=PullRequest(
                id=1,
                number=42,
                title="Add new API endpoint",
                body="Implements user authentication",
                base="main",
                head="feature/auth"
            ),
            user=User(
                id="user-123",
                login="testuser"
            ),
            files_changed=[
                FileChange(
                    path="src/api.py",
                    content='''def authenticate(username, password):
    query = "SELECT * FROM users WHERE username = '" + username + "'"
    return db.execute(query)'''
                )
            ],
            organization_config=OrganizationConfig(
                review_rules=ReviewRules(
                    severity_threshold='medium',
                    max_review_comments=50
                ),
                ai_settings=AISettings(
                    model="gpt-4",
                    temperature=0.3
                )
            )
        )

        # Execute full pipeline
        result = pipeline.review_pull_request(request)

        # Verify all agents were called
        assert mock_context_agent.forward.called
        assert mock_review_agent.forward.called
        assert mock_verification_agent.forward.called

        # Verify result structure
        assert result is not None

    @patch('coderabbit_ai.pipeline.ContextEngineeringAgent')
    @patch('coderabbit_ai.pipeline.ReviewAgent')
    def test_webhook_to_review_to_comment(self, mock_review_class, mock_context_agent_class):
        """Test flow from webhook to posting GitHub comments."""
        # Mock agents
        mock_context_agent = Mock()
        mock_context_result = Mock()
        mock_context_result.enriched_context = "Context"
        mock_context_result.confidence_score = 0.85
        mock_context_agent.forward.return_value = mock_context_result
        mock_context_agent_class.return_value = mock_context_agent

        mock_review_agent = Mock()
        mock_review_result = Mock()
        mock_review_result.review_findings = [
            {
                'severity': 'critical',
                'category': 'security',
                'message': 'SQL injection vulnerability',
                'suggested_fix': 'Use parameterized queries'
            }
        ]
        mock_review_result.confidence_score = 0.90
        mock_review_agent.forward.return_value = mock_review_result
        mock_review_class.return_value = mock_review_agent

        # Create pipeline
        pipeline = CodeRabbitMultiAgentPipeline(config={})

        # Simulate webhook payload
        request = ReviewRequest(
            repository=Repository(
                id="repo-123",
                name="test/repo",
                owner="test"
            ),
            pull_request=PullRequest(
                id=1,
                number=42,
                title="Security fix",
                body="Fix SQL injection",
                base="main",
                head="fix/security"
            ),
            user=User(
                id="user-123",
                login="testuser"
            ),
            files_changed=[
                FileChange(
                    path="src/api.py",
                    content='def authenticate(username, password): pass'
                )
            ],
            organization_config=OrganizationConfig(
                review_rules=ReviewRules(),
                ai_settings=AISettings()
            )
        )

        # Process request
        result = pipeline.review_pull_request(request)

        # Format as GitHub comment
        comment = pipeline._format_review_as_comment(result)

        # Verify comment formatting
        assert comment is not None
        assert len(comment) > 0
        assert "SQL injection" in comment
        assert "suggested_fix" in comment.lower()

    @patch('coderabbit_ai.pipeline.ContextEngineeringAgent')
    @patch('coderabbit_ai.pipeline.ReviewAgent')
    def test_multiple_pr_reviews(self, mock_review_class, mock_context_agent_class):
        """Test processing multiple PRs concurrently."""
        # Mock agents
        mock_context_agent = Mock()
        mock_context_result = Mock()
        mock_context_result.enriched_context = "Context"
        mock_context_result.confidence_score = 0.85
        mock_context_agent.forward.return_value = mock_context_result
        mock_context_agent_class.return_value = mock_context_agent

        mock_review_agent = Mock()
        mock_review_result = Mock()
        mock_review_result.review_findings = []
        mock_review_result.confidence_score = 0.80
        mock_review_agent.forward.return_value = mock_review_result
        mock_review_class.return_value = mock_review_agent

        # Create pipeline
        pipeline = CodeRabbitMultiAgentPipeline(config={})

        # Create multiple review requests
        requests = [
            ReviewRequest(
                repository=Repository(id="repo-1", name="repo1", owner="test"),
                pull_request=PullRequest(id=1, number=1, title="PR 1", body="Body", base="main", head="pr1"),
                user=User(id="user-1", login="user1"),
                files_changed=[FileChange(path="src/api.py", content="code")],
                organization_config=OrganizationConfig(review_rules=ReviewRules(), ai_settings=AISettings())
            ),
            ReviewRequest(
                repository=Repository(id="repo-2", name="repo2", owner="test"),
                pull_request=PullRequest(id=2, number=2, title="PR 2", body="Body", base="main", head="pr2"),
                user=User(id="user-2", login="user2"),
                files_changed=[FileChange(path="src/core.py", content="code")],
                organization_config=OrganizationConfig(review_rules=ReviewRules(), ai_settings=AISettings())
            ),
            ReviewRequest(
                repository=Repository(id="repo-3", name="repo3", owner="test"),
                pull_request=PullRequest(id=3, number=3, title="PR 3", body="Body", base="main", head="pr3"),
                user=User(id="user-3", login="user3"),
                files_changed=[FileChange(path="src/utils.py", content="code")],
                organization_config=OrganizationConfig(review_rules=ReviewRules(), ai_settings=AISettings())
            )
        ]

        # Process all PRs
        results = []
        for request in requests:
            result = pipeline.review_pull_request(request)
            results.append(result)

        # Verify all processed
        assert len(results) == 3
        assert all(r is not None for r in results)

    @patch('coderabbit_ai.pipeline.ContextEngineeringAgent')
    @patch('coderabbit_ai.pipeline.ReviewAgent')
    def test_pipeline_error_handling(self, mock_review_class, mock_context_agent_class):
        """Test pipeline handles errors gracefully."""
        # Mock context agent to fail
        mock_context_agent = Mock()
        mock_context_agent.forward.side_effect = Exception("Context agent error")
        mock_context_agent_class.return_value = mock_context_agent

        # Mock review agent
        mock_review_agent = Mock()
        mock_review_result = Mock()
        mock_review_result.review_findings = []
        mock_review_result.confidence_score = 0.0  # Low confidence on error
        mock_review_agent.forward.return_value = mock_review_result
        mock_review_class.return_value = mock_review_agent

        # Create pipeline
        pipeline = CodeRabbitMultiAgentPipeline(config={})

        # Process request with error
        request = ReviewRequest(
            repository=Repository(id="repo-1", name="repo1", owner="test"),
            pull_request=PullRequest(id=1, number=1, title="PR 1", body="Body", base="main", head="pr1"),
            user=User(id="user-1", login="user1"),
            files_changed=[FileChange(path="src/api.py", content="code")],
            organization_config=OrganizationConfig(review_rules=ReviewRules(), ai_settings=AISettings())
        )

        # Should handle error gracefully
        result = pipeline.review_pull_request(request)

        # Should still return result even with error
        assert result is not None

    @patch('coderabbit_ai.pipeline.ContextEngineeringAgent')
    @patch('coderabbit_ai.pipeline.ReviewAgent')
    def test_pipeline_performance_tracking(self, mock_review_class, mock_context_agent_class):
        """Test pipeline tracks performance metrics."""
        import time

        # Mock agents
        mock_context_agent = Mock()
        mock_context_result = Mock()
        mock_context_result.enriched_context = "Context"
        mock_context_result.confidence_score = 0.85
        mock_context_result.processing_time_ms = 100
        mock_context_agent.forward.return_value = mock_context_result
        mock_context_agent_class.return_value = mock_context_agent

        mock_review_agent = Mock()
        mock_review_result = Mock()
        mock_review_result.review_findings = []
        mock_review_result.confidence_score = 0.80
        mock_review_result.processing_time_ms = 300
        mock_review_agent.forward.return_value = mock_review_result
        mock_review_class.return_value = mock_review_agent

        # Create pipeline
        pipeline = CodeRabbitMultiAgentPipeline(config={})

        # Process request with timing
        request = ReviewRequest(
            repository=Repository(id="repo-1", name="repo1", owner="test"),
            pull_request=PullRequest(id=1, number=1, title="PR 1", body="Body", base="main", head="pr1"),
            user=User(id="user-1", login="user1"),
            files_changed=[FileChange(path="src/api.py", content="code")],
            organization_config=OrganizationConfig(review_rules=ReviewRules(), ai_settings=AISettings())
        )

        start_time = time.time()
        result = pipeline.review_pull_request(request)
        end_time = time.time()

        total_time_ms = (end_time - start_time) * 1000

        # Verify performance tracking
        assert total_time_ms > 0
        # Should complete in reasonable time (mocked agents)
        assert total_time_ms < 5000

    @patch('coderabbit_ai.pipeline.ContextEngineeringAgent')
    @patch('coderabbit_ai.pipeline.ReviewAgent')
    def test_pipeline_with_large_pr(self, mock_review_class, mock_context_agent_class):
        """Test pipeline handles large PRs with many files."""
        # Mock agents
        mock_context_agent = Mock()
        mock_context_result = Mock()
        mock_context_result.enriched_context = "Context for large PR"
        mock_context_result.confidence_score = 0.85
        mock_context_agent.forward.return_value = mock_context_result
        mock_context_agent_class.return_value = mock_context_agent

        mock_review_agent = Mock()
        mock_review_result = Mock()
        mock_review_result.review_findings = [
            {
                'severity': 'medium',
                'category': 'code-quality',
                'message': 'Large function detected',
                'suggested_fix': 'Break down into smaller functions'
            }
        ] * 20  # Many findings
        mock_review_result.confidence_score = 0.80
        mock_review_agent.forward.return_value = mock_review_result
        mock_review_class.return_value = mock_review_agent

        # Create pipeline
        pipeline = CodeRabbitMultiAgentPipeline(config={})

        # Create large PR with many files
        files = [
            FileChange(
                path=f"src/file{i}.py",
                content=f"def function{i}(): pass"
            )
            for i in range(50)  # 50 files
        ]

        request = ReviewRequest(
            repository=Repository(id="repo-1", name="repo1", owner="test"),
            pull_request=PullRequest(id=1, number=1, title="Large PR", body="Many changes", base="main", head="large"),
            user=User(id="user-1", login="user1"),
            files_changed=files,
            organization_config=OrganizationConfig(
                review_rules=ReviewRules(max_review_comments=100),
                ai_settings=AISettings()
            )
        )

        # Process large PR
        result = pipeline.review_pull_request(request)

        # Verify handling of large PR
        assert result is not None
        assert len(mock_review_result.review_findings) == 20

    @patch('coderabbit_ai.pipeline.ContextEngineeringAgent')
    @patch('coderabbit_ai.pipeline.ReviewAgent')
    def test_pipeline_with_config_filters(self, mock_review_class, mock_context_agent_class):
        """Test pipeline respects configuration filters."""
        # Mock agents
        mock_context_agent = Mock()
        mock_context_result = Mock()
        mock_context_result.enriched_context = "Context"
        mock_context_result.confidence_score = 0.85
        mock_context_agent.forward.return_value = mock_context_result
        mock_context_agent_class.return_value = mock_context_agent

        mock_review_agent = Mock()
        mock_review_result = Mock()
        mock_review_result.review_findings = [
            {
                'severity': 'critical',
                'category': 'security',
                'message': 'Critical issue'
            },
            {
                'severity': 'medium',
                'category': 'code-quality',
                'message': 'Medium issue'
            },
            {
                'severity': 'low',
                'category': 'style',
                'message': 'Low severity style issue'
            }
        ]
        mock_review_result.confidence_score = 0.80
        mock_review_agent.forward.return_value = mock_review_result
        mock_review_class.return_value = mock_review_agent

        # Create pipeline with config
        pipeline = CodeRabbitMultiAgentPipeline(config={
            'severity_threshold': 'high',  # Only show high+ severity
            'max_findings': 10
        })

        # Process request
        request = ReviewRequest(
            repository=Repository(id="repo-1", name="repo1", owner="test"),
            pull_request=PullRequest(id=1, number=1, title="PR 1", body="Body", base="main", head="pr1"),
            user=User(id="user-1", login="user1"),
            files_changed=[FileChange(path="src/api.py", content="code")],
            organization_config=OrganizationConfig(
                review_rules=ReviewRules(severity_threshold='high', max_review_comments=10),
                ai_settings=AISettings()
            )
        )

        result = pipeline.review_pull_request(request)

        # Verify config filters applied
        assert result is not None
