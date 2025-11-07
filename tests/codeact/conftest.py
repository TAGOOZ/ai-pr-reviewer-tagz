"""Pytest configuration for CodeAct tests."""

import os
import pytest
import dspy
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


@pytest.fixture(scope="session", autouse=True)
def configure_dspy():
    """Configure DSPy with LLM for all CodeAct tests."""
    # Try to get API key from environment
    openai_key = os.getenv("OPENAI_API_KEY")
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")

    if openai_key:
        # Use OpenAI GPT-3.5-turbo (fast and cheap for tests)
        lm = dspy.OpenAI(model="gpt-3.5-turbo", api_key=openai_key, max_tokens=1000)
        dspy.settings.configure(lm=lm)
        print("\n✓ DSPy configured with OpenAI GPT-3.5-turbo")
    elif anthropic_key:
        # Use Claude Haiku (fast and cheap)
        lm = dspy.Claude(model="claude-3-haiku-20240307", api_key=anthropic_key)
        dspy.settings.configure(lm=lm)
        print("\n✓ DSPy configured with Claude Haiku")
    else:
        pytest.skip(
            "No API key found. Set OPENAI_API_KEY or ANTHROPIC_API_KEY to run CodeAct tests."
        )


@pytest.fixture
def sandbox():
    """Create a CodeSandbox instance for testing."""
    from coderabbit_ai.codeact.sandbox import CodeSandbox

    return CodeSandbox(timeout=30, max_memory_mb=512)
