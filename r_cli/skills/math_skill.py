"""
Math Skill for R CLI.

Mathematical operations:
- Calculations and expressions
- Statistics
- Unit conversions
- Number base conversions
"""

import json
import math
from typing import Optional

from r_cli.core.agent import Skill
from r_cli.core.llm import Tool


class MathSkill(Skill):
    """Skill for mathematical operations."""

    name = "math"
    description = "Math: calculate, statistics, conversions"

    def get_tools(self) -> list[Tool]:
        return [
            Tool(
                name="calculate",
                description="Evaluate a mathematical expression",
                parameters={
                    "type": "object",
                    "properties": {
                        "expression": {
                            "type": "string",
                            "description": "Math expression (e.g., '2 + 2', 'sqrt(16)', 'sin(pi/2)')",
                        },
                    },
                    "required": ["expression"],
                },
                handler=self.calculate,
            ),
            Tool(
                name="statistics",
                description="Calculate statistics for a list of numbers",
                parameters={
                    "type": "object",
                    "properties": {
                        "numbers": {
                            "type": "string",
                            "description": "Comma-separated list of numbers",
                        },
                    },
                    "required": ["numbers"],
                },
                handler=self.statistics,
            ),
            Tool(
                name="convert_unit",
                description="Convert between units",
                parameters={
                    "type": "object",
                    "properties": {
                        "value": {
                            "type": "number",
                            "description": "Value to convert",
                        },
                        "from_unit": {
                            "type": "string",
                            "description": "Source unit",
                        },
                        "to_unit": {
                            "type": "string",
                            "description": "Target unit",
                        },
                    },
                    "required": ["value", "from_unit", "to_unit"],
                },
                handler=self.convert_unit,
            ),
            Tool(
                name="convert_base",
                description="Convert number between bases (binary, octal, decimal, hex)",
                parameters={
                    "type": "object",
                    "properties": {
                        "number": {
                            "type": "string",
                            "description": "Number to convert",
                        },
                        "from_base": {
                            "type": "integer",
                            "description": "Source base (2, 8, 10, 16)",
                        },
                        "to_base": {
                            "type": "integer",
                            "description": "Target base",
                        },
                    },
                    "required": ["number", "from_base", "to_base"],
                },
                handler=self.convert_base,
            ),
            Tool(
                name="percentage",
                description="Calculate percentages",
                parameters={
                    "type": "object",
                    "properties": {
                        "operation": {
                            "type": "string",
                            "description": "Operation: 'of' (X% of Y), 'change' (% change from X to Y), 'is' (X is what % of Y)",
                        },
                        "x": {
                            "type": "number",
                            "description": "First value",
                        },
                        "y": {
                            "type": "number",
                            "description": "Second value",
                        },
                    },
                    "required": ["operation", "x", "y"],
                },
                handler=self.percentage,
            ),
            Tool(
                name="factorial",
                description="Calculate factorial",
                parameters={
                    "type": "object",
                    "properties": {
                        "n": {
                            "type": "integer",
                            "description": "Number to calculate factorial of",
                        },
                    },
                    "required": ["n"],
                },
                handler=self.factorial,
            ),
            Tool(
                name="prime_check",
                description="Check if a number is prime",
                parameters={
                    "type": "object",
                    "properties": {
                        "n": {
                            "type": "integer",
                            "description": "Number to check",
                        },
                    },
                    "required": ["n"],
                },
                handler=self.prime_check,
            ),
            Tool(
                name="gcd_lcm",
                description="Calculate GCD and LCM of two numbers",
                parameters={
                    "type": "object",
                    "properties": {
                        "a": {
                            "type": "integer",
                            "description": "First number",
                        },
                        "b": {
                            "type": "integer",
                            "description": "Second number",
                        },
                    },
                    "required": ["a", "b"],
                },
                handler=self.gcd_lcm,
            ),
        ]

    def calculate(self, expression: str) -> str:
        """Evaluate math expression safely."""
        try:
            # Safe math functions
            safe_dict = {
                "abs": abs,
                "round": round,
                "min": min,
                "max": max,
                "sum": sum,
                "pow": pow,
                "sqrt": math.sqrt,
                "sin": math.sin,
                "cos": math.cos,
                "tan": math.tan,
                "asin": math.asin,
                "acos": math.acos,
                "atan": math.atan,
                "log": math.log,
                "log10": math.log10,
                "log2": math.log2,
                "exp": math.exp,
                "floor": math.floor,
                "ceil": math.ceil,
                "pi": math.pi,
                "e": math.e,
                "inf": math.inf,
            }

            result = eval(expression, {"__builtins__": {}}, safe_dict)
            return str(result)

        except Exception as e:
            return f"Error: {e}"

    def statistics(self, numbers: str) -> str:
        """Calculate statistics."""
        try:
            nums = [float(n.strip()) for n in numbers.split(",")]

            if not nums:
                return "No numbers provided"

            n = len(nums)
            mean = sum(nums) / n
            sorted_nums = sorted(nums)

            # Median
            if n % 2 == 0:
                median = (sorted_nums[n // 2 - 1] + sorted_nums[n // 2]) / 2
            else:
                median = sorted_nums[n // 2]

            # Variance and std dev
            variance = sum((x - mean) ** 2 for x in nums) / n
            std_dev = math.sqrt(variance)

            stats = {
                "count": n,
                "sum": sum(nums),
                "mean": round(mean, 4),
                "median": median,
                "min": min(nums),
                "max": max(nums),
                "range": max(nums) - min(nums),
                "variance": round(variance, 4),
                "std_dev": round(std_dev, 4),
            }

            return json.dumps(stats, indent=2)

        except Exception as e:
            return f"Error: {e}"

    def convert_unit(self, value: float, from_unit: str, to_unit: str) -> str:
        """Convert between units."""
        # Conversion factors to base units
        conversions = {
            # Length (base: meters)
            "m": 1, "km": 1000, "cm": 0.01, "mm": 0.001,
            "mi": 1609.344, "ft": 0.3048, "in": 0.0254, "yd": 0.9144,
            # Weight (base: grams)
            "g": 1, "kg": 1000, "mg": 0.001, "lb": 453.592, "oz": 28.3495,
            # Temperature handled separately
            # Time (base: seconds)
            "s": 1, "ms": 0.001, "min": 60, "h": 3600, "d": 86400,
            # Data (base: bytes)
            "b": 1, "kb": 1024, "mb": 1024**2, "gb": 1024**3, "tb": 1024**4,
        }

        from_u = from_unit.lower()
        to_u = to_unit.lower()

        # Temperature special case
        if from_u in ("c", "f", "k") or to_u in ("c", "f", "k"):
            return self._convert_temperature(value, from_u, to_u)

        if from_u not in conversions:
            return f"Unknown unit: {from_unit}"
        if to_u not in conversions:
            return f"Unknown unit: {to_unit}"

        # Convert to base, then to target
        base_value = value * conversions[from_u]
        result = base_value / conversions[to_u]

        return f"{value} {from_unit} = {result:.6g} {to_unit}"

    def _convert_temperature(self, value: float, from_u: str, to_u: str) -> str:
        """Convert temperature."""
        # Convert to Celsius first
        if from_u == "f":
            celsius = (value - 32) * 5 / 9
        elif from_u == "k":
            celsius = value - 273.15
        else:
            celsius = value

        # Convert from Celsius to target
        if to_u == "f":
            result = celsius * 9 / 5 + 32
        elif to_u == "k":
            result = celsius + 273.15
        else:
            result = celsius

        return f"{value}°{from_u.upper()} = {result:.2f}°{to_u.upper()}"

    def convert_base(self, number: str, from_base: int, to_base: int) -> str:
        """Convert number between bases."""
        try:
            # Parse from source base
            decimal = int(number, from_base)

            # Convert to target base
            if to_base == 2:
                result = bin(decimal)[2:]
            elif to_base == 8:
                result = oct(decimal)[2:]
            elif to_base == 10:
                result = str(decimal)
            elif to_base == 16:
                result = hex(decimal)[2:].upper()
            else:
                return f"Unsupported base: {to_base}"

            return f"{number} (base {from_base}) = {result} (base {to_base})"

        except ValueError as e:
            return f"Error: {e}"

    def percentage(self, operation: str, x: float, y: float) -> str:
        """Calculate percentages."""
        try:
            if operation == "of":
                # X% of Y
                result = (x / 100) * y
                return f"{x}% of {y} = {result}"
            elif operation == "change":
                # % change from X to Y
                if x == 0:
                    return "Cannot calculate change from 0"
                change = ((y - x) / abs(x)) * 100
                return f"Change from {x} to {y} = {change:.2f}%"
            elif operation == "is":
                # X is what % of Y
                if y == 0:
                    return "Cannot divide by 0"
                pct = (x / y) * 100
                return f"{x} is {pct:.2f}% of {y}"
            else:
                return f"Unknown operation: {operation}"
        except Exception as e:
            return f"Error: {e}"

    def factorial(self, n: int) -> str:
        """Calculate factorial."""
        if n < 0:
            return "Factorial not defined for negative numbers"
        if n > 170:
            return "Number too large (max 170)"
        return f"{n}! = {math.factorial(n)}"

    def prime_check(self, n: int) -> str:
        """Check if number is prime."""
        if n < 2:
            return f"{n} is not prime"
        if n == 2:
            return f"{n} is prime"
        if n % 2 == 0:
            return f"{n} is not prime (divisible by 2)"

        for i in range(3, int(math.sqrt(n)) + 1, 2):
            if n % i == 0:
                return f"{n} is not prime (divisible by {i})"

        return f"{n} is prime"

    def gcd_lcm(self, a: int, b: int) -> str:
        """Calculate GCD and LCM."""
        gcd = math.gcd(a, b)
        lcm = abs(a * b) // gcd

        return json.dumps({
            "gcd": gcd,
            "lcm": lcm,
        }, indent=2)

    def execute(self, **kwargs) -> str:
        """Direct skill execution."""
        return self.calculate(kwargs.get("expression", "0"))
