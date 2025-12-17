#!/usr/bin/env python3
"""
R CLI Performance Benchmarks

Run with: python benchmarks/benchmark.py
"""

import json
import statistics
import sys
import time
from pathlib import Path

# Add parent dir to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def benchmark_skill_loading():
    """Benchmark skill loading time for different modes."""
    from r_cli.core.agent import Agent
    from r_cli.core.config import Config

    results = {}

    for mode in ["lite", "standard", "blacklist"]:
        times = []
        for _ in range(3):
            config = Config.load()
            config.skills.mode = mode
            agent = Agent(config)

            start = time.perf_counter()
            agent.load_skills(verbose=False)
            elapsed = (time.perf_counter() - start) * 1000

            times.append(elapsed)

        results[mode] = {
            "skills": len(agent.skills),
            "tools": len(agent.tools),
            "avg_ms": round(statistics.mean(times), 2),
            "min_ms": round(min(times), 2),
            "max_ms": round(max(times), 2),
        }

    return results


def benchmark_tool_execution():
    """Benchmark direct tool execution time."""
    from r_cli.core.agent import Agent
    from r_cli.core.config import Config

    config = Config.load()
    config.skills.mode = "lite"
    agent = Agent(config)
    agent.load_skills(verbose=False)

    benchmarks = {
        "datetime": ("get_current_time", {}),
        "math": ("calculate", {"expression": "2+2"}),
        "crypto": ("hash_text", {"text": "hello", "algorithm": "md5"}),
        "json": ("parse_json", {"json_string": '{"a": 1}'}),
        "text": ("count_words", {"text": "hello world test"}),
    }

    results = {}

    for skill_name, (tool_name, args) in benchmarks.items():
        if skill_name not in agent.skills:
            continue

        skill = agent.skills[skill_name]
        tool = None
        for t in skill.get_tools():
            if t.name == tool_name:
                tool = t
                break

        if not tool:
            continue

        times = []
        for _ in range(10):
            start = time.perf_counter()
            try:
                tool.handler(**args)
            except Exception:
                pass
            elapsed = (time.perf_counter() - start) * 1000
            times.append(elapsed)

        results[f"{skill_name}.{tool_name}"] = {
            "avg_ms": round(statistics.mean(times), 3),
            "min_ms": round(min(times), 3),
            "max_ms": round(max(times), 3),
        }

    return results


def benchmark_token_usage():
    """Estimate token usage for different skill modes."""
    import tiktoken

    from r_cli.core.agent import Agent
    from r_cli.core.config import Config

    enc = tiktoken.get_encoding("cl100k_base")
    results = {}

    for mode in ["lite", "standard", "blacklist"]:
        config = Config.load()
        config.skills.mode = mode
        agent = Agent(config)
        agent.load_skills(verbose=False)

        # Build tool definitions as JSON (similar to what's sent to LLM)
        tools_json = []
        for tool in agent.tools:
            tools_json.append({
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters,
            })

        tools_str = json.dumps(tools_json)
        tokens = len(enc.encode(tools_str))

        results[mode] = {
            "skills": len(agent.skills),
            "tools": len(agent.tools),
            "tokens": tokens,
            "context_pct_4k": round(tokens / 4096 * 100, 1),
            "context_pct_8k": round(tokens / 8192 * 100, 1),
            "context_pct_32k": round(tokens / 32768 * 100, 1),
        }

    return results


def benchmark_smart_selection():
    """Benchmark smart tool selection."""
    from r_cli.core.agent import Agent
    from r_cli.core.config import Config

    config = Config.load()
    config.skills.mode = "blacklist"  # Load all
    agent = Agent(config)
    agent.load_skills(verbose=False)

    prompts = [
        "What time is it?",
        "Calculate 2+2",
        "Create a PDF document",
        "Search for files",
        "Hash this text with MD5",
        "Generate Python code",
        "Query the database with SQL",
        "Translate this to Spanish",
    ]

    results = {}
    for prompt in prompts:
        start = time.perf_counter()
        tools = agent.get_relevant_tools(prompt, max_tools=30)
        elapsed = (time.perf_counter() - start) * 1000

        results[prompt[:30]] = {
            "tools_selected": len(tools),
            "selection_ms": round(elapsed, 3),
            "tools": [t.name for t in tools[:5]],
        }

    return results


def main():
    print("=" * 60)
    print("R CLI Performance Benchmarks")
    print("=" * 60)

    print("\n1. Skill Loading Time")
    print("-" * 40)
    loading = benchmark_skill_loading()
    for mode, data in loading.items():
        print(f"  {mode:12} | {data['skills']:2} skills | {data['tools']:3} tools | {data['avg_ms']:.1f}ms avg")

    print("\n2. Tool Execution Time")
    print("-" * 40)
    execution = benchmark_tool_execution()
    for tool, data in execution.items():
        print(f"  {tool:25} | {data['avg_ms']:.3f}ms avg")

    print("\n3. Token Usage by Mode")
    print("-" * 40)
    tokens = benchmark_token_usage()
    for mode, data in tokens.items():
        print(f"  {mode:12} | {data['tools']:3} tools | {data['tokens']:5} tokens | {data['context_pct_8k']:.1f}% of 8k")

    print("\n4. Smart Tool Selection")
    print("-" * 40)
    selection = benchmark_smart_selection()
    for prompt, data in selection.items():
        print(f"  '{prompt}' -> {data['tools_selected']} tools in {data['selection_ms']:.2f}ms")

    print("\n" + "=" * 60)
    print("Benchmarks complete!")

    # Save results to JSON
    all_results = {
        "skill_loading": loading,
        "tool_execution": execution,
        "token_usage": tokens,
        "smart_selection": selection,
    }

    output_path = Path(__file__).parent / "results.json"
    with open(output_path, "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"Results saved to {output_path}")


if __name__ == "__main__":
    main()
