"""Core dependency graph for code analysis."""

import logging
from pathlib import Path
from typing import Dict, List, Set, Optional, Tuple
from dataclasses import dataclass, field
import networkx as nx

from .parsers import ParserRegistry, ImportStatement

logger = logging.getLogger(__name__)


@dataclass
class DependencyNode:
    """Represents a file node in the dependency graph."""

    file_path: str
    imports: List[str] = field(default_factory=list)
    imported_by: List[str] = field(default_factory=list)
    is_entry_point: bool = False
    language: Optional[str] = None


@dataclass
class DependencyMetrics:
    """Metrics about dependencies for a file or set of files."""

    total_dependencies: int  # Number of files this depends on
    total_dependents: int  # Number of files depending on this
    depth: int  # Max depth in dependency tree
    fan_out: int  # Direct dependencies
    fan_in: int  # Direct dependents
    is_hub: bool  # True if high fan-in (many dependents)
    is_leaf: bool  # True if no dependencies
    is_isolated: bool  # True if no deps and no dependents


class DependencyGraph:
    """Graph-based dependency analysis for code repositories."""

    def __init__(self, project_root: str):
        """
        Initialize dependency graph.

        Args:
            project_root: Root directory of the project
        """
        self.project_root = Path(project_root)
        self.graph = nx.DiGraph()  # Directed graph: A -> B means A imports B
        self.parser_registry = ParserRegistry()
        self._file_to_imports: Dict[str, List[ImportStatement]] = {}

    def build_graph(self, file_paths: Optional[List[str]] = None) -> None:
        """
        Build dependency graph from project files.

        Args:
            file_paths: Specific files to analyze (default: scan entire project)
        """
        if file_paths is None:
            file_paths = self._discover_source_files()

        logger.info(f"Building dependency graph for {len(file_paths)} files")

        # Parse all files
        for file_path in file_paths:
            self._parse_and_add_file(file_path)

        # Build edges based on imports
        self._build_edges()

        logger.info(
            f"Graph built: {self.graph.number_of_nodes()} nodes, "
            f"{self.graph.number_of_edges()} edges"
        )

    def _discover_source_files(self) -> List[str]:
        """Discover all source files in project."""
        source_files = []
        extensions = {'.py', '.js', '.jsx', '.ts', '.tsx', '.go', '.java', '.rs'}

        for ext in extensions:
            source_files.extend(
                str(p) for p in self.project_root.rglob(f'*{ext}')
                if not self._is_ignored_path(p)
            )

        return source_files

    def _is_ignored_path(self, path: Path) -> bool:
        """Check if path should be ignored."""
        ignored_dirs = {
            'node_modules', 'venv', 'env', '__pycache__',
            '.git', 'dist', 'build', 'target', '.venv'
        }

        return any(ignored in path.parts for ignored in ignored_dirs)

    def _parse_and_add_file(self, file_path: str) -> None:
        """Parse file and add node to graph."""
        # Parse imports
        imports = self.parser_registry.parse_file(file_path, str(self.project_root))
        self._file_to_imports[file_path] = imports

        # Add node to graph
        self.graph.add_node(
            file_path,
            imports=[imp.module for imp in imports],
            language=self._detect_language(file_path)
        )

    def _detect_language(self, file_path: str) -> str:
        """Detect programming language from file extension."""
        suffix = Path(file_path).suffix
        lang_map = {
            '.py': 'python',
            '.js': 'javascript',
            '.jsx': 'javascript',
            '.ts': 'typescript',
            '.tsx': 'typescript',
            '.go': 'go',
            '.java': 'java',
            '.rs': 'rust',
        }
        return lang_map.get(suffix, 'unknown')

    def _build_edges(self) -> None:
        """Build graph edges based on imports."""
        # Create mapping of module names to file paths
        module_to_file = self._build_module_map()

        for file_path, imports in self._file_to_imports.items():
            for imp in imports:
                # Only add edges for local imports
                if imp.is_local:
                    target_file = module_to_file.get(imp.module)
                    if target_file and target_file in self.graph:
                        # Edge: file_path imports target_file
                        self.graph.add_edge(file_path, target_file)

    def _build_module_map(self) -> Dict[str, str]:
        """Build mapping from module names to file paths."""
        module_map = {}

        for file_path in self.graph.nodes():
            # Python: convert file path to module name
            if file_path.endswith('.py'):
                module = self._file_to_module(file_path)
                module_map[module] = file_path

            # JS/TS: use file path directly for relative imports
            # (handled in parser)

        return module_map

    def _file_to_module(self, file_path: str) -> str:
        """Convert file path to Python module name."""
        rel_path = Path(file_path).relative_to(self.project_root)
        parts = list(rel_path.parts)

        # Remove file extension
        parts[-1] = parts[-1].replace('.py', '')

        # Remove __init__
        if parts[-1] == '__init__':
            parts = parts[:-1]

        return '.'.join(parts)

    def get_dependencies(self, file_path: str) -> List[str]:
        """
        Get all files that the given file depends on (imports).

        Args:
            file_path: Path to source file

        Returns:
            List of file paths this file depends on
        """
        if file_path not in self.graph:
            return []

        # Successors in directed graph are the files this file imports
        return list(self.graph.successors(file_path))

    def get_dependents(self, file_path: str) -> List[str]:
        """
        Get all files that depend on (import) the given file.

        Args:
            file_path: Path to source file

        Returns:
            List of file paths that depend on this file
        """
        if file_path not in self.graph:
            return []

        # Predecessors in directed graph are the files that import this file
        return list(self.graph.predecessors(file_path))

    def calculate_impact(self, changed_files: List[str]) -> Dict[str, any]:
        """
        Calculate impact radius of changes.

        Args:
            changed_files: List of files being changed

        Returns:
            Dict containing:
                - directly_affected: Files that import changed files
                - transitively_affected: All files affected through dependency chain
                - impact_score: Numeric score (0-1) of impact
                - critical_files: Changed files with high fan-in
        """
        directly_affected = set()
        transitively_affected = set()
        critical_files = []

        for file_path in changed_files:
            if file_path not in self.graph:
                continue

            # Get direct dependents
            direct = set(self.get_dependents(file_path))
            directly_affected.update(direct)

            # Get transitive dependents (all files up the dependency chain)
            transitive = self._get_transitive_dependents(file_path)
            transitively_affected.update(transitive)

            # Check if this is a critical file (many dependents)
            if len(direct) >= 5:  # Threshold for "critical"
                critical_files.append({
                    'file': file_path,
                    'direct_dependents': len(direct),
                    'transitive_dependents': len(transitive)
                })

        # Calculate impact score
        total_files = self.graph.number_of_nodes()
        impact_score = len(transitively_affected) / total_files if total_files > 0 else 0

        return {
            'directly_affected': list(directly_affected),
            'transitively_affected': list(transitively_affected),
            'directly_affected_count': len(directly_affected),
            'transitively_affected_count': len(transitively_affected),
            'impact_score': impact_score,
            'critical_files': critical_files,
        }

    def _get_transitive_dependents(self, file_path: str) -> Set[str]:
        """Get all files that transitively depend on this file."""
        if file_path not in self.graph:
            return set()

        # Use BFS to find all ancestors (files that import this, directly or indirectly)
        visited = set()
        queue = [file_path]

        while queue:
            current = queue.pop(0)
            if current in visited:
                continue

            visited.add(current)

            # Add all files that import current file
            for dependent in self.graph.predecessors(current):
                if dependent not in visited:
                    queue.append(dependent)

        # Remove the starting file itself
        visited.discard(file_path)
        return visited

    def get_metrics(self, file_path: str) -> Optional[DependencyMetrics]:
        """Get dependency metrics for a file."""
        if file_path not in self.graph:
            return None

        dependencies = self.get_dependencies(file_path)
        dependents = self.get_dependents(file_path)

        # Calculate depth (longest path to a leaf)
        depth = self._calculate_depth(file_path)

        return DependencyMetrics(
            total_dependencies=len(self._get_transitive_dependencies(file_path)),
            total_dependents=len(self._get_transitive_dependents(file_path)),
            depth=depth,
            fan_out=len(dependencies),
            fan_in=len(dependents),
            is_hub=len(dependents) >= 5,
            is_leaf=len(dependencies) == 0,
            is_isolated=len(dependencies) == 0 and len(dependents) == 0
        )

    def _get_transitive_dependencies(self, file_path: str) -> Set[str]:
        """Get all files this file transitively depends on."""
        if file_path not in self.graph:
            return set()

        # Use BFS to find all descendants
        visited = set()
        queue = [file_path]

        while queue:
            current = queue.pop(0)
            if current in visited:
                continue

            visited.add(current)

            for dependency in self.graph.successors(current):
                if dependency not in visited:
                    queue.append(dependency)

        visited.discard(file_path)
        return visited

    def _calculate_depth(self, file_path: str) -> int:
        """Calculate max depth in dependency tree."""
        if file_path not in self.graph:
            return 0

        # DFS to find longest path
        def dfs(node: str, visited: Set[str]) -> int:
            if node in visited:
                return 0  # Cycle detected

            visited.add(node)
            max_depth = 0

            for successor in self.graph.successors(node):
                depth = dfs(successor, visited.copy())
                max_depth = max(max_depth, depth + 1)

            return max_depth

        return dfs(file_path, set())

    def find_cycles(self) -> List[List[str]]:
        """Find circular dependencies in the graph."""
        try:
            cycles = list(nx.simple_cycles(self.graph))
            return cycles
        except Exception as e:
            logger.error(f"Error finding cycles: {e}")
            return []

    def get_strongly_connected_components(self) -> List[Set[str]]:
        """
        Find strongly connected components (groups of mutually dependent files).

        Returns:
            List of sets, each containing files in a strongly connected component
        """
        return [set(component) for component in nx.strongly_connected_components(self.graph)]

    def export_to_dict(self) -> Dict:
        """Export graph to dictionary format for serialization."""
        return {
            'nodes': list(self.graph.nodes()),
            'edges': list(self.graph.edges()),
            'node_count': self.graph.number_of_nodes(),
            'edge_count': self.graph.number_of_edges(),
        }
