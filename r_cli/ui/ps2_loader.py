"""
Animación de loading estilo PlayStation 2.

Renderiza en la terminal:
- Partículas flotantes
- Esfera/orbe central pulsante
- Efecto de código matrix opcional
- Todo en ASCII/Unicode para máxima compatibilidad
"""

import time
import random
import math
from typing import Optional
from rich.console import Console
from rich.live import Live
from rich.text import Text
from rich.panel import Panel
from rich.align import Align


class PS2Loader:
    """
    Animación de carga inspirada en PS2.

    Uso:
    ```python
    loader = PS2Loader()
    with loader.start("Procesando..."):
        # Tu código aquí
        time.sleep(2)
    ```
    """

    # Frames de la esfera central (ASCII art)
    SPHERE_FRAMES = [
        [
            "    ·····    ",
            "  ·········  ",
            " ··· ◉ ···  ",
            "  ·········  ",
            "    ·····    ",
        ],
        [
            "    ·····    ",
            "  ···◈···   ",
            " ···   ···  ",
            "  ···◈···   ",
            "    ·····    ",
        ],
        [
            "   ·······   ",
            "  ·· ◉◉ ··  ",
            " ··     ··  ",
            "  ·· ◉◉ ··  ",
            "   ·······   ",
        ],
        [
            "    ◈···◈    ",
            "  ·········  ",
            " ···     ··· ",
            "  ·········  ",
            "    ◈···◈    ",
        ],
    ]

    # Caracteres para partículas
    PARTICLES = ["·", "∙", "•", "◦", "○", "◎", "◉", "●", "◈", "◇"]

    # Caracteres para efecto matrix
    MATRIX_CHARS = "ﾊﾐﾋｰｳｼﾅﾓﾆｻﾜﾂｵﾘｱﾎﾃﾏｹﾒｴｶｷﾑﾕﾗｾﾈｽﾀﾇﾍ01234567890"

    def __init__(
        self,
        style: str = "ps2",
        width: int = 50,
        height: int = 12,
        color: str = "blue",
    ):
        self.style = style
        self.width = width
        self.height = height
        self.color = color
        self.console = Console()

        # Estado de animación
        self.frame = 0
        self.particles = self._init_particles()
        self.matrix_cols = self._init_matrix() if style == "matrix" else []
        self._running = False

    def _init_particles(self, count: int = 30) -> list[dict]:
        """Inicializa partículas flotantes."""
        particles = []
        for _ in range(count):
            particles.append(
                {
                    "x": random.uniform(0, self.width),
                    "y": random.uniform(0, self.height),
                    "vx": random.uniform(-0.3, 0.3),
                    "vy": random.uniform(-0.2, 0.2),
                    "char": random.choice(self.PARTICLES[:5]),
                    "brightness": random.uniform(0.3, 1.0),
                }
            )
        return particles

    def _init_matrix(self, cols: int = 20) -> list[dict]:
        """Inicializa columnas para efecto matrix."""
        return [
            {
                "x": i * 3,
                "y": random.randint(-10, 0),
                "speed": random.uniform(0.5, 2),
                "chars": [random.choice(self.MATRIX_CHARS) for _ in range(8)],
            }
            for i in range(cols)
        ]

    def _update_particles(self):
        """Actualiza posición de partículas."""
        for p in self.particles:
            # Mover
            p["x"] += p["vx"]
            p["y"] += p["vy"]

            # Efecto de atracción hacia el centro
            cx, cy = self.width / 2, self.height / 2
            dx, dy = cx - p["x"], cy - p["y"]
            dist = math.sqrt(dx * dx + dy * dy)

            if dist > 5:
                p["vx"] += dx * 0.001
                p["vy"] += dy * 0.001

            # Wrap around
            if p["x"] < 0:
                p["x"] = self.width
            elif p["x"] > self.width:
                p["x"] = 0
            if p["y"] < 0:
                p["y"] = self.height
            elif p["y"] > self.height:
                p["y"] = 0

            # Cambiar brillo ocasionalmente
            if random.random() < 0.1:
                p["brightness"] = random.uniform(0.3, 1.0)

    def _update_matrix(self):
        """Actualiza efecto matrix."""
        for col in self.matrix_cols:
            col["y"] += col["speed"]
            if col["y"] > self.height + 10:
                col["y"] = random.randint(-15, -5)
                col["chars"] = [random.choice(self.MATRIX_CHARS) for _ in range(8)]

    def _render_frame(self, message: str = "") -> Text:
        """Renderiza un frame de la animación."""
        # Canvas vacío
        canvas = [[" " for _ in range(self.width)] for _ in range(self.height)]

        if self.style == "matrix":
            # Renderizar efecto matrix
            for col in self.matrix_cols:
                x = int(col["x"]) % self.width
                for i, char in enumerate(col["chars"]):
                    y = int(col["y"]) + i
                    if 0 <= y < self.height:
                        canvas[y][x] = char
        else:
            # Renderizar partículas
            for p in self.particles:
                x, y = int(p["x"]), int(p["y"])
                if 0 <= x < self.width and 0 <= y < self.height:
                    canvas[y][x] = p["char"]

            # Renderizar esfera central
            sphere = self.SPHERE_FRAMES[self.frame % len(self.SPHERE_FRAMES)]
            sx = (self.width - len(sphere[0])) // 2
            sy = (self.height - len(sphere)) // 2

            for i, row in enumerate(sphere):
                for j, char in enumerate(row):
                    if char != " ":
                        x, y = sx + j, sy + i
                        if 0 <= x < self.width and 0 <= y < self.height:
                            canvas[y][x] = char

        # Convertir a Text con colores
        text = Text()

        for row in canvas:
            line = "".join(row)
            if self.style == "matrix":
                text.append(line + "\n", style="green")
            else:
                text.append(line + "\n", style=self.color)

        # Agregar mensaje
        if message:
            text.append("\n")
            text.append(f"  {message}", style=f"bold {self.color}")

        # Agregar indicador de progreso
        dots = "." * ((self.frame % 4) + 1)
        text.append(dots.ljust(4), style=f"dim {self.color}")

        return text

    def start(self, message: str = "Cargando"):
        """Context manager para mostrar la animación."""
        return _PS2LoaderContext(self, message)

    def show_once(self, message: str = "", duration: float = 2.0):
        """Muestra la animación por un tiempo determinado."""
        with Live(
            self._render_frame(message),
            console=self.console,
            refresh_per_second=10,
            transient=True,
        ) as live:
            start = time.time()
            while time.time() - start < duration:
                self.frame += 1
                self._update_particles()
                if self.style == "matrix":
                    self._update_matrix()
                live.update(self._render_frame(message))
                time.sleep(0.1)


class _PS2LoaderContext:
    """Context manager para PS2Loader."""

    def __init__(self, loader: PS2Loader, message: str):
        self.loader = loader
        self.message = message
        self.live = None

    def __enter__(self):
        self.live = Live(
            self.loader._render_frame(self.message),
            console=self.loader.console,
            refresh_per_second=10,
            transient=True,
        )
        self.live.__enter__()
        self._start_animation()
        return self

    def __exit__(self, *args):
        self.loader._running = False
        if self.live:
            self.live.__exit__(*args)

    def _start_animation(self):
        """Inicia el loop de animación en background."""
        import threading

        self.loader._running = True

        def animate():
            while self.loader._running:
                self.loader.frame += 1
                self.loader._update_particles()
                if self.loader.style == "matrix":
                    self.loader._update_matrix()
                if self.live:
                    self.live.update(self.loader._render_frame(self.message))
                time.sleep(0.1)

        thread = threading.Thread(target=animate, daemon=True)
        thread.start()

    def update_message(self, message: str):
        """Actualiza el mensaje mostrado."""
        self.message = message


def demo():
    """Demo de las animaciones."""
    console = Console()

    console.print("\n[bold blue]R CLI - Demo de Animaciones[/bold blue]\n")

    # Demo PS2
    console.print("[cyan]Estilo PS2:[/cyan]")
    loader = PS2Loader(style="ps2", color="blue")
    loader.show_once("Inicializando sistema", duration=3)

    console.print("\n[green]Estilo Matrix:[/green]")
    loader = PS2Loader(style="matrix", color="green")
    loader.show_once("Conectando a la red", duration=3)

    console.print("\n[bold green]✓ Demo completada[/bold green]\n")


if __name__ == "__main__":
    demo()
