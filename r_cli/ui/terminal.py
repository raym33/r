"""
Interfaz de terminal principal para R CLI.

Maneja:
- Rendering de respuestas con formato
- Paneles de información
- Tablas de skills/comandos
- Historial de conversación
"""

from typing import Optional
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.markdown import Markdown
from rich.syntax import Syntax
from rich.text import Text
from rich.tree import Tree
from rich.progress import Progress, SpinnerColumn, TextColumn

from r_cli.ui.themes import Theme, get_theme


class Terminal:
    """
    Interfaz de terminal rica para R CLI.

    Uso:
    ```python
    term = Terminal(theme="ps2")
    term.print_welcome()
    term.print_response("Hola, soy R!")
    term.print_skill_list(skills)
    ```
    """

    def __init__(self, theme: str = "ps2"):
        self.console = Console()
        self.theme = get_theme(theme)

    def print(self, message: str, style: Optional[str] = None):
        """Imprime un mensaje simple."""
        self.console.print(message, style=style or self.theme.secondary)

    def print_welcome(self):
        """Muestra banner de bienvenida."""
        banner = """
╔═══════════════════════════════════════════════════════════════╗
║                                                               ║
║     ██████╗        ██████╗██╗     ██╗                        ║
║     ██╔══██╗      ██╔════╝██║     ██║                        ║
║     ██████╔╝█████╗██║     ██║     ██║                        ║
║     ██╔══██╗╚════╝██║     ██║     ██║                        ║
║     ██║  ██║      ╚██████╗███████╗██║                        ║
║     ╚═╝  ╚═╝       ╚═════╝╚══════╝╚═╝                        ║
║                                                               ║
║     Local AI Operating System                                 ║
║     100% Privado · 100% Offline · 100% Tuyo                  ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
        """

        self.console.print(banner, style=self.theme.primary)
        self.console.print()

    def print_status(self, llm_connected: bool, skills_count: int):
        """Muestra estado del sistema."""
        status = Table(show_header=False, box=None, padding=(0, 2))
        status.add_column()
        status.add_column()

        # LLM status
        if llm_connected:
            status.add_row(
                f"[{self.theme.success}]{self.theme.success_symbol}[/] LLM",
                "[green]Conectado[/green]"
            )
        else:
            status.add_row(
                f"[{self.theme.error}]{self.theme.error_symbol}[/] LLM",
                "[red]Desconectado[/red]"
            )

        status.add_row(
            f"[{self.theme.secondary}]◈[/] Skills",
            f"[{self.theme.secondary}]{skills_count} disponibles[/]"
        )

        self.console.print(Panel(status, title="Estado", border_style=self.theme.dim))

    def print_response(self, response: str, title: str = "R"):
        """Muestra respuesta del agente con formato."""
        # Detectar si es markdown
        if any(marker in response for marker in ["```", "##", "- ", "**"]):
            content = Markdown(response)
        else:
            content = response

        self.console.print(Panel(
            content,
            title=f"[{self.theme.primary}]{title}[/]",
            border_style=self.theme.accent,
            padding=(1, 2),
        ))

    def print_user_input(self, message: str):
        """Muestra input del usuario."""
        self.console.print(
            f"[{self.theme.dim}]Tú:[/] [{self.theme.secondary}]{message}[/]"
        )

    def print_thinking(self, message: str = "Pensando"):
        """Muestra indicador de "pensando"."""
        return Progress(
            SpinnerColumn(spinner_name="dots", style=self.theme.accent),
            TextColumn(f"[{self.theme.dim}]{message}...[/]"),
            console=self.console,
            transient=True,
        )

    def print_skill_list(self, skills: dict):
        """Muestra tabla de skills disponibles."""
        table = Table(
            title="Skills Disponibles",
            show_header=True,
            header_style=self.theme.primary,
            border_style=self.theme.dim,
        )

        table.add_column("Skill", style=self.theme.accent)
        table.add_column("Descripción", style=self.theme.secondary)
        table.add_column("Comando", style=self.theme.dim)

        for name, skill in skills.items():
            table.add_row(
                name,
                skill.description,
                f"r {name} <args>",
            )

        self.console.print(table)

    def print_tool_call(self, tool_name: str, args: dict):
        """Muestra una llamada a herramienta."""
        args_str = ", ".join(f"{k}={v!r}" for k, v in args.items())
        self.console.print(
            f"[{self.theme.dim}]  {self.theme.thinking_symbol} {tool_name}({args_str})[/]"
        )

    def print_tool_result(self, result: str):
        """Muestra resultado de herramienta."""
        # Truncar si es muy largo
        if len(result) > 500:
            result = result[:500] + "..."

        self.console.print(
            Panel(
                result,
                title="Resultado",
                border_style=self.theme.dim,
                padding=(0, 1),
            )
        )

    def print_error(self, message: str):
        """Muestra un error."""
        self.console.print(
            f"[{self.theme.error}]{self.theme.error_symbol} Error: {message}[/]"
        )

    def print_success(self, message: str):
        """Muestra un mensaje de éxito."""
        self.console.print(
            f"[{self.theme.success}]{self.theme.success_symbol} {message}[/]"
        )

    def print_warning(self, message: str):
        """Muestra una advertencia."""
        self.console.print(
            f"[{self.theme.warning}]⚠ {message}[/]"
        )

    def print_code(self, code: str, language: str = "python"):
        """Muestra código con syntax highlighting."""
        syntax = Syntax(code, language, theme="monokai", line_numbers=True)
        self.console.print(syntax)

    def print_file_tree(self, path: str, files: list[str]):
        """Muestra árbol de archivos."""
        tree = Tree(f"📁 {path}", style=self.theme.accent)

        for f in files[:20]:  # Limitar
            if f.endswith("/"):
                tree.add(f"📁 {f}", style=self.theme.secondary)
            else:
                tree.add(f"📄 {f}", style=self.theme.dim)

        if len(files) > 20:
            tree.add(f"... y {len(files) - 20} más", style=self.theme.dim)

        self.console.print(tree)

    def get_input(self, prompt: str = "") -> str:
        """Obtiene input del usuario."""
        symbol = self.theme.prompt_symbol
        return self.console.input(f"[{self.theme.primary}]{symbol}[/] {prompt}")

    def clear(self):
        """Limpia la pantalla."""
        self.console.clear()

    def print_help(self):
        """Muestra ayuda general."""
        help_text = """
# R CLI - Comandos

## Chat
Simplemente escribe tu mensaje para chatear con R.

## Skills (comandos directos)
- `r pdf "contenido"` - Genera un PDF
- `r code script.py` - Crea código
- `r sql "query"` - Ejecuta SQL
- `r resume archivo.pdf` - Resume documento
- `r fs list` - Lista archivos

## Control
- `/help` - Muestra esta ayuda
- `/skills` - Lista skills disponibles
- `/clear` - Limpia pantalla
- `/config` - Muestra configuración
- `/exit` - Salir

## Ejemplos
```
> Genera un informe PDF sobre Python
> Resume este documento: informe.pdf
> SELECT * FROM ventas WHERE año = 2024
> Crea una función que ordene una lista
```
        """

        self.console.print(Markdown(help_text))
