"""Business Logic Analyzer for deep semantic validation of code changes."""

import re
import ast
from typing import Dict, Any, List, Optional, Tuple, Set
from dataclasses import dataclass


@dataclass
class LogicFlow:
    """Represents a logical flow in the code."""
    function_name: str
    inputs: List[str]
    outputs: List[str]
    conditions: List[str]
    side_effects: List[str]
    complexity_score: float


@dataclass
class BusinessRule:
    """Represents a business rule extracted from requirements/code."""
    rule_text: str
    affected_functions: List[str]
    validation_conditions: List[str]
    priority: str  # high, medium, low


class BusinessLogicAnalyzer:
    """Analyzes business logic correctness using full context."""
    
    def __init__(self):
        self.logic_flows: List[LogicFlow] = []
        self.business_rules: List[BusinessRule] = []
        self.detected_patterns: Dict[str, List[str]] = {}
        
    def analyze_business_logic(
        self, 
        code_changes: str, 
        pr_description: str, 
        requirements_context: str,
        rag_patterns: List[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Perform comprehensive business logic analysis.
        
        Args:
            code_changes: Raw code diffs
            pr_description: PR description text
            requirements_context: Requirements and specifications
            rag_patterns: Similar patterns from RAG
            
        Returns:
            Dictionary with business logic analysis results
        """
        analysis = {
            "logic_flows": [],
            "business_rule_violations": [],
            "semantic_mismatches": [],
            "edge_case_gaps": [],
            "complexity_concerns": [],
            "integration_issues": [],
            "risk_score": 0.0
        }
        
        # Extract logic flows from code changes
        self.logic_flows = self._extract_logic_flows(code_changes)
        analysis["logic_flows"] = [self._flow_to_dict(flow) for flow in self.logic_flows]
        
        # Extract business rules from requirements
        self.business_rules = self._extract_business_rules(requirements_context)
        
        # Check business rule compliance
        rule_violations = self._check_business_rule_compliance(code_changes)
        analysis["business_rule_violations"] = rule_violations
        
        # Analyze semantic consistency
        semantic_issues = self._analyze_semantic_consistency(code_changes, pr_description)
        analysis["semantic_mismatches"] = semantic_issues
        
        # Check edge cases using RAG patterns
        edge_case_gaps = self._analyze_edge_cases(code_changes, rag_patterns or [])
        analysis["edge_case_gaps"] = edge_case_gaps
        
        # Analyze complexity and maintainability
        complexity_concerns = self._analyze_complexity_concerns(code_changes)
        analysis["complexity_concerns"] = complexity_concerns
        
        # Check integration points
        integration_issues = self._analyze_integration_logic(code_changes)
        analysis["integration_issues"] = integration_issues
        
        # Calculate overall risk score
        analysis["risk_score"] = self._calculate_risk_score(analysis)
        
        return analysis
    
    def _extract_logic_flows(self, code_changes: str) -> List[LogicFlow]:
        """Extract logical flows from code changes."""
        flows = []
        
        # Find function definitions in added code
        function_pattern = r'^\+.*def\s+(\w+)\s*\(([^)]*)\):'
        matches = re.findall(function_pattern, code_changes, re.MULTILINE)
        
        for func_name, params in matches:
            # Parse parameters
            inputs = [p.strip().split(':')[0].strip() for p in params.split(',') if p.strip()]
            
            # Find the function body in the diff
            func_body = self._extract_function_body(code_changes, func_name)
            
            # Analyze the function logic
            conditions = self._extract_conditions(func_body)
            outputs = self._extract_outputs(func_body)
            side_effects = self._extract_side_effects(func_body)
            complexity = self._calculate_function_complexity(func_body)
            
            flows.append(LogicFlow(
                function_name=func_name,
                inputs=inputs,
                outputs=outputs,
                conditions=conditions,
                side_effects=side_effects,
                complexity_score=complexity
            ))
        
        return flows
    
    def _extract_function_body(self, code_changes: str, func_name: str) -> str:
        """Extract the body of a specific function from code changes."""
        lines = code_changes.split('\n')
        in_function = False
        function_lines = []
        indent_level = 0
        
        for line in lines:
            if line.startswith('+'):
                clean_line = line[1:]  # Remove + prefix
                
                if f'def {func_name}(' in clean_line:
                    in_function = True
                    indent_level = len(clean_line) - len(clean_line.lstrip())
                    function_lines.append(clean_line)
                elif in_function:
                    current_indent = len(clean_line) - len(clean_line.lstrip())
                    if clean_line.strip() and current_indent <= indent_level and not clean_line.strip().startswith('#'):
                        # End of function
                        break
                    function_lines.append(clean_line)
        
        return '\n'.join(function_lines)
    
    def _extract_conditions(self, func_body: str) -> List[str]:
        """Extract conditional logic from function body."""
        conditions = []
        
        # Find if statements
        if_pattern = r'if\s+([^:]+):'
        conditions.extend(re.findall(if_pattern, func_body))
        
        # Find elif statements
        elif_pattern = r'elif\s+([^:]+):'
        conditions.extend(re.findall(elif_pattern, func_body))
        
        # Find while loops
        while_pattern = r'while\s+([^:]+):'
        conditions.extend(re.findall(while_pattern, func_body))
        
        # Find assert statements
        assert_pattern = r'assert\s+([^,\n]+)'
        conditions.extend(re.findall(assert_pattern, func_body))
        
        return [c.strip() for c in conditions]
    
    def _extract_outputs(self, func_body: str) -> List[str]:
        """Extract return statements and output variables."""
        outputs = []
        
        # Find return statements
        return_pattern = r'return\s+([^#\n]+)'
        returns = re.findall(return_pattern, func_body)
        outputs.extend([r.strip() for r in returns])
        
        # Find yield statements
        yield_pattern = r'yield\s+([^#\n]+)'
        yields = re.findall(yield_pattern, func_body)
        outputs.extend([y.strip() for y in yields])
        
        return outputs
    
    def _extract_side_effects(self, func_body: str) -> List[str]:
        """Extract side effects like database calls, file operations, network calls."""
        side_effects = []
        
        # Database operations
        db_patterns = [
            r'\.save\(\)',
            r'\.delete\(\)',
            r'\.update\(',
            r'\.execute\(',
            r'\.commit\(\)',
            r'\.rollback\(\)'
        ]
        
        for pattern in db_patterns:
            if re.search(pattern, func_body):
                side_effects.append(f"Database operation: {pattern}")
        
        # File operations
        file_patterns = [
            r'open\(',
            r'\.write\(',
            r'\.read\(',
            r'os\.remove\(',
            r'shutil\.'
        ]
        
        for pattern in file_patterns:
            if re.search(pattern, func_body):
                side_effects.append(f"File operation: {pattern}")
        
        # Network calls
        network_patterns = [
            r'requests\.',
            r'urllib\.',
            r'http\.',
            r'\.send\(',
            r'\.post\(',
            r'\.get\('
        ]
        
        for pattern in network_patterns:
            if re.search(pattern, func_body):
                side_effects.append(f"Network operation: {pattern}")
        
        return side_effects
    
    def _calculate_function_complexity(self, func_body: str) -> float:
        """Calculate cyclomatic complexity and other metrics."""
        complexity = 1  # Base complexity
        
        # Count decision points
        decision_keywords = ['if', 'elif', 'while', 'for', 'except', 'and', 'or']
        for keyword in decision_keywords:
            complexity += len(re.findall(rf'\b{keyword}\b', func_body))
        
        # Normalize to 0-1 scale
        return min(complexity / 20.0, 1.0)
    
    def _extract_business_rules(self, requirements_context: str) -> List[BusinessRule]:
        """Extract business rules from requirements context."""
        rules = []
        
        # Look for "must" statements
        must_pattern = r'(must\s+[^.!?]*[.!?])'
        must_statements = re.findall(must_pattern, requirements_context, re.IGNORECASE)
        
        for statement in must_statements:
            rule = BusinessRule(
                rule_text=statement.strip(),
                affected_functions=[],  # Will be populated later
                validation_conditions=[],
                priority="high"
            )
            rules.append(rule)
        
        # Look for "should" statements
        should_pattern = r'(should\s+[^.!?]*[.!?])'
        should_statements = re.findall(should_pattern, requirements_context, re.IGNORECASE)
        
        for statement in should_statements:
            rule = BusinessRule(
                rule_text=statement.strip(),
                affected_functions=[],
                validation_conditions=[],
                priority="medium"
            )
            rules.append(rule)
        
        return rules
    
    def _check_business_rule_compliance(self, code_changes: str) -> List[Dict[str, Any]]:
        """Check if code changes comply with extracted business rules."""
        violations = []
        
        for rule in self.business_rules:
            # Check if the rule is addressed in the code
            rule_keywords = self._extract_keywords_from_rule(rule.rule_text)
            
            # Look for these keywords in the code changes
            found_keywords = []
            for keyword in rule_keywords:
                if keyword.lower() in code_changes.lower():
                    found_keywords.append(keyword)
            
            # If rule seems relevant but not properly implemented
            if len(rule_keywords) > 0 and len(found_keywords) / len(rule_keywords) < 0.5:
                violations.append({
                    "rule": rule.rule_text,
                    "priority": rule.priority,
                    "issue": f"Rule mentions {rule_keywords} but code only addresses {found_keywords}",
                    "completeness": len(found_keywords) / len(rule_keywords) if rule_keywords else 0
                })
        
        return violations
    
    def _extract_keywords_from_rule(self, rule_text: str) -> List[str]:
        """Extract key terms from a business rule."""
        # Remove common words and extract meaningful terms
        common_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'must', 'should', 'will', 'can', 'could', 'would'}
        
        words = re.findall(r'\b\w+\b', rule_text.lower())
        keywords = [w for w in words if w not in common_words and len(w) > 2]
        
        return keywords[:5]  # Return top 5 keywords
    
    def _analyze_semantic_consistency(self, code_changes: str, pr_description: str) -> List[Dict[str, Any]]:
        """Analyze semantic consistency between PR description and code implementation."""
        mismatches = []
        
        # Extract claimed actions from PR description
        action_patterns = [
            r'(?:add|implement|create|build)(?:ed|s)?\s+([^.!\n]+)',
            r'(?:fix|resolve|solve)(?:ed|s)?\s+([^.!\n]+)',
            r'(?:update|modify|change)(?:ed|s)?\s+([^.!\n]+)',
            r'(?:remove|delete)(?:ed|s)?\s+([^.!\n]+)'
        ]
        
        claimed_actions = []
        for pattern in action_patterns:
            matches = re.findall(pattern, pr_description, re.IGNORECASE)
            claimed_actions.extend(matches)
        
        # Analyze actual code changes
        actual_changes = self._categorize_code_changes(code_changes)
        
        # Check for semantic mismatches
        for claimed in claimed_actions:
            claimed_lower = claimed.lower().strip()
            found_match = False
            
            for category, items in actual_changes.items():
                for item in items:
                    if any(word in item.lower() for word in claimed_lower.split()[:3]):  # Check first 3 words
                        found_match = True
                        break
                if found_match:
                    break
            
            if not found_match and len(claimed_lower) > 10:  # Ignore very short claims
                mismatches.append({
                    "claimed_action": claimed.strip(),
                    "issue": "No matching implementation found in code changes",
                    "severity": "medium"
                })
        
        return mismatches
    
    def _categorize_code_changes(self, code_changes: str) -> Dict[str, List[str]]:
        """Categorize code changes by type."""
        categories = {
            "functions_added": [],
            "classes_added": [],
            "imports_added": [],
            "functions_modified": [],
            "variables_added": []
        }
        
        lines = code_changes.split('\n')
        for line in lines:
            if line.startswith('+'):
                clean_line = line[1:].strip()
                
                if clean_line.startswith('def '):
                    func_name = re.search(r'def\s+(\w+)', clean_line)
                    if func_name:
                        categories["functions_added"].append(func_name.group(1))
                
                elif clean_line.startswith('class '):
                    class_name = re.search(r'class\s+(\w+)', clean_line)
                    if class_name:
                        categories["classes_added"].append(class_name.group(1))
                
                elif clean_line.startswith('import ') or clean_line.startswith('from '):
                    categories["imports_added"].append(clean_line)
                
                elif '=' in clean_line and not clean_line.startswith('#'):
                    var_match = re.search(r'(\w+)\s*=', clean_line)
                    if var_match:
                        categories["variables_added"].append(var_match.group(1))
        
        return categories
    
    def _analyze_edge_cases(self, code_changes: str, rag_patterns: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Analyze edge cases using similar patterns from RAG."""
        edge_case_gaps = []
        
        # Common edge cases to check for
        edge_case_patterns = {
            "null_checks": [r'if\s+\w+\s+is\s+None', r'if\s+not\s+\w+', r'\.get\('],
            "empty_collections": [r'if\s+len\(', r'if\s+\w+:', r'\.empty\(\)'],
            "boundary_conditions": [r'<=|>=|<|>', r'range\(', r'\.split\('],
            "exception_handling": [r'try:', r'except\s+\w+', r'raise\s+\w+'],
        }
        
        for case_type, patterns in edge_case_patterns.items():
            found_any = any(re.search(pattern, code_changes) for pattern in patterns)
            
            if not found_any:
                # Check if RAG patterns suggest this edge case is important
                relevant_patterns = []
                for rag_pattern in rag_patterns:
                    content = rag_pattern.get('content_snippet', '')
                    if any(re.search(pattern, content) for pattern in patterns):
                        relevant_patterns.append(rag_pattern.get('file_path', 'unknown'))
                
                if relevant_patterns:
                    edge_case_gaps.append({
                        "case_type": case_type,
                        "issue": f"No {case_type.replace('_', ' ')} found but similar code uses it",
                        "similar_files": relevant_patterns[:3],  # Show top 3
                        "severity": "medium"
                    })
        
        return edge_case_gaps
    
    def _analyze_complexity_concerns(self, code_changes: str) -> List[Dict[str, Any]]:
        """Analyze complexity and maintainability concerns."""
        concerns = []
        
        for flow in self.logic_flows:
            if flow.complexity_score > 0.7:  # High complexity threshold
                concerns.append({
                    "function": flow.function_name,
                    "issue": f"High complexity score: {flow.complexity_score:.2f}",
                    "conditions_count": len(flow.conditions),
                    "side_effects_count": len(flow.side_effects),
                    "recommendation": "Consider breaking into smaller functions"
                })
        
        # Check for deeply nested code
        nesting_pattern = r'(\s+)(if|while|for|try).*:.*\n(\1\s{4,})(if|while|for|try)'
        deep_nesting = re.findall(nesting_pattern, code_changes, re.MULTILINE)
        
        if deep_nesting:
            concerns.append({
                "issue": f"Deep nesting detected in {len(deep_nesting)} locations",
                "severity": "medium",
                "recommendation": "Consider extracting nested logic into separate functions"
            })
        
        return concerns
    
    def _analyze_integration_logic(self, code_changes: str) -> List[Dict[str, Any]]:
        """Analyze integration points and external dependencies."""
        integration_issues = []
        
        # Check for API calls without error handling
        api_patterns = [
            r'requests\.(?:get|post|put|delete)\([^)]*\)',
            r'urllib\.',
            r'http\.'
        ]
        
        for pattern in api_patterns:
            matches = re.findall(pattern, code_changes)
            if matches:
                # Check if there's proper error handling nearby
                lines = code_changes.split('\n')
                for i, line in enumerate(lines):
                    if re.search(pattern, line):
                        # Look for try/except in surrounding lines
                        surrounding_lines = lines[max(0, i-3):i+4]
                        has_error_handling = any('try:' in l or 'except' in l for l in surrounding_lines)
                        
                        if not has_error_handling:
                            integration_issues.append({
                                "issue": f"API call without error handling: {pattern}",
                                "line_context": line.strip(),
                                "severity": "high",
                                "recommendation": "Add try/except block for network operations"
                            })
        
        return integration_issues
    
    def _calculate_risk_score(self, analysis: Dict[str, Any]) -> float:
        """Calculate overall risk score based on analysis results."""
        risk_factors = []
        
        # Business rule violations
        rule_violations = len(analysis.get("business_rule_violations", []))
        if rule_violations > 0:
            risk_factors.append(min(rule_violations * 0.2, 0.4))
        
        # Semantic mismatches
        semantic_issues = len(analysis.get("semantic_mismatches", []))
        if semantic_issues > 0:
            risk_factors.append(min(semantic_issues * 0.15, 0.3))
        
        # Edge case gaps
        edge_case_gaps = len(analysis.get("edge_case_gaps", []))
        if edge_case_gaps > 0:
            risk_factors.append(min(edge_case_gaps * 0.1, 0.2))
        
        # Complexity concerns
        complexity_concerns = len(analysis.get("complexity_concerns", []))
        if complexity_concerns > 0:
            risk_factors.append(min(complexity_concerns * 0.1, 0.2))
        
        # Integration issues
        integration_issues = len(analysis.get("integration_issues", []))
        if integration_issues > 0:
            risk_factors.append(min(integration_issues * 0.2, 0.3))
        
        return min(sum(risk_factors), 1.0)
    
    def _flow_to_dict(self, flow: LogicFlow) -> Dict[str, Any]:
        """Convert LogicFlow to dictionary for serialization."""
        return {
            "function_name": flow.function_name,
            "inputs": flow.inputs,
            "outputs": flow.outputs,
            "conditions": flow.conditions,
            "side_effects": flow.side_effects,
            "complexity_score": flow.complexity_score
        }