"""DSPy optimization with MIPRO for enhanced AI pipeline performance."""

import dspy
import random
import time
from typing import Dict, Any, List, Optional, Callable, Tuple
from collections import defaultdict
import json
from dataclasses import dataclass
from ..agents.context_engineering import ContextEngineeringAgent
from ..agents.review_agent import ReviewAgent
from ..models import ContextData, ContextEngineeringResponse, ReviewAgentResponse


@dataclass
class OptimizationResult:
    """Result from DSPy optimization process."""
    best_signature: Any
    best_score: float
    optimization_iterations: int
    improvement_percentage: float
    final_metrics: Dict[str, float]
    candidate_signatures: List[Dict[str, Any]]


class MIPROOptimizer:
    """MIPRO (Multi-prompt Instruction Proposal and Optimization) for DSPy signatures."""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.optimization_metric = self.config.get("optimization_metric", "review_quality")
        self.num_candidates = self.config.get("num_candidates", 50)
        self.init_temperature = self.config.get("init_temperature", 0.7)
        self.max_iterations = self.config.get("max_iterations", 100)
        self.evaluation_dataset_size = self.config.get("evaluation_dataset_size", 200)
        
        # Internal state
        self.current_signature = None
        self.best_signature = None
        self.best_score = 0.0
        self.optimization_history = []
        self.performance_metrics = defaultdict(list)
        
    def optimize_signature(
        self, 
        base_signature_class: type,
        training_data: List[Dict[str, Any]],
        evaluation_function: Optional[Callable] = None
    ) -> OptimizationResult:
        """
        Optimize a DSPy signature using MIPRO algorithm.
        
        Args:
            base_signature_class: The base signature class to optimize
            training_data: Training data for optimization
            evaluation_function: Custom evaluation function
            
        Returns:
            OptimizationResult with best signature and metrics
        """
        print(f"Starting MIPRO optimization for {base_signature_class.__name__}")
        print(f"Training data size: {len(training_data)}")
        print(f"Optimization metric: {self.optimization_metric}")
        
        # Initialize with base signature
        self.current_signature = base_signature_class()
        self.best_signature = base_signature_class()
        
        # Initial evaluation
        initial_score = self._evaluate_signature(self.current_signature, training_data, evaluation_function)
        self.best_score = initial_score
        
        print(f"Initial score: {initial_score:.4f}")
        
        # MIPRO optimization loop
        for iteration in range(self.max_iterations):
            # Generate candidate signatures
            candidates = self._generate_candidates()
            
            # Evaluate candidates
            best_candidate = None
            best_candidate_score = -1
            
            for candidate in candidates:
                score = self._evaluate_signature(candidate, training_data, evaluation_function)
                
                # Acceptance probability (simulated annealing)
                temperature = self.init_temperature * (1 - iteration / self.max_iterations)
                acceptance_prob = self._calculate_acceptance_probability(
                    score, self.best_score, temperature
                )
                
                if random.random() < acceptance_prob:
                    if score > best_candidate_score:
                        best_candidate = candidate
                        best_candidate_score = score
                        
                        if score > self.best_score:
                            self.best_signature = candidate
                            self.best_score = score
            
            # Record optimization progress
            self.optimization_history.append({
                "iteration": iteration + 1,
                "best_score": self.best_score,
                "temperature": temperature if 'temperature' in locals() else 0.0,
                "candidates_evaluated": len(candidates)
            })
            
            # Early stopping if no improvement for several iterations
            if iteration > 20 and self._no_recent_improvement():
                print(f"Early stopping at iteration {iteration + 1}")
                break
            
            if (iteration + 1) % 20 == 0:
                print(f"Iteration {iteration + 1}: Best score = {self.best_score:.4f}")
        
        # Final evaluation
        final_metrics = self._compute_final_metrics(training_data, evaluation_function)
        
        result = OptimizationResult(
            best_signature=self.best_signature,
            best_score=self.best_score,
            optimization_iterations=len(self.optimization_history),
            improvement_percentage=((self.best_score - initial_score) / initial_score) * 100,
            final_metrics=final_metrics,
            candidate_signatures=self.optimization_history
        )
        
        print(f"Optimization complete!")
        print(f"Final score: {self.best_score:.4f}")
        print(f"Improvement: {result.improvement_percentage:.2f}%")
        
        return result
    
    def _generate_candidates(self) -> List[Any]:
        """Generate candidate signatures through mutations."""
        candidates = []
        
        for _ in range(self.num_candidates):
            candidate = self._mutate_signature(self.current_signature)
            candidates.append(candidate)
        
        return candidates
    
    def _mutate_signature(self, signature: Any) -> Any:
        """Create a mutated version of the signature."""
        # Create a new instance with potentially modified fields
        mutated = type(signature)()
        
        # Copy and potentially mutate each field
        for field_name in dir(signature):
            if not field_name.startswith('_'):
                try:
                    field_value = getattr(signature, field_name)
                    
                    # Apply mutations based on field type
                    if isinstance(field_value, dspy.InputField):
                        mutated_field = self._mutate_input_field(field_value)
                        setattr(mutated, field_name, mutated_field)
                    elif isinstance(field_value, dspy.OutputField):
                        mutated_field = self._mutate_output_field(field_value)
                        setattr(mutated, field_name, mutated_field)
                    else:
                        setattr(mutated, field_name, field_value)
                        
                except (AttributeError, TypeError):
                    # Skip fields that can't be copied
                    continue
        
        return mutated
    
    def _mutate_input_field(self, field: dspy.InputField) -> dspy.InputField:
        """Mutate an input field."""
        # Add contextual hints for better performance
        enhanced_description = field.desc
        
        # Add performance optimization hints
        if "analysis" in enhanced_description.lower():
            enhanced_description += " Focus on accuracy and actionable insights."
        elif "review" in enhanced_description.lower():
            enhanced_description += " Provide specific, implementable suggestions."
        elif "context" in enhanced_description.lower():
            enhanced_description += " Extract relevant patterns and relationships."
        
        return dspy.InputField(desc=enhanced_description)
    
    def _mutate_output_field(self, field: dspy.OutputField) -> dspy.OutputField:
        """Mutate an output field."""
        # Enhance output field descriptions
        enhanced_description = field.desc
        
        # Add formatting guidance
        if "findings" in enhanced_description.lower():
            enhanced_description += " Structure as bullet points with severity levels."
        elif "improvements" in enhanced_description.lower():
            enhanced_description += " Prioritize by impact and feasibility."
        elif "confidence" in enhanced_description.lower():
            enhanced_description += " Use numerical scores from 0.0 to 1.0."
        
        return dspy.OutputField(desc=enhanced_description)
    
    def _evaluate_signature(
        self, 
        signature: Any, 
        training_data: List[Dict[str, Any]],
        evaluation_function: Optional[Callable] = None
    ) -> float:
        """Evaluate a signature's performance."""
        if evaluation_function:
            return evaluation_function(signature, training_data)
        
        # Default evaluation: measure review quality
        return self._default_evaluation(signature, training_data)
    
    def _default_evaluation(self, signature: Any, training_data: List[Dict[str, Any]]) -> float:
        """Default evaluation function for signature quality."""
        total_score = 0.0
        valid_evaluations = 0
        
        # Sample evaluation data
        sample_size = min(len(training_data), self.evaluation_dataset_size)
        sample_data = random.sample(training_data, sample_size)
        
        for data_point in sample_data:
            try:
                # Create a temporary module to test the signature
                temp_module = type('TempModule', (dspy.Module,), {
                    'forward': dspy.ChainOfThought(signature)
                })()
                
                # Test with sample data
                result = temp_module.forward(**data_point)
                
                # Calculate quality score based on result properties
                quality_score = self._calculate_quality_score(result)
                total_score += quality_score
                valid_evaluations += 1
                
            except Exception as e:
                # Penalize signatures that fail
                total_score += 0.1
                valid_evaluations += 1
        
        return total_score / valid_evaluations if valid_evaluations > 0 else 0.0
    
    def _calculate_quality_score(self, result: Any) -> float:
        """Calculate quality score for a signature result."""
        score = 0.5  # Base score
        
        # Check for meaningful content in outputs
        if hasattr(result, 'enriched_context') and len(str(result.enriched_context)) > 100:
            score += 0.1
        if hasattr(result, 'review_findings') and len(str(result.review_findings)) > 50:
            score += 0.1
        if hasattr(result, 'confidence_scores'):
            score += 0.1
        if hasattr(result, 'suggested_improvements'):
            score += 0.1
        if hasattr(result, 'filtered_findings') and len(str(result.filtered_findings)) > 50:
            score += 0.1
        
        return min(1.0, score)
    
    def _calculate_acceptance_probability(self, new_score: float, best_score: float, temperature: float) -> float:
        """Calculate acceptance probability for simulated annealing."""
        if new_score > best_score:
            return 1.0
        
        if temperature <= 0:
            return 0.0
        
        return (new_score - best_score) / (temperature * 10)
    
    def _no_recent_improvement(self, window_size: int = 10) -> bool:
        """Check if there's been no improvement in recent iterations."""
        if len(self.optimization_history) < window_size:
            return False
        
        recent_scores = [h["best_score"] for h in self.optimization_history[-window_size:]]
        return len(set(recent_scores)) == 1  # All scores are the same
    
    def _compute_final_metrics(self, training_data: List[Dict[str, Any]], evaluation_function: Optional[Callable]) -> Dict[str, float]:
        """Compute final performance metrics."""
        if len(self.optimization_history) == 0:
            return {}
        
        metrics = {
            "final_score": self.best_score,
            "improvement_rate": self._calculate_improvement_rate(),
            "convergence_iteration": self._find_convergence_iteration(),
            "optimization_stability": self._calculate_stability(),
        }
        
        # Add efficiency metrics
        metrics.update(self._calculate_efficiency_metrics())
        
        return metrics
    
    def _calculate_improvement_rate(self) -> float:
        """Calculate the rate of improvement during optimization."""
        if len(self.optimization_history) < 2:
            return 0.0
        
        first_score = self.optimization_history[0]["best_score"]
        last_score = self.optimization_history[-1]["best_score"]
        
        if first_score == 0:
            return float('inf') if last_score > 0 else 0.0
        
        return ((last_score - first_score) / first_score) * 100
    
    def _find_convergence_iteration(self) -> int:
        """Find when the optimization converged."""
        if len(self.optimization_history) < 10:
            return len(self.optimization_history)
        
        # Look for the iteration where 95% of final improvement was achieved
        final_improvement = self.optimization_history[-1]["best_score"] - self.optimization_history[0]["best_score"]
        target_improvement = final_improvement * 0.95
        
        for i, history in enumerate(self.optimization_history):
            current_improvement = history["best_score"] - self.optimization_history[0]["best_score"]
            if current_improvement >= target_improvement:
                return i + 1
        
        return len(self.optimization_history)
    
    def _calculate_stability(self) -> float:
        """Calculate optimization stability (lower variance = higher stability)."""
        if len(self.optimization_history) < 5:
            return 0.0
        
        scores = [h["best_score"] for h in self.optimization_history[-10:]]  # Last 10 iterations
        
        if len(scores) < 2:
            return 0.0
        
        mean_score = sum(scores) / len(scores)
        variance = sum((score - mean_score) ** 2 for score in scores) / len(scores)
        
        # Return stability as inverse of coefficient of variation
        if mean_score == 0:
            return 0.0
        
        cv = (variance ** 0.5) / mean_score
        return max(0.0, 1.0 - cv)
    
    def _calculate_efficiency_metrics(self) -> Dict[str, float]:
        """Calculate optimization efficiency metrics."""
        if not self.optimization_history:
            return {}
        
        total_candidates = sum(h["candidates_evaluated"] for h in self.optimization_history)
        total_iterations = len(self.optimization_history)
        
        return {
            "candidates_per_iteration": total_candidates / total_iterations,
            "exploration_efficiency": self.best_score / total_candidates if total_candidates > 0 else 0.0,
            "optimization_speed": total_iterations / self.max_iterations,
        }


class SignatureOptimizer:
    """High-level interface for optimizing DSPy signatures."""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.optimizer = MIPROOptimizer(self.config.get("mipro", {}))
        
    def optimize_context_engineering_signature(self, training_data: List[Dict[str, Any]]) -> OptimizationResult:
        """Optimize the Context Engineering signature."""
        return self.optimizer.optimize_signature(
            base_signature_class=ContextEngineeringSignature,
            training_data=training_data
        )
    
    def optimize_review_agent_signature(self, training_data: List[Dict[str, Any]]) -> OptimizationResult:
        """Optimize the Review Agent signature."""
        return self.optimizer.optimize_signature(
            base_signature_class=ReviewAgentSignature,
            training_data=training_data
        )
    
    def optimize_verification_signature(self, training_data: List[Dict[str, Any]]) -> OptimizationResult:
        """Optimize the Verification Agent signature."""
        return self.optimizer.optimize_signature(
            base_signature_class=VerificationAgentSignature,
            training_data=training_data
        )

    def optimize_security_analysis_signature(self, training_data: List[Dict[str, Any]]) -> OptimizationResult:
        """Optimize the Security Analysis signature."""
        return self.optimizer.optimize_signature(
            base_signature_class=SecurityAnalysisSignature,
            training_data=training_data
        )

    def optimize_performance_analysis_signature(self, training_data: List[Dict[str, Any]]) -> OptimizationResult:
        """Optimize the Performance Analysis signature."""
        return self.optimizer.optimize_signature(
            base_signature_class=PerformanceAnalysisSignature,
            training_data=training_data
        )

    def optimize_code_quality_signature(self, training_data: List[Dict[str, Any]]) -> OptimizationResult:
        """Optimize the Code Quality signature."""
        return self.optimizer.optimize_signature(
            base_signature_class=CodeQualitySignature,
            training_data=training_data
        )

    def optimize_documentation_review_signature(self, training_data: List[Dict[str, Any]]) -> OptimizationResult:
        """Optimize the Documentation Review signature."""
        return self.optimizer.optimize_signature(
            base_signature_class=DocumentationReviewSignature,
            training_data=training_data
        )

    def optimize_test_coverage_signature(self, training_data: List[Dict[str, Any]]) -> OptimizationResult:
        """Optimize the Test Coverage signature."""
        return self.optimizer.optimize_signature(
            base_signature_class=TestCoverageSignature,
            training_data=training_data
        )

    def optimize_architecture_review_signature(self, training_data: List[Dict[str, Any]]) -> OptimizationResult:
        """Optimize the Architecture Review signature."""
        return self.optimizer.optimize_signature(
            base_signature_class=ArchitectureReviewSignature,
            training_data=training_data
        )

    def optimize_api_design_signature(self, training_data: List[Dict[str, Any]]) -> OptimizationResult:
        """Optimize the API Design signature."""
        return self.optimizer.optimize_signature(
            base_signature_class=APIDesignSignature,
            training_data=training_data
        )

    def optimize_dependency_analysis_signature(self, training_data: List[Dict[str, Any]]) -> OptimizationResult:
        """Optimize the Dependency Analysis signature."""
        return self.optimizer.optimize_signature(
            base_signature_class=DependencyAnalysisSignature,
            training_data=training_data
        )

    def optimize_all_signatures(self, training_data: Dict[str, List[Dict[str, Any]]]) -> Dict[str, OptimizationResult]:
        """Optimize all available signatures with appropriate training data."""
        results = {}

        if "context_engineering" in training_data:
            results["context_engineering"] = self.optimize_context_engineering_signature(
                training_data["context_engineering"]
            )

        if "review_agent" in training_data:
            results["review_agent"] = self.optimize_review_agent_signature(
                training_data["review_agent"]
            )

        if "verification" in training_data:
            results["verification"] = self.optimize_verification_signature(
                training_data["verification"]
            )

        if "security_analysis" in training_data:
            results["security_analysis"] = self.optimize_security_analysis_signature(
                training_data["security_analysis"]
            )

        if "performance_analysis" in training_data:
            results["performance_analysis"] = self.optimize_performance_analysis_signature(
                training_data["performance_analysis"]
            )

        if "code_quality" in training_data:
            results["code_quality"] = self.optimize_code_quality_signature(
                training_data["code_quality"]
            )

        if "documentation_review" in training_data:
            results["documentation_review"] = self.optimize_documentation_review_signature(
                training_data["documentation_review"]
            )

        if "test_coverage" in training_data:
            results["test_coverage"] = self.optimize_test_coverage_signature(
                training_data["test_coverage"]
            )

        if "architecture_review" in training_data:
            results["architecture_review"] = self.optimize_architecture_review_signature(
                training_data["architecture_review"]
            )

        if "api_design" in training_data:
            results["api_design"] = self.optimize_api_design_signature(
                training_data["api_design"]
            )

        if "dependency_analysis" in training_data:
            results["dependency_analysis"] = self.optimize_dependency_analysis_signature(
                training_data["dependency_analysis"]
            )

        return results

    def get_optimization_report(self) -> Dict[str, Any]:
        """Generate a comprehensive optimization report."""
        if not self.optimizer.optimization_history:
            return {"status": "No optimization performed"}
        
        history = self.optimizer.optimization_history
        
        return {
            "optimization_summary": {
                "total_iterations": len(history),
                "final_score": history[-1]["best_score"],
                "improvement_percentage": ((history[-1]["best_score"] - history[0]["best_score"]) / history[0]["best_score"]) * 100,
                "optimization_metric": self.optimizer.optimization_metric
            },
            "performance_trends": {
                "score_progression": [h["best_score"] for h in history],
                "temperature_schedule": [h["temperature"] for h in history if "temperature" in h],
                "candidates_per_iteration": [h["candidates_evaluated"] for h in history]
            },
            "final_metrics": self.optimizer._compute_final_metrics([], None),
            "recommendations": self._generate_optimization_recommendations()
        }
    
    def _generate_optimization_recommendations(self) -> List[str]:
        """Generate recommendations based on optimization results."""
        recommendations = []
        
        if not self.optimizer.optimization_history:
            return ["No optimization data available"]
        
        history = self.optimizer.optimization_history
        final_score = history[-1]["best_score"]
        
        if final_score < 0.6:
            recommendations.append("Consider using a larger training dataset or different optimization approach")
        elif final_score > 0.9:
            recommendations.append("Optimization achieved excellent results. Consider reducing iterations for efficiency")
        
        if len(history) == self.optimizer.max_iterations:
            recommendations.append("Optimization reached maximum iterations. Consider adjusting parameters")
        
        # Check for early convergence
        convergence_iteration = self.optimizer._find_convergence_iteration()
        if convergence_iteration < len(history) * 0.3:
            recommendations.append("Early convergence detected. Consider starting with more diverse candidates")
        
        return recommendations


# Import required signatures
from ..models import (
    ContextEngineeringSignature,
    ReviewAgentSignature,
    VerificationAgentSignature,
    SecurityAnalysisSignature,
    PerformanceAnalysisSignature,
    CodeQualitySignature,
    DocumentationReviewSignature,
    TestCoverageSignature,
    ArchitectureReviewSignature,
    APIDesignSignature,
    DependencyAnalysisSignature,
)


def create_optimized_pipeline(config: Dict[str, Any] = None) -> Dict[str, Any]:
    """Create an optimized AI pipeline using MIPRO results."""
    optimizer_config = config or {}
    
    # Initialize components with optimization
    context_agent = ContextEngineeringAgent(optimizer_config.get("context_agent", {}))
    review_agent = ReviewAgent(optimizer_config.get("review_agent", {}))
    
    # Optimization configuration
    signature_optimizer = SignatureOptimizer(optimizer_config.get("optimization", {}))
    
    pipeline_config = {
        "agents": {
            "context_engineering": context_agent,
            "review_agent": review_agent,
        },
        "optimizer": signature_optimizer,
        "optimization_config": optimizer_config,
        "performance_metrics": {}
    }
    
    return pipeline_config


def evaluate_pipeline_performance(pipeline: Dict[str, Any], test_data: List[Dict[str, Any]]) -> Dict[str, float]:
    """Evaluate the performance of an optimized pipeline."""
    agents = pipeline["agents"]
    performance_results = []
    
    for data_point in test_data[:50]:  # Limit for performance
        try:
            # Test context engineering
            context_data = ContextData(**data_point["context_data"])
            context_result = agents["context_engineering"].forward(context_data)
            
            # Test review agent
            review_result = agents["review_agent"].forward(
                context_response=context_result,
                code_changes=data_point["code_changes"],
                org_config=data_point.get("org_config", {})
            )
            
            # Calculate composite score
            context_score = context_result.confidence_score
            review_score = review_result.confidence_score
            composite_score = (context_score + review_score) / 2
            
            performance_results.append({
                "context_score": context_score,
                "review_score": review_score,
                "composite_score": composite_score,
                "processing_time": context_result.processing_time_ms + review_result.processing_time_ms
            })
            
        except Exception as e:
            # Log error but continue evaluation
            performance_results.append({
                "context_score": 0.0,
                "review_score": 0.0,
                "composite_score": 0.0,
                "processing_time": 0
            })
    
    # Aggregate metrics
    if not performance_results:
        return {"error": "No valid performance results"}
    
    avg_context_score = sum(r["context_score"] for r in performance_results) / len(performance_results)
    avg_review_score = sum(r["review_score"] for r in performance_results) / len(performance_results)
    avg_composite_score = sum(r["composite_score"] for r in performance_results) / len(performance_results)
    avg_processing_time = sum(r["processing_time"] for r in performance_results) / len(performance_results)
    
    return {
        "average_context_score": avg_context_score,
        "average_review_score": avg_review_score,
        "average_composite_score": avg_composite_score,
        "average_processing_time_ms": avg_processing_time,
        "test_samples_evaluated": len(performance_results),
        "success_rate": len([r for r in performance_results if r["composite_score"] > 0.5]) / len(performance_results)
    }
