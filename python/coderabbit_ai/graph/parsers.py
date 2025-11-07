"""Import parsers for building dependency graphs."""

import ast
import re
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Set, Optional, Dict
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ImportStatement:
    """Represents an import in source code."""

    module: str  # Module being imported (e.g., "os.path")
    source_file: str  # File containing the import
    is_relative: bool = False
    is_local: bool = False  # True if importing from same project
    line_number: Optional[int] = None


class ImportParser(ABC):
    """Base class for language-specific import parsers."""

    @abstractmethod
    def parse_file(self, file_path: str, project_root: str) -> List[ImportStatement]:
        """Parse imports from a source file.

        Args:
            file_path: Path to source file
            project_root: Root directory of project

        Returns:
            List of ImportStatement objects
        """
        pass

    @abstractmethod
    def supports_file(self, file_path: str) -> bool:
        """Check if this parser supports the file type."""
        pass


class PythonImportParser(ImportParser):
    """Parser for Python imports."""

    EXTENSIONS = {'.py', '.pyi'}

    def supports_file(self, file_path: str) -> bool:
        """Check if file is Python."""
        return Path(file_path).suffix in self.EXTENSIONS

    def parse_file(self, file_path: str, project_root: str) -> List[ImportStatement]:
        """Parse Python imports using AST."""
        imports = []

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            tree = ast.parse(content, filename=file_path)

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.append(ImportStatement(
                            module=alias.name,
                            source_file=file_path,
                            is_relative=False,
                            is_local=self._is_local_module(alias.name, project_root),
                            line_number=node.lineno
                        ))

                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        # Resolve relative imports
                        if node.level > 0:  # Relative import
                            module = self._resolve_relative_import(
                                file_path, node.module, node.level, project_root
                            )
                        else:
                            module = node.module

                        imports.append(ImportStatement(
                            module=module,
                            source_file=file_path,
                            is_relative=node.level > 0,
                            is_local=self._is_local_module(module, project_root),
                            line_number=node.lineno
                        ))

        except Exception as e:
            logger.warning(f"Failed to parse Python imports from {file_path}: {e}")

        return imports

    def _is_local_module(self, module: str, project_root: str) -> bool:
        """Check if module is part of the project (not third-party)."""
        # Simple heuristic: check if module path exists in project
        module_path = Path(project_root) / module.replace('.', '/')
        return (
            module_path.with_suffix('.py').exists() or
            (module_path / '__init__.py').exists()
        )

    def _resolve_relative_import(
        self,
        file_path: str,
        module: Optional[str],
        level: int,
        project_root: str
    ) -> str:
        """Resolve relative import to absolute module path."""
        file_dir = Path(file_path).parent

        # Go up 'level' directories
        target_dir = file_dir
        for _ in range(level):
            target_dir = target_dir.parent

        # Convert to module path
        rel_path = target_dir.relative_to(project_root)
        module_parts = list(rel_path.parts)

        if module:
            module_parts.append(module)

        return '.'.join(module_parts)


class JavaScriptImportParser(ImportParser):
    """Parser for JavaScript/TypeScript imports."""

    EXTENSIONS = {'.js', '.jsx', '.ts', '.tsx', '.mjs', '.cjs'}

    # Regex patterns for different import styles
    IMPORT_PATTERNS = [
        # ES6 imports: import X from 'module'
        r'import\s+.*?\s+from\s+[\'"]([^\'"]+)[\'"]',
        # require: const X = require('module')
        r'require\s*\(\s*[\'"]([^\'"]+)[\'"]\s*\)',
        # Dynamic import: import('module')
        r'import\s*\(\s*[\'"]([^\'"]+)[\'"]\s*\)',
    ]

    def supports_file(self, file_path: str) -> bool:
        """Check if file is JavaScript/TypeScript."""
        return Path(file_path).suffix in self.EXTENSIONS

    def parse_file(self, file_path: str, project_root: str) -> List[ImportStatement]:
        """Parse JS/TS imports using regex."""
        imports = []

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            for line_num, line in enumerate(content.split('\n'), 1):
                # Skip comments
                if line.strip().startswith('//'):
                    continue

                for pattern in self.IMPORT_PATTERNS:
                    matches = re.finditer(pattern, line)
                    for match in matches:
                        module = match.group(1)
                        imports.append(ImportStatement(
                            module=module,
                            source_file=file_path,
                            is_relative=module.startswith('.'),
                            is_local=self._is_local_module(module, file_path, project_root),
                            line_number=line_num
                        ))

        except Exception as e:
            logger.warning(f"Failed to parse JS/TS imports from {file_path}: {e}")

        return imports

    def _is_local_module(self, module: str, file_path: str, project_root: str) -> bool:
        """Check if module is local to project."""
        # Relative imports are always local
        if module.startswith('.'):
            return True

        # Check if it's not a node_modules import
        if not module.startswith('@') and '/' not in module:
            # Could be node_modules package
            return False

        # Check if path exists in project
        module_path = Path(project_root) / module
        return module_path.exists()


class GoImportParser(ImportParser):
    """Parser for Go imports."""

    EXTENSIONS = {'.go'}

    # Regex for Go imports
    IMPORT_PATTERN = r'import\s+(?:\(\s*([^)]+)\s*\)|"([^"]+)")'

    def supports_file(self, file_path: str) -> bool:
        """Check if file is Go."""
        return Path(file_path).suffix in self.EXTENSIONS

    def parse_file(self, file_path: str, project_root: str) -> List[ImportStatement]:
        """Parse Go imports."""
        imports = []

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Find all import blocks
            for match in re.finditer(self.IMPORT_PATTERN, content, re.MULTILINE | re.DOTALL):
                if match.group(1):  # Multi-line import block
                    import_block = match.group(1)
                    for line in import_block.split('\n'):
                        line = line.strip()
                        if line and not line.startswith('//'):
                            # Extract module from quotes
                            module_match = re.search(r'"([^"]+)"', line)
                            if module_match:
                                module = module_match.group(1)
                                imports.append(ImportStatement(
                                    module=module,
                                    source_file=file_path,
                                    is_relative=module.startswith('.'),
                                    is_local=self._is_local_module(module, project_root)
                                ))
                else:  # Single import
                    module = match.group(2)
                    imports.append(ImportStatement(
                        module=module,
                        source_file=file_path,
                        is_relative=module.startswith('.'),
                        is_local=self._is_local_module(module, project_root)
                    ))

        except Exception as e:
            logger.warning(f"Failed to parse Go imports from {file_path}: {e}")

        return imports

    def _is_local_module(self, module: str, project_root: str) -> bool:
        """Check if module is local to project."""
        # In Go, local modules typically start with the module name from go.mod
        # For now, use heuristic: internal modules don't have dots except at start
        if module.startswith('.'):
            return True

        # Check if it's a standard library or third-party
        # Standard lib doesn't have domain in path
        if '.' not in module.split('/')[0]:
            return False  # Likely standard library

        return True  # Assume local module


class ParserRegistry:
    """Registry of import parsers for different languages."""

    def __init__(self):
        self.parsers: List[ImportParser] = [
            PythonImportParser(),
            JavaScriptImportParser(),
            GoImportParser(),
        ]

    def get_parser(self, file_path: str) -> Optional[ImportParser]:
        """Get appropriate parser for file."""
        for parser in self.parsers:
            if parser.supports_file(file_path):
                return parser
        return None

    def parse_file(self, file_path: str, project_root: str) -> List[ImportStatement]:
        """Parse imports from file using appropriate parser."""
        parser = self.get_parser(file_path)
        if parser:
            return parser.parse_file(file_path, project_root)
        return []
