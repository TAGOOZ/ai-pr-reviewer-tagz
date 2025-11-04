"""Requirements Validation Agent for cross-checking code changes against documented requirements."""

import dspy
import re
from typing import Dict, Any, List, Optional, Tuple
from ..models import (
    VerificationAgentResponse, 
    ReviewAgentResponse, 
    ContextEngineeringResponse
)


class RequirementsValidationSignature(dspy.Signature):
    """Validate code changes against documented requirements and specifications."""
    
    # Input fields
    pr_description: str = dspy.InputField(
        desc="Pull Request description with what developer claims to have implemented"
    )
    requirements_context: str = dspy.InputField(
        desc="Requirements, tasks, and specifications from documentation files (README, REQUIREMENTS.md, issues, etc.)"
    )
    code_changes: str = dspy.InputField(
        desc="Actual code changes and implementation details"
    )
    review_findings: str = dspy.InputField(
        desc="Findings from primary review agent for additional context"
    )
    
    # Output fields
    requirements_compliance: str = dspy.OutputField(
        desc="Assessment of how well code changes align with documented requirements"
    )
    feature_completeness: str = dspy.OutputField(
        desc="Analysis of whether all required features are implemented (not 3/4 or 5/4)"
    )
    scope_alignment: str = dspy.OutputField(
        desc="Detection of scope creep or missing requirements implementation"
    )
    requirements_quality_issues: str = dspy.OutputField(
        desc="Issues with the requirements themselves (ambiguous, insecure, outdated)"
    )


class RequirementsValidationAgent(dspy.Module):
    """Agent for validating code changes against documented requirements and detecting misalignment."""
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__()
        self.config = config or {}
        self.validator = dspy.ChainOfThought(RequirementsValidationSignature)
        
    def forward(
        self,
        review_response: ReviewAgentResponse,
        context_response: ContextEngineeringResponse,
        code_changes: str,
        pr_description: str,
        org_config: Dict[str, Any]
    ) -> VerificationAgentResponse:
        """
        Validate code changes against requirements and detect scope misalignment.
        
        Args:
            review_response: Response from Review Agent
            context_response: Context from Context Engineering Agent
            code_changes: Raw code changes/diffs
            pr_description: Pull Request description
            org_config: Organization configuration
            
        Returns:
            VerificationAgentResponse with requirements validation findings
        """
        import time
        start_time = time.time()
        
        # Extract requirements context from RAG and enriched context
        requirements_context = self._extract_requirements_context(context_response)
        
        # Parse what developer claims to have implemented
        claimed_features = self._parse_claimed_features(pr_description)
        
        # Analyze actual code changes for implemented features
        implemented_features = self._analyze_implemented_features(code_changes)
        
        # Perform requirements validation using DSPy
        result = self.validator(
            pr_description=pr_description,
            requirements_context=requirements_context,
            code_changes=code_changes,
            review_findings=review_response.review_findings
        )
        
        # Analyze feature count alignment
        feature_alignment = self._analyze_feature_alignment(
            claimed_features, 
            implemented_features, 
            requirements_context
        )
        
        # Combine findings with feature alignment analysis
        combined_findings = self._combine_validation_findings(result, feature_alignment)
        
        processing_time = int((time.time() - start_time) * 1000)
        
        # Calculate relevance score based on requirements issues found
        relevance_score = self._calculate_relevance_score(result, feature_alignment)
        
        return VerificationAgentResponse(
            agent_id="requirements_validation",
            confidence_score=0.85,  # High confidence for requirements checking
            processing_time_ms=processing_time,
            filtered_findings=combined_findings,
            relevance_score=relevance_score,
            specialization="requirements_validation"
        )
    
    def _extract_requirements_context(self, context_response: ContextEngineeringResponse) -> str:
        """Extract requirements-related context from RAG and enriched context."""
        requirements_sections = []
        
        # Get enriched context that may contain requirements
        enriched_context = getattr(context_response, 'enriched_context', '') or ''
        
        # Look for requirements-related content
        req_keywords = [
            'requirement', 'feature', 'specification', 'task', 'todo', 
            'user story', 'acceptance criteria', 'must have', 'should have'
        ]
        
        lines = enriched_context.split('\n')
        requirements_lines = []
        
        for line in lines:
            line_lower = line.lower()
            if any(keyword in line_lower for keyword in req_keywords):
                requirements_lines.append(line.strip())
        
        if requirements_lines:
            requirements_sections.append("Requirements from context:\n" + '\n'.join(requirements_lines[:20]))
        
        # Check RAG context for requirements documents
        if hasattr(context_response, 'metadata'):
            rag_enabled = context_response.metadata.get('rag_enabled', False)
            if rag_enabled:
                patterns_found = context_response.metadata.get('rag_patterns_found', 0)
                practices_found = context_response.metadata.get('rag_practices_found', 0)
                
                if patterns_found > 0 or practices_found > 0:
                    requirements_sections.append(
                        f"RAG found {patterns_found} similar patterns and {practices_found} best practices "
                        "that may contain requirements context."
                    )
        
        # Look for common requirements patterns
        requirements_patterns = self._extract_requirements_patterns(enriched_context)
        if requirements_patterns:
            requirements_sections.append("Requirements patterns:\n" + requirements_patterns)
        
        return '\n\n'.join(requirements_sections) if requirements_sections else "No requirements context found"
    
    def _extract_requirements_patterns(self, context: str) -> str:
        """Extract common requirements patterns from context."""
        patterns = []
        
        # Look for numbered lists (often requirements)
        numbered_list_pattern = r'^\s*\d+\.\s*(.+)$'
        numbered_items = re.findall(numbered_list_pattern, context, re.MULTILINE)
        if numbered_items and len(numbered_items) >= 2:  # At least 2 items to be a meaningful list
            patterns.append(f"Numbered requirements list found ({len(numbered_items)} items)")
            for i, item in enumerate(numbered_items[:5], 1):  # Show first 5
                patterns.append(f"  {i}. {item[:100]}...")
        
        # Look for bullet points
        bullet_pattern = r'^\s*[-*•]\s*(.+)$'
        bullet_items = re.findall(bullet_pattern, context, re.MULTILINE)
        if bullet_items and len(bullet_items) >= 2:
            patterns.append(f"Bulleted requirements found ({len(bullet_items)} items)")
        
        # Look for "must" statements (requirements)
        must_pattern = r'(must\s+(?:have|be|do|implement|support|provide)[^.!?]*[.!?])'
        must_statements = re.findall(must_pattern, context, re.IGNORECASE)
        if must_statements:
            patterns.append(f"'Must' requirements found ({len(must_statements)} statements)")
            for stmt in must_statements[:3]:  # Show first 3
                patterns.append(f"  - {stmt[:100]}...")
        
        return '\n'.join(patterns) if patterns else ""
    
    def _parse_claimed_features(self, pr_description: str) -> List[str]:
        """Parse what features the developer claims to have implemented."""
        features = []
        
        # Look for common implementation phrases
        implementation_patterns = [
            r'(?:implemented?|added?|created?|built?)\s+([^.!\n]+)',
            r'(?:feature|functionality):\s*([^.!\n]+)',
            r'this\s+pr\s+(?:adds?|implements?)\s+([^.!\n]+)',
            r'(?:new|added?):\s*([^.!\n]+)'
        ]
        
        for pattern in implementation_patterns:
            matches = re.findall(pattern, pr_description, re.IGNORECASE)
            features.extend(matches)
        
        # Look for numbered/bulleted lists in PR description
        numbered_items = re.findall(r'^\s*\d+\.\s*(.+)$', pr_description, re.MULTILINE)
        bullet_items = re.findall(r'^\s*[-*•]\s*(.+)$', pr_description, re.MULTILINE)
        
        features.extend(numbered_items)
        features.extend(bullet_items)
        
        # Clean up features
        cleaned_features = []
        for feature in features:
            cleaned = feature.strip()[:100]  # Limit length
            if len(cleaned) > 5 and cleaned not in cleaned_features:  # Avoid duplicates and too short
                cleaned_features.append(cleaned)
        
        return cleaned_features[:10]  # Limit to top 10
    
    def _analyze_implemented_features(self, code_changes: str) -> List[str]:
        """Analyze code changes to identify what features were actually implemented."""
        features = []
        
        # Look for new function/method definitions
        function_patterns = [
            r'^\+.*def\s+(\w+)',  # Python functions
            r'^\+.*function\s+(\w+)',  # JavaScript functions
            r'^\+.*fn\s+(\w+)',  # Rust functions
        ]
        
        for pattern in function_patterns:
            matches = re.findall(pattern, code_changes, re.MULTILINE)
            for match in matches:
                if not match.startswith('test_'):  # Exclude test functions
                    features.append(f"Function: {match}")
        
        # Look for new classes
        class_patterns = [
            r'^\+.*class\s+(\w+)',  # Python/JS classes
            r'^\+.*struct\s+(\w+)',  # Rust structs
        ]
        
        for pattern in class_patterns:
            matches = re.findall(pattern, code_changes, re.MULTILINE)
            for match in matches:
                features.append(f"Class/Struct: {match}")
        
        # Look for new API endpoints
        api_patterns = [
            r'^\+.*@app\.(?:route|get|post|put|delete)\s*\([\'"]([^\'"]+)',  # Flask/FastAPI
            r'^\+.*app\.(?:get|post|put|delete)\s*\([\'"]([^\'"]+)',
            r'^\+.*router\.(?:get|post|put|delete)\s*\([\'"]([^\'"]+)',
        ]
        
        for pattern in api_patterns:
            matches = re.findall(pattern, code_changes, re.MULTILINE)
            for match in matches:
                features.append(f"API Endpoint: {match}")
        
        # Look for new configuration/settings
        config_patterns = [
            r'^\+.*[\'"](\w+_\w+)[\'"]:\s*[\'"]?([^,}\]]+)',  # Config keys
        ]
        
        for pattern in config_patterns:
            matches = re.findall(pattern, code_changes, re.MULTILINE)
            for key, value in matches[:5]:  # Limit config items
                features.append(f"Configuration: {key}")
        
        return features[:15]  # Limit to top 15 features
    
    def _analyze_feature_alignment(
        self, 
        claimed_features: List[str], 
        implemented_features: List[str], 
        requirements_context: str
    ) -> Dict[str, Any]:
        """Analyze alignment between claimed, implemented, and required features."""
        alignment = {
            "claimed_count": len(claimed_features),
            "implemented_count": len(implemented_features),
            "alignment_issues": [],
            "scope_issues": []
        }
        
        # Extract required feature count from requirements
        required_count = self._extract_required_feature_count(requirements_context)
        if required_count:
            alignment["required_count"] = required_count
            
            # Check for feature count mismatches
            if alignment["claimed_count"] < required_count:
                alignment["alignment_issues"].append(
                    f"Claimed {alignment['claimed_count']} features but requirements specify {required_count} (missing features)"
                )
            elif alignment["claimed_count"] > required_count:
                alignment["scope_issues"].append(
                    f"Claimed {alignment['claimed_count']} features but requirements only specify {required_count} (scope creep)"
                )
        
        # Check for implementation vs claims mismatch
        if alignment["implemented_count"] != alignment["claimed_count"]:
            diff = alignment["implemented_count"] - alignment["claimed_count"]
            if diff < 0:
                alignment["alignment_issues"].append(
                    f"Claimed {alignment['claimed_count']} features but code only implements {alignment['implemented_count']}"
                )
            else:
                alignment["alignment_issues"].append(
                    f"Claimed {alignment['claimed_count']} features but code implements {alignment['implemented_count']} (undocumented work)"
                )
        
        # Look for specific feature mismatches
        claimed_lower = [f.lower() for f in claimed_features]
        implemented_lower = [f.lower() for f in implemented_features]
        
        # Find claimed but not implemented
        for claimed in claimed_features:
            if not any(claimed.lower() in impl.lower() or impl.lower() in claimed.lower() 
                      for impl in implemented_lower):
                alignment["alignment_issues"].append(f"Claimed '{claimed}' but no matching implementation found")
        
        return alignment
    
    def _extract_required_feature_count(self, requirements_context: str) -> Optional[int]:
        """Try to extract the required number of features from requirements context."""
        # Look for patterns like "4 features", "implement 3 items", etc.
        count_patterns = [
            r'(\d+)\s+(?:features?|requirements?|items?|tasks?)',
            r'(?:implement|build|create|add)\s+(\d+)',
            r'total\s+of\s+(\d+)',
        ]
        
        for pattern in count_patterns:
            matches = re.findall(pattern, requirements_context, re.IGNORECASE)
            if matches:
                try:
                    return int(matches[0])
                except ValueError:
                    continue
        
        # Count numbered items in requirements
        numbered_items = re.findall(r'^\s*\d+\.', requirements_context, re.MULTILINE)
        if len(numbered_items) >= 2:  # At least 2 items to be meaningful
            return len(numbered_items)
        
        return None
    
    def _combine_validation_findings(
        self, 
        dspy_result: Any, 
        feature_alignment: Dict[str, Any]
    ) -> str:
        """Combine DSPy validation results with feature alignment analysis."""
        findings = []
        
        # Add DSPy findings
        findings.append("=== REQUIREMENTS VALIDATION ===\n")
        
        if hasattr(dspy_result, 'requirements_compliance') and dspy_result.requirements_compliance:
            findings.append(f"Compliance Analysis:\n{dspy_result.requirements_compliance}\n")
        
        if hasattr(dspy_result, 'feature_completeness') and dspy_result.feature_completeness:
            findings.append(f"Feature Completeness:\n{dspy_result.feature_completeness}\n")
        
        if hasattr(dspy_result, 'scope_alignment') and dspy_result.scope_alignment:
            findings.append(f"Scope Alignment:\n{dspy_result.scope_alignment}\n")
        
        # Add feature alignment analysis
        findings.append("=== FEATURE COUNT ANALYSIS ===\n")
        findings.append(f"Claimed Features: {feature_alignment['claimed_count']}")
        findings.append(f"Implemented Features: {feature_alignment['implemented_count']}")
        
        if feature_alignment.get('required_count'):
            findings.append(f"Required Features: {feature_alignment['required_count']}")
        
        # Add alignment issues
        if feature_alignment['alignment_issues']:
            findings.append("\nAlignment Issues:")
            for issue in feature_alignment['alignment_issues']:
                findings.append(f"  ⚠️  {issue}")
        
        # Add scope issues
        if feature_alignment['scope_issues']:
            findings.append("\nScope Issues:")
            for issue in feature_alignment['scope_issues']:
                findings.append(f"  🔍 {issue}")
        
        # Add requirements quality issues
        if hasattr(dspy_result, 'requirements_quality_issues') and dspy_result.requirements_quality_issues:
            findings.append(f"\n=== REQUIREMENTS QUALITY ISSUES ===\n{dspy_result.requirements_quality_issues}")
        
        return '\n'.join(findings)
    
    def _calculate_relevance_score(
        self, 
        dspy_result: Any, 
        feature_alignment: Dict[str, Any]
    ) -> float:
        """Calculate relevance score based on requirements issues found."""
        score = 0.5  # Base score
        
        # Boost score if alignment issues found
        if feature_alignment['alignment_issues']:
            score += 0.3
        
        if feature_alignment['scope_issues']:
            score += 0.2
        
        # Boost if requirements quality issues found
        if hasattr(dspy_result, 'requirements_quality_issues') and dspy_result.requirements_quality_issues:
            if len(dspy_result.requirements_quality_issues) > 10:  # Non-trivial content
                score += 0.2
        
        # Boost if feature count mismatch detected
        if feature_alignment.get('required_count'):
            claimed = feature_alignment['claimed_count']
            required = feature_alignment['required_count']
            if claimed != required:
                score += 0.3
        
        return min(1.0, score)