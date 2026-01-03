"""Unit tests for dspy_optimization.py."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any, List

from coderabbit_ai.dspy_optimization import (
    OptimizationResult,
    MIPROOptimizer,
    SignatureOptimizer,
    create_optimized_pipeline,
    evaluate_pipeline_performance
)


class TestOptimizationResult:
    """Test OptimizationResult dataclass."""

    def test_optimization_result_creation(self):
        """Test creating OptimizationResult."""
        result = OptimizationResult(
            best_signature=Mock(),
            best_score=0.85,
            optimization_iterations=50,
            improvement_percentage=15.0,
            final_metrics={"final_score": 0.85},
            candidate_signatures=[{"iteration": 1, "score": 0.7}]
        )

        assert result.best_score == 0.85
        assert result.optimization_iterations == 50
        assert result.improvement_percentage == 15.0
        assert len(result.candidate_signatures) == 1


class TestMIPROOptimizerInit:
    """Test MIPROOptimizer initialization."""

    def test_init_with_defaults(self):
        """Test initialization with default values."""
        optimizer = MIPROOptimizer()

        assert optimizer.optimization_metric == "review_quality"
        assert optimizer.num_candidates == 50
        assert optimizer.init_temperature == 0.7
        assert optimizer.max_iterations == 100
        assert optimizer.evaluation_dataset_size == 200
        assert optimizer.best_score == 0.0
        assert len(optimizer.optimization_history) == 0

    def test_init_with_config(self):
        """Test initialization with custom config."""
        config = {
            "optimization_metric": "accuracy",
            "num_candidates": 100,
            "init_temperature": 0.5,
            "max_iterations": 200,
            "evaluation_dataset_size": 500
        }

        optimizer = MIPROOptimizer(config)

        assert optimizer.optimization_metric == "accuracy"
        assert optimizer.num_candidates == 100
        assert optimizer.init_temperature == 0.5
        assert optimizer.max_iterations == 200
        assert optimizer.evaluation_dataset_size == 500

    def test_init_partial_config(self):
        """Test initialization with partial config."""
        config = {
            "num_candidates": 75,
            "max_iterations": 150
        }

        optimizer = MIPROOptimizer(config)

        assert optimizer.num_candidates == 75
        assert optimizer.max_iterations == 150
        assert optimizer.optimization_metric == "review_quality"  # Default


class TestMIPROOptimizeSignature:
    """Test optimize_signature method."""

    @patch('coderabbit_ai.dspy_optimization.dspy')
    @patch('coderabbit_ai.dspy_optimization.random.random')
    def test_optimize_signature_success(self, mock_random, mock_dspy):
        """Test successful signature optimization."""
        # Mock DSPy classes
        mock_dspy.InputField = Mock
        mock_dspy.OutputField = Mock

        # Mock random to control acceptance
        mock_random.return_value = 0.1  # Accept

        # Create simple signature class
        class TestSignature:
            def __init__(self):
                pass

        optimizer = MIPROOptimizer(config={"max_iterations": 5, "num_candidates": 3})
        training_data = [{"input": "test"} * 10]

        result = optimizer.optimize_signature(TestSignature, training_data)

        assert isinstance(result, OptimizationResult)
        assert result.best_score >= 0.0
        assert result.optimization_iterations > 0
        assert result.final_metrics is not None

    @patch('coderabbit_ai.dspy_optimization.dspy')
    def test_optimize_signature_with_custom_eval(self, mock_dspy):
        """Test optimization with custom evaluation function."""
        mock_dspy.InputField = Mock
        mock_dspy.OutputField = Mock

        class TestSignature:
            def __init__(self):
                pass

        def custom_eval(sig, data):
            return 0.9

        optimizer = MIPROOptimizer(config={"max_iterations": 3})
        training_data = [{"input": "test"}]

        result = optimizer.optimize_signature(
            TestSignature,
            training_data,
            evaluation_function=custom_eval
        )

        assert result.best_score == 0.9

    def test_optimize_signature_empty_data(self):
        """Test optimization with empty training data."""
        optimizer = MIPROOptimizer()

        class TestSignature:
            def __init__(self):
                pass

        result = optimizer.optimize_signature(TestSignature, [])

        assert result.best_score == 0.0


class TestMIPROMutateSignature:
    """Test _mutate_signature method."""

    @patch('coderabbit_ai.dspy_optimization.dspy')
    def test_mutate_signature(self, mock_dspy):
        """Test signature mutation."""
        # Mock DSPy fields
        mock_input_field = Mock()
        mock_input_field.desc = "Test input"
        mock_dspy.InputField = Mock(return_value=mock_input_field)

        mock_output_field = Mock()
        mock_output_field.desc = "Test output"
        mock_dspy.OutputField = Mock(return_value=mock_output_field)

        class TestSignature:
            def __init__(self):
                self.input_field = mock_input_field
                self.output_field = mock_output_field

        optimizer = MIPROOptimizer()

        original = TestSignature()
        mutated = optimizer._mutate_signature(original)

        assert isinstance(mutated, TestSignature)
        assert mutated is not original


class TestMIPROMutateInputField:
    """Test _mutate_input_field method."""

    @patch('coderabbit_ai.dspy_optimization.dspy')
    def test_mutate_analysis_field(self, mock_dspy):
        """Test mutating analysis input field."""
        mock_field = Mock()
        mock_field.desc = "Code analysis task"
        mock_dspy.InputField = Mock(return_value=mock_field)

        optimizer = MIPROOptimizer()
        mutated = optimizer._mutate_input_field(mock_field)

        assert "Focus on accuracy" in mutated.desc

    @patch('coderabbit_ai.dspy_optimization.dspy')
    def test_mutate_review_field(self, mock_dspy):
        """Test mutating review input field."""
        mock_field = Mock()
        mock_field.desc = "Code review task"
        mock_dspy.InputField = Mock(return_value=mock_field)

        optimizer = MIPROOptimizer()
        mutated = optimizer._mutate_input_field(mock_field)

        assert "implementable suggestions" in mutated.desc

    @patch('coderabbit_ai.dspy_optimization.dspy')
    def test_mutate_context_field(self, mock_dspy):
        """Test mutating context input field."""
        mock_field = Mock()
        mock_field.desc = "Context extraction task"
        mock_dspy.InputField = Mock(return_value=mock_field)

        optimizer = MIPROOptimizer()
        mutated = optimizer._mutate_input_field(mock_field)

        assert "relevant patterns" in mutated.desc


class TestMIPROMutateOutputField:
    """Test _mutate_output_field method."""

    @patch('coderabbit_ai.dspy_optimization.dspy')
    def test_mutate_findings_field(self, mock_dspy):
        """Test mutating findings output field."""
        mock_field = Mock()
        mock_field.desc = "Security findings"
        mock_dspy.OutputField = Mock(return_value=mock_field)

        optimizer = MIPROOptimizer()
        mutated = optimizer._mutate_output_field(mock_field)

        assert "bullet points" in mutated.desc
        assert "severity levels" in mutated.desc

    @patch('coderabbit_ai.dspy_optimization.dspy')
    def test_mutate_improvements_field(self, mock_dspy):
        """Test mutating improvements output field."""
        mock_field = Mock()
        mock_field.desc = "Code improvements"
        mock_dspy.OutputField = Mock(return_value=mock_field)

        optimizer = MIPROOptimizer()
        mutated = optimizer._mutate_output_field(mock_field)

        assert "prioritize by impact" in mutated.desc


class TestMIPROCalculateQualityScore:
    """Test _calculate_quality_score method."""

    def test_quality_score_with_all_fields(self):
        """Test quality score with all output fields."""
        optimizer = MIPROOptimizer()

        mock_result = Mock()
        mock_result.enriched_context = "X" * 150
        mock_result.review_findings = "X" * 100
        mock_result.confidence_scores = [0.8, 0.9]
        mock_result.suggested_improvements = ["Improve X"]
        mock_result.filtered_findings = "X" * 100

        score = optimizer._calculate_quality_score(mock_result)

        assert score == 1.0  # Max score

    def test_quality_score_minimal(self):
        """Test quality score with minimal result."""
        optimizer = MIPROOptimizer()

        mock_result = Mock()
        # Remove all optional attributes
        del mock_result.enriched_context
        del mock_result.review_findings
        del mock_result.confidence_scores
        del mock_result.suggested_improvements
        del mock_result.filtered_findings

        score = optimizer._calculate_quality_score(mock_result)

        assert score == 0.5  # Base score

    def test_quality_score_partial(self):
        """Test quality score with some output fields."""
        optimizer = MIPROOptimizer()

        mock_result = Mock()
        mock_result.enriched_context = "X" * 150
        mock_result.review_findings = "X" * 100
        # Missing other fields
        del mock_result.confidence_scores
        del mock_result.suggested_improvements
        del mock_result.filtered_findings

        score = optimizer._calculate_quality_score(mock_result)

        assert score == 0.7  # Base + 0.1 + 0.1


class TestMIPROCalculateAcceptanceProbability:
    """Test _calculate_acceptance_probability method."""

    def test_acceptance_new_score_better(self):
        """Test acceptance when new score is better."""
        optimizer = MIPROOptimizer()
        prob = optimizer._calculate_acceptance_probability(0.9, 0.8, 0.5)

        assert prob == 1.0

    def test_acceptance_new_score_worse(self):
        """Test acceptance when new score is worse."""
        optimizer = MIPROOptimizer()
        prob = optimizer._calculate_acceptance_probability(0.7, 0.8, 0.5)

        assert prob < 1.0
        assert prob > 0.0

    def test_acceptance_zero_temperature(self):
        """Test acceptance with zero temperature."""
        optimizer = MIPROOptimizer()
        prob = optimizer._calculate_acceptance_probability(0.7, 0.8, 0.0)

        assert prob == 0.0

    def test_acceptance_equal_scores(self):
        """Test acceptance with equal scores."""
        optimizer = MIPROOptimizer()
        prob = optimizer._calculate_acceptance_probability(0.8, 0.8, 0.5)

        assert prob == 1.0


class TestMIPRONoRecentImprovement:
    """Test _no_recent_improvement method."""

    def test_no_improvement_empty_history(self):
        """Test with empty optimization history."""
        optimizer = MIPROOptimizer()

        result = optimizer._no_recent_improvement()

        assert result == False

    def test_no_improvement_short_history(self):
        """Test with short history (< window size)."""
        optimizer = MIPROOptimizer()
        optimizer.optimization_history = [
            {"best_score": 0.7},
            {"best_score": 0.75},
        ]

        result = optimizer._no_recent_improvement()

        assert result == False

    def test_no_improvement_stagnant(self):
        """Test with stagnant scores."""
        optimizer = MIPROOptimizer()
        optimizer.optimization_history = [
            {"best_score": 0.8} for _ in range(15)
        ]

        result = optimizer._no_recent_improvement()

        assert result == True

    def test_no_improvement_improving(self):
        """Test with improving scores."""
        optimizer = MIPROOptimizer()
        optimizer.optimization_history = [
            {"best_score": 0.5 + i * 0.02}
            for i in range(15)
        ]

        result = optimizer._no_recent_improvement()

        assert result == False


class TestMIPROCalculateStability:
    """Test _calculate_stability method."""

    def test_stability_empty_history(self):
        """Test stability with empty history."""
        optimizer = MIPROOptimizer()

        stability = optimizer._calculate_stability()

        assert stability == 0.0

    def test_stability_short_history(self):
        """Test stability with short history."""
        optimizer = MIPROOptimizer()
        optimizer.optimization_history = [
            {"best_score": 0.7},
            {"best_score": 0.75},
        ]

        stability = optimizer._calculate_stability()

        assert stability == 0.0

    def test_stability_consistent(self):
        """Test stability with consistent scores."""
        optimizer = MIPROOptimizer()
        optimizer.optimization_history = [
            {"best_score": 0.8 + (i % 2) * 0.01}
            for i in range(15)
        ]

        stability = optimizer._calculate_stability()

        assert stability > 0.8  # High stability

    def test_stability_variable(self):
        """Test stability with variable scores."""
        optimizer = MIPROOptimizer()
        optimizer.optimization_history = [
            {"best_score": 0.5 + i * 0.05}
            for i in range(15)
        ]

        stability = optimizer._calculate_stability()

        assert stability < 0.5  # Low stability


class TestMIPROCalculateEfficiencyMetrics:
    """Test _calculate_efficiency_metrics method."""

    def test_efficiency_empty_history(self):
        """Test efficiency with empty history."""
        optimizer = MIPROOptimizer()

        metrics = optimizer._calculate_efficiency_metrics()

        assert metrics == {}

    def test_efficiency_with_history(self):
        """Test efficiency with optimization history."""
        optimizer = MIPROOptimizer(config={"num_candidates": 10, "max_iterations": 50})
        optimizer.best_score = 0.85
        optimizer.optimization_history = [
            {"best_score": 0.7 + i * 0.01, "candidates_evaluated": 10}
            for i in range(10)
        ]

        metrics = optimizer._calculate_efficiency_metrics()

        assert "candidates_per_iteration" in metrics
        assert "exploration_efficiency" in metrics
        assert "optimization_speed" in metrics
        assert metrics["candidates_per_iteration"] == 10.0


class TestSignatureOptimizerInit:
    """Test SignatureOptimizer initialization."""

    def test_init_with_defaults(self):
        """Test initialization with defaults."""
        optimizer = SignatureOptimizer()

        assert optimizer.config == {}
        assert optimizer.optimizer is not None

    def test_init_with_config(self):
        """Test initialization with config."""
        config = {
            "optimization": {
                "max_iterations": 200,
                "num_candidates": 100
            }
        }

        optimizer = SignatureOptimizer(config)

        assert optimizer.config == config
        assert optimizer.optimizer.max_iterations == 200
        assert optimizer.optimizer.num_candidates == 100


class TestSignatureOptimizerOptimizeAll:
    """Test optimize_all_signatures method."""

    @patch('coderabbit_ai.dspy_optimization.MIPROOptimizer.optimize_signature')
    def test_optimize_all_signatures(self, mock_optimize):
        """Test optimizing all signatures."""
        mock_optimize.return_value = OptimizationResult(
            best_signature=Mock(),
            best_score=0.8,
            optimization_iterations=50,
            improvement_percentage=10.0,
            final_metrics={},
            candidate_signatures=[]
        )

        optimizer = SignatureOptimizer()
        training_data = {
            "context_engineering": [{"test": "data"}],
            "review_agent": [{"test": "data"}],
            "verification": [{"test": "data"}],
        }

        results = optimizer.optimize_all_signatures(training_data)

        assert "context_engineering" in results
        assert "review_agent" in results
        assert "verification" in results
        assert len(results) == 3

    @patch('coderabbit_ai.dspy_optimization.MIPROOptimizer.optimize_signature')
    def test_optimize_all_partial_data(self, mock_optimize):
        """Test optimizing with partial training data."""
        mock_optimize.return_value = OptimizationResult(
            best_signature=Mock(),
            best_score=0.8,
            optimization_iterations=50,
            improvement_percentage=10.0,
            final_metrics={},
            candidate_signatures=[]
        )

        optimizer = SignatureOptimizer()
        training_data = {
            "review_agent": [{"test": "data"}],
        }

        results = optimizer.optimize_all_signatures(training_data)

        assert "review_agent" in results
        assert len(results) == 1


class TestSignatureOptimizerReport:
    """Test get_optimization_report method."""

    def test_report_no_optimization(self):
        """Test report with no optimization performed."""
        optimizer = SignatureOptimizer()

        report = optimizer.get_optimization_report()

        assert report["status"] == "No optimization performed"

    @patch('coderabbit_ai.dspy_optimization.MIPROOptimizer.optimize_signature')
    def test_report_with_optimization(self, mock_optimize):
        """Test report with optimization history."""
        mock_optimize.return_value = OptimizationResult(
            best_signature=Mock(),
            best_score=0.85,
            optimization_iterations=10,
            improvement_percentage=15.0,
            final_metrics={},
            candidate_signatures=[]
        )

        optimizer = SignatureOptimizer()
        training_data = {"review_agent": [{"test": "data"}]}

        results = optimizer.optimize_all_signatures(training_data)
        report = optimizer.get_optimization_report()

        assert "optimization_summary" in report
        assert "performance_trends" in report
        assert "final_metrics" in report
        assert "recommendations" in report


class TestSignatureOptimizerRecommendations:
    """Test _generate_optimization_recommendations method."""

    @patch('coderabbit_ai.dspy_optimization.MIPROOptimizer.optimize_signature')
    def test_recommendations_low_score(self, mock_optimize):
        """Test recommendations for low final score."""
        mock_optimize.return_value = OptimizationResult(
            best_signature=Mock(),
            best_score=0.5,
            optimization_iterations=10,
            improvement_percentage=10.0,
            final_metrics={},
            candidate_signatures=[]
        )

        optimizer = SignatureOptimizer()
        optimizer.optimizer.optimization_history = [
            {"best_score": 0.5} for _ in range(10)
        ]

        recommendations = optimizer._generate_optimization_recommendations()

        assert len(recommendations) > 0
        assert any("training dataset" in rec for rec in recommendations)

    @patch('coderabbit_ai.dspy_optimization.MIPROOptimizer.optimize_signature')
    def test_recommendations_high_score(self, mock_optimize):
        """Test recommendations for high final score."""
        mock_optimize.return_value = OptimizationResult(
            best_signature=Mock(),
            best_score=0.95,
            optimization_iterations=10,
            improvement_percentage=15.0,
            final_metrics={},
            candidate_signatures=[]
        )

        optimizer = SignatureOptimizer()
        optimizer.optimizer.optimization_history = [
            {"best_score": 0.95} for _ in range(10)
        ]

        recommendations = optimizer._generate_optimization_recommendations()

        assert len(recommendations) > 0
        assert any("excellent results" in rec for rec in recommendations)


class TestCreateOptimizedPipeline:
    """Test create_optimized_pipeline function."""

    @patch('coderabbit_ai.dspy_optimization.ContextEngineeringAgent')
    @patch('coderabbit_ai.dspy_optimization.ReviewAgent')
    def test_create_pipeline_default_config(self, mock_review, mock_context):
        """Test creating pipeline with default config."""
        mock_context.return_value = Mock()
        mock_review.return_value = Mock()

        pipeline = create_optimized_pipeline()

        assert "agents" in pipeline
        assert "optimizer" in pipeline
        assert "optimization_config" in pipeline
        assert "performance_metrics" in pipeline
        assert "context_engineering" in pipeline["agents"]
        assert "review_agent" in pipeline["agents"]

    @patch('coderabbit_ai.dspy_optimization.ContextEngineeringAgent')
    @patch('coderabbit_ai.dspy_optimization.ReviewAgent')
    def test_create_pipeline_custom_config(self, mock_review, mock_context):
        """Test creating pipeline with custom config."""
        config = {
            "optimization": {
                "max_iterations": 200
            },
            "context_agent": {
                "model": "gpt-4"
            }
        }

        mock_context.return_value = Mock()
        mock_review.return_value = Mock()

        pipeline = create_optimized_pipeline(config)

        assert pipeline["optimization_config"] == config
        assert pipeline["optimizer"].optimizer.max_iterations == 200


class TestEvaluatePipelinePerformance:
    """Test evaluate_pipeline_performance function."""

    @patch('coderabbit_ai.dspy_optimization.ContextEngineeringAgent')
    @patch('coderabbit_ai.dspy_optimization.ReviewAgent')
    @patch('coderabbit_ai.dspy_optimization.ContextData')
    def test_evaluate_performance_success(self, mock_context_data, mock_review, mock_context):
        """Test successful pipeline evaluation."""
        # Mock context agent
        mock_context_result = Mock()
        mock_context_result.confidence_score = 0.85
        mock_context_result.processing_time_ms = 100
        mock_context.return_value.forward.return_value = mock_context_result

        # Mock review agent
        mock_review_result = Mock()
        mock_review_result.confidence_score = 0.90
        mock_review_result.processing_time_ms = 150
        mock_review.return_value.forward.return_value = mock_review_result

        # Mock ContextData
        mock_context_data.return_value = Mock()

        pipeline = {
            "agents": {
                "context_engineering": mock_context.return_value,
                "review_agent": mock_review.return_value
            }
        }

        test_data = [
            {
                "context_data": {"test": "data"},
                "code_changes": {"diff": "change"},
                "org_config": {}
            }
        ] * 10

        results = evaluate_pipeline_performance(pipeline, test_data)

        assert "average_context_score" in results
        assert "average_review_score" in results
        assert "average_composite_score" in results
        assert "average_processing_time_ms" in results
        assert "test_samples_evaluated" in results
        assert "success_rate" in results
        assert results["test_samples_evaluated"] == 10

    def test_evaluate_performance_no_data(self):
        """Test evaluation with no test data."""
        pipeline = {
            "agents": {
                "context_engineering": Mock(),
                "review_agent": Mock()
            }
        }

        results = evaluate_pipeline_performance(pipeline, [])

        assert results["error"] == "No valid performance results"

    @patch('coderabbit_ai.dspy_optimization.ContextEngineeringAgent')
    @patch('coderabbit_ai.dspy_optimization.ReviewAgent')
    @patch('coderabbit_ai.dspy_optimization.ContextData')
    def test_evaluate_performance_with_errors(self, mock_context_data, mock_review, mock_context):
        """Test evaluation with some errors."""
        # Mock context agent to fail sometimes
        mock_context.return_value.forward.side_effect = [
            Mock(confidence_score=0.85, processing_time_ms=100),
            Exception("Context error"),
            Mock(confidence_score=0.80, processing_time_ms=90),
        ]

        # Mock review agent
        mock_review_result = Mock()
        mock_review_result.confidence_score = 0.90
        mock_review_result.processing_time_ms = 150
        mock_review.return_value.forward.return_value = mock_review_result

        # Mock ContextData
        mock_context_data.return_value = Mock()

        pipeline = {
            "agents": {
                "context_engineering": mock_context.return_value,
                "review_agent": mock_review.return_value
            }
        }

        test_data = [
            {
                "context_data": {"test": "data"},
                "code_changes": {"diff": "change"},
                "org_config": {}
            }
        ] * 3

        results = evaluate_pipeline_performance(pipeline, test_data)

        assert results["test_samples_evaluated"] == 3
        assert "success_rate" in results
        assert results["success_rate"] < 1.0  # Not all succeeded
