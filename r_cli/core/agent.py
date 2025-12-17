"""
Main agent for R CLI.

Orchestrates:
- LLM Client for reasoning
- Skills for task execution
- Memory for context
- UI for user feedback
"""

import os
from typing import Optional

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from r_cli.core.config import Config
from r_cli.core.llm import LLMClient, Tool
from r_cli.core.memory import Memory

console = Console()


# Base system prompt for the agent
SYSTEM_PROMPT = """You are R, a local AI assistant that runs 100% offline in the user's terminal.

Your personality:
- Direct and efficient (no unnecessary flourishes)
- Technically competent
- Action-oriented (prefer to act rather than ask too many questions)

Capabilities:
- Generate documents (PDF, LaTeX, Markdown)
- Summarize long texts
- Write and analyze code
- SQL queries in natural language
- Manage local files
- Remember context from previous conversations

Restrictions:
- You can only access the user's local files
- You have no internet access
- Respond in the same language as the user

When using tools:
1. Briefly explain what you're going to do
2. Execute the tool
3. Report the result concisely

If you can't do something, explain why and suggest alternatives.
"""


class Agent:
    """
    Main agent that processes user requests.

    Usage:
    ```python
    agent = Agent()
    response = agent.run("Generate a PDF with the project summary")
    ```
    """

    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self.config.ensure_directories()

        # Core components
        self.llm = LLMClient(self.config)
        self.memory = Memory(self.config)

        # Registered skills (loaded dynamically)
        self.skills: dict[str, Skill] = {}
        self.tools: list[Tool] = []

        # State
        self.is_running = False

        # Configure LLM
        self._setup_llm()

    def _setup_llm(self) -> None:
        """Configure the LLM with system prompt and context."""
        # Load previous session if exists
        if self.memory.load_session():
            session_summary = self.memory.get_session_summary()
            full_prompt = f"{SYSTEM_PROMPT}\n\n{session_summary}"
        else:
            full_prompt = SYSTEM_PROMPT

        self.llm.set_system_prompt(full_prompt)

    def register_skill(self, skill: "Skill", verbose: bool = False) -> None:
        """Register a skill and its tools."""
        self.skills[skill.name] = skill

        # Add skill's tools
        for tool in skill.get_tools():
            self.tools.append(tool)

        if verbose:
            console.print(f"[dim]Skill registered: {skill.name}[/dim]")

    def load_skills(self, verbose: bool = False, auto_detect: bool = True) -> None:
        """Load all available skills, respecting configuration.

        Args:
            verbose: Show skill loading messages
            auto_detect: Auto-detect skill mode based on context size
        """
        from r_cli.skills import get_all_skills

        # Auto-detect mode based on context if enabled and mode is "auto"
        if auto_detect and self.config.skills.mode == "auto":
            mode = self.config.skills.set_auto_mode(self.config.llm.max_context_tokens)
            if verbose:
                console.print(f"[dim]Auto-detected skill mode: {mode} (context: {self.config.llm.max_context_tokens} tokens)[/dim]")

        loaded = 0
        skipped = 0

        for skill_class in get_all_skills():
            try:
                skill = skill_class(self.config)

                # Check if skill is enabled in config
                if not self.config.skills.is_skill_enabled(skill.name):
                    skipped += 1
                    continue

                self.register_skill(skill, verbose=verbose)
                loaded += 1
            except ImportError as e:
                if verbose:
                    console.print(
                        f"[yellow]Missing dependency for {skill_class.__name__}: {e}[/yellow]"
                    )
            except TypeError as e:
                if verbose:
                    console.print(
                        f"[yellow]Configuration error in {skill_class.__name__}: {e}[/yellow]"
                    )
            except OSError as e:
                if verbose:
                    console.print(f"[yellow]File/IO error in {skill_class.__name__}: {e}[/yellow]")
            except Exception as e:
                if verbose:
                    console.print(
                        f"[yellow]Unexpected error loading {skill_class.__name__}: {e}[/yellow]"
                    )

        if verbose:
            console.print(f"[dim]Loaded {loaded} skills ({skipped} disabled)[/dim]")

    def get_relevant_tools(self, user_input: str, max_tools: int = 30) -> list[Tool]:
        """
        Select tools relevant to the user's query.

        Uses keyword matching to filter tools, reducing context usage.
        """
        # Keyword to skill mapping
        SKILL_KEYWORDS = {
            "datetime": ["time", "date", "today", "now", "calendar", "schedule", "when", "hour", "minute"],
            "math": ["calculate", "math", "sum", "multiply", "divide", "equation", "number", "factorial", "sqrt", "2+2", "2 + 2"],
            "text": ["text", "string", "word", "count", "uppercase", "lowercase", "slug", "reverse", "trim"],
            "json": ["json", "parse json", "format json", "validate json"],
            "yaml": ["yaml", "yml", "config file"],
            "csv": ["csv", "spreadsheet", "comma separated"],
            "crypto": ["hash", "md5", "sha256", "sha", "encrypt", "decrypt", "base64", "encode", "decode", "hmac"],
            "pdf": ["pdf", "document", "report"],
            "code": ["code", "program", "script", "function", "class", "python", "javascript", "generate code"],
            "sql": ["sql", "query", "database", "select from", "insert into"],
            "git": ["git", "commit", "branch", "merge", "repository", "repo", "diff", "status"],
            "http": ["http", "api", "request", "fetch", "endpoint", "rest"],
            "fs": ["file", "folder", "directory", "read file", "write file", "list files", "delete file", "copy file"],
            "archive": ["zip", "tar", "compress", "extract", "archive", "unzip"],
            "regex": ["regex", "pattern", "regular expression", "match pattern"],
            "translate": ["translate", "translation", "spanish", "english", "french", "german", "idioma"],
            "image": ["image", "picture", "photo", "resize image", "crop", "png", "jpg", "jpeg"],
            "video": ["video", "movie", "clip", "ffmpeg", "mp4"],
            "audio": ["audio", "sound", "music", "mp3", "wav", "recording"],
            "weather": ["weather", "temperature", "forecast", "rain", "sunny", "clima"],
            "email": ["email", "mail", "send email", "smtp"],
            "docker": ["docker", "container", "compose", "dockerfile"],
            "ssh": ["ssh", "remote server", "connect to server"],
            "qr": ["qr", "qrcode", "qr code"],
            "barcode": ["barcode", "ean", "upc"],
            "ocr": ["ocr", "text from image", "extract text", "recognize text"],
            "voice": ["voice", "speech", "tts", "speak", "transcribe", "whisper", "audio to text"],
        }

        user_lower = user_input.lower()
        matched_skills = set()

        # Always include core skills for general queries
        matched_skills.add("datetime")

        # Find matching skills based on keywords
        for skill_name, keywords in SKILL_KEYWORDS.items():
            for keyword in keywords:
                if keyword in user_lower:
                    matched_skills.add(skill_name)
                    break

        # Build tool-to-skill mapping from loaded skills
        skill_tools = {}
        for skill_name, skill in self.skills.items():
            skill_tools[skill_name] = [t.name for t in skill.get_tools()]

        # Filter tools to only those from matched skills
        relevant_tools = []
        for tool in self.tools:
            for skill_name in matched_skills:
                if skill_name in skill_tools and tool.name in skill_tools[skill_name]:
                    relevant_tools.append(tool)
                    break

        # If too few tools matched, return core tools
        if len(relevant_tools) < 3:
            # Return tools from core skills
            core_skills = ["datetime", "math", "text", "fs", "json"]
            for tool in self.tools:
                for skill_name in core_skills:
                    if skill_name in skill_tools and tool.name in skill_tools[skill_name]:
                        relevant_tools.append(tool)
                        break
                if len(relevant_tools) >= max_tools:
                    break

        return relevant_tools[:max_tools]

    def run(self, user_input: str, show_thinking: bool = True, smart_tools: bool = True) -> str:
        """
        Process user input and return response.

        Args:
            user_input: User's message
            show_thinking: Whether to show reasoning process
            smart_tools: Use intelligent tool selection to reduce context

        Returns:
            Agent's response
        """
        # Add to memory
        self.memory.add_short_term(user_input, entry_type="user_input")

        # Get relevant context
        context = self.memory.get_relevant_context(user_input)

        # Prepare message with context
        if context:
            augmented_input = f"{user_input}\n\n[Available context]\n{context}"
        else:
            augmented_input = user_input

        # Execute with tools if skills are registered
        if self.tools:
            # Use smart tool selection if enabled
            tools_to_use = self.get_relevant_tools(user_input) if smart_tools else self.tools
            response = self.llm.chat_with_tools(augmented_input, tools_to_use)
        else:
            response_msg = self.llm.chat(augmented_input)
            response = response_msg.content or ""

        # Add response to memory
        self.memory.add_short_term(response, entry_type="agent_response")

        # Save session
        self.memory.save_session()

        return response

    def run_stream(self, user_input: str):
        """
        Process user input with streaming.

        Yields response chunks as they arrive.

        Args:
            user_input: User's message

        Yields:
            Text chunks of the response
        """
        # Add to memory
        self.memory.add_short_term(user_input, entry_type="user_input")

        # Get relevant context
        context = self.memory.get_relevant_context(user_input)

        # Prepare message with context
        if context:
            augmented_input = f"{user_input}\n\n[Available context]\n{context}"
        else:
            augmented_input = user_input

        # Use streaming (without tools for simple streaming)
        full_response = ""
        for chunk in self.llm.chat_stream_sync(augmented_input):
            full_response += chunk
            yield chunk

        # Add complete response to memory
        self.memory.add_short_term(full_response, entry_type="agent_response")

        # Save session
        self.memory.save_session()

    def run_skill_directly(self, skill_name: str, **kwargs) -> str:
        """
        Execute a skill directly without going through the LLM.

        Useful for direct commands like: r pdf "content"
        """
        if skill_name not in self.skills:
            return f"Skill not found: {skill_name}"

        skill = self.skills[skill_name]
        return skill.execute(**kwargs)

    def check_connection(self) -> bool:
        """Check connection to the LLM server."""
        return self.llm._check_connection()

    def get_available_skills(self) -> list[str]:
        """Return list of available skills."""
        return list(self.skills.keys())

    def show_help(self) -> None:
        """Show help about available skills."""
        help_text = "# Available Skills\n\n"

        for name, skill in self.skills.items():
            help_text += f"## {name}\n"
            help_text += f"{skill.description}\n\n"
            help_text += f"**Usage:** `r {name} <args>`\n\n"

        console.print(Panel(Markdown(help_text), title="R CLI Help", border_style="blue"))


class Skill:
    """
    Base class for skills.

    Skills are specialized mini-programs that the agent can use.

    Implementation example:
    ```python
    class PDFSkill(Skill):
        name = "pdf"
        description = "Generate PDF documents"

        def get_tools(self) -> list[Tool]:
            return [
                Tool(
                    name="generate_pdf",
                    description="Generate a PDF",
                    parameters={...},
                    handler=self.generate_pdf,
                )
            ]

        def generate_pdf(self, content: str, output: str) -> str:
            # Implementation
            return f"PDF generated: {output}"
    ```
    """

    name: str = "base_skill"
    description: str = "Base skill"

    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self.output_dir = os.path.expanduser(self.config.output_dir)

    def get_tools(self) -> list[Tool]:
        """Return the tools this skill provides."""
        return []

    def execute(self, **kwargs) -> str:
        """Direct execution of the skill (without LLM)."""
        return "Not implemented"
