"""Verification Agents for specialized review validation."""

import asyncio
import dspy
from typing import Dict, Any, List
from ..models import (
    VerificationAgentResponse,
    ReviewAgentResponse,
    ContextEngineeringResponse,
    VerificationAgentSignature as ModelVerificationAgentSignature,
)


class VerificationAgentSignature(ModelVerificationAgentSignature):
    """Alias to centralized signature defined in models.py."""


class VerificationAgent(dspy.Module):
    """Specialized verification agent for specific code review aspects."""
    
    SPECIALIZATIONS = [
        "security",
        "performance", 
        "style",
        "logic",
        "testing",
        "documentation",
        "accessibility",
        "maintainability",
        "architecture",
        "dependencies",
        "requirements_validation"
    ]
    
    def __init__(self, specialization: str, config: Dict[str, Any] = None):
        super().__init__()
        if specialization not in self.SPECIALIZATIONS:
            raise ValueError(f"Invalid specialization: {specialization}. Must be one of {self.SPECIALIZATIONS}")
            
        self.specialization = specialization
        self.config = config or {}
        self.verifier = dspy.ChainOfThought(VerificationAgentSignature)
        
    def forward(
        self,
        review_response: ReviewAgentResponse,
        context_response: ContextEngineeringResponse,
        code_changes: str,
        pr_description: str,
        org_config: Dict[str, Any]
    ) -> VerificationAgentResponse:
        """
        Verify and filter findings based on specialization.
        
        Args:
            review_response: Response from Review Agent
            context_response: Context from Context Engineering Agent (enriched context, relationships, RAG)
            code_changes: Raw code changes/diffs for the PR
            pr_description: Pull Request description text
            org_config: Organization-specific configuration
            
        Returns:
            VerificationAgentResponse with filtered findings
        """
        import time
        start_time = time.time()
        
        # Generate specialization-specific context
        specialization_context = self._generate_specialization_context()
        
        # Format organization config
        org_config_str = self._format_org_config(org_config)

        # Build a rich code context visible to the verifier
        enriched_context = getattr(context_response, 'enriched_context', '') or ''
        code_relationships = getattr(context_response, 'code_relationships', '') or ''
        rag_summary = ''
        try:
            if hasattr(context_response, 'metadata'):
                rag_enabled = context_response.metadata.get('rag_enabled', False)
                if rag_enabled:
                    rag_summary = (
                        f"RAG: patterns={context_response.metadata.get('rag_patterns_found', 0)}, "
                        f"issues={context_response.metadata.get('rag_issues_found', 0)}, "
                        f"practices={context_response.metadata.get('rag_practices_found', 0)}"
                    )
        except Exception:
            pass

        # Keep code context bounded while retaining high signal
        from .. import config
        def _truncate(text: str, limit: int = None) -> str:
            if limit is None:
                limit = config.TRUNCATE_VERIFICATION_TEXT
            return text if len(text) <= limit else text[:limit] + "\n... [truncated]"

        code_context = (
            f"PR Description:\n{_truncate(pr_description or '')}\n\n"
            f"Enriched Context:\n{_truncate(enriched_context)}\n\n"
            f"Code Relationships:\n{_truncate(code_relationships)}\n\n"
            f"Code Changes (diff excerpts):\n{_truncate(code_changes)}\n\n"
            f"{rag_summary}\n"
        )
        
        # Enhanced logic verification for business logic specialization
        if self.specialization == "logic":
            enhanced_findings = self._perform_enhanced_logic_analysis(
                code_changes, pr_description, enriched_context, context_response
            )
            
            # Combine DSPy findings with enhanced analysis
            result = self.verifier(
                review_findings=review_response.review_findings + "\n\n" + enhanced_findings,
                specialization_context=specialization_context,
                organization_config=org_config_str,
                code_context=code_context
            )
        else:
            # Standard verification using DSPy
            result = self.verifier(
                review_findings=review_response.review_findings,
                specialization_context=specialization_context,
                organization_config=org_config_str,
                code_context=code_context
            )
        
        processing_time = int((time.time() - start_time) * 1000)
        
        # Calculate confidence score based on multiple factors
        confidence_score = self._calculate_confidence(
            result=result,
            review_response=review_response,
            processing_time=processing_time
        )
        
        return VerificationAgentResponse(
            agent_id=f"verification_{self.specialization}",
            confidence_score=confidence_score,
            processing_time_ms=processing_time,
            filtered_findings=result.filtered_findings,
            relevance_score=self._coerce_relevance(result.relevance_score),
            specialization=self.specialization
        )
    
    def _calculate_confidence(
        self,
        result: Any,
        review_response: ReviewAgentResponse,
        processing_time: int
    ) -> float:
        """
        Calculate confidence score based on multiple factors.
        
        Args:
            result: Verification result from DSPy
            review_response: Original review response
            processing_time: Time taken to process
            
        Returns:
            Confidence score between 0.0 and 1.0
        """
        factors = []
        
        # Factor 1: Relevance score from the model (0-1)
        relevance = self._coerce_relevance(getattr(result, 'relevance_score', 0.7))
        if isinstance(relevance, (int, float)):
            factors.append(min(max(float(relevance), 0.0), 1.0))
        else:
            factors.append(0.7)  # Default moderate confidence
        
        # Factor 2: Processing time (faster = more confident in simple cases)
        # Normalize processing time: < 1s = high confidence, > 5s = lower confidence
        time_factor = max(0.5, 1.0 - (processing_time / 10000))
        factors.append(time_factor)
        
        # Factor 3: Number of findings vs filtered findings
        # Higher filtering rate = higher confidence in remaining items
        try:
            original_findings_count = len(review_response.review_findings.split('\n'))
            filtered_findings_count = len(result.filtered_findings.split('\n'))
            
            if original_findings_count > 0:
                retention_rate = filtered_findings_count / original_findings_count
                # Medium retention (30-70%) = highest confidence
                # Very low or very high retention = lower confidence
                if 0.3 <= retention_rate <= 0.7:
                    filter_factor = 0.9
                elif 0.1 <= retention_rate <= 0.9:
                    filter_factor = 0.8
                else:
                    filter_factor = 0.7
                factors.append(filter_factor)
        except Exception:
            factors.append(0.75)  # Default if calculation fails
        
        # Factor 4: Specialization-specific confidence
        # Some specializations are more deterministic than others
        specialization_confidence = {
            "security": 0.9,      # High - well-defined rules
            "performance": 0.85,  # High - measurable metrics
            "style": 0.95,        # Very high - clear standards
            "logic": 0.75,        # Medium - complex reasoning
            "testing": 0.9,       # High - coverage metrics
            "documentation": 0.85,
            "accessibility": 0.8,
            "maintainability": 0.75,
            "architecture": 0.7,  # Lower - subjective
            "dependencies": 0.85,
        }
        factors.append(specialization_confidence.get(self.specialization, 0.8))
        
        # Factor 5: Historical accuracy (if available)
        # TODO: Track actual accuracy over time per agent
        historical_accuracy = self._get_historical_accuracy()
        if historical_accuracy is not None:
            factors.append(historical_accuracy)
        
        # Calculate weighted average
        # Give more weight to relevance and specialization
        weights = [0.3, 0.1, 0.2, 0.25, 0.15] if len(factors) == 5 else [0.35, 0.15, 0.25, 0.25]
        
        confidence = sum(f * w for f, w in zip(factors, weights[:len(factors)]))
        
        # Ensure confidence is between 0.0 and 1.0
        return min(max(confidence, 0.0), 1.0)

    def _coerce_relevance(self, value: Any) -> float:
        """Attempt to coerce relevance_score from model output into a float in [0,1]."""
        try:
            if isinstance(value, (int, float)):
                return float(value)
            if isinstance(value, str):
                return float(value.strip())
        except Exception:
            pass
        return 0.7
    
    def _get_historical_accuracy(self) -> float | None:
        """
        Get historical accuracy for this agent from past reviews.
        
        Returns:
            Historical accuracy score or None if not available
        """
        try:
            # TODO: Implement actual historical tracking
            # This would query a database of past reviews and their outcomes
            # For now, return None to use other factors
            return None
        except Exception:
            return None
    
    def _perform_enhanced_logic_analysis(
        self, 
        code_changes: str, 
        pr_description: str, 
        enriched_context: str,
        context_response: ContextEngineeringResponse
    ) -> str:
        """
        Perform enhanced business logic analysis using the BusinessLogicAnalyzer.
        
        Args:
            code_changes: Raw code diffs
            pr_description: PR description
            enriched_context: Enriched context from context engineering
            context_response: Full context response
            
        Returns:
            Enhanced findings as formatted string
        """
        try:
            from .business_logic_analyzer import BusinessLogicAnalyzer
            
            analyzer = BusinessLogicAnalyzer()
            
            # Extract RAG patterns if available
            rag_patterns = []
            if hasattr(context_response, 'metadata'):
                rag_enabled = context_response.metadata.get('rag_enabled', False)
                if rag_enabled:
                    # Mock RAG patterns structure - in real implementation, 
                    # this would come from the actual RAG context
                    rag_patterns = [
                        {
                            'content_snippet': enriched_context[:500],  # Sample
                            'file_path': 'similar_code.py',
                            'similarity_score': 0.8
                        }
                    ]
            
            # Perform comprehensive business logic analysis
            analysis = analyzer.analyze_business_logic(
                code_changes=code_changes,
                pr_description=pr_description, 
                requirements_context=enriched_context,
                rag_patterns=rag_patterns
            )
            
            # Format findings for DSPy consumption
            findings_parts = []
            
            findings_parts.append("=== ENHANCED BUSINESS LOGIC ANALYSIS ===")
            
            # Logic flows analysis
            if analysis["logic_flows"]:
                findings_parts.append(f"\nLogic Flows Detected: {len(analysis['logic_flows'])}")
                for flow in analysis["logic_flows"][:3]:  # Top 3 flows
                    findings_parts.append(
                        f"- Function: {flow['function_name']} "
                        f"(Complexity: {flow['complexity_score']:.2f}, "
                        f"Conditions: {len(flow['conditions'])}, "
                        f"Side Effects: {len(flow['side_effects'])})"
                    )
            
            # Business rule violations
            if analysis["business_rule_violations"]:
                findings_parts.append(f"\nBusiness Rule Violations: {len(analysis['business_rule_violations'])}")
                for violation in analysis["business_rule_violations"][:3]:
                    findings_parts.append(f"- [{violation['priority'].upper()}] {violation['issue']}")
            
            # Semantic mismatches
            if analysis["semantic_mismatches"]:
                findings_parts.append(f"\nSemantic Mismatches: {len(analysis['semantic_mismatches'])}")
                for mismatch in analysis["semantic_mismatches"][:2]:
                    findings_parts.append(f"- {mismatch['claimed_action']}: {mismatch['issue']}")
            
            # Edge case gaps
            if analysis["edge_case_gaps"]:
                findings_parts.append(f"\nEdge Case Gaps: {len(analysis['edge_case_gaps'])}")
                for gap in analysis["edge_case_gaps"][:2]:
                    findings_parts.append(f"- {gap['case_type']}: {gap['issue']}")
            
            # Complexity concerns
            if analysis["complexity_concerns"]:
                findings_parts.append(f"\nComplexity Concerns: {len(analysis['complexity_concerns'])}")
                for concern in analysis["complexity_concerns"][:2]:
                    if 'function' in concern:
                        findings_parts.append(f"- Function {concern['function']}: {concern['issue']}")
                    else:
                        findings_parts.append(f"- {concern['issue']}")
            
            # Integration issues
            if analysis["integration_issues"]:
                findings_parts.append(f"\nIntegration Issues: {len(analysis['integration_issues'])}")
                for issue in analysis["integration_issues"][:2]:
                    findings_parts.append(f"- {issue['issue']} (Severity: {issue['severity']})")
            
            # Overall risk assessment
            risk_score = analysis["risk_score"]
            risk_level = "LOW" if risk_score < 0.3 else "MEDIUM" if risk_score < 0.7 else "HIGH"
            findings_parts.append(f"\nOverall Business Logic Risk: {risk_level} (Score: {risk_score:.2f})")
            
            return "\n".join(findings_parts)
            
        except ImportError:
            return "Enhanced business logic analysis unavailable (BusinessLogicAnalyzer not found)"
        except Exception as e:
            return f"Enhanced business logic analysis failed: {str(e)}"
    
    def _generate_specialization_context(self) -> str:
        """Generate context specific to this agent's specialization."""
        contexts = {
            "security": """
            Focus on security vulnerabilities, authentication issues, authorization flaws,
            input validation problems, SQL injection risks, XSS vulnerabilities, 
            cryptographic issues, and secure coding practices.
            
            Specific checks:
            - Input sanitization and validation
            - Authentication and authorization logic
            - Data exposure and privacy concerns
            - Secure communication (TLS/SSL)
            - Injection vulnerabilities (SQL, command, etc.)
            - Cryptographic implementations
            """,
            "performance": """
            Focus on performance bottlenecks, inefficient algorithms, memory leaks,
            database query optimization, caching opportunities, and scalability concerns.
            
            Specific checks:
            - Algorithm complexity (Big O notation)
            - Database query efficiency
            - Memory usage patterns
            - I/O operation efficiency
            - Caching opportunities
            - Resource cleanup
            """,
            "style": """
            Focus on code formatting, naming conventions, code organization,
            consistency with project standards, and readability improvements.
            
            Specific checks:
            - Code formatting standards
            - Naming conventions
            - Comment quality and coverage
            - File and folder organization
            - Import/dependency organization
            """,
            "logic": """
            Focus on deep business logic validation, semantic correctness, and complex reasoning errors.
            With full context available (code, requirements, RAG), perform comprehensive logical analysis.
            
            Enhanced checks with full context:
            - Business rule correctness vs documented requirements
            - Semantic consistency between PR description and implementation
            - Complex edge case validation using similar patterns from RAG
            - Cross-function/class logic flow validation
            - State transition correctness and consistency
            - Data flow and transformation logic validation
            - Algorithmic correctness for business calculations
            - Integration point logic validation
            - Conditional logic completeness (all branches covered)
            - Loop termination and boundary condition analysis
            - Exception handling completeness and appropriateness
            - Concurrency and thread safety logic issues
            - Resource lifecycle and cleanup logic
            - API contract compliance and behavior consistency
            - Business invariant preservation across operations
            """,
            "testing": """
            Focus on test coverage, test quality, missing test cases,
            test maintainability, and testing best practices.
            
            Specific checks:
            - Unit test coverage
            - Integration test coverage
            - Test assertion quality
            - Mock/stub usage
            - Edge case testing
            """,
            "documentation": """
            Focus on code comments, API documentation, README updates,
            inline documentation quality, and knowledge transfer needs.
            
            Specific checks:
            - API documentation completeness
            - Inline comment quality
            - README updates for changes
            - Function/class docstrings
            - Breaking change documentation
            """,
            "accessibility": """
            Focus on web accessibility standards (WCAG), keyboard navigation,
            screen reader compatibility, and inclusive design practices.
            
            Specific checks:
            - Semantic HTML structure
            - ARIA labels and roles
            - Keyboard navigation
            - Color contrast ratios
            - Screen reader compatibility
            """,
            "maintainability": """
            Focus on code complexity, technical debt, refactoring opportunities,
            code duplication, and long-term maintenance concerns.
            
            Specific checks:
            - Cyclomatic complexity
            - Code duplication
            - Long function/class detection
            - Technical debt indicators
            - Coupling and cohesion
            """,
            "architecture": """
            Focus on architectural patterns, design principles, separation of concerns,
            dependency management, and system design quality.
            
            Specific checks:
            - SOLID principles adherence
            - Design pattern usage
            - Dependency injection
            - Separation of concerns
            - Layered architecture
            """,
            "dependencies": """
            Focus on dependency management, version conflicts, security vulnerabilities
            in dependencies, license compatibility, and dependency updates.
            
            Specific checks:
            - Outdated dependencies
            - Security vulnerabilities
            - License compatibility
            - Unused dependencies
            - Version conflicts
            """,
            "requirements_validation": """
            Focus on validating code changes against documented requirements, specifications,
            and project goals. Detect feature count mismatches and scope alignment issues.
            
            Specific checks:
            - Requirements compliance validation
            - Feature count alignment (3/4 vs 4/4 vs 5/4 implementation)
            - Scope creep detection
            - PR description vs actual implementation
            - Requirements quality assessment
            - Missing or extra feature detection
            """
        }
        
        return contexts.get(self.specialization, "General code review context.")
    
    def _format_org_config(self, org_config: Dict[str, Any]) -> str:
        """Format organization configuration relevant to this specialization."""
        config_parts = []
        
        if "review_rules" in org_config:
            rules = org_config["review_rules"]
            enabled_checks = rules.get("enabled_checks", [])
            
            # Filter checks relevant to this specialization
            relevant_checks = [check for check in enabled_checks if self.specialization in check.lower()]
            if relevant_checks:
                config_parts.append(f"Relevant checks: {', '.join(relevant_checks)}")
                
            # Add severity thresholds
            thresholds = rules.get("severity_thresholds", {})
            relevant_thresholds = {k: v for k, v in thresholds.items() if self.specialization in k.lower()}
            if relevant_thresholds:
                config_parts.append(f"Severity thresholds: {relevant_thresholds}")
        
        return "\n".join(config_parts) if config_parts else f"Default {self.specialization} configuration"


class VerificationAgentPool:
    """Pool of verification agents for parallel processing."""
    
    def __init__(self, specializations: List[str] = None, config: Dict[str, Any] = None):
        self.specializations = specializations or VerificationAgent.SPECIALIZATIONS[:5]  # Use first 5 by default
        self.config = config or {}
        self.agents = {}
        
        # Create appropriate agent for each specialization
        for spec in self.specializations:
            if spec == "requirements_validation":
                # Import here to avoid circular imports
                from .requirements_validation_agent import RequirementsValidationAgent
                self.agents[spec] = RequirementsValidationAgent(config)
            else:
                self.agents[spec] = VerificationAgent(spec, config)
    
    async def verify_parallel(
        self,
        review_response: ReviewAgentResponse,
        context_response: ContextEngineeringResponse,
        code_changes: str,
        pr_description: str,
        org_config: Dict[str, Any]
    ) -> List[VerificationAgentResponse]:
        """
        Run verification agents in parallel for improved performance.
        
        Args:
            review_response: Response from Review Agent
            context_response: Context from Context Engineering Agent
            code_changes: Raw code changes
            pr_description: PR description text
            org_config: Organization configuration
            
        Returns:
            List of verification responses from all agents
        """
        tasks = []
        
        # Create tasks for each agent
        for agent in self.agents.values():
            task = asyncio.create_task(
                self._run_agent_verification(
                    agent,
                    review_response,
                    context_response,
                    code_changes,
                    pr_description,
                    org_config,
                )
            )
            tasks.append(task)
        
        # Execute all verification agents in parallel
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out any failed tasks
        valid_responses = []
        for response in responses:
            if isinstance(response, VerificationAgentResponse):
                valid_responses.append(response)
            else:
                # Log error but continue
                print(f"Warning: Verification agent failed: {response}")
        
        return valid_responses
    
    async def _run_agent_verification(
        self,
        agent: VerificationAgent,
        review_response: ReviewAgentResponse,
        context_response: ContextEngineeringResponse,
        code_changes: str,
        pr_description: str,
        org_config: Dict[str, Any]
    ) -> VerificationAgentResponse:
        """Run verification for a single agent with error handling."""
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            return agent.forward(
                review_response,
                context_response,
                code_changes,
                pr_description,
                org_config,
            )
        except Exception as e:
            logger.error(f"Verification agent {agent.specialization} failed: {e}", exc_info=True)
            # Return a dummy response to allow other agents to continue
            return VerificationAgentResponse(
                agent_id=f"verification_{agent.specialization}",
                confidence_score=0.0,
                processing_time_ms=0,
                filtered_findings=f"Agent failed: {str(e)}",
                relevance_score=0.0,
                specialization=agent.specialization
            )
    
    def build_consensus(self, responses: List[VerificationAgentResponse]) -> Dict[str, Any]:
        """
        Build consensus from multiple verification agent responses.
        
        Args:
            responses: List of verification responses
            
        Returns:
            Consensus results with aggregated findings
        """
        if not responses:
            return {
                "consensus_score": 0.0,
                "filtered_findings": "",
                "agent_agreement": {},
                "participating_agents": 0
            }
        
        # Calculate consensus score
        relevance_scores = [r.relevance_score for r in responses]
        consensus_score = sum(relevance_scores) / len(relevance_scores)
        
        # Aggregate findings with specialization headers
        all_findings = []
        agent_agreement = {}
        detailed_scores = {}
        
        for response in responses:
            if response.filtered_findings.strip():
                # Add specialization context to findings
                findings_text = f"**[{response.specialization.upper()} VERIFICATION]**\n\n{response.filtered_findings}\n\n"
                findings_text += f"*Confidence: {response.relevance_score:.2f}, Processing time: {response.processing_time_ms}ms*\n\n"
                
                all_findings.append(findings_text)
            
            agent_agreement[response.specialization] = response.relevance_score
            detailed_scores[response.specialization] = {
                "confidence": response.confidence_score,
                "relevance": response.relevance_score,
                "processing_time": response.processing_time_ms
            }
        
        # Identify low-scoring agents (potential issues)
        low_performing_agents = [
            agent for agent, score in agent_agreement.items() 
            if score < 0.6
        ]
        
        return {
            "consensus_score": consensus_score,
            "filtered_findings": "\n".join(all_findings),
            "agent_agreement": agent_agreement,
            "detailed_scores": detailed_scores,
            "participating_agents": len(responses),
            "low_performing_agents": low_performing_agents,
            "consensus_quality": "high" if consensus_score > 0.8 else "medium" if consensus_score > 0.6 else "low"
        }
