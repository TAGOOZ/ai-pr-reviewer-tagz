"""Review Agent for primary code review analysis with enhanced multi-model routing."""

import dspy
import time
import json
import re
from typing import Dict, Any, List, Tuple, Optional
from ..models import ReviewAgentResponse, ContextEngineeringResponse, ReviewAgentSignature


class EnhancedModelRouter:
    """Advanced intelligent model selection with cost-quality optimization."""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.models = {
            "claude-3-5-sonnet": {
                "cost_per_token": 0.003, 
                "quality_score": 0.95, 
                "speed_score": 0.8,
                "context_length": 200000,
                "specialties": ["security", "complex_logic", "architecture"]
            },
            "gpt-4": {
                "cost_per_token": 0.03, 
                "quality_score": 0.9, 
                "speed_score": 0.7,
                "context_length": 8192,
                "specialties": ["general_code", "performance", "best_practices"]
            },
            "gpt-3.5-turbo": {
                "cost_per_token": 0.001, 
                "quality_score": 0.75, 
                "speed_score": 0.95,
                "context_length": 4096,
                "specialties": ["simple_changes", "documentation", "style"]
            },
            "claude-3-haiku": {
                "cost_per_token": 0.00025, 
                "quality_score": 0.7, 
                "speed_score": 0.98,
                "context_length": 200000,
                "specialties": ["quick_review", "initial_analysis"]
            }
        }
        
    def select_optimal_model(
        self, 
        complexity_score: float, 
        budget_constraint: float = None,
        quality_threshold: float = 0.8,
        latency_requirement: float = None,
        code_language: str = "python",
        analysis_type: str = "general"
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Select the optimal model based on multiple factors.
        
        Returns:
            Tuple of (selected_model, selection_reasoning)
        """
        candidates = []
        
        for model_name, specs in self.models.items():
            # Calculate cost score (lower is better)
            cost_score = 1.0 / (specs["cost_per_token"] + 0.0001)
            
            # Calculate quality fit
            quality_fit = specs["quality_score"]
            
            # Calculate speed fit (if latency requirement specified)
            speed_fit = 1.0
            if latency_requirement:
                speed_fit = specs["speed_score"] if specs["speed_score"] >= latency_requirement else 0.5
            
            # Calculate specialty match
            specialty_match = 1.0
            if analysis_type in specs["specialties"] or code_language in specs["specialties"]:
                specialty_match = 1.2
            
            # Calculate complexity suitability
            complexity_factor = self._calculate_complexity_factor(complexity_score, specs)
            
            # Calculate budget constraint
            budget_factor = 1.0
            if budget_constraint:
                estimated_cost = self._estimate_cost(complexity_score, specs)
                budget_factor = 1.0 if estimated_cost <= budget_constraint else 0.3
            
            # Combined score
            total_score = (
                quality_fit * 0.4 +
                (cost_score / 100) * 0.3 +  # Normalize cost score
                speed_fit * 0.2 +
                specialty_match * 0.1 +
                complexity_factor * 0.1
            ) * budget_factor
            
            candidates.append({
                "model": model_name,
                "score": total_score,
                "estimated_cost": self._estimate_cost(complexity_score, specs),
                "reasoning": self._generate_reasoning(model_name, specs, quality_fit, cost_score, speed_fit, specialty_match)
            })
        
        # Sort by score and select best
        candidates.sort(key=lambda x: x["score"], reverse=True)
        best_candidate = candidates[0]
        
        return best_candidate["model"], {
            "selection_reasoning": best_candidate["reasoning"],
            "estimated_cost_usd": best_candidate["estimated_cost"],
            "all_candidates": candidates[:3],  # Top 3 options
            "quality_threshold_met": best_candidate["score"] >= quality_threshold
        }
    
    def _calculate_complexity_factor(self, complexity: float, specs: Dict[str, Any]) -> float:
        """Calculate how well a model handles the complexity level."""
        if complexity > 0.8:
            return 1.2 if specs["quality_score"] > 0.9 else 0.8
        elif complexity > 0.5:
            return 1.0 if specs["quality_score"] > 0.8 else 0.9
        else:
            return 1.1 if specs["speed_score"] > 0.9 else 1.0
    
    def _estimate_cost(self, complexity: float, specs: Dict[str, Any]) -> float:
        """Estimate cost for the analysis based on complexity."""
        base_tokens = 1000 + (complexity * 5000)  # More complex = more tokens
        return base_tokens * specs["cost_per_token"]
    
    def _generate_reasoning(self, model_name: str, specs: Dict[str, Any], 
                          quality: float, cost: float, speed: float, specialty: float) -> str:
        """Generate human-readable reasoning for model selection."""
        reasons = []
        
        if quality > 0.9:
            reasons.append("high quality")
        if cost < 0.01:
            reasons.append("cost-effective")
        if speed > 0.9:
            reasons.append("fast processing")
        if specialty > 1.1:
            reasons.append("specialized for this task")
            
        return f"Selected {model_name} for {', '.join(reasons)}"


class ReviewAgent(dspy.Module):
    """Enhanced Agent responsible for primary code review analysis with multi-model routing."""
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__()
        self.config = config or {}
        self.reviewer = dspy.ChainOfThought(ReviewAgentSignature)
        self.model_router = EnhancedModelRouter(config)
        self.performance_tracker = ModelPerformanceTracker()
        
    def forward(
        self, 
        context_response: ContextEngineeringResponse,
        code_changes: str,
        org_config: Dict[str, Any],
        analysis_requirements: Optional[Dict[str, Any]] = None
    ) -> ReviewAgentResponse:
        """
        Perform primary code review analysis with intelligent model selection.
        
        Args:
            context_response: Response from Context Engineering Agent
            code_changes: Raw code changes to review
            org_config: Organization-specific configuration
            analysis_requirements: Specific requirements for analysis
            
        Returns:
            ReviewAgentResponse with findings and suggestions
        """
        start_time = time.time()
        
        # Extract analysis requirements
        requirements = analysis_requirements or {}
        complexity_score = self._calculate_enhanced_complexity(code_changes, context_response)
        code_language = self._detect_primary_language(code_changes)
        analysis_type = self._determine_analysis_type(code_changes, context_response)
        
        # Get budget and quality constraints
        budget_constraint = org_config.get("ai_settings", {}).get("cost_budget", None)
        quality_threshold = org_config.get("ai_settings", {}).get("quality_threshold", 0.8)
        latency_requirement = requirements.get("latency_requirement_ms", None)
        
        # Select optimal model
        selected_model, selection_metadata = self.model_router.select_optimal_model(
            complexity_score=complexity_score,
            budget_constraint=budget_constraint,
            quality_threshold=quality_threshold,
            latency_requirement=latency_requirement,
            code_language=code_language,
            analysis_type=analysis_type
        )
        
        # Format organization config
        org_config_str = self._format_enhanced_org_config(org_config, requirements)
        
        # Perform review using DSPy with selected model
        result = self.reviewer(
            enriched_context=context_response.enriched_context,
            code_changes=code_changes,
            organization_config=org_config_str,
            model_selection_hint=f"Use {selected_model} for {analysis_type} analysis"
        )
        
        # Enhanced parsing of results
        confidence_scores = self._parse_enhanced_confidence_scores(result.confidence_scores)
        improvements = self._parse_enhanced_improvements(result.suggested_improvements)
        
        processing_time = int((time.time() - start_time) * 1000)
        
        # Track performance for future optimization
        self.performance_tracker.record_usage(
            model=selected_model,
            complexity=complexity_score,
            processing_time=processing_time,
            confidence_score=sum(confidence_scores.values()) / len(confidence_scores)
        )
        
        # NEW: Extract hybrid context and security metadata if available
        hybrid_metadata = {}
        security_metadata = {}
        if hasattr(context_response, 'metadata') and context_response.metadata:
            if context_response.metadata.get('hybrid_context_enabled'):
                hybrid_metadata = {
                    "context_sources": context_response.metadata.get('context_sources', []),
                    "graph_risk_level": context_response.metadata.get('graph_risk_level', 'UNKNOWN'),
                    "deepwiki_available": context_response.metadata.get('deepwiki_available', False),
                }

            # NEW: Extract security metadata
            if context_response.metadata.get('security_findings_count', 0) > 0:
                security_metadata = {
                    "total_findings": context_response.metadata.get('security_findings_count', 0),
                    "critical_issues": context_response.metadata.get('critical_security_issues', 0),
                    "high_issues": context_response.metadata.get('high_security_issues', 0),
                    "tools_used": context_response.metadata.get('security_tools_used', []),
                    "security_risk_weight": self._calculate_security_risk_weight(context_response)
                }

        return ReviewAgentResponse(
            agent_id="review_agent",
            confidence_score=sum(confidence_scores.values()) / len(confidence_scores) if confidence_scores else 0.8,
            processing_time_ms=processing_time,
            review_findings=result.review_findings,
            confidence_scores=confidence_scores,
            suggested_improvements=improvements,
            metadata={
                "selected_model": selected_model,
                "complexity_score": complexity_score,
                "code_language": code_language,
                "analysis_type": analysis_type,
                "model_selection": selection_metadata,
                "performance_metrics": self.performance_tracker.get_recent_metrics(selected_model),
                # Hybrid context metadata
                "hybrid_context": hybrid_metadata if hybrid_metadata else None,
                # NEW: Security metadata
                "security": security_metadata if security_metadata else None
            }
        )
    
    def _calculate_enhanced_complexity(self, code_changes: str, context_response: ContextEngineeringResponse) -> float:
        """Enhanced complexity calculation using multiple factors."""
        # Base complexity from change size
        lines = code_changes.count('\n')
        size_complexity = min(1.0, lines / 200)

        # NEW: Factor in graph-based risk assessment
        graph_complexity = 0.0
        if hasattr(context_response, 'metadata') and context_response.metadata:
            graph_risk = context_response.metadata.get('graph_risk_level', '')
            if graph_risk:
                from ..integrations.context_adapter import ContextAdapter
                graph_complexity = ContextAdapter.get_risk_level_weight(graph_risk) * 0.3

        # NEW: Factor in security risk from ast-grep findings
        security_risk = self._calculate_security_risk_weight(context_response)

        # Structural complexity
        structural_keywords = ['class', 'function', 'async', 'lambda', 'decorator']
        structural_count = sum(code_changes.lower().count(keyword) for keyword in structural_keywords)
        structural_complexity = min(1.0, structural_count / 50)
        
        # Logic complexity
        logic_keywords = ['if', 'elif', 'else', 'for', 'while', 'try', 'except', 'match']
        logic_count = sum(code_changes.lower().count(keyword) for keyword in logic_keywords)
        logic_complexity = min(1.0, logic_count / 30)
        
        # Context complexity from metadata
        ast_complexity = context_response.metadata.get("ast_complexity", 0)
        context_complexity = min(1.0, ast_complexity / 20)
        
        # Risk complexity
        risk_assessment = context_response.metadata.get("risk_assessment", {})
        risk_level = 0.5  # default medium risk
        if isinstance(risk_assessment, dict):
            if risk_assessment.get("complexity") == "high":
                risk_level = 0.9
            elif risk_assessment.get("complexity") == "low":
                risk_level = 0.3
        elif isinstance(risk_assessment, str):
            # Handle string risk_assessment
            if risk_assessment.lower() == "high":
                risk_level = 0.9
            elif risk_assessment.lower() == "low":
                risk_level = 0.3

        # Weighted combination
        if graph_complexity > 0 or security_risk > 0:
            # With graph and/or security context: rebalance weights
            complexity_score = (
                size_complexity * 0.10 +           # Reduced from 0.15/0.2
                structural_complexity * 0.20 +     # Reduced from 0.25/0.3
                logic_complexity * 0.20 +          # Reduced from 0.25/0.3
                context_complexity * 0.10 +        # Same
                risk_level * 0.05 +                # Same
                graph_complexity * 0.20 +          # Graph-based risk (20%)
                security_risk * 0.15               # NEW: Security risk (15%)
            )
        else:
            # Without graph or security context: use original weights
            complexity_score = (
                size_complexity * 0.2 +
                structural_complexity * 0.3 +
                logic_complexity * 0.3 +
                context_complexity * 0.1 +
                risk_level * 0.1
            )

        return min(1.0, complexity_score)

    def _calculate_security_risk_weight(self, context_response: ContextEngineeringResponse) -> float:
        """
        Calculate security risk weight from security findings (ast-grep, etc.).

        Args:
            context_response: Context engineering response with security metadata

        Returns:
            Security risk weight (0.0 to 1.0)
        """
        if not hasattr(context_response, 'metadata') or not context_response.metadata:
            return 0.0

        critical_issues = context_response.metadata.get('critical_security_issues', 0)
        high_issues = context_response.metadata.get('high_security_issues', 0)
        total_findings = context_response.metadata.get('security_findings_count', 0)

        if total_findings == 0:
            return 0.0

        # Weight calculation based on severity
        if critical_issues > 0:
            # Any critical issue = maximum risk
            return 1.0
        elif high_issues >= 5:
            # Many high-severity issues = very high risk
            return 0.9
        elif high_issues >= 3:
            # Multiple high-severity issues = high risk
            return 0.7
        elif high_issues >= 1:
            # Some high-severity issues = medium-high risk
            return 0.5
        elif total_findings >= 10:
            # Many medium/low issues = medium risk
            return 0.4
        elif total_findings >= 5:
            # Several medium/low issues = low-medium risk
            return 0.3
        else:
            # Few medium/low issues = low risk
            return 0.2

    def _detect_primary_language(self, code_changes: str) -> str:
        """Detect the primary programming language from code changes."""
        language_indicators = {
            "python": [r"def \w+", r"class \w+", r"import \w+", r"from \w+ import"],
            "javascript": [r"function \w+", r"const \w+", r"let \w+", r"=>"],
            "rust": [r"fn \w+", r"struct \w+", r"impl \w+", r"let mut"],
            "java": [r"public class", r"private void", r"public static"],
            "go": [r"func \w+", r"type \w+ struct", r"import \("]  # Fixed: escaped parenthesis
        }
        
        scores = {}
        for lang, patterns in language_indicators.items():
            score = 0
            for pattern in patterns:
                score += len(re.findall(pattern, code_changes))
            scores[lang] = score
        
        return max(scores, key=scores.get) if scores else "unknown"
    
    def _determine_analysis_type(self, code_changes: str, context_response: ContextEngineeringResponse) -> str:
        """Determine the primary analysis type needed."""
        # Check for security-related changes
        security_patterns = ["auth", "login", "password", "token", "encrypt", "decrypt", "hash"]
        if any(pattern in code_changes.lower() for pattern in security_patterns):
            return "security"
        
        # Check for performance-related changes
        performance_patterns = ["optimize", "performance", "cache", "async", "parallel"]
        if any(pattern in code_changes.lower() for pattern in performance_patterns):
            return "performance"
        
        # Check for API-related changes
        api_patterns = ["api", "endpoint", "request", "response", "http"]
        if any(pattern in code_changes.lower() for pattern in api_patterns):
            return "api_design"
        
        # Check for testing changes
        test_patterns = ["test", "spec", "assert", "mock"]
        if any(pattern in code_changes.lower() for pattern in test_patterns):
            return "testing"
        
        # Default to general code review
        return "general"
    
    def _format_enhanced_org_config(self, org_config: Dict[str, Any], requirements: Dict[str, Any]) -> str:
        """Enhanced organization configuration formatting."""
        config_parts = []
        
        # Basic configuration
        if "review_rules" in org_config:
            rules = org_config["review_rules"]
            config_parts.append(f"Enabled checks: {', '.join(rules.get('enabled_checks', []))}")
            if "custom_rules" in rules and rules["custom_rules"]:
                config_parts.append(f"Custom rules: {', '.join(rules['custom_rules'])}")
        
        # AI settings
        if "ai_settings" in org_config:
            ai_settings = org_config["ai_settings"]
            config_parts.append(f"Primary model: {ai_settings.get('primary_model', 'auto-select')}")
            config_parts.append(f"Temperature: {ai_settings.get('temperature', 0.7)}")
            config_parts.append(f"Max tokens: {ai_settings.get('max_tokens', 2000)}")
        
        # Analysis requirements
        if requirements:
            config_parts.append(f"Analysis focus: {requirements.get('focus_areas', 'general')}")
            if requirements.get("security_focus"):
                config_parts.append("Enhanced security review required")
            if requirements.get("performance_focus"):
                config_parts.append("Enhanced performance review required")
        
        return "\n".join(config_parts) if config_parts else "Default configuration"
    
    def _parse_enhanced_confidence_scores(self, confidence_str: str) -> Dict[str, float]:
        """Enhanced parsing of confidence scores with better error handling."""
        scores = {}
        
        try:
            # Try to parse as JSON first
            if confidence_str.strip().startswith('{'):
                scores = json.loads(confidence_str)
            else:
                # Parse as key-value pairs
                lines = confidence_str.split('\n')
                for line in lines:
                    line = line.strip()
                    if ':' in line and not line.startswith('#'):
                        key, value = line.split(':', 1)
                        key = key.strip().lower().replace(' ', '_')
                        try:
                            scores[key] = float(value.strip())
                        except ValueError:
                            continue
                            
        except (json.JSONDecodeError, ValueError):
            # Fallback to pattern matching
            patterns = [
                (r'overall[:\s]+([0-9.]+)', 'overall'),
                (r'security[:\s]+([0-9.]+)', 'security'),
                (r'performance[:\s]+([0-9.]+)', 'performance'),
                (r'quality[:\s]+([0-9.]+)', 'quality'),
                (r'maintainability[:\s]+([0-9.]+)', 'maintainability'),
            ]
            
            for pattern, key in patterns:
                match = re.search(pattern, confidence_str.lower())
                if match:
                    scores[key] = float(match.group(1))
        
        # Ensure we have minimum required scores
        if not scores:
            scores = {"overall": 0.8, "general": 0.8}
        
        # Validate scores are in valid range
        for key, value in scores.items():
            scores[key] = max(0.0, min(1.0, value))
        
        return scores
    
    def _parse_enhanced_improvements(self, improvements_str: str) -> List[str]:
        """Enhanced parsing of improvement suggestions with categorization."""
        improvements = []
        
        # Split by common delimiters
        lines = re.split(r'[\n\r]+|[•\-\*]\s*|\d+\.\s*', improvements_str)
        
        for line in lines:
            line = line.strip()
            if line and len(line) > 10:  # Filter out very short lines
                # Clean up the line
                cleaned_line = re.sub(r'^\d+[\.\)]\s*', '', line)  # Remove numbering
                cleaned_line = re.sub(r'^\s*-\s*', '', cleaned_line)  # Remove bullets
                
                if cleaned_line and cleaned_line not in improvements:
                    improvements.append(cleaned_line)
        
        # Categorize improvements by priority
        priority_categories = {
            "critical": [],
            "high": [],
            "medium": [],
            "low": []
        }
        
        for improvement in improvements[:15]:  # Limit to top 15
            lower_imp = improvement.lower()
            if any(keyword in lower_imp for keyword in ["security", "vulnerability", "exploit"]):
                priority_categories["critical"].append(improvement)
            elif any(keyword in lower_imp for keyword in ["performance", "optimize", "slow"]):
                priority_categories["high"].append(improvement)
            elif any(keyword in lower_imp for keyword in ["maintainability", "readable", "document"]):
                priority_categories["medium"].append(improvement)
            else:
                priority_categories["low"].append(improvement)
        
        # Return prioritized list
        prioritized_improvements = []
        for priority in ["critical", "high", "medium", "low"]:
            prioritized_improvements.extend(priority_categories[priority])
        
        return prioritized_improvements[:10]  # Return top 10


class ModelPerformanceTracker:
    """Track model performance for optimization."""
    
    def __init__(self):
        self.metrics = {}
    
    def record_usage(self, model: str, complexity: float, processing_time: int, confidence_score: float):
        """Record usage metrics for a model."""
        if model not in self.metrics:
            self.metrics[model] = {
                "usage_count": 0,
                "avg_processing_time": 0,
                "avg_confidence": 0,
                "avg_complexity": 0
            }
        
        metrics = self.metrics[model]
        metrics["usage_count"] += 1
        
        # Update rolling averages
        count = metrics["usage_count"]
        metrics["avg_processing_time"] = ((metrics["avg_processing_time"] * (count - 1)) + processing_time) / count
        metrics["avg_confidence"] = ((metrics["avg_confidence"] * (count - 1)) + confidence_score) / count
        metrics["avg_complexity"] = ((metrics["avg_complexity"] * (count - 1)) + complexity) / count
    
    def get_recent_metrics(self, model: str) -> Dict[str, float]:
        """Get recent performance metrics for a model."""
        return self.metrics.get(model, {})
