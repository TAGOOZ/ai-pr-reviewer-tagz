"""Unit tests for Graph modules."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import networkx as nx

from coderabbit_ai.graph.dependency_graph import DependencyGraph, DependencyNode, DependencyMetrics
from coderabbit_ai.graph.impact_analyzer import ImpactAnalyzer


@pytest.fixture
def test_project_root(tmp_path):
    """Create a temporary project root for testing."""
    root = tmp_path / "test_project"
    root.mkdir(parents=True)
    return root


class TestDependencyNode:
    """Test suite for DependencyNode dataclass."""

    def test_dependency_node_initialization_empty(self):
        """Test DependencyNode with no imports."""
        node = DependencyNode(file_path="test.py", imports=[], imported_by=[], is_entry_point=True)
        assert node.file_path == "test.py"
        assert node.imports == []
        assert node.imported_by == []
        assert node.is_entry_point is True

    def test_dependency_node_with_data(self):
        """Test DependencyNode with full data."""
        node = DependencyNode(
            file_path="test.py",
            imports=["module1", "module2"],
            imported_by=["test_module"],
            is_entry_point=False,
            language="python"
        )
        assert len(node.imports) == 2
        assert len(node.imported_by) == 1
        assert node.is_entry_point is False
        assert node.language == "python"


class TestDependencyMetrics:
    """Test suite for DependencyMetrics dataclass."""

    def test_dependency_metrics_zero_dependencies(self):
        """Test metrics for node with no dependencies."""
        metrics = DependencyMetrics(
            total_dependencies=0,
            total_dependents=0,
            depth=0,
            fan_out=0,
            fan_in=0,
            is_hub=False,
            is_leaf=True,
            is_isolated=True
        )

        assert metrics.total_dependencies == 0
        assert metrics.total_dependents == 0
        assert metrics.depth == 0
        assert metrics.fan_out == 0
        assert metrics.fan_in == 0
        assert metrics.is_hub is False
        assert metrics.is_leaf is True
        assert metrics.is_isolated is True

    def test_dependency_metrics_hub_node(self):
        """Test metrics for a hub node."""
        metrics = DependencyMetrics(
            total_dependencies=5,
            total_dependents=10,
            depth=3,
            fan_out=5,
            fan_in=10,
            is_hub=True,
            is_leaf=False,
            is_isolated=False
        )

        assert metrics.total_dependencies == 5
        assert metrics.total_dependents == 10
        assert metrics.is_hub is True
        assert metrics.is_leaf is False

    def test_dependency_metrics_leaf_node(self):
        """Test metrics for a leaf node."""
        metrics = DependencyMetrics(
            total_dependencies=2,
            total_dependents=0,
            depth=2,
            fan_out=2,
            fan_in=0,
            is_hub=False,
            is_leaf=True,
            is_isolated=False
        )

        assert metrics.total_dependencies == 2
        assert metrics.total_dependents == 0
        assert metrics.fan_in == 0
        assert metrics.is_leaf is True


class TestDependencyGraphInitialization:
    """Test suite for DependencyGraph initialization."""

    def test_graph_initialization(self, test_project_root):
        """Test DependencyGraph initialization."""
        graph = DependencyGraph(project_root=str(test_project_root))

        assert isinstance(graph.graph, nx.DiGraph)
        assert graph.project_root == test_project_root
        assert len(graph.graph.nodes) == 0
        assert len(graph.graph.edges) == 0

    def test_graph_initialization_with_path(self, test_project_root):
        """Test DependencyGraph initialization with Path object."""
        graph = DependencyGraph(project_root=test_project_root)

        assert graph.project_root == test_project_root


class TestDependencyGraphBuildGraph:
    """Test suite for DependencyGraph.build_graph()."""

    @patch('coderabbit_ai.graph.dependency_graph.Path')
    def test_build_graph_no_files(self, mock_path, test_project_root):
        """Test building graph with no files."""
        mock_path.return_value = test_project_root
        mock_path.is_dir.return_value = False
        mock_path.glob.return_value = []

        graph = DependencyGraph(project_root=str(test_project_root))
        result = graph.build_graph()

        assert len(result.nodes) == 0
        assert len(result.edges) == 0

    @patch('coderabbit_ai.graph.dependency_graph.Path')
    @patch('coderabbit_ai.graph.dependency_graph.os.listdir')
    def test_build_graph_with_python_files(self, mock_path, mock_listdir, test_project_root):
        """Test building graph with Python files."""
        test_file = test_project_root / "test.py"

        mock_path.return_value = test_project_root
        mock_path.is_dir.return_value = True
        mock_path.glob.return_value = [test_file]
        mock_path.is_file.return_value = True

        mock_listdir.return_value = ["test.py"]

        # Mock file reading to return empty imports
        with patch('builtins.open', MagicMock(return_value=Mock(__enter__=Mock(return_value=Mock(read=Mock(return_value=""))))):
            graph = DependencyGraph(project_root=str(test_project_root))
            result = graph.build_graph()

        assert len(result.nodes) == 0

    @patch('coderabbit_ai.graph.dependency_graph.Path')
    def test_build_graph_creates_edges(self, mock_path, test_project_root):
        """Test that build_graph creates dependency edges."""
        test_file1 = test_project_root / "module_a.py"
        test_file2 = test_project_root / "module_b.py"

        mock_path.return_value = test_project_root
        mock_path.is_dir.return_value = True
        mock_path.glob.return_value = [test_file1, test_file2]
        mock_path.is_file.return_value = True

        mock_listdir.return_value = ["module_a.py", "module_b.py"]

        # Mock file reading to simulate imports
        mock_file_content_a = "import module_b"
        mock_file_content_b = "# no imports"

        def mock_open(path, *args, **kwargs):
            mock = MagicMock()
            mock.__enter__ = Mock(return_value=mock)
            mock.read.return_value = mock_file_content_a if "module_a" in str(path) else mock_file_content_b
            return mock

        with patch('builtins.open', mock_open):
            graph = DependencyGraph(project_root=str(test_project_root))
            result = graph.build_graph()

        # Should create at least one edge: module_a -> module_b
        assert len(result.edges) >= 1


class TestDependencyGraphMetrics:
    """Test suite for DependencyGraph.get_node_metrics()."""

    def test_get_node_metrics_existing_node(self, test_project_root):
        """Test getting metrics for existing node."""
        graph = DependencyGraph(project_root=str(test_project_root))
        graph.graph.add_node("test.py")
        graph.graph.add_edge("test.py", "dep.py")

        metrics = graph.get_node_metrics("test.py")

        assert isinstance(metrics, DependencyMetrics)
        assert metrics.total_dependencies == 1
        assert metrics.fan_out == 1

    def test_get_node_metrics_nonexistent_node(self, test_project_root):
        """Test getting metrics for nonexistent node."""
        graph = DependencyGraph(project_root=str(test_project_root))

        metrics = graph.get_node_metrics("nonexistent.py")

        assert isinstance(metrics, DependencyMetrics)
        assert metrics.total_dependencies == 0
        assert metrics.total_dependents == 0
        assert metrics.is_isolated is True


class TestDependencyGraphAnalysis:
    """Test suite for DependencyGraph analysis methods."""

    @patch('coderabbit_ai.graph.dependency_graph.nx')
    def test_find_hubs(self, mock_nx):
        """Test finding hub nodes."""
        mock_graph = nx.DiGraph()
        mock_graph.add_node("hub", degree=10)
        mock_graph.add_node("leaf", degree=1)
        mock_nx.DiGraph.return_value = mock_graph

        graph = DependencyGraph(project_root="/tmp")
        graph.graph = mock_graph

        hubs = graph.find_hubs(threshold=5)

        assert "hub" in hubs
        assert "leaf" not in hubs

    @patch('coderabbit_ai.graph.dependency_graph.nx')
    def test_find_leaf_nodes(self, mock_nx):
        """Test finding leaf nodes."""
        mock_graph = nx.DiGraph()
        mock_graph.add_node("leaf", in_degree=0, out_degree=0)
        mock_graph.add_node("internal", in_degree=1, out_degree=1)
        mock_nx.DiGraph.return_value = mock_graph

        graph = DependencyGraph(project_root="/tmp")
        graph.graph = mock_graph

        leaves = graph.find_leaf_nodes()

        assert "leaf" in leaves
        assert "internal" not in leaves

    @patch('coderabbit_ai.graph.dependency_graph.nx')
    def test_find_cycles(self, mock_nx):
        """Test finding cycles in graph."""
        mock_graph = nx.DiGraph()
        mock_graph.add_node("a")
        mock_graph.add_node("b")
        mock_graph.add_node("c")
        mock_graph.add_edge("a", "b")
        mock_graph.add_edge("b", "c")
        mock_graph.add_edge("c", "a")  # Creates cycle
        mock_nx.DiGraph.return_value = mock_graph

        graph = DependencyGraph(project_root="/tmp")
        graph.graph = mock_graph

        cycles = graph.find_cycles()

        assert len(cycles) == 1
        assert len(cycles[0]) == 3  # a -> b -> c -> a

    @patch('coderabbit_ai.graph.dependency_graph.nx')
    def test_get_critical_paths(self, mock_nx):
        """Test finding critical paths in graph."""
        mock_graph = nx.DiGraph()
        mock_graph.add_node("critical")
        mock_graph.add_node("normal")
        mock_graph.add_edge("critical", "normal")
        mock_nx.DiGraph.return_value = mock_graph

        graph = DependencyGraph(project_root="/tmp")
        graph.graph = mock_graph

        paths = graph.get_critical_paths()

        assert len(paths) == 1
        assert paths[0] == ["critical", "normal"]


class TestImpactAnalyzer:
    """Test suite for ImpactAnalyzer."""

    @patch('coderabbit_ai.graph.impact_analyzer.Path')
    def test_impact_analyzer_initialization(self, mock_path):
        """Test ImpactAnalyzer initialization."""
        test_root = tmp_path / "test_project"
        test_root.mkdir(parents=True)

        mock_path.return_value = test_root

        analyzer = ImpactAnalyzer(project_root=str(test_root))

        assert analyzer.project_root == test_root

    @patch('coderabbit_ai.graph.impact_analyzer.Path')
    def test_analyze_impact_success(self, mock_path):
        """Test successful impact analysis."""
        test_root = tmp_path / "test_project"
        test_root.mkdir(parents=True)
        test_file = test_root / "test.py"
        test_file.write_text("import os\nprint('test')")

        mock_path.return_value = test_root

        analyzer = ImpactAnalyzer(project_root=str(test_root))
        impact = analyzer.analyze_file(str(test_file))

        assert impact["file_path"] == str(test_file)
        assert "dependencies" in impact
        assert "impact_score" in impact

    @patch('coderabbit_ai.graph.impact_analyzer.Path')
    def test_analyze_impact_file_not_found(self, mock_path):
        """Test impact analysis for nonexistent file."""
        mock_path.return_value = tmp_path / "nonexistent.py"
        mock_path.is_file.return_value = False

        analyzer = ImpactAnalyzer(project_root=str(tmp_path))

        impact = analyzer.analyze_file("nonexistent.py")

        assert "error" in impact
        assert "File not found" in impact["error"]


class TestGraphIntegration:
    """Integration tests for graph module interactions."""

    @patch('coderabbit_ai.graph.dependency_graph.Path')
    def test_full_graph_analysis_pipeline(self, mock_path, tmp_path):
        """Test full graph analysis from build to metrics."""
        test_root = tmp_path / "test_project"
        test_root.mkdir(parents=True)
        test_file = test_root / "main.py"
        test_file.write_text("import module_a\nimport module_b\nmodule_b")

        mock_path.return_value = test_root
        mock_path.is_dir.return_value = True
        mock_path.glob.return_value = [test_file]
        mock_path.is_file.return_value = True

        def mock_open(path, *args, **kwargs):
            mock = MagicMock()
            mock.__enter__ = Mock(return_value=mock)
            mock.read.return_value = "import module_a" if "main.py" in str(path) else "import module_b"
            return mock

        with patch('builtins.open', mock_open):
            graph = DependencyGraph(project_root=str(test_root))
            graph.build_graph()

            # Test graph structure
            assert len(graph.graph.nodes) >= 1

            # Test metrics
            if "main.py" in graph.graph.nodes:
                metrics = graph.get_node_metrics("main.py")
                assert isinstance(metrics, DependencyMetrics)


class TestGraphEdgeCases:
    """Edge case tests for graph module."""

    @patch('coderabbit_ai.graph.dependency_graph.Path')
    @patch('coderabbit_ai.graph.dependency_graph.os.access')
    def test_build_graph_permission_denied(self, mock_path, mock_access):
        """Test handling of permission denied errors."""
        test_root = tmp_path / "test_project"
        test_root.mkdir(parents=True)
        test_file = test_root / "restricted.py"
        test_file.write_text("# test")

        mock_path.return_value = test_root
        mock_path.is_dir.return_value = True
        mock_path.glob.return_value = [test_file]
        mock_access.side_effect = PermissionError("Access denied")

        graph = DependencyGraph(project_root=str(test_root))
        result = graph.build_graph()

        # Should handle permission errors gracefully
        assert isinstance(result, DependencyGraph)

    @patch('coderabbit_ai.graph.dependency_graph.Path')
    def test_build_graph_circular_dependencies(self, mock_path, tmp_path):
        """Test handling of circular dependencies."""
        test_root = tmp_path / "test_project"
        test_root.mkdir(parents=True)
        test_file1 = test_root / "a.py"
        test_file2 = test_root / "b.py"
        test_file3 = test_root / "c.py"

        # Create circular dependency: a -> b -> c -> a
        test_file1.write_text("import b\ndef func():\n    b.func()")
        test_file2.write_text("import c\ndef func():\n    c.func()")
        test_file3.write_text("import a\ndef func():\n    a.func()")

        mock_path.return_value = test_root
        mock_path.is_dir.return_value = True
        mock_path.glob.return_value = [test_file1, test_file2, test_file3]
        mock_path.is_file.return_value = True

        def mock_open(path, *args, **kwargs):
            mock = MagicMock()
            mock.__enter__ = Mock(return_value=mock)
            filename = str(path).split("/")[-1]
            content = ""
            if "a.py" in filename:
                content = "import b\ndef func():\n    b.func()"
            elif "b.py" in filename:
                content = "import c\ndef func():\n    c.func()"
            elif "c.py" in filename:
                content = "import a\ndef func():\n    a.func()"
            mock.read.return_value = content
            return mock

        with patch('builtins.open', mock_open):
            graph = DependencyGraph(project_root=str(test_root))
            result = graph.build_graph()

            # Should detect circular dependencies
            assert len(graph.graph.nodes) == 3

            # Should find cycles
            cycles = graph.find_cycles()
            assert len(cycles) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
