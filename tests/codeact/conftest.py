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
        lm = dspy.LM(model="openai/gpt-3.5-turbo", api_key=openai_key, max_tokens=4000)
        dspy.settings.configure(lm=lm)
        print("\n✓ DSPy configured with OpenAI GPT-3.5-turbo")
    elif anthropic_key:
        # Use Anthropic Claude via LiteLLM (DSPy uses dspy.LM with LiteLLM format)
        # Using Sonnet 4.5 with extended thinking for best CoT and structured output
        lm = dspy.LM(
            model="anthropic/claude-sonnet-4-5-20250929",
            api_key=anthropic_key,
            max_tokens=4000
        )
        dspy.settings.configure(lm=lm)
        print("\n✓ DSPy configured with Claude Sonnet 4.5")
    else:
        pytest.skip(
            "No API key found. Set OPENAI_API_KEY or ANTHROPIC_API_KEY to run CodeAct tests."
        )


@pytest.fixture
def sandbox():
    """Create a CodeSandbox instance for testing."""
    from coderabbit_ai.codeact.sandbox import CodeSandbox

    return CodeSandbox(timeout=30, max_memory_mb=512)
