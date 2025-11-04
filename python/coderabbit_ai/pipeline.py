"""Main DSPy pipeline orchestrating all agents."""

import dspy
from typing import Dict, Any, List
from .models import (
    ReviewRequest, 
    ReviewResponse, 
    ReviewComment,
    ContextData,
    ReviewMetrics
)
from .agents import ContextEngineeringAgent, ReviewAgent, VerificationAgent
from .agents.verification_agent import VerificationAgentPool


class CodeRabbitMultiAgentPipeline(dspy.Module):
    """Main pipeline orchestrating Context Engineering, Review, and Verification agents."""
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__()
        self.config = config or {}
        
        # Initialize agents
        self.context_agent = ContextEngineeringAgent(config)
        self.review_agent = ReviewAgent(config)
        
        # Initialize verification agent pool
        verification_specs = config.get("verification_specializations", [
            "security", "performance", "style", "logic", "testing", "requirements_validation"
        ])
        self.verification_pool = VerificationAgentPool(verification_specs, config)
        
    def forward(self, request: ReviewRequest) -> ReviewResponse:
        """
        Process a review request through the multi-agent pipeline.
        
        Args:
            request: ReviewRequest containing repository, PR, and config data
            
        Returns:
            ReviewResponse with comments and metrics
        """
        import time
        start_time = time.time()
        
        # Step 1: Context Engineering
        context_data = self._prepare_context_data(request)
        context_response = self.context_agent.forward(context_data)
        
        # Step 2: Primary Review Analysis
        code_changes = self._format_code_changes(request.pull_request.files_changed)
        org_config = self._format_org_config(request.config)
        review_response = self.review_agent.forward(
            context_response, 
            code_changes, 
            org_config
        )
        
        # Step 3: Verification Agents (Parallel)
        pr_description = request.pull_request.description if hasattr(request, 'pull_request') else ""
        verification_responses = self._run_verification_agents(
            review_response,
            context_response,
            code_changes,
            pr_description,
            org_config,
        )
        
        # Step 4: Build Consensus and Filter Comments
        consensus = self.verification_pool.build_consensus(verification_responses)
        final_comments = self._generate_final_comments(
            review_response, 
            verification_responses, 
            consensus
        )
        
        # Calculate metrics
        processing_time = int((time.time() - start_time) * 1000)

        # Extract RAG metrics if available
        rag_metrics = {}
        if hasattr(context_response, 'metadata'):
            rag_metrics = {
                'rag_enabled': context_response.metadata.get('rag_enabled', False),
                'rag_patterns_found': context_response.metadata.get('rag_patterns_found', 0),
                'rag_issues_found': context_response.metadata.get('rag_issues_found', 0),
                'rag_practices_found': context_response.metadata.get('rag_practices_found', 0)
            }

        metrics = ReviewMetrics(
            analysis_time_ms=processing_time,
            files_analyzed=len(request.pull_request.files_changed),
            issues_found=len(final_comments),
            ai_cost=self._estimate_ai_cost(request, verification_responses)
        )
        
        return ReviewResponse(
            review_id=f"review_{int(time.time())}",
            status="completed",
            comments=final_comments,
            metrics=metrics
        )
    
    def _prepare_context_data(self, request: ReviewRequest) -> ContextData:
        """Prepare context data for the Context Engineering Agent."""
        # Format repository structure
        repo_structure = f"""
        Repository: {request.repository.name}
        Owner: {request.repository.owner}
        Platform: {request.repository.platform}
        Default Branch: {request.repository.default_branch}
        """

        # Format code changes
        code_changes = self._format_code_changes(request.pull_request.files_changed)

        # Gather historical data from git history
        historical_data = self._gather_historical_data(request)

        # Run static analysis tools
        static_analysis_results = self._run_static_analysis(request.pull_request.files_changed)

        # Extract RAG context from request if available
        rag_context = getattr(request, 'rag_context', None)

        return ContextData(
            repo_structure=repo_structure,
            code_changes=code_changes,
            historical_data=historical_data,
            static_analysis_results=static_analysis_results,
            rag_context=rag_context
        )
    
    def _gather_historical_data(self, request: ReviewRequest) -> str:
        """Gather historical data from git repository."""
        try:
            import subprocess
            import os
            
            # Build historical context
            historical_parts = []
            
            # 1. Get recent commits to affected files
            for file_change in request.pull_request.files_changed[:5]:  # Limit to first 5 files
                try:
                    # Get last 5 commits that touched this file
                    result = subprocess.run(
                        ['git', 'log', '-5', '--oneline', '--', file_change.path],
                        capture_output=True,
                        text=True,
                        timeout=5,
                        cwd=os.path.dirname(file_change.path) if os.path.exists(file_change.path) else '.'
                    )
                    if result.returncode == 0 and result.stdout:
                        historical_parts.append(f"\nRecent commits to {file_change.path}:\n{result.stdout}")
                except Exception as e:
                    tracing.debug(f"Could not get history for {file_change.path}: {e}")
            
            # 2. Get similar past changes (by searching commit messages)
            try:
                # Search for commits with similar keywords from PR title
                keywords = ' '.join(request.pull_request.title.split()[:3])
                result = subprocess.run(
                    ['git', 'log', '--grep', keywords, '-10', '--oneline'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode == 0 and result.stdout:
                    historical_parts.append(f"\nSimilar past changes:\n{result.stdout}")
            except Exception as e:
                tracing.debug(f"Could not search similar commits: {e}")
            
            # 3. Get blame information for context
            for file_change in request.pull_request.files_changed[:3]:  # Top 3 files
                try:
                    if os.path.exists(file_change.path):
                        result = subprocess.run(
                            ['git', 'blame', '-L', '1,10', file_change.path],
                            capture_output=True,
                            text=True,
                            timeout=5
                        )
                        if result.returncode == 0 and result.stdout:
                            historical_parts.append(f"\nRecent authors of {file_change.path}:\n{result.stdout[:200]}")
                except Exception as e:
                    tracing.debug(f"Could not get blame for {file_change.path}: {e}")
            
            if historical_parts:
                return '\n'.join(historical_parts)
            else:
                return "No historical data available for this change"
                
        except Exception as e:
            tracing.error(f"Failed to gather historical data: {e}")
            return f"Historical data gathering failed: {str(e)}"
    
    def _run_static_analysis(self, files_changed: List[Any]) -> List[Dict[str, Any]]:
        """Run static analysis tools on changed files."""
        try:
            # Import the Rust-based static analyzer via bridge
            # This would call the crates/code-analyzer/src/static_analysis.rs
            from .bridge import call_static_analyzer
            
            results = []
            for file_change in files_changed:
                try:
                    # Call the static analyzer for each file
                    analysis_result = call_static_analyzer(
                        file_path=file_change.path,
                        language=file_change.language,
                        content=getattr(file_change, 'content', '')
                    )
                    
                    if analysis_result and analysis_result.get('issues'):
                        results.extend(analysis_result['issues'])
                        
                except Exception as e:
                    tracing.debug(f"Static analysis failed for {file_change.path}: {e}")
            
            return results
            
        except ImportError:
            tracing.warning("Static analyzer bridge not available, skipping static analysis")
            return []
        except Exception as e:
            tracing.error(f"Static analysis failed: {e}")
            return []
    
    def _format_code_changes(self, files_changed: List[Any]) -> str:
        """Format file changes into a readable string."""
        changes = []
        for file_change in files_changed:
            changes.append(f"""
            File: {file_change.path}
            Language: {file_change.language}
            Change Type: {file_change.change_type}
            Diff:
            {file_change.diff}
            """)
        return "\n".join(changes)
    
    def _format_org_config(self, config: Any) -> Dict[str, Any]:
        """Format organization configuration for agents."""
        return {
            "review_rules": {
                "enabled_checks": config.review_rules.enabled_checks,
                "severity_thresholds": config.review_rules.severity_thresholds,
                "custom_rules": config.review_rules.custom_rules
            },
            "ai_settings": {
                "primary_model": config.ai_settings.primary_model,
                "fallback_models": config.ai_settings.fallback_models,
                "temperature": config.ai_settings.temperature,
                "max_tokens": config.ai_settings.max_tokens
            }
        }
    
    def _run_verification_agents(
        self,
        review_response,
        context_response,
        code_changes: str,
        pr_description: str,
        org_config: Dict[str, Any],
    ) -> List[Any]:
        """Run verification agents on the review response with full context."""
        import asyncio

        # Create event loop if not exists
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        # Run verification agents in parallel
        verification_responses = loop.run_until_complete(
            self.verification_pool.verify_parallel(
                review_response,
                context_response,
                code_changes,
                pr_description,
                org_config,
            )
        )

        return verification_responses
    
    def _generate_final_comments(
        self,
        review_response,
        verification_responses: List[Any],
        consensus: Dict[str, Any]
    ) -> List[ReviewComment]:
        """Generate final filtered comments based on all agent responses."""
        final_comments = []

        # Extract review findings from the review agent
        if hasattr(review_response, 'review_findings') and review_response.review_findings:
            # Parse review findings into individual issues
            findings = self._parse_review_findings(review_response.review_findings)

            # Filter findings based on consensus and relevance
            consensus_score = consensus.get("consensus_score", 0.0)

            for finding in findings:
                # Only include findings if consensus score is reasonable
                if consensus_score >= 0.6:
                    comment = ReviewComment(
                        file_path=finding.get("file_path", "unknown"),
                        line_number=finding.get("line_number", 0),
                        message=finding.get("message", ""),
                        severity=finding.get("severity", "info"),
                        category=finding.get("category", "general"),
                        suggestion=finding.get("suggestion", None)
                    )
                    final_comments.append(comment)

        # Add verification agent findings if consensus is high
        if consensus.get("consensus_quality") in ["high", "medium"]:
            verified_findings = consensus.get("filtered_findings", "")
            if verified_findings:
                # Parse verification findings
                verification_comments = self._parse_verification_findings(verified_findings, consensus)
                final_comments.extend(verification_comments)

        # Deduplicate comments based on file path and message similarity
        final_comments = self._deduplicate_comments(final_comments)

        # Sort by severity (critical, high, medium, low, info)
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
        final_comments.sort(key=lambda c: severity_order.get(c.severity, 5))

        return final_comments

    def _parse_review_findings(self, findings_text: str) -> List[Dict[str, Any]]:
        """Parse review findings text into structured findings."""
        findings = []

        # Simple parsing logic - in production, this would be more sophisticated
        lines = findings_text.strip().split('\n')
        current_finding = {}

        for line in lines:
            line = line.strip()
            if not line:
                if current_finding:
                    findings.append(current_finding)
                    current_finding = {}
                continue

            # Parse common patterns
            if line.startswith("File:"):
                current_finding["file_path"] = line.replace("File:", "").strip()
            elif line.startswith("Line:"):
                try:
                    current_finding["line_number"] = int(line.replace("Line:", "").strip())
                except ValueError:
                    current_finding["line_number"] = 0
            elif line.startswith("Severity:"):
                current_finding["severity"] = line.replace("Severity:", "").strip().lower()
            elif line.startswith("Category:"):
                current_finding["category"] = line.replace("Category:", "").strip()
            elif line.startswith("Message:"):
                current_finding["message"] = line.replace("Message:", "").strip()
            elif line.startswith("Suggestion:"):
                current_finding["suggestion"] = line.replace("Suggestion:", "").strip()
            elif "message" not in current_finding and line:
                # If no structured format, treat the whole line as a message
                current_finding["message"] = line
                current_finding["severity"] = "info"
                current_finding["category"] = "general"

        # Add the last finding
        if current_finding:
            findings.append(current_finding)

        return findings

    def _parse_verification_findings(self, findings_text: str, consensus: Dict[str, Any]) -> List[ReviewComment]:
        """Parse verification agent findings into comments."""
        comments = []

        # Extract specialization-specific findings
        sections = findings_text.split("**[")

        for section in sections[1:]:  # Skip first empty section
            if not section.strip():
                continue

            # Extract specialization and content
            parts = section.split("]**", 1)
            if len(parts) < 2:
                continue

            specialization = parts[0].strip().lower().replace(" verification", "")
            content = parts[1].strip()

            # Extract the actual finding (before confidence line)
            content_lines = content.split("*Confidence:")
            if content_lines:
                finding_text = content_lines[0].strip()

                # Create a comment for this finding
                if finding_text:
                    comment = ReviewComment(
                        file_path="multiple",  # Verification findings are often cross-file
                        line_number=0,
                        message=finding_text,
                        severity=self._map_specialization_to_severity(specialization),
                        category=specialization,
                        suggestion=None
                    )
                    comments.append(comment)

        return comments

    def _map_specialization_to_severity(self, specialization: str) -> str:
        """Map verification specialization to severity level."""
        severity_map = {
            "security": "critical",
            "logic": "high",
            "performance": "medium",
            "testing": "medium",
            "style": "low",
            "documentation": "low",
            "accessibility": "medium",
            "maintainability": "medium",
            "architecture": "medium",
            "dependencies": "high"
        }
        return severity_map.get(specialization, "info")

    def _deduplicate_comments(self, comments: List[ReviewComment]) -> List[ReviewComment]:
        """Remove duplicate comments based on similarity."""
        if not comments:
            return []

        unique_comments = []
        seen_messages = set()

        for comment in comments:
            # Create a normalized key for deduplication
            key = f"{comment.file_path}:{comment.line_number}:{comment.message[:100]}"

            if key not in seen_messages:
                seen_messages.add(key)
                unique_comments.append(comment)

        return unique_comments
    
    def _estimate_ai_cost(self, request: ReviewRequest, verification_responses: List[Any]) -> float:
        """Estimate the AI API cost for this review."""
        # Simple cost estimation based on content size
        total_chars = sum(len(fc.content) + len(fc.diff) for fc in request.pull_request.files_changed)
        
        # Rough estimate: $0.001 per 1000 characters
        estimated_cost = (total_chars / 1000) * 0.001
        
        # Add cost for verification agents
        estimated_cost += len(verification_responses) * 0.0005
        
        return round(estimated_cost, 4)


class PipelineOptimizer:
    """DSPy optimizer for the CodeRabbit pipeline."""
    
    def __init__(self, pipeline: CodeRabbitMultiAgentPipeline):
        self.pipeline = pipeline
        
    def optimize(self, training_data: List[Dict[str, Any]], validation_data: List[Dict[str, Any]]):
        """
        Optimize the pipeline using DSPy's MIPRO optimizer.
        
        This uses the MIPRO (Multi-prompt Instruction Proposal Optimizer) to:
        1. Generate better prompts for each agent
        2. Optimize the examples shown to agents
        3. Improve agent interaction patterns
        
        Args:
            training_data: List of ReviewRequest/ReviewResponse pairs for training
            validation_data: List of ReviewRequest/ReviewResponse pairs for validation
        """
        from dspy.teleprompt import MIPRO
        import dspy
        
        # Define evaluation metric for code reviews
        def review_quality_metric(example, prediction, trace=None):
            """
            Evaluate the quality of a code review.
            
            Metrics considered:
            - Accuracy: Did we catch the real issues?
            - Precision: Are the comments actually valid?
            - Completeness: Did we cover all important aspects?
            - Clarity: Are comments clear and actionable?
            """
            scores = []
            
            # 1. Check if critical issues were identified
            if 'expected_issues' in example:
                expected = set(example['expected_issues'])
                found = set(self._extract_issues(prediction))
                
                if expected:
                    recall = len(expected & found) / len(expected)
                    scores.append(recall)
            
            # 2. Check for false positives
            if 'invalid_issues' in example:
                invalid = set(example['invalid_issues'])
                found = set(self._extract_issues(prediction))
                
                false_positives = len(invalid & found)
                precision = 1.0 - (false_positives / max(len(found), 1))
                scores.append(precision)
            
            # 3. Check comment quality (if human ratings available)
            if 'quality_rating' in example:
                # Normalize rating to 0-1
                quality = example['quality_rating'] / 5.0
                scores.append(quality)
            
            # Return average of all available metrics
            return sum(scores) / len(scores) if scores else 0.5
        
        # Prepare training examples in DSPy format
        train_examples = []
        for item in training_data:
            try:
                example = dspy.Example(
                    request=item['request'],
                    response=item.get('expected_response'),
                    expected_issues=item.get('expected_issues', []),
                    invalid_issues=item.get('invalid_issues', []),
                    quality_rating=item.get('quality_rating')
                ).with_inputs('request')
                train_examples.append(example)
            except Exception as e:
                print(f"Warning: Skipping invalid training example: {e}")
        
        # Prepare validation examples
        val_examples = []
        for item in validation_data:
            try:
                example = dspy.Example(
                    request=item['request'],
                    response=item.get('expected_response'),
                    expected_issues=item.get('expected_issues', []),
                    invalid_issues=item.get('invalid_issues', []),
                    quality_rating=item.get('quality_rating')
                ).with_inputs('request')
                val_examples.append(example)
            except Exception as e:
                print(f"Warning: Skipping invalid validation example: {e}")
        
        if not train_examples:
            raise ValueError("No valid training examples provided")
        
        # Initialize MIPRO optimizer
        optimizer = MIPRO(
            metric=review_quality_metric,
            num_candidates=10,  # Number of prompt candidates to generate
            init_temperature=1.0,  # Temperature for prompt generation
        )
        
        # Run optimization
        print(f"Starting MIPRO optimization with {len(train_examples)} training examples...")
        optimized_pipeline = optimizer.compile(
            self.pipeline,
            trainset=train_examples,
            valset=val_examples[:min(50, len(val_examples))],  # Limit validation set size
            max_bootstrapped_demos=4,  # Max examples to show in prompts
            max_labeled_demos=4,
            num_trials=20,  # Number of optimization trials
        )
        
        # Update the pipeline with optimized version
        self.pipeline = optimized_pipeline
        print("MIPRO optimization completed successfully")
        
        return optimized_pipeline
    
    def _extract_issues(self, prediction) -> List[str]:
        """Extract issue descriptions from a prediction."""
        issues = []
        try:
            if hasattr(prediction, 'comments'):
                issues = [c.comment for c in prediction.comments]
            elif hasattr(prediction, 'review_findings'):
                # Parse findings from text
                for line in prediction.review_findings.split('\n'):
                    if line.strip() and not line.startswith('#'):
                        issues.append(line.strip())
        except Exception:
            pass
        return issues
    
    def evaluate(self, test_data: List[Dict[str, Any]]) -> Dict[str, float]:
        """
        Evaluate pipeline performance on test data.
        
        Args:
            test_data: List of ReviewRequest/ReviewResponse pairs
            
        Returns:
            Dictionary of evaluation metrics
        """
        if not test_data:
            return {
                "accuracy": 0.0,
                "precision": 0.0,
                "recall": 0.0,
                "f1_score": 0.0,
                "cost_efficiency": 0.0
            }
        
        total_tp = 0  # True positives
        total_fp = 0  # False positives
        total_fn = 0  # False negatives
        total_cost = 0.0
        
        for item in test_data:
            try:
                # Run pipeline on test input
                request = item['request']
                prediction = self.pipeline.forward(request)
                
                # Extract expected and predicted issues
                expected_issues = set(item.get('expected_issues', []))
                predicted_issues = set(self._extract_issues(prediction))
                invalid_issues = set(item.get('invalid_issues', []))
                
                # Calculate confusion matrix values
                tp = len(expected_issues & predicted_issues)
                fp = len((predicted_issues & invalid_issues) | (predicted_issues - expected_issues - invalid_issues))
                fn = len(expected_issues - predicted_issues)
                
                total_tp += tp
                total_fp += fp
                total_fn += fn
                
                # Track cost (if available)
                if hasattr(prediction, 'metrics') and hasattr(prediction.metrics, 'total_cost'):
                    total_cost += prediction.metrics.total_cost
                    
            except Exception as e:
                print(f"Warning: Evaluation failed for test item: {e}")
                total_fn += 1  # Count as missed
        
        # Calculate metrics
        precision = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0.0
        recall = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0.0
        f1_score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
        accuracy = total_tp / (total_tp + total_fp + total_fn) if (total_tp + total_fp + total_fn) > 0 else 0.0
        
        # Cost efficiency: issues found per dollar spent
        cost_efficiency = total_tp / total_cost if total_cost > 0 else 0.0
        
        return {
            "accuracy": round(accuracy, 3),
            "precision": round(precision, 3),
            "recall": round(recall, 3),
            "f1_score": round(f1_score, 3),
            "cost_efficiency": round(cost_efficiency, 3),
            "total_cost": round(total_cost, 2),
            "total_issues_found": total_tp,
            "false_positives": total_fp,
            "missed_issues": total_fn,
        }