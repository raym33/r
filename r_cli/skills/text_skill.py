"""
Text Skill for R CLI.

Text utilities:
- Word/character count
- Case conversion
- Diff comparison
- Lorem ipsum generation
- Slug generation
"""

import json
import re
import unicodedata
from typing import Optional

from r_cli.core.agent import Skill
from r_cli.core.llm import Tool


class TextSkill(Skill):
    """Skill for text utilities."""

    name = "text"
    description = "Text: count, case, diff, lorem, slug, wrap"

    def get_tools(self) -> list[Tool]:
        return [
            Tool(
                name="text_count",
                description="Count words, characters, lines in text",
                parameters={
                    "type": "object",
                    "properties": {
                        "text": {
                            "type": "string",
                            "description": "Text to analyze",
                        },
                    },
                    "required": ["text"],
                },
                handler=self.text_count,
            ),
            Tool(
                name="text_case",
                description="Convert text case",
                parameters={
                    "type": "object",
                    "properties": {
                        "text": {
                            "type": "string",
                            "description": "Text to convert",
                        },
                        "case": {
                            "type": "string",
                            "description": "Case: upper, lower, title, capitalize, swap, camel, snake, kebab",
                        },
                    },
                    "required": ["text", "case"],
                },
                handler=self.text_case,
            ),
            Tool(
                name="text_diff",
                description="Compare two texts and show differences",
                parameters={
                    "type": "object",
                    "properties": {
                        "text1": {
                            "type": "string",
                            "description": "First text",
                        },
                        "text2": {
                            "type": "string",
                            "description": "Second text",
                        },
                    },
                    "required": ["text1", "text2"],
                },
                handler=self.text_diff,
            ),
            Tool(
                name="text_lorem",
                description="Generate lorem ipsum text",
                parameters={
                    "type": "object",
                    "properties": {
                        "paragraphs": {
                            "type": "integer",
                            "description": "Number of paragraphs (default: 1)",
                        },
                        "words": {
                            "type": "integer",
                            "description": "Approximate words per paragraph",
                        },
                    },
                },
                handler=self.text_lorem,
            ),
            Tool(
                name="text_slug",
                description="Generate URL-friendly slug from text",
                parameters={
                    "type": "object",
                    "properties": {
                        "text": {
                            "type": "string",
                            "description": "Text to convert to slug",
                        },
                    },
                    "required": ["text"],
                },
                handler=self.text_slug,
            ),
            Tool(
                name="text_wrap",
                description="Wrap text to specified width",
                parameters={
                    "type": "object",
                    "properties": {
                        "text": {
                            "type": "string",
                            "description": "Text to wrap",
                        },
                        "width": {
                            "type": "integer",
                            "description": "Line width (default: 80)",
                        },
                    },
                    "required": ["text"],
                },
                handler=self.text_wrap,
            ),
            Tool(
                name="text_reverse",
                description="Reverse text",
                parameters={
                    "type": "object",
                    "properties": {
                        "text": {
                            "type": "string",
                            "description": "Text to reverse",
                        },
                    },
                    "required": ["text"],
                },
                handler=self.text_reverse,
            ),
            Tool(
                name="text_truncate",
                description="Truncate text to specified length",
                parameters={
                    "type": "object",
                    "properties": {
                        "text": {
                            "type": "string",
                            "description": "Text to truncate",
                        },
                        "length": {
                            "type": "integer",
                            "description": "Max length",
                        },
                        "suffix": {
                            "type": "string",
                            "description": "Suffix to add (default: '...')",
                        },
                    },
                    "required": ["text", "length"],
                },
                handler=self.text_truncate,
            ),
            Tool(
                name="text_remove_diacritics",
                description="Remove accents and diacritics from text",
                parameters={
                    "type": "object",
                    "properties": {
                        "text": {
                            "type": "string",
                            "description": "Text to process",
                        },
                    },
                    "required": ["text"],
                },
                handler=self.text_remove_diacritics,
            ),
        ]

    def text_count(self, text: str) -> str:
        """Count text statistics."""
        lines = text.split("\n")
        words = text.split()
        chars = len(text)
        chars_no_spaces = len(text.replace(" ", "").replace("\n", ""))

        # Sentences (rough estimate)
        sentences = len(re.findall(r'[.!?]+', text))

        return json.dumps({
            "characters": chars,
            "characters_no_spaces": chars_no_spaces,
            "words": len(words),
            "lines": len(lines),
            "sentences": sentences,
            "paragraphs": len([p for p in text.split("\n\n") if p.strip()]),
        }, indent=2)

    def text_case(self, text: str, case: str) -> str:
        """Convert text case."""
        case_lower = case.lower()

        if case_lower == "upper":
            return text.upper()
        elif case_lower == "lower":
            return text.lower()
        elif case_lower == "title":
            return text.title()
        elif case_lower == "capitalize":
            return text.capitalize()
        elif case_lower == "swap":
            return text.swapcase()
        elif case_lower == "camel":
            words = re.split(r'[\s_-]+', text)
            return words[0].lower() + ''.join(w.capitalize() for w in words[1:])
        elif case_lower == "snake":
            # Convert camelCase to snake_case
            s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', text)
            s2 = re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1)
            return re.sub(r'[\s-]+', '_', s2).lower()
        elif case_lower == "kebab":
            s1 = re.sub('(.)([A-Z][a-z]+)', r'\1-\2', text)
            s2 = re.sub('([a-z0-9])([A-Z])', r'\1-\2', s1)
            return re.sub(r'[\s_]+', '-', s2).lower()
        else:
            return f"Unknown case: {case}. Available: upper, lower, title, capitalize, swap, camel, snake, kebab"

    def text_diff(self, text1: str, text2: str) -> str:
        """Compare two texts."""
        import difflib

        lines1 = text1.splitlines(keepends=True)
        lines2 = text2.splitlines(keepends=True)

        diff = difflib.unified_diff(lines1, lines2, fromfile='text1', tofile='text2')
        result = ''.join(diff)

        if not result:
            return "No differences found"

        return result

    def text_lorem(self, paragraphs: int = 1, words: int = 50) -> str:
        """Generate lorem ipsum."""
        lorem_words = [
            "lorem", "ipsum", "dolor", "sit", "amet", "consectetur", "adipiscing",
            "elit", "sed", "do", "eiusmod", "tempor", "incididunt", "ut", "labore",
            "et", "dolore", "magna", "aliqua", "enim", "ad", "minim", "veniam",
            "quis", "nostrud", "exercitation", "ullamco", "laboris", "nisi",
            "aliquip", "ex", "ea", "commodo", "consequat", "duis", "aute", "irure",
            "in", "reprehenderit", "voluptate", "velit", "esse", "cillum", "fugiat",
            "nulla", "pariatur", "excepteur", "sint", "occaecat", "cupidatat",
            "non", "proident", "sunt", "culpa", "qui", "officia", "deserunt",
            "mollit", "anim", "id", "est", "laborum"
        ]

        import random
        result = []

        for _ in range(paragraphs):
            para_words = []
            for i in range(words):
                word = random.choice(lorem_words)
                if i == 0:
                    word = word.capitalize()
                para_words.append(word)

            # Add punctuation
            text = " ".join(para_words)
            sentences = []
            current = []
            for i, word in enumerate(para_words):
                current.append(word)
                if len(current) >= random.randint(8, 15):
                    sentences.append(" ".join(current) + ".")
                    current = []
            if current:
                sentences.append(" ".join(current) + ".")

            result.append(" ".join(sentences))

        return "\n\n".join(result)

    def text_slug(self, text: str) -> str:
        """Generate URL slug."""
        # Remove diacritics
        text = unicodedata.normalize('NFKD', text)
        text = text.encode('ASCII', 'ignore').decode('ASCII')

        # Convert to lowercase and replace spaces
        text = text.lower()
        text = re.sub(r'[^\w\s-]', '', text)
        text = re.sub(r'[-\s]+', '-', text)

        return text.strip('-')

    def text_wrap(self, text: str, width: int = 80) -> str:
        """Wrap text to width."""
        import textwrap
        return textwrap.fill(text, width=width)

    def text_reverse(self, text: str) -> str:
        """Reverse text."""
        return text[::-1]

    def text_truncate(
        self,
        text: str,
        length: int,
        suffix: str = "...",
    ) -> str:
        """Truncate text."""
        if len(text) <= length:
            return text
        return text[:length - len(suffix)] + suffix

    def text_remove_diacritics(self, text: str) -> str:
        """Remove diacritics/accents."""
        normalized = unicodedata.normalize('NFKD', text)
        return ''.join(c for c in normalized if not unicodedata.combining(c))

    def execute(self, **kwargs) -> str:
        """Direct skill execution."""
        action = kwargs.get("action", "count")
        if action == "count":
            return self.text_count(kwargs.get("text", ""))
        elif action == "lorem":
            return self.text_lorem()
        return f"Unknown action: {action}"
