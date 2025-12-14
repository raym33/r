#!/usr/bin/env python3
"""
R CLI - Basic Usage Examples

This file demonstrates how to use R CLI programmatically.
"""

from r_cli.core.config import Config
from r_cli.core.agent import Agent


def example_basic_chat():
    """Basic chat example."""
    # Create agent with default config
    agent = Agent()
    agent.load_skills()

    # Send a message (requires LLM server running)
    response = agent.run("Explain what machine learning is in one sentence")
    print(f"Response: {response}")


def example_direct_skill():
    """Execute a skill directly without LLM."""
    agent = Agent()
    agent.load_skills()

    # Generate a PDF directly
    result = agent.run_skill_directly(
        "pdf",
        content="# My Document\n\nThis is a test document.",
        title="Test PDF",
        template="minimal",
    )
    print(f"PDF Result: {result}")


def example_sql_query():
    """Execute SQL on a CSV file."""
    agent = Agent()
    agent.load_skills()

    # Query a CSV file
    result = agent.run_skill_directly(
        "sql",
        query="SELECT * FROM data LIMIT 5",
        csv="./my_data.csv",  # Replace with your CSV path
    )
    print(f"SQL Result: {result}")


def example_code_generation():
    """Generate and run Python code."""
    agent = Agent()
    agent.load_skills()

    # Generate code
    result = agent.run_skill_directly(
        "code",
        code="def fibonacci(n):\n    if n <= 1:\n        return n\n    return fibonacci(n-1) + fibonacci(n-2)\n\nprint([fibonacci(i) for i in range(10)])",
        filename="fibonacci.py",
        action="run",
    )
    print(f"Code Result: {result}")


def example_custom_config():
    """Use custom configuration."""
    # Create custom config
    config = Config()
    config.llm.provider = "ollama"
    config.llm.base_url = "http://localhost:11434/v1"
    config.llm.model = "qwen2.5:32b"
    config.ui.theme = "matrix"

    # Create agent with custom config
    agent = Agent(config)
    agent.load_skills()

    # Check connection
    if agent.check_connection():
        print("Connected to Ollama!")
    else:
        print("Ollama not running")


if __name__ == "__main__":
    print("R CLI Examples")
    print("=" * 40)

    print("\n1. Direct skill example (PDF generation):")
    example_direct_skill()

    print("\n2. Custom config example:")
    example_custom_config()
