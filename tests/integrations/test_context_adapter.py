"""Unit tests for context_adapter.py."""

import pytest
from datetime import datetime
from dataclasses import dataclass
from typing import Dict, Any, List, Optional

from coderabbit_ai.integrations.context_adapter import ContextAdapter
from coderabbit_ai.integrations.hybrid_context_provider import HybridContext
from coderabbit_ai.integrations.deepwiki_client import DeepWikiContext
from coderabbit_ai.models import GraphContextData, DeepWikiContextData, HybridContextData


class TestHybridToGraphContext:
    """Test hybrid_to_graph_context conversion."""

    def test_basic_conversion(self):
        """Test basic conversion from HybridContext to GraphContextData."""
        hybrid_ctx = HybridContext(
            graph_context={
                'impact_analysis': {
                    'risk_level': 'HIGH',
                    'impact_score': 0.75,
                    'affected_files_count': 15,
                    'critical_files': [
                        {'file': 'src/core.py', 'direct_dependents': 8}
                    ],
                    'component_breakdown': {'api': 10, 'db': 5}
                },
                'dependency_info': {
                    'src/core.py': {
                        'metrics': {'fan_in': 10, 'fan_out': 5, 'is_hub': True}
                    }
                },
                'recommendations': ['Add tests', 'Refactor database']
            },
            deepwiki_context=None,
            deepwiki_available=False,
            on_demand_context=None,
            repo='test/repo',
            changed_files=['src/api.py', 'src/core.py'],
            timestamp=datetime.now()
        )

        result = ContextAdapter.hybrid_to_graph_context(hybrid_ctx)

        assert isinstance(result, GraphContextData)
        assert result.risk_level == 'HIGH'
        assert result.impact_score == 0.75
        assert result.affected_files_count == 15
        assert len(result.directly_affected) == 1
        assert result.component_breakdown == {'api': 10, 'db': 5}
        assert len(result.recommendations) == 2

    def test_empty_dependency_info(self):
        """Test conversion with empty dependency_info."""
        hybrid_ctx = HybridContext(
            graph_context={
                'impact_analysis': {
                    'risk_level': 'LOW',
                    'impact_score': 0.1,
                    'affected_files_count': 2,
                    'critical_files': [],
                    'component_breakdown': {}
                }
            },
            deepwiki_context=None,
            deepwiki_available=False,
            on_demand_context=None,
            repo='test/repo',
            changed_files=['src/api.py'],
            timestamp=datetime.now()
        )

        result = ContextAdapter.hybrid_to_graph_context(hybrid_ctx)

        assert result.risk_level == 'LOW'
        assert result.impact_score == 0.1
        assert len(result.directly_affected) == 0
        assert result.dependency_info == {}


class TestHybridToDeepWikiContext:
    """Test hybrid_to_deepwiki_context conversion."""

    def test_with_deepwiki_available(self):
        """Test conversion when DeepWiki context is available."""
        deepwiki_ctx = DeepWikiContext(
            repo='test/repo',
            architectural_overview='Test architecture overview',
            component_relationships={
                'src/api.py': {'raw_answer': 'API module handles HTTP requests'}
            },
            relevant_documentation=['README.md', 'docs/api.md'],
            patterns_and_conventions=['Use type hints', 'Follow PEP 8'],
            timestamp=datetime.now()
        )

        hybrid_ctx = HybridContext(
            graph_context={'impact_analysis': {'risk_level': 'LOW', 'impact_score': 0.0, 'affected_files_count': 0, 'critical_files': [], 'component_breakdown': {}}},
            deepwiki_context=deepwiki_ctx,
            deepwiki_available=True,
            on_demand_context=None,
            repo='test/repo',
            changed_files=[],
            timestamp=datetime.now()
        )

        result = ContextAdapter.hybrid_to_deepwiki_context(hybrid_ctx)

        assert isinstance(result, DeepWikiContextData)
        assert result.repo == 'test/repo'
        assert result.architectural_overview == 'Test architecture overview'
        assert result.available == True
        assert len(result.relevant_documentation) == 1
        assert len(result.patterns_and_conventions) == 1

    def test_without_deepwiki_available(self):
        """Test conversion returns None when DeepWiki is unavailable."""
        hybrid_ctx = HybridContext(
            graph_context={'impact_analysis': {'risk_level': 'LOW', 'impact_score': 0.0, 'affected_files_count': 0, 'critical_files': [], 'component_breakdown': {}}},
            deepwiki_context=None,
            deepwiki_available=False,
            on_demand_context=None,
            repo='test/repo',
            changed_files=[],
            timestamp=datetime.now()
        )

        result = ContextAdapter.hybrid_to_deepwiki_context(hybrid_ctx)

        assert result is None


class TestHybridToHybridContextData:
    """Test hybrid_to_hybrid_context_data conversion."""

    def test_complete_conversion(self):
        """Test complete conversion from HybridContext to HybridContextData."""
        deepwiki_ctx = DeepWikiContext(
            repo='test/repo',
            architectural_overview='Test architecture',
            component_relationships={},
            relevant_documentation=[],
            patterns_and_conventions=[],
            timestamp=datetime.now()
        )

        hybrid_ctx = HybridContext(
            graph_context={
                'impact_analysis': {
                    'risk_level': 'MEDIUM',
                    'impact_score': 0.5,
                    'affected_files_count': 10,
                    'critical_files': [],
                    'component_breakdown': {}
                }
            },
            deepwiki_context=deepwiki_ctx,
            deepwiki_available=True,
            on_demand_context=None,
            repo='test/repo',
            changed_files=['src/api.py'],
            timestamp=datetime.now()
        )

        result = ContextAdapter.hybrid_to_hybrid_context_data(hybrid_ctx)

        assert isinstance(result, HybridContextData)
        assert result.graph_context.risk_level == 'MEDIUM'
        assert result.deepwiki_context is not None
        assert result.deepwiki_context.available == True
        assert 'graph' in result.context_sources
        assert 'deepwiki' in result.context_sources

    def test_without_deepwiki(self):
        """Test conversion without DeepWiki context."""
        hybrid_ctx = HybridContext(
            graph_context={
                'impact_analysis': {
                    'risk_level': 'LOW',
                    'impact_score': 0.2,
                    'affected_files_count': 5,
                    'critical_files': [],
                    'component_breakdown': {}
                }
            },
            deepwiki_context=None,
            deepwiki_available=False,
            on_demand_context=None,
            repo='test/repo',
            changed_files=[],
            timestamp=datetime.now()
        )

        result = ContextAdapter.hybrid_to_hybrid_context_data(hybrid_ctx)

        assert result.graph_context.risk_level == 'LOW'
        assert result.deepwiki_context is None
        assert result.context_sources == ['graph']


class TestFormatGraphContextForLLM:
    """Test format_graph_context_for_llm method."""

    def test_basic_formatting(self):
        """Test basic graph context formatting."""
        ctx = GraphContextData(
            risk_level='HIGH',
            impact_score=0.75,
            affected_files_count=15,
            directly_affected=['src/api.py'],
            transitively_affected=[],
            critical_files=[],
            component_breakdown={},
            recommendations=[],
            dependency_info={}
        )

        result = ContextAdapter.format_graph_context_for_llm(ctx)

        assert '## Dependency Graph Analysis' in result
        assert '**Risk Level**: HIGH' in result
        assert '**Impact Score**: 75.0%' in result
        assert '**Affected Files**: 15' in result

    def test_with_critical_files(self):
        """Test formatting with critical files."""
        ctx = GraphContextData(
            risk_level='HIGH',
            impact_score=0.8,
            affected_files_count=20,
            directly_affected=[],
            transitively_affected=[],
            critical_files=[
                {'file': 'src/core.py', 'direct_dependents': 10},
                {'file': 'src/db.py', 'direct_dependents': 5}
            ],
            component_breakdown={},
            recommendations=[],
            dependency_info={}
        )

        result = ContextAdapter.format_graph_context_for_llm(ctx)

        assert '**Critical Files**:' in result
        assert '`core.py`' in result
        assert '10 direct dependents' in result

    def test_with_component_breakdown(self):
        """Test formatting with component breakdown."""
        ctx = GraphContextData(
            risk_level='MEDIUM',
            impact_score=0.5,
            affected_files_count=10,
            directly_affected=[],
            transitively_affected=[],
            critical_files=[],
            component_breakdown={'api': 5, 'db': 3, 'utils': 2},
            recommendations=[],
            dependency_info={}
        )

        result = ContextAdapter.format_graph_context_for_llm(ctx)

        assert '**Impact by Component**:' in result
        assert 'api: 5 files' in result
        assert 'db: 3 files' in result

    def test_with_dependency_info(self):
        """Test formatting with dependency info."""
        ctx = GraphContextData(
            risk_level='MEDIUM',
            impact_score=0.5,
            affected_files_count=5,
            directly_affected=[],
            transitively_affected=[],
            critical_files=[],
            component_breakdown={},
            recommendations=[],
            dependency_info={
                'src/core.py': {
                    'metrics': {'fan_in': 10, 'fan_out': 5, 'is_hub': True}
                }
            }
        )

        result = ContextAdapter.format_graph_context_for_llm(ctx)

        assert '**File Dependencies**:' in result
        assert '`core.py`' in result
        assert 'fan-in=10' in result
        assert 'fan-out=5' in result
        assert '[HUB]' in result

    def test_with_recommendations(self):
        """Test formatting with recommendations."""
        ctx = GraphContextData(
            risk_level='HIGH',
            impact_score=0.7,
            affected_files_count=10,
            directly_affected=[],
            transitively_affected=[],
            critical_files=[],
            component_breakdown={},
            recommendations=['Add tests', 'Refactor database', 'Update docs'],
            dependency_info={}
        )

        result = ContextAdapter.format_graph_context_for_llm(ctx)

        assert '**Recommendations**:' in result
        assert 'Add tests' in result
        assert 'Refactor database' in result


class TestFormatDeepWikiContextForLLM:
    """Test format_deepwiki_context_for_llm method."""

    def test_none_context(self):
        """Test with None context."""
        result = ContextAdapter.format_deepwiki_context_for_llm(None)
        assert result == ''

    def test_unavailable_context(self):
        """Test with unavailable context."""
        ctx = DeepWikiContextData(
            repo='test/repo',
            architectural_overview='Test',
            component_relationships={},
            relevant_documentation=[],
            patterns_and_conventions=[],
            available=False
        )
        result = ContextAdapter.format_deepwiki_context_for_llm(ctx)
        assert result == ''

    def test_available_context(self):
        """Test with available context."""
        ctx = DeepWikiContextData(
            repo='test/repo',
            architectural_overview='This is a test architecture overview',
            component_relationships={
                'src/api.py': {'raw_answer': 'API handles requests'}
            },
            relevant_documentation=['README.md', 'docs/api.md'],
            patterns_and_conventions=['Use type hints', 'PEP 8'],
            available=True
        )

        result = ContextAdapter.format_deepwiki_context_for_llm(ctx)

        assert '## DeepWiki Semantic Context' in result
        assert '**Repository**: test/repo' in result
        assert '**Architectural Overview**:' in result
        assert 'This is a test architecture overview' in result
        assert '**Component Relationships**:' in result
        assert '**Patterns & Conventions**:' in result
        assert '**Relevant Documentation**:' in result


class TestFormatHybridContextForLLM:
    """Test format_hybrid_context_for_llm method."""

    def test_graph_only(self):
        """Test formatting with only graph context."""
        graph_ctx = GraphContextData(
            risk_level='MEDIUM',
            impact_score=0.5,
            affected_files_count=10,
            directly_affected=[],
            transitively_affected=[],
            critical_files=[],
            component_breakdown={},
            recommendations=[],
            dependency_info={}
        )

        hybrid_ctx = HybridContextData(
            graph_context=graph_ctx,
            deepwiki_context=None,
            context_sources=['graph']
        )

        result = ContextAdapter.format_hybrid_context_for_llm(hybrid_ctx)

        assert '# Multi-Layer Context Analysis' in result
        assert '**Context Sources**: graph' in result
        assert '## Dependency Graph Analysis' in result
        assert '## DeepWiki Semantic Context' not in result

    def test_graph_and_deepwiki(self):
        """Test formatting with graph and DeepWiki context."""
        graph_ctx = GraphContextData(
            risk_level='HIGH',
            impact_score=0.8,
            affected_files_count=15,
            directly_affected=[],
            transitively_affected=[],
            critical_files=[],
            component_breakdown={},
            recommendations=[],
            dependency_info={}
        )

        deepwiki_ctx = DeepWikiContextData(
            repo='test/repo',
            architectural_overview='Test',
            component_relationships={},
            relevant_documentation=[],
            patterns_and_conventions=[],
            available=True
        )

        hybrid_ctx = HybridContextData(
            graph_context=graph_ctx,
            deepwiki_context=deepwiki_ctx,
            context_sources=['graph', 'deepwiki']
        )

        result = ContextAdapter.format_hybrid_context_for_llm(hybrid_ctx)

        assert '# Multi-Layer Context Analysis' in result
        assert '**Context Sources**: graph, deepwiki' in result
        assert '## Dependency Graph Analysis' in result
        assert '## DeepWiki Semantic Context' in result
        assert '---' in result


class TestExtractChangedFilesFromPR:
    """Test extract_changed_files_from_pr method."""

    def test_with_objects(self):
        """Test extraction with objects having .path attribute."""
        @dataclass
        class FileChange:
            path: str

        changes = [
            FileChange(path='src/api.py'),
            FileChange(path='src/core.py'),
            FileChange(path='tests/test_api.py')
        ]

        result = ContextAdapter.extract_changed_files_from_pr(changes)

        assert result == ['src/api.py', 'src/core.py', 'tests/test_api.py']

    def test_with_dicts(self):
        """Test extraction with dictionary changes."""
        changes = [
            {'path': 'src/api.py'},
            {'path': 'src/core.py'},
            {'path': 'tests/test_api.py'}
        ]

        result = ContextAdapter.extract_changed_files_from_pr(changes)

        assert result == ['src/api.py', 'src/core.py', 'tests/test_api.py']

    def test_mixed_format(self):
        """Test extraction with mixed object and dict formats."""
        @dataclass
        class FileChange:
            path: str

        changes = [
            FileChange(path='src/api.py'),
            {'path': 'src/core.py'},
            FileChange(path='tests/test_api.py')
        ]

        result = ContextAdapter.extract_changed_files_from_pr(changes)

        assert result == ['src/api.py', 'src/core.py', 'tests/test_api.py']

    def test_empty_paths(self):
        """Test extraction filters out empty paths."""
        changes = [
            {'path': 'src/api.py'},
            {'path': ''},
            {'path': 'src/core.py'}
        ]

        result = ContextAdapter.extract_changed_files_from_pr(changes)

        assert result == ['src/api.py', 'src/core.py']

    def test_unknown_format_logs_warning(self, caplog):
        """Test extraction logs warning for unknown format."""
        changes = [
            {'path': 'src/api.py'},
            'invalid_format',
            {'path': 'src/core.py'}
        ]

        with caplog.at_level('WARNING'):
            result = ContextAdapter.extract_changed_files_from_pr(changes)

        assert result == ['src/api.py', 'src/core.py']
        assert 'Unknown file change format' in caplog.text


class TestGetRiskLevelWeight:
    """Test get_risk_level_weight method."""

    def test_low_risk(self):
        """Test LOW risk level weight."""
        weight = ContextAdapter.get_risk_level_weight('LOW')
        assert weight == 0.2

    def test_medium_risk(self):
        """Test MEDIUM risk level weight."""
        weight = ContextAdapter.get_risk_level_weight('MEDIUM')
        assert weight == 0.5

    def test_high_risk(self):
        """Test HIGH risk level weight."""
        weight = ContextAdapter.get_risk_level_weight('HIGH')
        assert weight == 0.8

    def test_critical_risk(self):
        """Test CRITICAL risk level weight."""
        weight = ContextAdapter.get_risk_level_weight('CRITICAL')
        assert weight == 1.0

    def test_case_insensitive(self):
        """Test case insensitivity."""
        weight = ContextAdapter.get_risk_level_weight('low')
        assert weight == 0.2

    def test_unknown_risk_level(self):
        """Test unknown risk level defaults to MEDIUM."""
        weight = ContextAdapter.get_risk_level_weight('UNKNOWN')
        assert weight == 0.5


class TestShouldApplyExtraScrutiny:
    """Test should_apply_extra_scrutiny method."""

    def test_high_risk(self):
        """Test HIGH risk triggers extra scrutiny."""
        graph_ctx = GraphContextData(
            risk_level='HIGH',
            impact_score=0.1,
            affected_files_count=5,
            directly_affected=[],
            transitively_affected=[],
            critical_files=[],
            component_breakdown={},
            recommendations=[],
            dependency_info={}
        )

        hybrid_ctx = HybridContextData(
            graph_context=graph_ctx,
            deepwiki_context=None,
            context_sources=['graph']
        )

        assert ContextAdapter.should_apply_extra_scrutiny(hybrid_ctx) == True

    def test_critical_risk(self):
        """Test CRITICAL risk triggers extra scrutiny."""
        graph_ctx = GraphContextData(
            risk_level='CRITICAL',
            impact_score=0.1,
            affected_files_count=5,
            directly_affected=[],
            transitively_affected=[],
            critical_files=[],
            component_breakdown={},
            recommendations=[],
            dependency_info={}
        )

        hybrid_ctx = HybridContextData(
            graph_context=graph_ctx,
            deepwiki_context=None,
            context_sources=['graph']
        )

        assert ContextAdapter.should_apply_extra_scrutiny(hybrid_ctx) == True

    def test_large_impact(self):
        """Test large impact score triggers extra scrutiny."""
        graph_ctx = GraphContextData(
            risk_level='LOW',
            impact_score=0.4,
            affected_files_count=5,
            directly_affected=[],
            transitively_affected=[],
            critical_files=[],
            component_breakdown={},
            recommendations=[],
            dependency_info={}
        )

        hybrid_ctx = HybridContextData(
            graph_context=graph_ctx,
            deepwiki_context=None,
            context_sources=['graph']
        )

        assert ContextAdapter.should_apply_extra_scrutiny(hybrid_ctx) == True

    def test_critical_files(self):
        """Test critical files trigger extra scrutiny."""
        graph_ctx = GraphContextData(
            risk_level='LOW',
            impact_score=0.2,
            affected_files_count=5,
            directly_affected=[],
            transitively_affected=[],
            critical_files=[{'file': 'src/core.py', 'direct_dependents': 10}],
            component_breakdown={},
            recommendations=[],
            dependency_info={}
        )

        hybrid_ctx = HybridContextData(
            graph_context=graph_ctx,
            deepwiki_context=None,
            context_sources=['graph']
        )

        assert ContextAdapter.should_apply_extra_scrutiny(hybrid_ctx) == True

    def test_many_affected_files(self):
        """Test many affected files trigger extra scrutiny."""
        graph_ctx = GraphContextData(
            risk_level='LOW',
            impact_score=0.2,
            affected_files_count=25,
            directly_affected=[],
            transitively_affected=[],
            critical_files=[],
            component_breakdown={},
            recommendations=[],
            dependency_info={}
        )

        hybrid_ctx = HybridContextData(
            graph_context=graph_ctx,
            deepwiki_context=None,
            context_sources=['graph']
        )

        assert ContextAdapter.should_apply_extra_scrutiny(hybrid_ctx) == True

    def test_no_extra_scrutiny(self):
        """Test no extra scrutiny needed for low-risk changes."""
        graph_ctx = GraphContextData(
            risk_level='LOW',
            impact_score=0.2,
            affected_files_count=5,
            directly_affected=[],
            transitively_affected=[],
            critical_files=[],
            component_breakdown={},
            recommendations=[],
            dependency_info={}
        )

        hybrid_ctx = HybridContextData(
            graph_context=graph_ctx,
            deepwiki_context=None,
            context_sources=['graph']
        )

        assert ContextAdapter.should_apply_extra_scrutiny(hybrid_ctx) == False


class TestGetContextQualityScore:
    """Test get_context_quality_score method."""

    def test_graph_only(self):
        """Test quality score with only graph context."""
        graph_ctx = GraphContextData(
            risk_level='LOW',
            impact_score=0.2,
            affected_files_count=5,
            directly_affected=[],
            transitively_affected=[],
            critical_files=[],
            component_breakdown={},
            recommendations=[],
            dependency_info={}
        )

        hybrid_ctx = HybridContextData(
            graph_context=graph_ctx,
            deepwiki_context=None,
            context_sources=['graph']
        )

        score = ContextAdapter.get_context_quality_score(hybrid_ctx)
        assert score == 0.6

    def test_graph_and_deepwiki_basic(self):
        """Test quality score with basic DeepWiki."""
        graph_ctx = GraphContextData(
            risk_level='LOW',
            impact_score=0.2,
            affected_files_count=5,
            directly_affected=[],
            transitively_affected=[],
            critical_files=[],
            component_breakdown={},
            recommendations=[],
            dependency_info={}
        )

        deepwiki_ctx = DeepWikiContextData(
            repo='test/repo',
            architectural_overview=None,
            component_relationships={},
            relevant_documentation=[],
            patterns_and_conventions=[],
            available=True
        )

        hybrid_ctx = HybridContextData(
            graph_context=graph_ctx,
            deepwiki_context=deepwiki_ctx,
            context_sources=['graph', 'deepwiki']
        )

        score = ContextAdapter.get_context_quality_score(hybrid_ctx)
        assert score == 0.9

    def test_graph_and_deepwiki_rich(self):
        """Test quality score with rich DeepWiki content."""
        graph_ctx = GraphContextData(
            risk_level='LOW',
            impact_score=0.2,
            affected_files_count=5,
            directly_affected=[],
            transitively_affected=[],
            critical_files=[],
            component_breakdown={},
            recommendations=[],
            dependency_info={}
        )

        deepwiki_ctx = DeepWikiContextData(
            repo='test/repo',
            architectural_overview='Detailed architecture',
            component_relationships={},
            relevant_documentation=[],
            patterns_and_conventions=['Pattern 1', 'Pattern 2'],
            available=True
        )

        hybrid_ctx = HybridContextData(
            graph_context=graph_ctx,
            deepwiki_context=deepwiki_ctx,
            context_sources=['graph', 'deepwiki']
        )

        score = ContextAdapter.get_context_quality_score(hybrid_ctx)
        assert score == 1.0

    def test_unavailable_deepwiki(self):
        """Test quality score with unavailable DeepWiki."""
        graph_ctx = GraphContextData(
            risk_level='LOW',
            impact_score=0.2,
            affected_files_count=5,
            directly_affected=[],
            transitively_affected=[],
            critical_files=[],
            component_breakdown={},
            recommendations=[],
            dependency_info={}
        )

        deepwiki_ctx = DeepWikiContextData(
            repo='test/repo',
            architectural_overview='Test',
            component_relationships={},
            relevant_documentation=[],
            patterns_and_conventions=[],
            available=False
        )

        hybrid_ctx = HybridContextData(
            graph_context=graph_ctx,
            deepwiki_context=deepwiki_ctx,
            context_sources=['graph']
        )

        score = ContextAdapter.get_context_quality_score(hybrid_ctx)
        assert score == 0.6
