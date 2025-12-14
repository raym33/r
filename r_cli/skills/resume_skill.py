"""
Document Summarization Skill for R CLI.

Features:
- Summarize long documents (PDFs, text)
- Iterative/hierarchical summarization for very long docs
- Key points extraction
- Study flashcards generation
"""

from pathlib import Path

from r_cli.core.agent import Skill
from r_cli.core.llm import Tool


class ResumeSkill(Skill):
    """Skill for summarizing long documents."""

    name = "resume"
    description = "Summarize long documents, extract key points, generate flashcards"

    # Chunking configuration
    CHUNK_SIZE = 3000  # characters per chunk
    CHUNK_OVERLAP = 200

    def get_tools(self) -> list[Tool]:
        return [
            Tool(
                name="summarize_text",
                description="Summarize a long text",
                parameters={
                    "type": "object",
                    "properties": {
                        "text": {
                            "type": "string",
                            "description": "Text to summarize",
                        },
                        "style": {
                            "type": "string",
                            "enum": ["concise", "detailed", "bullets", "academic"],
                            "description": "Summary style",
                        },
                        "max_length": {
                            "type": "integer",
                            "description": "Maximum summary length in words",
                        },
                    },
                    "required": ["text"],
                },
                handler=self.summarize_text,
            ),
            Tool(
                name="summarize_file",
                description="Summarize a text file or PDF",
                parameters={
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "Path to the file to summarize",
                        },
                        "style": {
                            "type": "string",
                            "enum": ["concise", "detailed", "bullets", "academic"],
                            "description": "Summary style",
                        },
                    },
                    "required": ["file_path"],
                },
                handler=self.summarize_file,
            ),
            Tool(
                name="extract_key_points",
                description="Extract key points from a text",
                parameters={
                    "type": "object",
                    "properties": {
                        "text": {
                            "type": "string",
                            "description": "Text from which to extract key points",
                        },
                        "num_points": {
                            "type": "integer",
                            "description": "Number of points to extract (default: 10)",
                        },
                    },
                    "required": ["text"],
                },
                handler=self.extract_key_points,
            ),
            Tool(
                name="generate_flashcards",
                description="Generate study flashcards from a text",
                parameters={
                    "type": "object",
                    "properties": {
                        "text": {
                            "type": "string",
                            "description": "Text from which to generate flashcards",
                        },
                        "num_cards": {
                            "type": "integer",
                            "description": "Number of flashcards (default: 20)",
                        },
                        "format": {
                            "type": "string",
                            "enum": ["text", "anki", "csv"],
                            "description": "Output format",
                        },
                    },
                    "required": ["text"],
                },
                handler=self.generate_flashcards,
            ),
            Tool(
                name="compare_texts",
                description="Compare two texts and show differences/similarities",
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
                handler=self.compare_texts,
            ),
        ]

    def summarize_text(
        self,
        text: str,
        style: str = "concise",
        max_length: int = 500,
    ) -> str:
        """
        Summarize a text.

        For very long texts, uses iterative summarization:
        1. Split into chunks
        2. Summarize each chunk
        3. Summarize the summaries
        """
        try:
            # If text is short, direct summarization
            if len(text) < self.CHUNK_SIZE * 2:
                return self._generate_summary(text, style, max_length)

            # Iterative summarization for long texts
            chunks = self._split_into_chunks(text)

            # First pass: summarize each chunk
            chunk_summaries = []
            for i, chunk in enumerate(chunks):
                summary = self._generate_summary(chunk, "concise", max_length // len(chunks))
                chunk_summaries.append(f"[Section {i + 1}] {summary}")

            # Second pass: summarize the summaries
            combined = "\n\n".join(chunk_summaries)

            if len(combined) > self.CHUNK_SIZE * 2:
                # Needs another pass
                return self._generate_summary(combined, style, max_length)
            else:
                final_summary = self._generate_summary(combined, style, max_length)
                return f"Summary ({len(chunks)} sections processed):\n\n{final_summary}"

        except Exception as e:
            return f"Error summarizing text: {e}"

    def _split_into_chunks(self, text: str) -> list[str]:
        """Split text into chunks with overlap."""
        chunks = []
        start = 0

        while start < len(text):
            end = start + self.CHUNK_SIZE

            # Try to cut at a period or paragraph
            if end < len(text):
                # Find end of paragraph
                paragraph_end = text.rfind("\n\n", start, end)
                if paragraph_end > start + self.CHUNK_SIZE // 2:
                    end = paragraph_end + 2
                else:
                    # Find end of sentence
                    sentence_end = text.rfind(". ", start, end)
                    if sentence_end > start + self.CHUNK_SIZE // 2:
                        end = sentence_end + 2

            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)

            start = end - self.CHUNK_OVERLAP

        return chunks

    def _generate_summary(self, text: str, style: str, max_length: int) -> str:
        """
        Generate summary using the LLM.

        Note: In a real implementation, this would call the LLM.
        For now returns a basic summary for demonstration.
        """
        # Placeholder: In the full version, this calls the LLM
        # For now, we do a simple extractive summary

        sentences = text.replace("\n", " ").split(". ")
        sentences = [s.strip() for s in sentences if len(s.strip()) > 20]

        if style == "bullets":
            # Top sentences as bullets
            top_n = min(10, len(sentences))
            bullets = ["• " + s for s in sentences[:top_n]]
            return "\n".join(bullets)

        elif style == "concise":
            # First and last sentences
            if len(sentences) <= 5:
                return ". ".join(sentences) + "."
            else:
                summary = sentences[:3] + ["..."] + sentences[-2:]
                return ". ".join(summary)

        elif style == "detailed":
            # More sentences
            top_n = min(15, len(sentences))
            return ". ".join(sentences[:top_n]) + "."

        else:  # academic
            # Structure: intro, main points, conclusion
            if len(sentences) < 6:
                return ". ".join(sentences) + "."

            intro = sentences[0]
            main_points = sentences[1:-1][:5]
            conclusion = sentences[-1]

            return (
                f"{intro}.\n\nMain points:\n"
                + "\n".join([f"• {p}" for p in main_points])
                + f"\n\nConclusion: {conclusion}."
            )

    def summarize_file(self, file_path: str, style: str = "concise") -> str:
        """Summarize a file."""
        try:
            path = Path(file_path)

            if not path.exists():
                return f"Error: File not found: {file_path}"

            # Read content based on type
            if path.suffix.lower() == ".pdf":
                text = self._extract_pdf_text(path)
            elif path.suffix.lower() in [".txt", ".md", ".rst"]:
                with open(path, encoding="utf-8", errors="replace") as f:
                    text = f.read()
            else:
                # Try to read as text
                try:
                    with open(path, encoding="utf-8", errors="replace") as f:
                        text = f.read()
                except Exception:
                    return f"Error: Cannot read file: {file_path}"

            if not text.strip():
                return "Error: File is empty or text could not be extracted."

            # Add file info
            result = [
                f"Summary of: {path.name}",
                f"   Size: {len(text):,} characters",
                f"   Words: ~{len(text.split()):,}",
                "",
            ]

            summary = self.summarize_text(text, style)
            result.append(summary)

            return "\n".join(result)

        except Exception as e:
            return f"Error summarizing file: {e}"

    def _extract_pdf_text(self, pdf_path: Path) -> str:
        """Extract text from a PDF."""
        try:
            from pypdf import PdfReader

            reader = PdfReader(str(pdf_path))
            text_parts = []

            for page in reader.pages:
                text = page.extract_text()
                if text:
                    text_parts.append(text)

            return "\n\n".join(text_parts)

        except ImportError:
            return "Error: pypdf not installed. Run: pip install pypdf"
        except Exception as e:
            return f"Error extracting PDF: {e}"

    def extract_key_points(self, text: str, num_points: int = 10) -> str:
        """Extract key points from text."""
        try:
            # Split into sentences
            sentences = text.replace("\n", " ").split(". ")
            sentences = [s.strip() + "." for s in sentences if len(s.strip()) > 30]

            if len(sentences) == 0:
                return "No key points found."

            # Select the most "important" sentences
            # (simplification: the longest and most diverse)
            scored = []
            for s in sentences:
                # Score based on length and presence of keywords
                score = len(s.split())
                if any(kw in s.lower() for kw in ["important", "key", "main", "must", "necessary"]):
                    score *= 1.5
                if any(kw in s.lower() for kw in ["first", "second", "finally", "also"]):
                    score *= 1.3
                scored.append((score, s))

            # Sort by score and take the top
            scored.sort(reverse=True, key=lambda x: x[0])
            top_points = [s for _, s in scored[:num_points]]

            result = [f"{num_points} Key Points:\n"]
            for i, point in enumerate(top_points, 1):
                result.append(f"{i}. {point}")

            return "\n".join(result)

        except Exception as e:
            return f"Error extracting key points: {e}"

    def generate_flashcards(
        self,
        text: str,
        num_cards: int = 20,
        format: str = "text",
    ) -> str:
        """Generate flashcards for study."""
        try:
            # Extract sentences with factual information
            sentences = text.replace("\n", " ").split(". ")
            sentences = [s.strip() for s in sentences if len(s.strip()) > 40]

            if len(sentences) < 5:
                return "Error: Text too short to generate flashcards."

            cards = []

            for i, sentence in enumerate(sentences[:num_cards]):
                # Create simple question (placeholder - LLM would do this better)
                words = sentence.split()
                if len(words) > 5:
                    # Hide a key part
                    mid = len(words) // 2
                    question_words = words[:mid] + ["___"] + words[mid + 2 :]
                    answer = " ".join(words[mid : mid + 2])

                    question = " ".join(question_words) + "?"
                    cards.append({"q": question, "a": answer, "full": sentence})

            if not cards:
                return "Could not generate flashcards."

            # Format output
            if format == "csv":
                output = ["question,answer"]
                for card in cards:
                    output.append(f'"{card["q"]}","{card["a"]}"')
                return "\n".join(output)

            elif format == "anki":
                # Tab-separated format for Anki
                output = []
                for card in cards:
                    output.append(f"{card['q']}\t{card['a']}")
                return "\n".join(output)

            else:  # text
                output = [f"{len(cards)} Flashcards Generated:\n"]
                for i, card in enumerate(cards, 1):
                    output.append(f"Card {i}:")
                    output.append(f"  Q: {card['q']}")
                    output.append(f"  A: {card['a']}")
                    output.append("")
                return "\n".join(output)

        except Exception as e:
            return f"Error generating flashcards: {e}"

    def compare_texts(self, text1: str, text2: str) -> str:
        """Compare two texts."""
        try:
            # Basic statistics
            words1 = set(text1.lower().split())
            words2 = set(text2.lower().split())

            common = words1 & words2
            only1 = words1 - words2
            only2 = words2 - words1

            similarity = len(common) / max(len(words1 | words2), 1) * 100

            result = [
                "Text Comparison:",
                "",
                f"Text 1: {len(text1):,} characters, {len(words1):,} unique words",
                f"Text 2: {len(text2):,} characters, {len(words2):,} unique words",
                "",
                f"Similarity (Jaccard): {similarity:.1f}%",
                f"Words in common: {len(common):,}",
                f"Only in text 1: {len(only1):,}",
                f"Only in text 2: {len(only2):,}",
            ]

            # Show some unique words
            if only1:
                sample1 = list(only1)[:10]
                result.append(f"\nUnique words text 1: {', '.join(sample1)}...")

            if only2:
                sample2 = list(only2)[:10]
                result.append(f"Unique words text 2: {', '.join(sample2)}...")

            return "\n".join(result)

        except Exception as e:
            return f"Error comparing texts: {e}"

    def execute(self, **kwargs) -> str:
        """Direct skill execution."""
        text = kwargs.get("text", "")
        file_path = kwargs.get("file")

        if file_path:
            return self.summarize_file(file_path, kwargs.get("style", "concise"))
        elif text:
            return self.summarize_text(text, kwargs.get("style", "concise"))
        else:
            return "Error: Text or file required for summarization"
