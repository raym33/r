"""
R CLI - Main entry point.

Usage:
    r                    # Start interactive mode
    r "message"          # Direct chat
    r pdf "content"      # Execute skill directly
    r --help             # Show help
"""

import sys
from typing import Optional

import click
from rich.console import Console
from rich.prompt import Prompt
from rich.table import Table

from r_cli import __version__
from r_cli.core.agent import Agent
from r_cli.core.config import Config
from r_cli.ui.ps2_loader import PS2Loader
from r_cli.ui.terminal import Terminal

console = Console()


# Skill categories for better organization
SKILL_CATEGORIES = {
    "Documents": ["pdf", "latex", "resume", "ocr"],
    "Development": ["code", "sql", "json", "git"],
    "AI & Knowledge": ["rag", "multiagent", "translate"],
    "Media": ["voice", "design", "screenshot"],
    "System": ["fs", "archive", "clipboard", "calendar", "email"],
    "Network": ["web", "http", "ssh", "docker"],
    "Other": ["plugin"],
}


def get_all_skill_names() -> list[str]:
    """Get all available skill names."""
    from r_cli.skills import get_all_skills

    return [skill_class.name for skill_class in get_all_skills() if hasattr(skill_class, "name")]


def select_skills_interactive() -> list[str]:
    """Interactive skill selector at startup."""
    all_skills = get_all_skill_names()

    console.print("\n[bold cyan]═══ Skill Selection ═══[/bold cyan]\n")
    console.print("[dim]Select which skills to load. More skills = larger context for LLM.[/dim]\n")

    # Show categories
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("#", style="cyan", width=4)
    table.add_column("Category", style="green")
    table.add_column("Skills", style="white")

    category_list = list(SKILL_CATEGORIES.items())
    for i, (category, skills) in enumerate(category_list, 1):
        available = [s for s in skills if s in all_skills]
        if available:
            table.add_row(str(i), category, ", ".join(available))

    table.add_row("A", "ALL", f"Load all {len(all_skills)} skills")
    table.add_row("M", "MINIMAL", "pdf, code, sql (recommended)")
    table.add_row("C", "CUSTOM", "Enter skill names manually")

    console.print(table)

    console.print(
        "\n[dim]Enter numbers separated by commas (e.g., 1,2,3) or a letter option.[/dim]"
    )
    choice = Prompt.ask("\n[bold]Select skills to load[/bold]", default="M")

    choice = choice.strip().upper()

    if choice == "A":
        console.print(f"[green]Loading all {len(all_skills)} skills...[/green]")
        return all_skills
    elif choice == "M":
        selected = ["pdf", "code", "sql"]
        console.print(f"[green]Loading minimal set: {', '.join(selected)}[/green]")
        return selected
    elif choice == "C":
        custom = Prompt.ask("[bold]Enter skill names[/bold] (comma-separated)")
        selected = [s.strip().lower() for s in custom.split(",") if s.strip()]
        valid = [s for s in selected if s in all_skills]
        if valid:
            console.print(f"[green]Loading: {', '.join(valid)}[/green]")
            return valid
        else:
            console.print("[yellow]No valid skills found. Loading minimal set.[/yellow]")
            return ["pdf", "code", "sql"]
    else:
        # Parse numeric choices
        try:
            indices = [int(x.strip()) - 1 for x in choice.split(",") if x.strip().isdigit()]
            selected = []
            for idx in indices:
                if 0 <= idx < len(category_list):
                    category, skills = category_list[idx]
                    available = [s for s in skills if s in all_skills]
                    selected.extend(available)

            if selected:
                selected = list(set(selected))  # Remove duplicates
                console.print(f"[green]Loading: {', '.join(selected)}[/green]")
                return selected
        except (ValueError, IndexError):
            pass

        console.print("[yellow]Invalid selection. Loading minimal set.[/yellow]")
        return ["pdf", "code", "sql"]


def create_agent(
    config: Optional[Config] = None,
    selected_skills: Optional[list[str]] = None,
    verbose: bool = False,
) -> Agent:
    """Create and configure the agent."""
    if config is None:
        config = Config.load()

    # If specific skills selected, configure whitelist
    if selected_skills:
        config.skills.mode = "whitelist"
        config.skills.enabled = selected_skills

    agent = Agent(config)
    agent.load_skills(verbose=verbose)
    return agent


@click.group(invoke_without_command=True)
@click.option("--version", "-v", is_flag=True, help="Show version")
@click.option("--theme", "-t", default="ps2", help="Visual theme (ps2, matrix, minimal)")
@click.option("--no-animation", is_flag=True, help="Disable animations")
@click.option("--stream/--no-stream", default=True, help="Enable/disable response streaming")
@click.option("--skills-mode", "-s", type=click.Choice(["auto", "lite", "standard", "full"]), default=None, help="Skill loading mode")
@click.pass_context
def cli(ctx, version: bool, theme: str, no_animation: bool, stream: bool, skills_mode: str):
    """
    R CLI - Local AI Agent Runtime.

    100% private · 100% offline · 100% yours

    Examples:
        r                          # Interactive mode
        r "Explain what Python is" # Direct chat
        r pdf "My document"        # Generate PDF
        r sql sales.csv "SELECT * FROM data"
        r --skills-mode lite       # Use minimal skills for small context
    """
    ctx.ensure_object(dict)
    ctx.obj["theme"] = theme
    ctx.obj["no_animation"] = no_animation
    ctx.obj["stream"] = stream
    ctx.obj["skills_mode"] = skills_mode

    if version:
        console.print(f"R CLI v{__version__}")
        sys.exit(0)

    # If no subcommand, start interactive mode
    if ctx.invoked_subcommand is None:
        interactive_mode(theme, not no_animation, stream, skills_mode)


@cli.command()
@click.argument("message", nargs=-1, required=True)
@click.pass_context
def chat(ctx, message: tuple):
    """Send a message to the agent."""
    theme = ctx.obj.get("theme", "ps2")
    no_animation = ctx.obj.get("no_animation", False)
    skills_mode = ctx.obj.get("skills_mode")

    msg = " ".join(message)
    single_query(msg, theme, not no_animation, skills_mode)


@cli.command()
@click.argument("content", required=True)
@click.option("--title", "-t", help="Document title")
@click.option("--output", "-o", help="Output path")
@click.option("--template", default="minimal", help="Template: minimal, business, academic")
def pdf(content: str, title: Optional[str], output: Optional[str], template: str):
    """Generate a PDF document."""
    agent = create_agent()

    result = agent.run_skill_directly(
        "pdf",
        content=content,
        title=title,
        output=output,
        template=template,
    )

    console.print(result)


@cli.command()
@click.argument("file_path", required=True)
@click.option("--style", "-s", default="concise", help="Style: concise, detailed, bullets")
def resume(file_path: str, style: str):
    """Summarize a document."""
    agent = create_agent()

    result = agent.run_skill_directly("resume", file=file_path, style=style)
    console.print(result)


@cli.command()
@click.argument("query", required=True)
@click.option("--csv", "-c", help="CSV file to query")
def sql(query: str, csv: Optional[str]):
    """Execute a SQL query."""
    agent = create_agent()

    result = agent.run_skill_directly("sql", query=query, csv=csv)
    console.print(result)


@cli.command()
@click.argument("code", required=True)
@click.option("--filename", "-f", default="script.py", help="File name")
@click.option("--run", "-r", is_flag=True, help="Run after creating")
def code(code: str, filename: str, run: bool):
    """Generate code."""
    agent = create_agent()

    result = agent.run_skill_directly("code", code=code, filename=filename, action="write")
    console.print(result)

    if run and filename.endswith(".py"):
        console.print("\n[dim]Running...[/dim]\n")
        run_result = agent.run_skill_directly("code", code=code, action="run")
        console.print(run_result)


@cli.command()
@click.argument("path", default=".")
@click.option("--pattern", "-p", help="Search pattern (e.g., *.py)")
def ls(path: str, pattern: Optional[str]):
    """List files in a directory."""
    agent = create_agent()

    result = agent.run_skill_directly("fs", action="list", path=path, pattern=pattern)
    console.print(result)


@cli.command()
def skills():
    """List available skills."""
    term = Terminal()
    agent = create_agent(verbose=True)

    term.print_skill_list(agent.skills)


def show_config():
    """Show current configuration (helper function)."""
    cfg = Config.load()

    console.print("[bold]R CLI Configuration[/bold]\n")
    console.print(f"LLM Provider: {cfg.llm.provider}")
    console.print(f"LLM URL: {cfg.llm.base_url}")
    console.print(f"Model: {cfg.llm.model}")
    console.print(f"Theme: {cfg.ui.theme}")
    console.print("\nDirectories:")
    console.print(f"  Home: {cfg.home_dir}")
    console.print(f"  Output: {cfg.output_dir}")
    console.print(f"  RAG DB: {cfg.rag.persist_directory}")


@cli.command("config")
def config_command():
    """Show current configuration."""
    show_config()


@cli.command()
def demo():
    """Run animation demo."""
    from r_cli.ui.ps2_loader import demo as ps2_demo

    ps2_demo()


@cli.command()
@click.option("--host", "-h", default="127.0.0.1", help="Host to bind to")
@click.option("--port", "-p", default=8765, help="Port to listen on")
@click.option("--reload", is_flag=True, help="Enable auto-reload for development")
@click.option("--workers", "-w", default=1, help="Number of worker processes")
def serve(host: str, port: int, reload: bool, workers: int):
    """
    Start the R CLI API server (daemon mode).

    This runs R as a persistent REST API server that can be accessed
    by other applications, IDEs, or scripts.

    Examples:
        r serve                    # Start on localhost:8765
        r serve --port 8080        # Custom port
        r serve --host 0.0.0.0     # Listen on all interfaces
        r serve --reload           # Development mode with auto-reload
    """
    from r_cli.api import run_server

    console.print("[bold cyan]R CLI API Server[/bold cyan]")
    console.print(f"Starting on http://{host}:{port}")
    console.print(f"API docs: http://{host}:{port}/docs")
    console.print("[dim]Press Ctrl+C to stop[/dim]\n")

    run_server(host=host, port=port, reload=reload, workers=workers)


def interactive_mode(theme: str = "ps2", show_animation: bool = True, use_streaming: bool = True, skills_mode: str = None):
    """Main interactive mode."""
    term = Terminal(theme=theme)
    config = Config.load()
    config.ui.theme = theme

    # Apply skills mode if specified
    if skills_mode:
        if skills_mode == "full":
            config.skills.mode = "blacklist"
        else:
            config.skills.mode = skills_mode

    # Show welcome
    term.clear()
    term.print_welcome()

    # Interactive skill selection (skip if mode already set)
    selected_skills = None
    if not skills_mode:
        selected_skills = select_skills_interactive()

    # Loading animation
    if show_animation:
        loader = PS2Loader(style=theme if theme in ["ps2", "matrix"] else "ps2")
        loader.show_once("Initializing R CLI", duration=2)

    # Create agent with selected skills
    agent = create_agent(config, selected_skills)

    # Check LLM connection
    llm_connected = agent.check_connection()
    term.print_status(llm_connected, len(agent.skills))

    if not llm_connected:
        term.print_warning(
            "No LLM server detected. Start LM Studio or Ollama.\n"
            "Direct skills (pdf, sql, etc.) will work without LLM."
        )

    stream_status = "[green]enabled[/green]" if use_streaming else "[yellow]disabled[/yellow]"
    term.print(f"\nStreaming: {stream_status}")
    term.print("Type your message or /help for help. /exit to quit.\n")

    # Main loop
    while True:
        try:
            user_input = term.get_input()

            if not user_input.strip():
                continue

            # Special commands
            if user_input.startswith("/"):
                cmd = user_input[1:].lower().strip()

                if cmd in ["exit", "quit", "q"]:
                    term.print_success("Goodbye!")
                    break
                if cmd == "help":
                    term.print_help()
                elif cmd == "clear":
                    term.clear()
                    term.print_welcome()
                    agent.llm.clear_history()
                    term.print_success("History cleared")
                elif cmd == "skills":
                    term.print_skill_list(agent.skills)
                elif cmd == "config":
                    # Show configuration directly
                    show_config()
                elif cmd == "status":
                    llm_connected = agent.check_connection()
                    term.print_status(llm_connected, len(agent.skills))
                elif cmd == "stream":
                    use_streaming = not use_streaming
                    status = "enabled" if use_streaming else "disabled"
                    term.print_success(f"Streaming {status}")
                else:
                    term.print_error(f"Unknown command: /{cmd}")
                continue

            # Show user input
            term.print_user_input(user_input)

            # Process with agent - use streaming if enabled and connected
            if use_streaming and llm_connected and not agent.tools:
                # Streaming mode (only for chat without tools)
                term.print_stream_start()
                try:
                    for chunk in agent.run_stream(user_input):
                        term.print_stream_chunk(chunk)
                    term.print_stream_end()
                except Exception as e:
                    term.print_stream_end()
                    term.print_error(f"Streaming error: {e}")
            else:
                # Traditional mode (with tools or without streaming)
                with term.print_thinking("Thinking"):
                    response = agent.run(user_input)
                term.print_response(response)

            term.print()

        except KeyboardInterrupt:
            term.print("\n")
            term.print_success("Goodbye!")
            break
        except EOFError:
            break
        except Exception as e:
            term.print_error(str(e))


def single_query(message: str, theme: str = "ps2", show_animation: bool = True, skills_mode: str = None):
    """Execute a single query and exit."""
    term = Terminal(theme=theme)

    # Configure skills mode
    config = Config.load()
    if skills_mode:
        if skills_mode == "full":
            config.skills.mode = "blacklist"
        else:
            config.skills.mode = skills_mode

    agent = create_agent(config)

    # Brief animation
    if show_animation:
        loader = PS2Loader(style="ps2")
        with loader.start("Processing"):
            response = agent.run(message)
    else:
        response = agent.run(message)

    term.print_response(response)


def main():
    """Entry point."""
    cli(obj={})


if __name__ == "__main__":
    main()
