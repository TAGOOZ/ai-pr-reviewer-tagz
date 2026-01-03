# Contributing to CodeRabbit

First off, thanks for taking the time to contribute! 🎉

The following is a set of guidelines for contributing to CodeRabbit. These are mostly guidelines, not rules. Use your best judgment, and feel free to propose changes to this document in a pull request.

## Code of Conduct

This project and everyone participating in it is governed by the [CodeRabbit Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code. Please report unacceptable behavior to abuse@coderabbit.ai.

## Development Philosophy

We follow **Ralph-Driven Development** principles:

1.  **Loops over Chat**: We prefer small, iterative loops of (Task -> Implementation -> Verification) over long, unstructured conversations.
2.  **Evidence-Based**: Decisions should be backed by code analysis (`grep`, `ls`, reading files) rather than assumptions.
3.  **Safety First**: Always verify paths, sanitize inputs, and use safe patterns (e.g., `shlex.split` for subprocess).
4.  **Documentation as Code**: Documentation (like `AGENTS.md`) is a living part of the codebase and should be updated when patterns are discovered.

## Getting Started

### Prerequisites

- **Rust**: 1.75+ (via [rustup](https://rustup.rs/))
- **Python**: 3.11+ (via [pyenv](https://github.com/pyenv/pyenv) recommended)
- **Poetry**: Python dependency manager
- **Docker**: For running services and the sandbox environment
- **pre-commit**: For git hooks

### Setting up the Environment

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/coderabbitai/ai-pr-reviewer.git
    cd ai-pr-reviewer
    ```

2.  **Install dependencies:**
    ```bash
    ./scripts/setup-dev.sh
    ```

3.  **Install pre-commit hooks:**
    ```bash
    pre-commit install
    ```

4.  **Configure environment:**
    ```bash
    cp .env.example .env
    # Edit .env with your API keys (OpenAI, GitHub, etc.)
    ```

## Development Workflow

### 1. Create a Branch

Create a new branch for your feature or bugfix:

```bash
git checkout -b feature/amazing-feature
# or
git checkout -b fix/nasty-bug
```

### 2. Make Changes

- **Rust**: Code lives in `crates/`. Use `cargo` for building and testing.
- **Python**: Code lives in `python/`. Use `poetry` for dependency management.

### 3. Verify Changes

Before committing, ensure your changes pass all checks:

**Rust:**
```bash
cargo fmt --all -- --check
cargo clippy --all-targets --all-features -- -D warnings
cargo test --workspace
```

**Python:**
```bash
poetry run black --check python/
poetry run isort --check-only python/
poetry run flake8 python/
poetry run mypy python/
poetry run pytest tests/
```

### 4. Commit Messages

We follow the [Conventional Commits](https://www.conventionalcommits.org/) specification:

- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation only changes
- `style`: Changes that do not affect the meaning of the code (white-space, formatting, etc)
- `refactor`: A code change that neither fixes a bug nor adds a feature
- `perf`: A code change that improves performance
- `test`: Adding missing tests or correcting existing tests
- `chore`: Changes to the build process or auxiliary tools and libraries

Example:
```
feat: add streaming support to OpenAI client
fix: resolve memory leak in vector store
docs: update configuration guide
```

### 5. Submit a Pull Request

Push your branch to GitHub and open a Pull Request. Ensure the PR description clearly describes the problem and solution.

## Project Structure

```
├── config/                 # Configuration files
├── crates/                 # Rust workspace (Backend services)
│   ├── api-gateway/        # HTTP API
│   ├── code-analyzer/      # Static analysis
│   ├── orchestrator/       # Task orchestration
│   ├── shared/             # Shared types
│   └── vector-engine/      # Vector DB integration
├── docs/                   # Documentation
├── python/                 # Python workspace (AI Pipeline)
│   └── coderabbit_ai/      # AI agents and logic
├── scripts/                # Utility scripts
└── tests/                  # Integration tests
```

## Testing Guidelines

- **Unit Tests**: Should cover individual functions and modules.
- **Integration Tests**: Located in `tests/`, covering interactions between components.
- **Mocking**: Use mocks for external services (GitHub API, OpenAI API) in tests.

## AGENTS.md

The `AGENTS.md` file contains "signs" and patterns that our AI agents (and human developers) should follow. If you discover a common pitfall or a better way to do something, please update this file!

## Getting Help

If you need help, please ask in our [community Slack](https://community.coderabbit.ai) or open an issue on GitHub.
