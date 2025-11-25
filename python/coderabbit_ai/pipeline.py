"""Main DSPy pipeline orchestrating all agents."""

import dspy
import logging
from typing import Dict, Any, List, Tuple
from . import config
from .models import (
    ReviewRequest,
    ReviewResponse,
    ReviewComment,
    CommentType,
    ContextData,
    ReviewMetrics,
    SecurityFinding
)
from .agents import ContextEngineeringAgent, ReviewAgent, VerificationAgent
from .agents.verification_agent import VerificationAgentPool
from .agents.requirements_validator_codeact import RequirementsValidatorCodeAct
from .agents.business_logic_codeact import BusinessLogicAnalyzerCodeAct
from .agents.metrics_codeact import MetricsGeneratorCodeAct
from .analyzers import SecurityAggregator, comment_formatter
from .codeact import CodeSandbox

logger = logging.getLogger(__name__)


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

        # Initialize Phase 3: Security Aggregator
        security_config = config.get("security", {})
        self.security_aggregator = SecurityAggregator(
            block_on_critical=security_config.get("block_on_critical", True),
            max_high_severity=security_config.get("max_high_severity", 3),
            confidence_threshold=security_config.get("confidence_threshold", 0.7)
        )

        # CodeAct agents (Phase 1-3)
        use_codeact = config.get("use_codeact", True)
        if use_codeact:
            # Get security config for sandbox settings
            security_config = config.get("security", {})
            sandbox_timeout = security_config.get("sandbox_timeout_seconds", 30)
            max_retries = security_config.get("sandbox_max_retries", 3)
            
            sandbox = CodeSandbox(timeout=sandbox_timeout, max_memory_mb=512)
            self.req_validator_codeact = RequirementsValidatorCodeAct(sandbox, max_retries=max_retries)
            self.business_logic_codeact = BusinessLogicAnalyzerCodeAct(sandbox, max_retries=max_retries)
            self.metrics_codeact = MetricsGeneratorCodeAct(sandbox, max_retries=max_retries)
        else:
            self.req_validator_codeact = None
            self.business_logic_codeact = None
            self.metrics_codeact = None
        
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

        # Parse line number mappings from diffs for accurate line numbers
        self.line_mappings = self._parse_line_numbers_from_diffs(request.pull_request.files_changed)
        logger.info(f"Parsed line mappings for {len(self.line_mappings)} files")

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
        
        # Step 4: CodeAct Analysis (Phase 1-3)
        codeact_results = {}
        if self.req_validator_codeact:
            codeact_results = self._run_codeact_analysis(
                request,
                context_response,
                code_changes,
                review_response
            )

        # Step 5: Build Consensus and Filter Comments
        consensus = self.verification_pool.build_consensus(verification_responses)
        final_comments = self._generate_final_comments(
            review_response,
            verification_responses,
            consensus,
            codeact_results
        )

        # Step 6: Phase 3 Security Aggregation (ALWAYS RUN)
        security_summary = None
        security_recommendation_dict = None
        try:
            # Collect security findings from multiple sources
            security_findings_list = []

            # Source 1: AST-Grep static analysis findings (if available)
            if hasattr(context_data, 'security_findings') and context_data.security_findings:
                security_findings_list.extend(context_data.security_findings)
                logger.info(f"Phase 3: Found {len(context_data.security_findings)} AST-Grep findings")

            # Source 2: Convert existing high-severity comments to security findings
            # This ensures SecurityAggregator runs even without AST-Grep
            comment_security_findings = self._comments_to_security_findings(final_comments)
            security_findings_list.extend(comment_security_findings)
            logger.info(f"Phase 3: Converted {len(comment_security_findings)} comments to security findings")

            # Run Security Aggregator
            context_metadata = getattr(context_response, 'metadata', {})
            prioritized_findings, security_summary, security_recommendation = self.security_aggregator.aggregate(
                security_findings=security_findings_list,
                context_metadata=context_metadata,
                verification_findings=verification_responses
            )

            # Convert SecurityRecommendation dataclass to dict for model
            security_recommendation_dict = {
                "action": security_recommendation.action,
                "severity_level": security_recommendation.severity_level,
                "message": security_recommendation.message,
                "total_issues": security_recommendation.total_issues
            }

            logger.info(f"Phase 3: Aggregated {len(prioritized_findings)} security findings, "
                       f"recommendation: {security_recommendation.action}")
        except Exception as e:
            logger.error(f"Phase 3 security aggregation failed: {e}", exc_info=True)

        # Step 7: PR Test Execution (Optional)
        test_result = None
        if config.get_env_bool("ENABLE_PR_TEST_RUNNER", False):
            try:
                from .pr_test_runner import PRTestRunner
                logger.info("Phase 4: Running PR tests in sandbox...")

                pr_test_runner = PRTestRunner(
                    timeout=config.get_env_int("PR_TEST_TIMEOUT", 300),
                    max_memory_mb=config.get_env_int("PR_TEST_MAX_MEMORY_MB", 2048),
                    max_cpus=config.get_env_float("PR_TEST_MAX_CPUS", 2.0),
                    use_sandbox=True
                )

                # Detect language and run tests
                test_result = pr_test_runner.run_tests(
                    pr_files=request.pull_request.files_changed,
                    language=None,  # Auto-detect
                    test_command=getattr(request.config, 'test_command', None) if hasattr(request, 'config') else None
                )

                logger.info(f"Phase 4: Tests {'passed' if test_result.passed else 'FAILED'} "
                           f"(exit code: {test_result.exit_code}, duration: {test_result.duration_ms}ms)")

                # Add test result as a comment if tests failed
                if not test_result.passed:
                    import hashlib
                    test_comment_id = hashlib.md5(f"test_failure_{test_result.test_command}".encode()).hexdigest()[:8]

                    # Build failure message
                    failure_msg = f"❌ **Tests Failed**\n\nCommand: `{test_result.test_command}`\n\n"
                    if test_result.failed_tests:
                        failure_msg += f"**Failed Tests ({len(test_result.failed_tests)}):**\n"
                        for failed_test in test_result.failed_tests[:5]:  # Show first 5
                            failure_msg += f"- {failed_test}\n"
                        if len(test_result.failed_tests) > 5:
                            failure_msg += f"- ... and {len(test_result.failed_tests) - 5} more\n"

                    if test_result.stderr:
                        failure_msg += f"\n**Error Output:**\n```\n{test_result.stderr[:500]}\n```"

                    test_failure_comment = ReviewComment(
                        id=test_comment_id,
                        file_path="tests",
                        line_number=0,
                        comment_type=CommentType.ISSUE,
                        severity="critical",
                        message=failure_msg,
                        suggested_fix=None,
                        confidence_score=1.0
                    )
                    final_comments.insert(0, test_failure_comment)  # Add at top

            except ImportError:
                logger.warning("PR Test Runner not available - install dependencies")
            except Exception as e:
                logger.error(f"Phase 4 PR test execution failed: {e}", exc_info=True)

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
            metrics=metrics,
            security_summary=security_summary,
            security_recommendation=security_recommendation_dict
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

        # Run static analysis tools (Phase 1 + Phase 3 integration)
        # Returns both linter results and security findings
        project_root = getattr(request.repository, 'clone_url', '.').replace('.git', '')
        static_analysis_results, security_findings = self._run_static_analysis(
            request.pull_request.files_changed,
            project_root=project_root
        )

        # Extract RAG context from request if available
        rag_context = getattr(request, 'rag_context', None)

        return ContextData(
            repo_structure=repo_structure,
            code_changes=code_changes,
            historical_data=historical_data,
            static_analysis_results=static_analysis_results,
            rag_context=rag_context,
            security_findings=security_findings  # Phase 3: Include security findings
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
                    logger.debug(f"Could not get history for {file_change.path}: {e}")
            
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
                logger.debug(f"Could not search similar commits: {e}")
            
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
                    logger.debug(f"Could not get blame for {file_change.path}: {e}")
            
            if historical_parts:
                return '\n'.join(historical_parts)
            else:
                return "No historical data available for this change"
                
        except Exception as e:
            logger.error(f"Failed to gather historical data: {e}")
            return f"Historical data gathering failed: {str(e)}"
    
    def _run_static_analysis(self, files_changed: List[Any], project_root: str = ".") -> Tuple[List[Dict[str, Any]], List[SecurityFinding]]:
        """
        Run static analysis tools on changed files.

        Returns:
            Tuple of (linter_results, security_findings)
        """
        try:
            # Use StaticAnalysisAggregator from Phase 1
            from .analyzers import StaticAnalysisAggregator

            # Extract file paths
            changed_file_paths = [fc.path for fc in files_changed if hasattr(fc, 'path')]

            if not changed_file_paths:
                logger.warning("No valid file paths to analyze")
                return ([], [])

            # Initialize aggregator
            aggregator = StaticAnalysisAggregator(
                enable_astgrep=True,
                enable_linters=True
            )

            # Run analysis
            result = aggregator.analyze(
                changed_files=changed_file_paths,
                project_root=project_root,
                language=None  # Auto-detect
            )

            linter_results = result.get("linter_results", [])
            security_findings = result.get("security_findings", [])

            logger.info(f"Static analysis complete: {len(linter_results)} linter results, "
                       f"{len(security_findings)} security findings")

            return (linter_results, security_findings)

        except ImportError as e:
            logger.warning(f"StaticAnalysisAggregator not available: {e}, skipping static analysis")
            return ([], [])
        except Exception as e:
            logger.error(f"Static analysis failed: {e}", exc_info=True)
            return ([], [])
    
    def _format_code_changes(self, files_changed: List[Any]) -> str:
        """Format file changes into a readable string."""
        if not files_changed:
            logger.warning("No files changed in the PR")
            return "No code changes detected."
        
        if not isinstance(files_changed, list):
            logger.error(f"files_changed must be a list, got {type(files_changed)}")
            return "Invalid code changes format."
        
        changes = []
        for file_change in files_changed:
            try:
                changes.append(f"""
            File: {file_change.path}
            Language: {file_change.language}
            Change Type: {file_change.change_type}
            Diff:
            {file_change.diff}
            """)
            except AttributeError as e:
                logger.warning(f"Malformed file_change object: {e}")
                continue
        
        return "\n".join(changes) if changes else "No valid code changes found."
    
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

    def _run_codeact_analysis(
        self,
        request: ReviewRequest,
        context_response,
        code_changes: str,
        review_response
    ) -> Dict[str, Any]:
        """
        Run CodeAct agents (Phase 1-3) for executable code analysis.

        Args:
            request: ReviewRequest with PR data
            context_response: Context from context engineering agent
            code_changes: Formatted code changes
            review_response: Review agent response

        Returns:
            dict with results from Phase 1-3 agents
        """
        results = {}

        # Phase 1: Requirements Validation
        try:
            requirements_text = self._extract_requirements(request, context_response)
            if requirements_text and self.req_validator_codeact:
                pr_description = request.pull_request.description if hasattr(request, 'pull_request') else ""
                req_result = self.req_validator_codeact.validate(
                    requirements_text=requirements_text,
                    code_changes=code_changes,
                    pr_description=pr_description
                )
                if req_result.get('success'):
                    results['requirements'] = req_result
                    logger.info(f"Requirements validation: {req_result.get('status')}")
                else:
                    logger.warning(f"Requirements validation failed: {req_result.get('error')}")
        except Exception as e:
            logger.error(f"Requirements validation agent failed: {e}", exc_info=True)
            results['requirements'] = {'error': str(e), 'success': False}

        # Phase 2: Business Logic Analysis
        try:
            complexity_score = getattr(review_response, 'complexity_score', 0.5)
            if complexity_score > 0.6 or self._has_async_code(code_changes):
                if self.business_logic_codeact:
                    bl_result = self.business_logic_codeact.analyze(
                        code_changes=code_changes,
                        context={'complexity_score': complexity_score}
                    )
                    if bl_result.get('success'):
                        results['business_logic'] = bl_result
                        risk_score = bl_result.get('risk_score', 0.0)
                        logger.info(f"Business logic analysis: risk_score={risk_score}")
                    else:
                        logger.warning(f"Business logic analysis failed: {bl_result.get('error')}")
        except Exception as e:
            logger.error(f"Business logic analysis agent failed: {e}", exc_info=True)
            results['business_logic'] = {'error': str(e), 'success': False}

        # Phase 3: Custom Metrics
        try:
            if self.metrics_codeact:
                metrics_result = self.metrics_codeact.generate_metrics(code_changes)
                if metrics_result.get('success'):
                    results['metrics'] = metrics_result
                    logger.info(f"Custom metrics: {metrics_result.get('summary', 'N/A')}")
                else:
                    logger.warning(f"Metrics generation failed: {metrics_result.get('error')}")
        except Exception as e:
            logger.error(f"Metrics generation agent failed: {e}", exc_info=True)
            results['metrics'] = {'error': str(e), 'success': False}

        return results

    def _extract_requirements(self, request: ReviewRequest, context_response) -> str:
        """Extract requirements text from PR context."""
        requirements = ""

        # Check context for README or REQUIREMENTS files
        if hasattr(context_response, 'retrieved_context'):
            for ctx in context_response.retrieved_context:
                filename = ctx.get('filename', '').lower()
                if 'readme' in filename or 'requirements' in filename or 'spec' in filename:
                    requirements += ctx.get('content', '')

        # Fallback: PR description as requirements
        if not requirements and hasattr(request, 'pull_request'):
            requirements = request.pull_request.description or ""

        return requirements

    def _has_async_code(self, code_changes: str) -> bool:
        """Check if code changes contain async patterns."""
        async_patterns = ['async def', 'await ', 'asyncio', 'aiohttp', 'threading', 'multiprocessing']
        return any(pattern in code_changes for pattern in async_patterns)

    def _generate_final_comments(
        self,
        review_response,
        verification_responses: List[Any],
        consensus: Dict[str, Any],
        codeact_results: Dict[str, Any] = None
    ) -> List[ReviewComment]:
        """Generate final filtered comments based on all agent responses including CodeAct."""
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
                    # Map severity to valid values
                    severity = finding.get("severity", "low")
                    if severity not in ["low", "medium", "high", "critical"]:
                        severity = "medium"

                    # Generate unique ID
                    import hashlib
                    finding_id = hashlib.md5(
                        f"{finding.get('file_path', 'unknown')}:{finding.get('line_number', 0)}:{finding.get('message', '')}".encode()
                    ).hexdigest()[:8]

                    # Get line number from finding, fallback to diff mapping
                    file_path = finding.get("file_path", "unknown")
                    line_num = finding.get("line_number", 0)
                    if line_num == 0:
                        line_num = self._get_line_number_for_file(file_path)

                    # Format message with professional CodeRabbit-style template
                    formatted_message = comment_formatter.format_comment(
                        message=finding.get("message", ""),
                        severity=severity,
                        suggested_fix=finding.get("suggestion", None),
                        category=finding.get("category", "general"),
                        file_path=file_path,
                        cwe_id=finding.get("cwe_id"),
                        owasp_category=finding.get("owasp_category"),
                        references=finding.get("references", [])
                    )

                    comment = ReviewComment(
                        id=finding_id,
                        file_path=file_path,
                        line_number=line_num,
                        comment_type=CommentType.ISSUE,
                        message=formatted_message,
                        severity=severity,
                        suggested_fix=finding.get("suggestion", None),
                        confidence_score=min(1.0, consensus_score)
                    )
                    final_comments.append(comment)

        # Add verification agent findings if consensus is high
        if consensus.get("consensus_quality") in ["high", "medium"]:
            verified_findings = consensus.get("filtered_findings", "")
            if verified_findings:
                # Parse verification findings
                verification_comments = self._parse_verification_findings(verified_findings, consensus)
                final_comments.extend(verification_comments)

        # Add CodeAct findings (Phase 1-3)
        if codeact_results:
            codeact_comments = self._parse_codeact_findings(codeact_results)
            final_comments.extend(codeact_comments)

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
        """Parse verification agent findings into comments, splitting numbered lists."""
        import re
        import hashlib

        comments = []
        base_consensus_score = consensus.get("consensus_score", 0.7)

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
            if not content_lines:
                continue

            finding_text = content_lines[0].strip()
            if not finding_text:
                continue

            # Split numbered lists into individual findings
            # Pattern: "1. ", "2. ", etc. at start of line or after newline
            numbered_items = re.split(r'(?:^|\n)\s*(\d+)\.\s+', finding_text)

            # Re-pair numbers with their content
            items = []
            for i in range(1, len(numbered_items), 2):
                if i + 1 < len(numbered_items):
                    items.append(numbered_items[i + 1].strip())

            # If no numbered items found, treat whole text as one item
            if not items:
                items = [finding_text]

            # Process each item as a separate comment
            for idx, item in enumerate(items):
                if not item.strip():
                    continue

                # Extract file path from backticks (e.g., `assets/theme.js`:)
                file_match = re.search(r'`([^`]+\.(?:js|css|json|liquid|yml|yaml|html|py|rb|java|go|ts|tsx))`', item)
                file_path = file_match.group(1) if file_match else "multiple"

                # Clean up the message
                message = item.strip()

                # Vary confidence based on position and specialization
                confidence_variation = 1.0
                if specialization == "security":
                    confidence_variation = 1.05  # Boost security findings
                elif specialization == "style":
                    confidence_variation = 0.95  # Lower style findings

                # Slight decrease for items later in list (less critical)
                position_factor = max(0.85, 1.0 - (idx * 0.03))

                item_confidence = min(1.0, base_consensus_score * confidence_variation * position_factor)

                # Generate unique ID
                finding_id = hashlib.md5(
                    f"{file_path}:{specialization}:{message[:100]}".encode()
                ).hexdigest()[:8]

                # Infer severity from message content
                severity = self._infer_severity_from_message(message, specialization)

                # Get line number from diff mapping
                line_num = self._get_line_number_for_file(file_path)

                # Format message with professional template
                formatted_message = comment_formatter.format_comment(
                    message=message,
                    severity=severity,
                    category=specialization,
                    file_path=file_path
                )

                comment = ReviewComment(
                    id=finding_id,
                    file_path=file_path,
                    line_number=line_num,
                    comment_type=CommentType.ISSUE,
                    message=formatted_message,
                    severity=severity,
                    suggested_fix=None,
                    confidence_score=item_confidence
                )
                comments.append(comment)

        return comments

    def _infer_severity_from_message(self, message: str, specialization: str) -> str:
        """Infer severity level from message content keywords."""
        message_lower = message.lower()

        # Critical keywords
        critical_keywords = [
            "security vulnerabilit", "sql injection", "xss", "cross-site scripting",
            "authentication", "authorization", "credential", "password", "secret",
            "will prevent", "will break", "syntax error", "will not execute",
            "cannot execute", "will fail", "invalid json", "invalid liquid"
        ]

        # High keywords
        high_keywords = [
            "missing", "error", "incorrect", "broken", "issue",
            "should be fixed", "needs to be", "must be", "can lead to",
            "rendering problem", "trailing comma"
        ]

        # Check for critical issues
        for keyword in critical_keywords:
            if keyword in message_lower:
                return "critical"

        # Check for high priority
        for keyword in high_keywords:
            if keyword in message_lower:
                return "high"

        # Positive changes are low severity (informational)
        if "positive change" in message_lower or "good practice" in message_lower:
            return "low"

        # Specialization-based defaults
        if specialization == "security":
            return "high"
        elif specialization == "performance":
            return "medium"
        elif specialization == "style":
            return "low"

        return self._map_specialization_to_severity(specialization)

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
        return severity_map.get(specialization, "medium")

    def _create_review_comment(
        self,
        file_path: str,
        line_number: int,
        message: str,
        severity: str,
        category: str = "general",
        suggestion: str = None,
        confidence: float = 0.7
    ) -> ReviewComment:
        """Helper to create ReviewComment with all required fields."""
        import hashlib

        # Use diff mapping as fallback if line_number is 0
        if line_number == 0:
            line_number = self._get_line_number_for_file(file_path)

        # Generate unique ID
        comment_id = hashlib.md5(
            f"{file_path}:{line_number}:{message[:100]}".encode()
        ).hexdigest()[:8]

        # Ensure severity is valid
        if severity not in ["low", "medium", "high", "critical"]:
            severity = "medium"

        # Format message with professional template
        formatted_message = comment_formatter.format_comment(
            message=message,
            severity=severity,
            suggested_fix=suggestion,
            category=category,
            file_path=file_path
        )

        return ReviewComment(
            id=comment_id,
            file_path=file_path,
            line_number=line_number,
            comment_type=CommentType.ISSUE,
            message=formatted_message,
            severity=severity,
            suggested_fix=suggestion,
            confidence_score=min(1.0, max(0.0, confidence))
        )

    def _parse_codeact_findings(self, codeact_results: Dict[str, Any]) -> List[ReviewComment]:
        """Parse CodeAct analysis results into review comments."""
        comments = []

        # Phase 1: Requirements Validation
        if 'requirements' in codeact_results:
            req_data = codeact_results.get('requirements', {})
            status = req_data.get('status', 'UNKNOWN')

            if status == 'INCOMPLETE':
                missing = req_data.get('missing_features', [])
                if missing:
                    implemented_count = req_data.get('implemented_count', 0)
                    required_count = req_data.get('required_count', 0)
                    message = f"Requirements validation: {status}\n"
                    message += f"Implemented {implemented_count}/{required_count} features\n"
                    message += "Missing:\n" + "\n".join(f"- {f}" for f in missing)

                    comments.append(self._create_review_comment(
                        file_path="requirements",
                        line_number=0,
                        message=message,
                        severity="high",
                        category="requirements",
                        suggestion="Implement missing requirements before merging"
                    ))

            elif status == 'SCOPE_CREEP':
                extra = req_data.get('extra_features', [])
                if extra:
                    implemented_count = req_data.get('implemented_count', 0)
                    required_count = req_data.get('required_count', 0)
                    message = f"Requirements validation: {status}\n"
                    message += f"Implemented {implemented_count} features but only {required_count} required\n"
                    message += "Extra features:\n" + "\n".join(f"- {f}" for f in extra)

                    comments.append(self._create_review_comment(
                        file_path="requirements",
                        line_number=0,
                        message=message,
                        severity="medium",
                        category="requirements",
                        suggestion="Confirm extra features with stakeholders"
                    ))

        # Phase 2: Business Logic Analysis
        if 'business_logic' in codeact_results:
            bl_data = codeact_results.get('business_logic', {})
            risk_score = bl_data.get('risk_score', 0.0)

            # Race conditions
            race_conditions = bl_data.get('race_conditions', [])
            if race_conditions:
                message = f"Business logic risk score: {risk_score:.2f}\n"
                message += f"Found {len(race_conditions)} potential race condition(s):\n"
                for rc in race_conditions[:3]:  # Limit to top 3
                    message += f"- {rc}\n"

                comments.append(self._create_review_comment(
                    file_path="business_logic",
                    line_number=0,
                    message=message,
                    severity="critical" if risk_score > 0.8 else "high",
                    category="concurrency",
                    suggestion="Add locks or use atomic operations for shared state"
                ))

            # Edge case gaps
            edge_cases = bl_data.get('edge_case_gaps', [])
            if edge_cases:
                message = f"Missing edge case handling ({len(edge_cases)} issues):\n"
                for ec in edge_cases[:3]:  # Limit to top 3
                    message += f"- {ec}\n"

                comments.append(self._create_review_comment(
                    file_path="business_logic",
                    line_number=0,
                    message=message,
                    severity="high" if risk_score > 0.7 else "medium",
                    category="edge_cases",
                    suggestion="Add None checks and input validation"
                ))

        # Phase 3: Custom Metrics
        if 'metrics' in codeact_results:
            metrics_data = codeact_results.get('metrics', {})
            quality_score = metrics_data.get('quality_score', 100)

            if quality_score < 70:
                complexity = metrics_data.get('cyclomatic_complexity', 0)
                message = f"Code quality score: {quality_score}/100\n"
                if complexity > 15:
                    message += f"High cyclomatic complexity: {complexity}\n"
                message += metrics_data.get('summary', '')

                comments.append(self._create_review_comment(
                    file_path="metrics",
                    line_number=0,
                    message=message,
                    severity="medium" if quality_score < 50 else "low",
                    category="code_quality",
                    suggestion="Consider refactoring complex functions"
                ))

        return comments

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

    def _comments_to_security_findings(self, comments: List[ReviewComment]) -> List[SecurityFinding]:
        """
        Convert ReviewComments to SecurityFinding objects for aggregation.
        Only converts comments with severity critical/high that look like security issues.
        """
        security_findings = []

        for comment in comments:
            # Only convert high-severity comments
            if comment.severity not in ["critical", "high"]:
                continue

            # Determine category and rule from message keywords
            message_lower = comment.message.lower()
            category = "general"
            rule_id = "ai-review"

            # Categorize based on keywords
            if any(kw in message_lower for kw in ["sql injection", "sql query", "database query"]):
                category = "injection"
                rule_id = "sql-injection-detected"
            elif any(kw in message_lower for kw in ["xss", "cross-site scripting", "unsafe html"]):
                category = "xss"
                rule_id = "xss-vulnerability-detected"
            elif any(kw in message_lower for kw in ["hardcoded", "credential", "secret", "password", "api key"]):
                category = "secrets"
                rule_id = "hardcoded-credentials"
            elif any(kw in message_lower for kw in ["authentication", "authorization", "session"]):
                category = "authentication"
                rule_id = "auth-vulnerability"
            elif any(kw in message_lower for kw in ["input validation", "sanitiz", "escap"]):
                category = "input-validation"
                rule_id = "missing-input-validation"
            elif any(kw in message_lower for kw in ["crypto", "encryption", "hash", "md5", "sha1"]):
                category = "cryptography"
                rule_id = "weak-cryptography"

            # Create SecurityFinding from comment
            finding = SecurityFinding(
                file=comment.file_path,
                line=comment.line_number,
                severity=comment.severity,
                rule_id=rule_id,
                category=category,
                message=comment.message[:200],  # Truncate for summary
                tool="ai-review",
                confidence=comment.confidence_score,
                code_snippet=None,
                suggestion=comment.suggested_fix,
                cwe_id=None,
                owasp_category=None,
                references=[]
            )
            security_findings.append(finding)

        return security_findings

    def _parse_line_numbers_from_diffs(self, file_changes: List) -> Dict[str, Dict[int, int]]:
        """
        Parse diff hunks to map old line numbers to new line numbers.

        Returns:
            Dict mapping file_path -> {old_line_num: new_line_num}
        """
        import re

        line_mappings = {}

        for file_change in file_changes:
            if not hasattr(file_change, 'diff') or not file_change.diff:
                continue

            file_path = file_change.path
            mappings = {}

            # Parse diff hunks: @@ -10,5 +12,7 @@
            # This means: old file line 10, 5 lines -> new file line 12, 7 lines
            hunk_pattern = r'@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@'
            hunks = re.finditer(hunk_pattern, file_change.diff)

            for hunk in hunks:
                old_start = int(hunk.group(1))
                old_count = int(hunk.group(2)) if hunk.group(2) else 1
                new_start = int(hunk.group(3))
                new_count = int(hunk.group(4)) if hunk.group(4) else 1

                # For new files (old_count=0), just track the new line numbers
                if old_count == 0:
                    # Store first new line as a reference point
                    mappings[0] = new_start
                else:
                    # Simple mapping: assume 1:1 correspondence within hunk
                    for i in range(min(old_count, new_count)):
                        mappings[old_start + i] = new_start + i

            line_mappings[file_path] = mappings

        return line_mappings

    def _get_line_number_for_file(self, file_path: str) -> int:
        """
        Get a reasonable line number for a file from the diff.
        Returns the first changed line number, or 0 if not available.

        Args:
            file_path: Path to the file

        Returns:
            Line number (first changed line or 0 if unknown)
        """
        if not hasattr(self, 'line_mappings'):
            return 0

        mappings = self.line_mappings.get(file_path, {})
        if mappings:
            # Return the first new line number from the mappings
            return min(mappings.values())

        return 0


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

    def _comments_to_security_findings(self, comments: List[ReviewComment]) -> List[SecurityFinding]:
        """
        Convert ReviewComments to SecurityFinding objects for aggregation.
        Only converts comments with severity critical/high that look like security issues.
        """
        security_findings = []
        
        for comment in comments:
            # Only convert high-severity comments
            if comment.severity not in ["critical", "high"]:
                continue
            
            # Determine category and rule from message keywords
            message_lower = comment.message.lower()
            category = "general"
            rule_id = "ai-review"
            
            # Categorize based on keywords
            if any(kw in message_lower for kw in ["sql injection", "sql query", "execute query"]):
                category = "injection"
                rule_id = "sql-injection-detected"
            elif any(kw in message_lower for kw in ["xss", "cross-site scripting", "render_template_string"]):
                category = "xss"
                rule_id = "xss-vulnerability-detected"
            elif any(kw in message_lower for kw in ["hardcoded", "credential", "password", "secret", "api key", "api_key"]):
                category = "secrets"
                rule_id = "hardcoded-secrets-detected"
            elif any(kw in message_lower for kw in ["md5", "sha1", "weak hash", "weak crypto"]):
                category = "crypto"
                rule_id = "weak-cryptography-detected"
            elif any(kw in message_lower for kw in ["authentication", "authorization", "session"]):
                category = "auth"
                rule_id = "authentication-issue-detected"
            elif any(kw in message_lower for kw in ["syntax error", "will not execute", "will break"]):
                category = "syntax"
                rule_id = "critical-syntax-error"
            elif any(kw in message_lower for kw in ["security vulnerabilit", "security issue"]):
                category = "security"
                rule_id = "security-vulnerability-detected"
            
            # Create SecurityFinding
            finding = SecurityFinding(
                file=comment.file_path,
                line=comment.line_number,
                severity=comment.severity,
                rule_id=rule_id,
                category=category,
                message=comment.message[:200],  # Truncate for summary
                tool="ai-review",
                confidence=comment.confidence_score,
                code_snippet=None,
                suggestion=comment.suggested_fix,
                cwe_id=None,
                owasp_category=None,
                references=[]
            )
            security_findings.append(finding)
        
        return security_findings

