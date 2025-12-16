"""
Benchmark Skill for R CLI.

Performance profiling and benchmarking:
- Profile Python scripts with cProfile
- Benchmark commands (time, memory)
- Compare performance between runs
- Identify bottlenecks
"""

import cProfile
import io
import os
import pstats
import resource
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Optional

from r_cli.core.agent import Skill
from r_cli.core.llm import Tool


class BenchmarkSkill(Skill):
    """Skill for performance profiling and benchmarking."""

    name = "benchmark"
    description = "Performance profiling: benchmark commands, profile Python, compare runs"

    TIMEOUT = 300  # 5 minutes max for benchmarks

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._benchmark_history: list[dict] = []

    def get_tools(self) -> list[Tool]:
        return [
            Tool(
                name="profile_python",
                description="Profile a Python script with cProfile to find bottlenecks",
                parameters={
                    "type": "object",
                    "properties": {
                        "script_path": {
                            "type": "string",
                            "description": "Path to Python script to profile",
                        },
                        "args": {
                            "type": "string",
                            "description": "Arguments to pass to the script",
                        },
                        "sort_by": {
                            "type": "string",
                            "enum": ["cumtime", "tottime", "calls", "ncalls"],
                            "description": "Sort results by (default: cumtime)",
                        },
                        "top_n": {
                            "type": "integer",
                            "description": "Number of top functions to show (default: 20)",
                        },
                    },
                    "required": ["script_path"],
                },
                handler=self.profile_python,
            ),
            Tool(
                name="benchmark_command",
                description="Benchmark a shell command, measuring time and resource usage",
                parameters={
                    "type": "object",
                    "properties": {
                        "command": {
                            "type": "string",
                            "description": "Shell command to benchmark",
                        },
                        "runs": {
                            "type": "integer",
                            "description": "Number of runs for averaging (default: 3)",
                        },
                        "warmup": {
                            "type": "integer",
                            "description": "Warmup runs before measuring (default: 1)",
                        },
                        "name": {
                            "type": "string",
                            "description": "Name for this benchmark (for comparison)",
                        },
                    },
                    "required": ["command"],
                },
                handler=self.benchmark_command,
            ),
            Tool(
                name="benchmark_python",
                description="Benchmark Python code snippet with timeit",
                parameters={
                    "type": "object",
                    "properties": {
                        "code": {
                            "type": "string",
                            "description": "Python code to benchmark",
                        },
                        "setup": {
                            "type": "string",
                            "description": "Setup code (imports, etc.)",
                        },
                        "iterations": {
                            "type": "integer",
                            "description": "Number of iterations (default: auto)",
                        },
                        "name": {
                            "type": "string",
                            "description": "Name for this benchmark",
                        },
                    },
                    "required": ["code"],
                },
                handler=self.benchmark_python,
            ),
            Tool(
                name="compare_benchmarks",
                description="Compare benchmark results from the current session",
                parameters={
                    "type": "object",
                    "properties": {
                        "benchmark1": {
                            "type": "string",
                            "description": "Name of first benchmark",
                        },
                        "benchmark2": {
                            "type": "string",
                            "description": "Name of second benchmark",
                        },
                    },
                },
                handler=self.compare_benchmarks,
            ),
            Tool(
                name="memory_profile",
                description="Profile memory usage of a Python script",
                parameters={
                    "type": "object",
                    "properties": {
                        "script_path": {
                            "type": "string",
                            "description": "Path to Python script",
                        },
                        "args": {
                            "type": "string",
                            "description": "Arguments to pass to the script",
                        },
                    },
                    "required": ["script_path"],
                },
                handler=self.memory_profile,
            ),
            Tool(
                name="list_benchmarks",
                description="List all benchmarks from the current session",
                parameters={
                    "type": "object",
                    "properties": {},
                },
                handler=self.list_benchmarks,
            ),
        ]

    def profile_python(
        self,
        script_path: str,
        args: str = "",
        sort_by: str = "cumtime",
        top_n: int = 20,
    ) -> str:
        """Profile a Python script with cProfile."""
        path = Path(script_path).expanduser()
        if not path.exists():
            return f"Error: Script not found: {script_path}"

        if path.suffix != ".py":
            return "Error: Only Python scripts (.py) are supported"

        result = ["=== Python Profile Results ===\n"]
        result.append(f"Script: {script_path}")
        if args:
            result.append(f"Arguments: {args}")
        result.append("")

        try:
            # Run with cProfile
            cmd = ["python", "-m", "cProfile", "-o", "/tmp/r_profile.prof", str(path)]
            if args:
                cmd.extend(args.split())

            start_time = time.time()
            proc = subprocess.run(
                cmd,
                check=False,
                capture_output=True,
                text=True,
                timeout=self.TIMEOUT,
            )
            elapsed = time.time() - start_time

            result.append(f"Total execution time: {elapsed:.3f}s")

            if proc.returncode != 0:
                result.append(f"\nScript stderr:\n{proc.stderr[:500]}")

            # Parse profile stats
            if os.path.exists("/tmp/r_profile.prof"):
                stats = pstats.Stats("/tmp/r_profile.prof")

                # Get sorted stats
                stream = io.StringIO()
                stats_obj = pstats.Stats("/tmp/r_profile.prof", stream=stream)
                stats_obj.sort_stats(sort_by)
                stats_obj.print_stats(top_n)

                result.append(f"\n## Top {top_n} Functions (sorted by {sort_by})")
                result.append(stream.getvalue())

                # Get callers for top time consumers
                stream2 = io.StringIO()
                stats_obj2 = pstats.Stats("/tmp/r_profile.prof", stream=stream2)
                stats_obj2.sort_stats("cumtime")
                stats_obj2.print_callers(5)

                result.append("\n## Top Callers")
                result.append(stream2.getvalue()[:2000])

                os.remove("/tmp/r_profile.prof")

        except subprocess.TimeoutExpired:
            return f"Error: Script exceeded timeout ({self.TIMEOUT}s)"
        except Exception as e:
            return f"Error profiling script: {e}"

        return "\n".join(result)

    def benchmark_command(
        self,
        command: str,
        runs: int = 3,
        warmup: int = 1,
        name: Optional[str] = None,
    ) -> str:
        """Benchmark a shell command."""
        result = ["=== Command Benchmark ===\n"]
        result.append(f"Command: {command}")
        result.append(f"Runs: {runs} (warmup: {warmup})")
        result.append("")

        times = []
        max_rss = []
        outputs = []

        try:
            # Warmup runs
            for i in range(warmup):
                subprocess.run(
                    command,
                    check=False,
                    shell=True,
                    capture_output=True,
                    timeout=self.TIMEOUT,
                )

            # Measured runs
            for i in range(runs):
                start = time.perf_counter()

                proc = subprocess.run(
                    command,
                    check=False,
                    shell=True,
                    capture_output=True,
                    timeout=self.TIMEOUT,
                )

                elapsed = time.perf_counter() - start
                times.append(elapsed)

                # Try to get memory info (Unix only)
                try:
                    usage = resource.getrusage(resource.RUSAGE_CHILDREN)
                    max_rss.append(usage.ru_maxrss)
                except Exception:
                    pass

                if i == 0:
                    outputs.append(proc.stdout.decode()[:200] if proc.stdout else "")

        except subprocess.TimeoutExpired:
            return f"Error: Command exceeded timeout ({self.TIMEOUT}s)"
        except Exception as e:
            return f"Error running command: {e}"

        # Calculate statistics
        avg_time = sum(times) / len(times)
        min_time = min(times)
        max_time = max(times)
        std_dev = (sum((t - avg_time) ** 2 for t in times) / len(times)) ** 0.5

        result.append("## Timing Results")
        result.append(f"  Average: {avg_time:.4f}s")
        result.append(f"  Min:     {min_time:.4f}s")
        result.append(f"  Max:     {max_time:.4f}s")
        result.append(f"  Std Dev: {std_dev:.4f}s")

        if max_rss:
            avg_mem = sum(max_rss) / len(max_rss)
            # Convert to MB (macOS returns bytes, Linux returns KB)
            import platform

            if platform.system() == "Darwin":
                avg_mem_mb = avg_mem / (1024 * 1024)
            else:
                avg_mem_mb = avg_mem / 1024
            result.append("\n## Memory Usage")
            result.append(f"  Max RSS: {avg_mem_mb:.2f} MB")

        # Store in history
        benchmark_name = name or f"cmd_{len(self._benchmark_history)}"
        self._benchmark_history.append(
            {
                "name": benchmark_name,
                "type": "command",
                "command": command,
                "avg_time": avg_time,
                "min_time": min_time,
                "max_time": max_time,
                "std_dev": std_dev,
                "runs": runs,
                "timestamp": time.time(),
            }
        )

        result.append(f"\nBenchmark saved as: {benchmark_name}")

        return "\n".join(result)

    def benchmark_python(
        self,
        code: str,
        setup: str = "",
        iterations: Optional[int] = None,
        name: Optional[str] = None,
    ) -> str:
        """Benchmark Python code with timeit."""
        import timeit

        result = ["=== Python Benchmark ===\n"]
        result.append(f"Code: {code[:100]}...")
        if setup:
            result.append(f"Setup: {setup[:50]}...")
        result.append("")

        try:
            # Auto-determine iterations if not specified
            if iterations is None:
                # Quick test to estimate
                timer = timeit.Timer(code, setup)
                iterations, _ = timer.autorange()

            result.append(f"Iterations: {iterations}")

            # Run benchmark
            timer = timeit.Timer(code, setup)
            times = timer.repeat(repeat=5, number=iterations)

            # Calculate per-iteration time
            per_iter = [t / iterations for t in times]
            avg = sum(per_iter) / len(per_iter)
            best = min(per_iter)
            worst = max(per_iter)

            result.append("\n## Results")

            # Format time appropriately
            def format_time(t):
                if t < 1e-6:
                    return f"{t * 1e9:.2f} ns"
                elif t < 1e-3:
                    return f"{t * 1e6:.2f} µs"
                elif t < 1:
                    return f"{t * 1e3:.2f} ms"
                else:
                    return f"{t:.3f} s"

            result.append(f"  Average: {format_time(avg)}/iteration")
            result.append(f"  Best:    {format_time(best)}/iteration")
            result.append(f"  Worst:   {format_time(worst)}/iteration")
            result.append(f"  Total:   {format_time(sum(times))} ({iterations * 5} iterations)")

            # Store in history
            benchmark_name = name or f"python_{len(self._benchmark_history)}"
            self._benchmark_history.append(
                {
                    "name": benchmark_name,
                    "type": "python",
                    "code": code[:100],
                    "avg_time": avg,
                    "min_time": best,
                    "max_time": worst,
                    "iterations": iterations,
                    "timestamp": time.time(),
                }
            )

            result.append(f"\nBenchmark saved as: {benchmark_name}")

        except Exception as e:
            return f"Error running benchmark: {e}"

        return "\n".join(result)

    def compare_benchmarks(
        self,
        benchmark1: Optional[str] = None,
        benchmark2: Optional[str] = None,
    ) -> str:
        """Compare benchmark results."""
        if not self._benchmark_history:
            return "No benchmarks recorded yet. Run some benchmarks first."

        result = ["=== Benchmark Comparison ===\n"]

        if benchmark1 and benchmark2:
            # Compare two specific benchmarks
            b1 = next((b for b in self._benchmark_history if b["name"] == benchmark1), None)
            b2 = next((b for b in self._benchmark_history if b["name"] == benchmark2), None)

            if not b1:
                return f"Benchmark not found: {benchmark1}"
            if not b2:
                return f"Benchmark not found: {benchmark2}"

            result.append(f"## {b1['name']} vs {b2['name']}\n")

            # Time comparison
            diff = b2["avg_time"] - b1["avg_time"]
            pct = (diff / b1["avg_time"]) * 100 if b1["avg_time"] > 0 else 0

            result.append(f"  {b1['name']}: {b1['avg_time']:.6f}s")
            result.append(f"  {b2['name']}: {b2['avg_time']:.6f}s")
            result.append("")

            if diff > 0:
                result.append(f"  {b2['name']} is {abs(pct):.1f}% SLOWER")
            elif diff < 0:
                result.append(f"  {b2['name']} is {abs(pct):.1f}% FASTER")
            else:
                result.append("  No significant difference")

            speedup = b1["avg_time"] / b2["avg_time"] if b2["avg_time"] > 0 else 0
            result.append(f"  Speedup factor: {speedup:.2f}x")

        else:
            # Show all benchmarks
            result.append("## All Benchmarks\n")
            result.append(f"{'Name':<20} {'Type':<10} {'Avg Time':<15} {'Min Time':<15}")
            result.append("-" * 60)

            for b in self._benchmark_history:
                avg = f"{b['avg_time']:.6f}s"
                min_t = f"{b['min_time']:.6f}s"
                result.append(f"{b['name']:<20} {b['type']:<10} {avg:<15} {min_t:<15}")

        return "\n".join(result)

    def memory_profile(
        self,
        script_path: str,
        args: str = "",
    ) -> str:
        """Profile memory usage of a Python script."""
        path = Path(script_path).expanduser()
        if not path.exists():
            return f"Error: Script not found: {script_path}"

        result = ["=== Memory Profile ===\n"]
        result.append(f"Script: {script_path}")
        result.append("")

        # Try to use memory_profiler if available
        try:
            # First try with tracemalloc (built-in)
            profile_code = f"""
import tracemalloc
import sys
sys.argv = ["{path}"] + {args.split() if args else []}

tracemalloc.start()

# Run the script
with open("{path}") as f:
    code = compile(f.read(), "{path}", "exec")
    exec(code, {{"__name__": "__main__", "__file__": "{path}"}})

current, peak = tracemalloc.get_traced_memory()
tracemalloc.stop()

print(f"MEMORY_CURRENT: {{current / 1024 / 1024:.2f}}")
print(f"MEMORY_PEAK: {{peak / 1024 / 1024:.2f}}")

# Get top allocations
tracemalloc.start()
exec(code, {{"__name__": "__main__", "__file__": "{path}"}})
snapshot = tracemalloc.take_snapshot()
top_stats = snapshot.statistics("lineno")[:10]
print("TOP_ALLOCATIONS:")
for stat in top_stats:
    print(f"  {{stat}}")
"""

            with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
                f.write(profile_code)
                temp_path = f.name

            try:
                proc = subprocess.run(
                    ["python", temp_path],
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=self.TIMEOUT,
                )

                output = proc.stdout + proc.stderr

                # Parse results
                for line in output.split("\n"):
                    if line.startswith("MEMORY_CURRENT:"):
                        mb = float(line.split(":")[1].strip())
                        result.append(f"Current memory: {mb:.2f} MB")
                    elif line.startswith("MEMORY_PEAK:"):
                        mb = float(line.split(":")[1].strip())
                        result.append(f"Peak memory: {mb:.2f} MB")
                    elif line.startswith("TOP_ALLOCATIONS:"):
                        result.append("\n## Top Memory Allocations")
                    elif line.strip().startswith("/") or line.strip().startswith("<"):
                        result.append(f"  {line.strip()}")

            finally:
                os.unlink(temp_path)

        except subprocess.TimeoutExpired:
            return f"Error: Script exceeded timeout ({self.TIMEOUT}s)"
        except Exception as e:
            result.append(f"Error profiling memory: {e}")

            # Fallback: just run with resource tracking
            try:
                cmd = ["python", str(path)] + (args.split() if args else [])
                proc = subprocess.run(cmd, check=False, capture_output=True, timeout=self.TIMEOUT)

                usage = resource.getrusage(resource.RUSAGE_CHILDREN)
                import platform

                if platform.system() == "Darwin":
                    max_rss_mb = usage.ru_maxrss / (1024 * 1024)
                else:
                    max_rss_mb = usage.ru_maxrss / 1024

                result.append(f"\nMax RSS (child process): {max_rss_mb:.2f} MB")
            except Exception as e2:
                result.append(f"Fallback also failed: {e2}")

        return "\n".join(result)

    def list_benchmarks(self) -> str:
        """List all benchmarks from the current session."""
        if not self._benchmark_history:
            return "No benchmarks recorded yet."

        result = ["=== Benchmark History ===\n"]

        for i, b in enumerate(self._benchmark_history, 1):
            result.append(f"{i}. {b['name']} ({b['type']})")
            result.append(f"   Avg: {b['avg_time']:.6f}s")
            if b["type"] == "command":
                result.append(f"   Command: {b.get('command', 'N/A')[:50]}")
            elif b["type"] == "python":
                result.append(f"   Code: {b.get('code', 'N/A')[:50]}")
            result.append("")

        return "\n".join(result)

    def get_prompt(self) -> str:
        return """You are a performance analysis expert. Help users:
- Profile Python scripts to find bottlenecks
- Benchmark commands and code snippets
- Compare performance between different implementations
- Identify memory issues

Use profile_python to analyze script performance with cProfile.
Use benchmark_command to measure command execution time.
Use benchmark_python to benchmark Python code snippets.
Use compare_benchmarks to compare different runs.
Use memory_profile to analyze memory usage.
"""
