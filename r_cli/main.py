"""
R CLI - Main entry point.

Usage:
    r                    # Start interactive mode
    r "message"          # Direct chat
    r pdf "content"      # Execute skill directly
    r --help             # Show help
"""

import contextlib
import io
import json
import sys
from pathlib import Path
from typing import Optional

import click
from click.shell_completion import get_completion_class
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table

from r_cli import __version__
from r_cli.core.agent import Agent
from r_cli.core.config import Config, discover_config_path
from r_cli.ui.ps2_loader import PS2Loader
from r_cli.ui.terminal import Terminal

console = Console()


class DirectChatGroup(click.Group):
    """Treat an unknown positional command as a direct chat message."""

    def resolve_command(self, ctx, args):
        try:
            return super().resolve_command(ctx, args)
        except click.UsageError:
            if not args or args[0].startswith("-"):
                raise

            chat_command = self.get_command(ctx, "chat")
            if chat_command is None:
                raise

            return "chat", chat_command, args


# Skill categories for better organization
SKILL_CATEGORIES = {
    "Documents": ["pdf", "latex", "resume", "ocr"],
    "Development": ["code", "sql", "json", "git"],
    "AI & Knowledge": ["rag", "multiagent", "translate", "distributed_ai", "p2p"],
    "Media": ["voice", "design", "screenshot"],
    "System": ["fs", "archive", "clipboard", "calendar", "email"],
    "Network": ["web", "http", "ssh", "docker"],
    "Other": ["plugin"],
}


def get_all_skill_names() -> list[str]:
    """Get all available skill names."""
    from r_cli.skills import get_all_skills

    return [skill_class.name for skill_class in get_all_skills() if hasattr(skill_class, "name")]


def get_config_path() -> str:
    """Return the active configuration path."""
    return str(discover_config_path())


def approval_prompt(request) -> bool:
    """Ask the user to approve a high-risk tool call."""
    console.print(
        Panel(
            f"[bold]{request.target}[/bold]\n"
            f"Risk: [yellow]{request.risk.value}[/yellow]\n"
            f"Arguments: {json.dumps(request.arguments, default=str)[:1000]}",
            title="Permission required",
            border_style="yellow",
        )
    )
    return Confirm.ask("Allow this action?", default=False)


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
    auto_approve: bool = False,
) -> Agent:
    """Create and configure the agent."""
    if config is None:
        config = Config.load()

    # If specific skills selected, configure whitelist
    if selected_skills:
        config.skills.mode = "whitelist"
        config.skills.enabled = selected_skills

    callback = approval_prompt if sys.stdin.isatty() and not auto_approve else None
    agent = Agent(config, approval_callback=callback, auto_approve=auto_approve)
    agent.load_skills(verbose=verbose)
    return agent


@click.group(
    cls=DirectChatGroup,
    invoke_without_command=True,
    context_settings={"help_option_names": ["-h", "--help"], "max_content_width": 100},
    epilog="""
\b
Examples:
  r                              Start interactive mode
  r "Explain what Python is"     Send a direct message
  r doctor                       Diagnose the local setup
  r skills --search pdf          Find relevant skills
  r --skills-mode lite chat      Use a smaller tool context
""",
)
@click.option("--version", "-v", is_flag=True, help="Show version")
@click.option("--theme", "-t", default="ps2", help="Visual theme (ps2, matrix, minimal)")
@click.option("--no-animation", is_flag=True, help="Disable animations")
@click.option("--stream/--no-stream", default=True, help="Enable/disable response streaming")
@click.option("--yes", is_flag=True, help="Approve high-risk actions without prompting")
@click.option(
    "--skills-mode",
    "-s",
    type=click.Choice(["auto", "lite", "standard", "full"]),
    default=None,
    help="Skill loading mode",
)
@click.pass_context
def cli(
    ctx,
    version: bool,
    theme: str,
    no_animation: bool,
    stream: bool,
    yes: bool,
    skills_mode: str,
):
    """R CLI - Local AI Agent Runtime. Private, local, and extensible."""
    ctx.ensure_object(dict)
    ctx.obj["theme"] = theme
    ctx.obj["no_animation"] = no_animation
    ctx.obj["stream"] = stream
    ctx.obj["yes"] = yes
    ctx.obj["skills_mode"] = skills_mode

    if version:
        console.print(f"R CLI v{__version__}")
        sys.exit(0)

    # If no subcommand, start interactive mode
    if ctx.invoked_subcommand is None:
        if not sys.stdin.isatty():
            message = sys.stdin.read().strip()
            if message:
                single_query(message, theme, False, skills_mode, stream, yes)
            else:
                click.echo(ctx.get_help())
            return
        interactive_mode(theme, not no_animation, stream, skills_mode, yes)


@cli.command()
@click.argument("message", nargs=-1, required=True)
@click.option(
    "--stream/--no-stream",
    "command_stream",
    default=None,
    help="Enable/disable response streaming",
)
@click.pass_context
def chat(ctx, message: tuple, command_stream: Optional[bool]):
    """Send a message to the agent."""
    theme = ctx.obj.get("theme", "ps2")
    no_animation = ctx.obj.get("no_animation", False)
    skills_mode = ctx.obj.get("skills_mode")
    use_streaming = ctx.obj.get("stream", True) if command_stream is None else command_stream

    msg = " ".join(message)
    single_query(
        msg,
        theme,
        not no_animation,
        skills_mode,
        use_streaming,
        ctx.obj.get("yes", False),
    )


@cli.command()
@click.argument("content", required=False)
@click.option(
    "--file",
    "input_file",
    type=click.Path(exists=True, dir_okay=False, path_type=str),
    help="Read content from a text or Markdown file",
)
@click.option("--title", "-t", help="Document title")
@click.option("--output", "-o", help="Output path")
@click.option(
    "--template",
    type=click.Choice(["minimal", "business", "academic", "report"]),
    default="minimal",
)
@click.option("--author", help="Document author")
def pdf(
    content: Optional[str],
    input_file: Optional[str],
    title: Optional[str],
    output: Optional[str],
    template: str,
    author: Optional[str],
):
    """Generate a PDF document."""
    if input_file and content:
        raise click.UsageError("Use either CONTENT or --file, not both")
    if input_file:
        content = Path(input_file).read_text(encoding="utf-8")
    elif content is None and not sys.stdin.isatty():
        content = sys.stdin.read()
    if not content or not content.strip():
        raise click.UsageError("Provide CONTENT, --file, or pipe text through stdin")

    agent = create_agent(selected_skills=["pdf"])

    result = agent.run_skill_directly(
        "pdf",
        content=content,
        title=title,
        output=output,
        template=template,
        author=author,
    )

    console.print(result)


@cli.command("tool")
@click.argument("skill_name")
@click.argument("tool_name", required=False)
@click.option("--arg", "values", multiple=True, metavar="KEY=VALUE", help="Tool argument")
@click.option("--params", help="Tool arguments as a JSON object")
@click.option("--schema", is_flag=True, help="Print the selected tool's JSON schema")
@click.option("--json", "as_json", is_flag=True, help="Wrap the result as JSON")
@click.option("--yes", is_flag=True, help="Approve this action without prompting")
@click.pass_context
def tool_command(
    ctx,
    skill_name: str,
    tool_name: Optional[str],
    values: tuple[str, ...],
    params: Optional[str],
    schema: bool,
    as_json: bool,
    yes: bool,
):
    """List or execute any tool exposed by an R skill."""
    from r_cli.core.permissions import PermissionDeniedError
    from r_cli.tool_runner import (
        ToolRunnerError,
        build_arguments,
        execute_tool,
        load_skill,
        normalize_result,
        resolve_tool,
    )

    try:
        if tool_name is None:
            with (
                contextlib.redirect_stdout(io.StringIO()),
                contextlib.redirect_stderr(io.StringIO()),
            ):
                skill = load_skill(skill_name)
            tools = [
                {
                    "name": item.name,
                    "description": item.description,
                    "parameters": item.parameters,
                }
                for item in skill.get_tools()
            ]
            if as_json:
                click.echo(json.dumps({"skill": skill_name, "tools": tools}, indent=2))
                return

            table = Table(title=f"{skill_name} tools ({len(tools)})")
            table.add_column("Tool", style="cyan")
            table.add_column("Description")
            for item in tools:
                table.add_row(item["name"], item["description"])
            console.print(table)
            return

        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            match = resolve_tool(skill_name, tool_name)
        if schema:
            click.echo(json.dumps(match.tool.parameters, indent=2))
            return

        arguments = build_arguments(params, values)
        auto_approve = yes or ctx.obj.get("yes", False)
        callback = approval_prompt if sys.stdin.isatty() and not auto_approve else None
        result = execute_tool(
            skill_name,
            tool_name,
            arguments,
            approval_callback=callback,
            auto_approve=auto_approve,
        )
    except (ToolRunnerError, PermissionDeniedError) as exc:
        raise click.ClickException(str(exc)) from exc

    if as_json:
        click.echo(
            json.dumps(
                {
                    "skill": skill_name,
                    "tool": tool_name,
                    "arguments": arguments,
                    "result": normalize_result(result),
                },
                indent=2,
                default=str,
            )
        )
    else:
        console.print(result)


@cli.group()
def project():
    """Understand and work with local projects."""


@project.command("inspect")
@click.argument("path", default=".", type=click.Path(path_type=str))
@click.option("--json", "as_json", is_flag=True, help="Output machine-readable JSON")
def project_inspect(path: str, as_json: bool):
    """Detect stacks and recommend relevant R skills."""
    from r_cli.project_inspector import inspect_project

    try:
        report = inspect_project(path)
    except (FileNotFoundError, NotADirectoryError) as exc:
        raise click.ClickException(str(exc)) from exc

    if as_json:
        click.echo(json.dumps(report.to_dict(), indent=2))
        return

    table = Table(show_header=False, box=None)
    table.add_column("Field", style="cyan")
    table.add_column("Value")
    table.add_row("Project", report.name)
    table.add_row("Path", report.path)
    table.add_row("Stacks", ", ".join(report.stacks) or "Unknown")
    table.add_row("Traits", ", ".join(report.traits) or "None detected")
    table.add_row("Files", str(report.files_scanned))
    table.add_row("Recommended skills", ", ".join(report.recommended_skills) or "None")
    console.print(Panel(table, title="Project inspection"))

    if report.suggested_commands:
        console.print("\n[bold]Suggested commands[/bold]")
        for command in report.suggested_commands:
            console.print(f"  [dim]$[/dim] {command}")


@project.command("init")
@click.argument("path", default=".", type=click.Path(path_type=str))
@click.option("--force", is_flag=True, help="Overwrite an existing project profile")
def project_init(path: str, force: bool):
    """Create a local .r-cli.yaml profile with recommended skills."""
    from r_cli.project_inspector import initialize_project

    try:
        config_path, report = initialize_project(path, force=force)
    except (FileNotFoundError, NotADirectoryError, FileExistsError, OSError) as exc:
        raise click.ClickException(str(exc)) from exc

    console.print(f"[green]Created {config_path}[/green]")
    console.print(f"Enabled {len(report.recommended_skills)} project-aware skills.")


@cli.group()
def permissions():
    """Inspect local execution policy and audit decisions."""


@permissions.command("explain")
@click.argument("skill_name")
@click.argument("tool_name", default="direct")
@click.option("--json", "as_json", is_flag=True, help="Output machine-readable JSON")
def permissions_explain(skill_name: str, tool_name: str, as_json: bool):
    """Explain the effective risk and policy for a tool."""
    from r_cli.core.permissions import classify_risk

    config = Config.load()
    target = f"{skill_name}.{tool_name}"
    risk = classify_risk(skill_name, tool_name)
    explicitly_allowed = (
        skill_name in config.security.allowed_skills or target in config.security.allowed_tools
    )
    explicitly_denied = (
        skill_name in config.security.denied_skills or target in config.security.denied_tools
    )
    requires_confirmation = (
        skill_name in config.skills.require_confirmation
        or risk.value in config.security.confirm_risk
    )
    result = {
        "target": target,
        "risk": risk.value,
        "mode": config.security.mode,
        "explicitly_allowed": explicitly_allowed,
        "explicitly_denied": explicitly_denied,
        "requires_confirmation": requires_confirmation,
    }

    if as_json:
        click.echo(json.dumps(result, indent=2))
        return

    table = Table(show_header=False, box=None)
    for key, value in result.items():
        table.add_row(key.replace("_", " ").title(), str(value))
    console.print(Panel(table, title="Permission policy"))


@permissions.command("audit")
@click.option("--limit", default=20, type=click.IntRange(min=1, max=1000))
@click.option("--json", "as_json", is_flag=True, help="Output machine-readable JSON")
def permissions_audit(limit: int, as_json: bool):
    """Show recent local tool authorization decisions."""
    config = Config.load()
    audit_path = Path(config.security.audit_path).expanduser()
    if not audit_path.is_absolute():
        audit_path = Path(config.home_dir).expanduser() / audit_path

    records = []
    if audit_path.exists():
        for line in audit_path.read_text(encoding="utf-8").splitlines()[-limit:]:
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    if as_json:
        click.echo(json.dumps(records, indent=2))
        return

    table = Table(title=f"Permission audit ({len(records)})")
    table.add_column("Time")
    table.add_column("Decision")
    table.add_column("Risk")
    table.add_column("Target")
    for record in records:
        table.add_row(
            record.get("timestamp", ""),
            record.get("decision", ""),
            record.get("risk", ""),
            f"{record.get('skill', '')}.{record.get('tool', '')}",
        )
    console.print(table)


@cli.group()
def traces():
    """Inspect performance and outcomes of local tool executions."""


@traces.command("list")
@click.option("--limit", default=20, type=click.IntRange(min=1, max=1000))
@click.option("--decision", type=click.Choice(["completed", "denied", "error"]))
@click.option("--risk", type=click.Choice(["low", "medium", "high", "critical"]))
@click.option("--skill")
@click.option("--source")
@click.option("--json", "as_json", is_flag=True, help="Output machine-readable JSON")
def traces_list(
    limit: int,
    decision: str | None,
    risk: str | None,
    skill: str | None,
    source: str | None,
    as_json: bool,
):
    """List recent completed, denied, or failed executions."""
    from r_cli.observability import TraceStore

    records = TraceStore(Config.load()).read(
        limit=limit,
        decision=decision,
        risk=risk,
        skill=skill,
        source=source,
        terminal_only=True,
    )
    if as_json:
        click.echo(json.dumps(records, indent=2))
        return

    table = Table(title=f"Execution traces ({len(records)})")
    table.add_column("Time")
    table.add_column("Status")
    table.add_column("Source")
    table.add_column("Target")
    table.add_column("Risk")
    table.add_column("Duration")
    for record in records:
        duration = record.get("duration_ms")
        table.add_row(
            record.get("timestamp", ""),
            record.get("decision", ""),
            record.get("source", "local"),
            f"{record.get('skill', '')}.{record.get('tool', '')}",
            record.get("risk", ""),
            f"{duration:.1f} ms" if isinstance(duration, (int, float)) else "-",
        )
    console.print(table)


@traces.command("summary")
@click.option("--json", "as_json", is_flag=True, help="Output machine-readable JSON")
def traces_summary(as_json: bool):
    """Summarize execution reliability and latency."""
    from r_cli.observability import TraceStore

    result = TraceStore(Config.load()).summary()
    if as_json:
        click.echo(json.dumps(result, indent=2))
        return

    table = Table(show_header=False, box=None)
    table.add_column("Metric", style="cyan")
    table.add_column("Value")
    table.add_row("Executions", str(result["total"]))
    table.add_row("Completed", str(result["completed"]))
    table.add_row("Errors", str(result["errors"]))
    table.add_row("Denied", str(result["denied"]))
    table.add_row("Success rate", f"{result['success_rate']:.2f}%")
    table.add_row("Average latency", f"{result['average_duration_ms']:.1f} ms")
    table.add_row("P50 latency", f"{result['p50_duration_ms']:.1f} ms")
    table.add_row("P95 latency", f"{result['p95_duration_ms']:.1f} ms")
    console.print(Panel(table, title="Execution summary"))


@traces.command("export")
@click.argument("output", type=click.Path(path_type=Path))
@click.option("--format", "file_format", type=click.Choice(["json", "csv"]))
def traces_export(output: Path, file_format: str | None):
    """Export the complete trace history to JSON or CSV."""
    from r_cli.observability import TraceStore

    selected_format = file_format or ("csv" if output.suffix.lower() == ".csv" else "json")
    count = TraceStore(Config.load()).export(output, selected_format)
    console.print(f"[green]Exported {count} trace records to {output}[/green]")


@cli.group()
def workflow():
    """Validate and run reproducible YAML workflows."""


@workflow.command("validate")
@click.argument("path", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--json", "as_json", is_flag=True, help="Output machine-readable JSON")
def workflow_validate(path: Path, as_json: bool):
    """Validate structure, dependencies, tools, and argument names."""
    from r_cli.tool_runner import ToolRunnerError
    from r_cli.workflows import WorkflowError, load_workflow, validate_workflow_tools

    try:
        definition = load_workflow(path)
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            validate_workflow_tools(definition)
    except (WorkflowError, ToolRunnerError) as exc:
        raise click.ClickException(str(exc)) from exc

    result = {
        "valid": True,
        "name": definition.name,
        "version": definition.version,
        "steps": len(definition.steps),
    }
    if as_json:
        click.echo(json.dumps(result, indent=2))
    else:
        console.print(
            f"[green]Valid workflow[/green] {definition.name} ({len(definition.steps)} steps)"
        )


@workflow.command("run")
@click.argument("path", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--var", "values", multiple=True, metavar="KEY=VALUE", help="Workflow variable")
@click.option("--dry-run", is_flag=True, help="Render and plan without executing tools")
@click.option("--yes", is_flag=True, help="Approve risky actions without prompting")
@click.option("--json", "as_json", is_flag=True, help="Output machine-readable JSON")
@click.pass_context
def workflow_run(
    ctx,
    path: Path,
    values: tuple[str, ...],
    dry_run: bool,
    yes: bool,
    as_json: bool,
):
    """Execute a workflow with dependency-aware tool calls."""
    from r_cli.tool_runner import ToolRunnerError, parse_key_value
    from r_cli.workflows import WorkflowError, load_workflow, run_workflow

    try:
        variables = dict(parse_key_value(value) for value in values)
        definition = load_workflow(path)
        auto_approve = yes or ctx.obj.get("yes", False)
        callback = approval_prompt if sys.stdin.isatty() and not auto_approve else None
        result = run_workflow(
            definition,
            variables=variables,
            approval_callback=callback,
            auto_approve=auto_approve,
            dry_run=dry_run,
        )
    except (WorkflowError, ToolRunnerError) as exc:
        raise click.ClickException(str(exc)) from exc

    payload = result.to_dict()
    if as_json:
        click.echo(json.dumps(payload, indent=2, default=str))
    else:
        table = Table(title=f"Workflow: {result.name}")
        table.add_column("Step", style="cyan")
        table.add_column("Tool")
        table.add_column("Status")
        table.add_column("Attempts", justify="right")
        table.add_column("Duration", justify="right")
        for step in result.steps:
            table.add_row(
                step.id,
                step.target,
                step.status,
                str(step.attempts or "-"),
                f"{step.duration_ms:.1f} ms",
            )
        console.print(table)
        console.print(f"Status: [bold]{result.status}[/bold] ({result.duration_ms:.1f} ms)")

    if result.status == "error":
        ctx.exit(1)


@workflow.command("init")
@click.argument("path", default="r-workflow.yaml", type=click.Path(path_type=Path))
@click.option("--force", is_flag=True, help="Overwrite an existing file")
def workflow_init(path: Path, force: bool):
    """Create an example workflow."""
    if path.exists() and not force:
        raise click.ClickException(f"File already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        """version: 1
name: calculation-report

variables:
  expression: 6 * 7
  multiplier: 2

steps:
  - id: calculate
    uses: math.calculate
    with:
      expression: "{{ vars.expression }}"

  - id: scale
    uses: math.calculate
    depends_on: [calculate]
    with:
      expression: "{{ steps.calculate.result }} * {{ vars.multiplier }}"
""",
        encoding="utf-8",
    )
    console.print(f"[green]Created workflow {path}[/green]")


@cli.group("mcp")
def mcp_command():
    """Manage Model Context Protocol servers and tools."""


@mcp_command.command("add")
@click.argument("name")
@click.option("--command", "server_command", required=True, help="Server executable")
@click.option("--arg", "server_args", multiple=True, help="Server command argument")
@click.option("--env", "environment", multiple=True, metavar="KEY=VALUE")
@click.option("--cwd", type=click.Path(file_okay=False, path_type=str))
@click.option("--timeout", default=30.0, type=click.FloatRange(min=0.1))
def mcp_add(
    name: str,
    server_command: str,
    server_args: tuple[str, ...],
    environment: tuple[str, ...],
    cwd: Optional[str],
    timeout: float,
):
    """Register a local stdio MCP server."""
    from r_cli.core.config import MCPServerConfig
    from r_cli.tool_runner import ToolRunnerError, parse_key_value

    env = {}
    try:
        for item in environment:
            key, value = parse_key_value(item)
            env[key] = str(value)
    except ToolRunnerError as exc:
        raise click.ClickException(str(exc)) from exc

    config = Config.load()
    config.mcp.servers[name] = MCPServerConfig(
        command=server_command,
        args=list(server_args),
        env=env,
        cwd=cwd,
        timeout_seconds=timeout,
    )
    config.save(get_config_path())
    console.print(f"[green]Registered MCP server: {name}[/green]")


@mcp_command.command("remove")
@click.argument("name")
def mcp_remove(name: str):
    """Remove an MCP server from configuration."""
    config = Config.load()
    if name not in config.mcp.servers:
        raise click.ClickException(f"Unknown MCP server: {name}")
    del config.mcp.servers[name]
    config.save(get_config_path())
    console.print(f"[green]Removed MCP server: {name}[/green]")


@mcp_command.command("list")
@click.option("--json", "as_json", is_flag=True, help="Output machine-readable JSON")
def mcp_list(as_json: bool):
    """List configured MCP servers."""
    config = Config.load()
    servers = {name: server.model_dump() for name, server in sorted(config.mcp.servers.items())}
    if as_json:
        click.echo(json.dumps(servers, indent=2))
        return

    table = Table(title=f"MCP servers ({len(servers)})")
    table.add_column("Name", style="cyan")
    table.add_column("Command")
    table.add_column("Enabled")
    table.add_column("Timeout")
    for name, server in servers.items():
        command = " ".join([server["command"], *server["args"]])
        table.add_row(name, command, str(server["enabled"]), str(server["timeout_seconds"]))
    console.print(table)


@mcp_command.command("tools")
@click.argument("server_name")
@click.option("--json", "as_json", is_flag=True, help="Output machine-readable JSON")
def mcp_tools(server_name: str, as_json: bool):
    """Discover tools exposed by an MCP server."""
    from r_cli.mcp_client import MCPClient, MCPError

    try:
        tools = MCPClient().list_tools(server_name)
    except MCPError as exc:
        raise click.ClickException(str(exc)) from exc

    payload = [
        {
            "name": tool.name,
            "description": tool.description,
            "input_schema": tool.input_schema,
        }
        for tool in tools
    ]
    if as_json:
        click.echo(json.dumps(payload, indent=2))
        return

    table = Table(title=f"{server_name} MCP tools ({len(payload)})")
    table.add_column("Tool", style="cyan")
    table.add_column("Description")
    for tool in payload:
        table.add_row(tool["name"], tool["description"])
    console.print(table)


@mcp_command.command("call")
@click.argument("server_name")
@click.argument("tool_name")
@click.option("--arg", "values", multiple=True, metavar="KEY=VALUE")
@click.option("--params", help="Tool arguments as a JSON object")
@click.option("--json", "as_json", is_flag=True, help="Output machine-readable JSON")
@click.option("--yes", is_flag=True, help="Approve this action without prompting")
@click.pass_context
def mcp_call(
    ctx,
    server_name: str,
    tool_name: str,
    values: tuple[str, ...],
    params: Optional[str],
    as_json: bool,
    yes: bool,
):
    """Call a tool on a configured MCP server."""
    from r_cli.core.permissions import PermissionDeniedError
    from r_cli.mcp_client import MCPClient, MCPError
    from r_cli.tool_runner import ToolRunnerError, build_arguments, normalize_result

    try:
        arguments = build_arguments(params, values)
        auto_approve = yes or ctx.obj.get("yes", False)
        callback = approval_prompt if sys.stdin.isatty() and not auto_approve else None
        result = MCPClient().call_tool(
            server_name,
            tool_name,
            arguments,
            approval_callback=callback,
            auto_approve=auto_approve,
        )
    except (MCPError, ToolRunnerError, PermissionDeniedError) as exc:
        raise click.ClickException(str(exc)) from exc

    if as_json:
        click.echo(
            json.dumps(
                {
                    "server": server_name,
                    "tool": tool_name,
                    "arguments": arguments,
                    "result": normalize_result(result),
                },
                indent=2,
                default=str,
            )
        )
    else:
        console.print(result)


@cli.command()
@click.argument("file_path", required=True)
@click.option("--style", "-s", default="concise", help="Style: concise, detailed, bullets")
def resume(file_path: str, style: str):
    """Summarize a document."""
    agent = create_agent(selected_skills=["resume"])

    result = agent.run_skill_directly("resume", file=file_path, style=style)
    console.print(result)


@cli.command()
@click.argument("query", required=True)
@click.option("--csv", "-c", help="CSV file to query")
def sql(query: str, csv: Optional[str]):
    """Execute a SQL query."""
    agent = create_agent(selected_skills=["sql"])

    result = agent.run_skill_directly("sql", query=query, csv=csv)
    console.print(result)


@cli.command()
@click.argument("code", required=True)
@click.option("--filename", "-f", default="script.py", help="File name")
@click.option("--run", "-r", is_flag=True, help="Run after creating")
@click.pass_context
def code(ctx, code: str, filename: str, run: bool):
    """Generate code."""
    agent = create_agent(
        selected_skills=["code"],
        auto_approve=ctx.obj.get("yes", False),
    )

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
    agent = create_agent(selected_skills=["fs"])

    result = agent.run_skill_directly("fs", action="list", path=path, pattern=pattern)
    console.print(result)


@cli.command()
@click.option("--search", "-s", help="Filter skills by name or description")
@click.option("--json", "as_json", is_flag=True, help="Output machine-readable JSON")
def skills(search: Optional[str], as_json: bool):
    """List available skills."""
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        agent = create_agent()
    skill_items = [
        {
            "name": name,
            "description": skill.description,
            "tools": [tool.name for tool in skill.get_tools()],
        }
        for name, skill in sorted(agent.skills.items())
        if not search
        or search.lower() in name.lower()
        or search.lower() in skill.description.lower()
    ]

    if as_json:
        click.echo(json.dumps(skill_items, indent=2))
        return

    table = Table(title=f"Available Skills ({len(skill_items)})")
    table.add_column("Skill", style="cyan")
    table.add_column("Description")
    table.add_column("Tools", justify="right")
    for item in skill_items:
        table.add_row(item["name"], item["description"], str(len(item["tools"])))
    console.print(table)


def show_config(as_json: bool = False):
    """Show current configuration (helper function)."""
    cfg = Config.load(get_config_path())
    config_data = cfg.model_dump()

    if as_json:
        click.echo(json.dumps(config_data, indent=2))
        return

    console.print("[bold]R CLI Configuration[/bold]\n")
    console.print(f"Config file: {get_config_path()}")
    console.print(f"LLM Provider: {cfg.llm.provider}")
    console.print(f"LLM URL: {cfg.llm.base_url}")
    console.print(f"Model: {cfg.llm.model}")
    console.print(f"Theme: {cfg.ui.theme}")
    console.print("\nDirectories:")
    console.print(f"  Home: {cfg.home_dir}")
    console.print(f"  Output: {cfg.output_dir}")
    console.print(f"  RAG DB: {cfg.rag.persist_directory}")


@cli.command("config")
@click.option("--json", "as_json", is_flag=True, help="Output machine-readable JSON")
@click.option("--path", "show_path", is_flag=True, help="Print the configuration file path")
def config_command(as_json: bool, show_path: bool):
    """Show current configuration."""
    if show_path:
        click.echo(get_config_path())
        return
    show_config(as_json=as_json)


@cli.command()
@click.option("--json", "as_json", is_flag=True, help="Output machine-readable JSON")
def doctor(as_json: bool):
    """Diagnose configuration, storage, and local LLM backends."""
    from r_cli.diagnostics import collect_diagnostics, diagnostics_status

    checks = collect_diagnostics(get_config_path())
    overall = diagnostics_status(checks)

    if as_json:
        click.echo(
            json.dumps(
                {
                    "status": overall,
                    "checks": [check.to_dict() for check in checks],
                },
                indent=2,
            )
        )
        return

    symbols = {
        "ok": "[green]OK[/green]",
        "warning": "[yellow]WARN[/yellow]",
        "error": "[red]FAIL[/red]",
    }
    table = Table(show_header=True, header_style="bold")
    table.add_column("Status", width=8)
    table.add_column("Check")
    table.add_column("Details")
    for check in checks:
        table.add_row(symbols[check.status], check.name, check.message)
        if check.hint:
            table.add_row("", "", f"[dim]{check.hint}[/dim]")

    console.print(Panel(table, title=f"R CLI doctor: {overall.upper()}"))


cli.add_command(doctor, "status")


@cli.command()
@click.argument("shell", type=click.Choice(["bash", "zsh", "fish"]))
def completion(shell: str):
    """Generate a shell completion script."""
    completion_class = get_completion_class(shell)
    if completion_class is None:
        raise click.ClickException(f"Shell completion is not available for {shell}")

    script = completion_class(cli, {}, "r", "_R_COMPLETE").source()
    click.echo(script)


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


def interactive_mode(
    theme: str = "ps2",
    show_animation: bool = True,
    use_streaming: bool = True,
    skills_mode: str | None = None,
    auto_approve: bool = False,
):
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
    agent = create_agent(config, selected_skills, auto_approve=auto_approve)

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


def single_query(
    message: str,
    theme: str = "ps2",
    show_animation: bool = True,
    skills_mode: str | None = None,
    use_streaming: bool = True,
    auto_approve: bool = False,
):
    """Execute a single query and exit."""
    term = Terminal(theme=theme)

    # Configure skills mode
    config = Config.load()
    if skills_mode:
        if skills_mode == "full":
            config.skills.mode = "blacklist"
        else:
            config.skills.mode = skills_mode

    agent = create_agent(config, auto_approve=auto_approve)

    if use_streaming and not agent.tools:
        term.print_stream_start()
        for chunk in agent.run_stream(message):
            term.print_stream_chunk(chunk)
        term.print_stream_end()
        return

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
