"""
R CLI - Punto de entrada principal.

Uso:
    r                    # Inicia modo interactivo
    r "mensaje"          # Chat directo
    r pdf "contenido"    # Ejecuta skill directamente
    r --help             # Muestra ayuda
"""

import sys
import click
from typing import Optional

from rich.console import Console

from r_cli import __version__
from r_cli.core.config import Config
from r_cli.core.agent import Agent
from r_cli.ui.terminal import Terminal
from r_cli.ui.ps2_loader import PS2Loader


console = Console()


def create_agent(config: Optional[Config] = None) -> Agent:
    """Crea y configura el agente."""
    agent = Agent(config)
    agent.load_skills()
    return agent


@click.group(invoke_without_command=True)
@click.option("--version", "-v", is_flag=True, help="Muestra la versión")
@click.option("--theme", "-t", default="ps2", help="Tema visual (ps2, matrix, minimal)")
@click.option("--no-animation", is_flag=True, help="Desactiva animaciones")
@click.pass_context
def cli(ctx, version: bool, theme: str, no_animation: bool):
    """
    R CLI - Tu AI Operating System local.

    100% privado · 100% offline · 100% tuyo

    Ejemplos:
        r                          # Modo interactivo
        r "Explica qué es Python"  # Chat directo
        r pdf "Mi documento"       # Genera PDF
        r sql ventas.csv "SELECT * FROM data"
    """
    ctx.ensure_object(dict)
    ctx.obj["theme"] = theme
    ctx.obj["no_animation"] = no_animation

    if version:
        console.print(f"R CLI v{__version__}")
        sys.exit(0)

    # Si no hay subcomando, iniciar modo interactivo
    if ctx.invoked_subcommand is None:
        interactive_mode(theme, not no_animation)


@cli.command()
@click.argument("message", nargs=-1, required=True)
@click.pass_context
def chat(ctx, message: tuple):
    """Envía un mensaje al agente."""
    theme = ctx.obj.get("theme", "ps2")
    no_animation = ctx.obj.get("no_animation", False)

    msg = " ".join(message)
    single_query(msg, theme, not no_animation)


@cli.command()
@click.argument("content", required=True)
@click.option("--title", "-t", help="Título del documento")
@click.option("--output", "-o", help="Ruta de salida")
@click.option("--template", default="minimal", help="Template: minimal, business, academic")
def pdf(content: str, title: Optional[str], output: Optional[str], template: str):
    """Genera un documento PDF."""
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
@click.option("--style", "-s", default="concise", help="Estilo: concise, detailed, bullets")
def resume(file_path: str, style: str):
    """Resume un documento."""
    agent = create_agent()

    result = agent.run_skill_directly("resume", file=file_path, style=style)
    console.print(result)


@cli.command()
@click.argument("query", required=True)
@click.option("--csv", "-c", help="Archivo CSV a consultar")
def sql(query: str, csv: Optional[str]):
    """Ejecuta una consulta SQL."""
    agent = create_agent()

    result = agent.run_skill_directly("sql", query=query, csv=csv)
    console.print(result)


@cli.command()
@click.argument("code", required=True)
@click.option("--filename", "-f", default="script.py", help="Nombre del archivo")
@click.option("--run", "-r", is_flag=True, help="Ejecutar después de crear")
def code(code: str, filename: str, run: bool):
    """Genera código."""
    agent = create_agent()

    result = agent.run_skill_directly("code", code=code, filename=filename, action="write")
    console.print(result)

    if run and filename.endswith(".py"):
        console.print("\n[dim]Ejecutando...[/dim]\n")
        run_result = agent.run_skill_directly("code", code=code, action="run")
        console.print(run_result)


@cli.command()
@click.argument("path", default=".")
@click.option("--pattern", "-p", help="Patrón de búsqueda (ej: *.py)")
def ls(path: str, pattern: Optional[str]):
    """Lista archivos en un directorio."""
    agent = create_agent()

    result = agent.run_skill_directly("fs", action="list", path=path, pattern=pattern)
    console.print(result)


@cli.command()
def skills():
    """Lista los skills disponibles."""
    term = Terminal()
    agent = create_agent()

    term.print_skill_list(agent.skills)


@cli.command()
def config():
    """Muestra la configuración actual."""
    cfg = Config.load()

    console.print("[bold]Configuración de R CLI[/bold]\n")
    console.print(f"LLM Provider: {cfg.llm.provider}")
    console.print(f"LLM URL: {cfg.llm.base_url}")
    console.print(f"Model: {cfg.llm.model}")
    console.print(f"Theme: {cfg.ui.theme}")
    console.print(f"\nDirectorios:")
    console.print(f"  Home: {cfg.home_dir}")
    console.print(f"  Output: {cfg.output_dir}")
    console.print(f"  RAG DB: {cfg.rag.persist_directory}")


@cli.command()
def demo():
    """Ejecuta demo de animaciones."""
    from r_cli.ui.ps2_loader import demo as ps2_demo

    ps2_demo()


def interactive_mode(theme: str = "ps2", show_animation: bool = True):
    """Modo interactivo principal."""
    term = Terminal(theme=theme)
    config = Config()
    config.ui.theme = theme

    # Mostrar bienvenida
    term.clear()
    term.print_welcome()

    # Animación de carga
    if show_animation:
        loader = PS2Loader(style=theme if theme in ["ps2", "matrix"] else "ps2")
        loader.show_once("Inicializando R CLI", duration=2)

    # Crear agente
    agent = create_agent(config)

    # Verificar conexión LLM
    llm_connected = agent.check_connection()
    term.print_status(llm_connected, len(agent.skills))

    if not llm_connected:
        term.print_warning(
            "No se detectó servidor LLM. Inicia LM Studio u Ollama.\n"
            "Los skills directos (pdf, sql, etc.) funcionarán sin LLM."
        )

    term.print("\nEscribe tu mensaje o /help para ayuda. /exit para salir.\n")

    # Loop principal
    while True:
        try:
            user_input = term.get_input()

            if not user_input.strip():
                continue

            # Comandos especiales
            if user_input.startswith("/"):
                cmd = user_input[1:].lower().strip()

                if cmd in ["exit", "quit", "q"]:
                    term.print_success("¡Hasta luego!")
                    break
                elif cmd == "help":
                    term.print_help()
                elif cmd == "clear":
                    term.clear()
                    term.print_welcome()
                elif cmd == "skills":
                    term.print_skill_list(agent.skills)
                elif cmd == "config":
                    ctx = click.Context(config)
                    ctx.invoke(config)
                elif cmd == "status":
                    llm_connected = agent.check_connection()
                    term.print_status(llm_connected, len(agent.skills))
                else:
                    term.print_error(f"Comando no reconocido: /{cmd}")
                continue

            # Mostrar input del usuario
            term.print_user_input(user_input)

            # Procesar con agente
            with term.print_thinking("Pensando"):
                response = agent.run(user_input)

            # Mostrar respuesta
            term.print_response(response)
            term.print()

        except KeyboardInterrupt:
            term.print("\n")
            term.print_success("¡Hasta luego!")
            break
        except EOFError:
            break
        except Exception as e:
            term.print_error(str(e))


def single_query(message: str, theme: str = "ps2", show_animation: bool = True):
    """Ejecuta una sola consulta y sale."""
    term = Terminal(theme=theme)
    agent = create_agent()

    # Animación breve
    if show_animation:
        loader = PS2Loader(style="ps2")
        with loader.start("Procesando"):
            response = agent.run(message)
    else:
        response = agent.run(message)

    term.print_response(response)


def main():
    """Entry point."""
    cli(obj={})


if __name__ == "__main__":
    main()
