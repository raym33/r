"""
R OS Simulator - Main Application.

Android-like TUI built with Textual.
"""

import asyncio
from datetime import datetime
from typing import Optional

from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Grid, Horizontal, Vertical
from textual.reactive import reactive
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Label, Static

# ============================================================================
# Theme Colors
# ============================================================================

THEMES = {
    "material": {
        "background": "#121212",
        "surface": "#1e1e1e",
        "primary": "#bb86fc",
        "secondary": "#03dac6",
        "accent": "#cf6679",
        "text": "#ffffff",
        "text_dim": "#888888",
    },
    "amoled": {
        "background": "#000000",
        "surface": "#0a0a0a",
        "primary": "#00ff88",
        "secondary": "#00d4ff",
        "accent": "#ff0080",
        "text": "#ffffff",
        "text_dim": "#666666",
    },
    "light": {
        "background": "#f5f5f5",
        "surface": "#ffffff",
        "primary": "#6200ee",
        "secondary": "#03dac6",
        "accent": "#b00020",
        "text": "#000000",
        "text_dim": "#666666",
    },
}

# ============================================================================
# App Definitions
# ============================================================================

APPS = [
    # Row 1 - Communication
    {"id": "sms", "icon": "💬", "name": "Messages", "skill": "android", "action": "sms"},
    {"id": "phone", "icon": "📞", "name": "Phone", "skill": "android", "action": "call"},
    {"id": "email", "icon": "📧", "name": "Email", "skill": "email", "action": "send"},
    {"id": "browser", "icon": "🌐", "name": "Browser", "skill": "web", "action": "fetch"},
    # Row 2 - Media
    {"id": "camera", "icon": "📷", "name": "Camera", "skill": "android", "action": "photo"},
    {"id": "gallery", "icon": "🖼️", "name": "Gallery", "skill": "image", "action": "info"},
    {"id": "music", "icon": "🎵", "name": "Music", "skill": "audio", "action": "info"},
    {"id": "video", "icon": "🎬", "name": "Video", "skill": "video", "action": "info"},
    # Row 3 - Utilities
    {"id": "files", "icon": "📁", "name": "Files", "skill": "fs", "action": "list"},
    {"id": "calendar", "icon": "📅", "name": "Calendar", "skill": "calendar", "action": "list"},
    {"id": "clock", "icon": "⏰", "name": "Clock", "skill": "datetime", "action": "now"},
    {"id": "calculator", "icon": "🔢", "name": "Calculator", "skill": "math", "action": "eval"},
    # Row 4 - AI & Tools
    {"id": "r_chat", "icon": "🤖", "name": "R Chat", "skill": "chat", "action": "start"},
    {"id": "voice", "icon": "🎤", "name": "Voice", "skill": "voice", "action": "record"},
    {"id": "translate", "icon": "🌍", "name": "Translate", "skill": "translate", "action": "text"},
    {"id": "notes", "icon": "📝", "name": "Notes", "skill": "fs", "action": "edit"},
    # Row 5 - System
    {"id": "settings", "icon": "⚙️", "name": "Settings", "skill": "system", "action": "settings"},
    {"id": "wifi", "icon": "📶", "name": "WiFi", "skill": "wifi", "action": "scan"},
    {"id": "bluetooth", "icon": "🔵", "name": "Bluetooth", "skill": "bluetooth", "action": "scan"},
    {"id": "battery", "icon": "🔋", "name": "Battery", "skill": "power", "action": "battery"},
    # Row 6 - Hardware (Pi)
    {"id": "gpio", "icon": "💡", "name": "GPIO", "skill": "gpio", "action": "status"},
    {"id": "terminal", "icon": "💻", "name": "Terminal", "skill": "bash", "action": "shell"},
    {"id": "network", "icon": "🔌", "name": "Network", "skill": "network", "action": "info"},
    {"id": "system", "icon": "📊", "name": "System", "skill": "system", "action": "info"},
]

# ============================================================================
# Widgets
# ============================================================================


class StatusBar(Static):
    """Android-style status bar."""

    time = reactive("00:00")
    battery = reactive(100)
    wifi_connected = reactive(True)
    signal = reactive(4)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._update_task: Optional[asyncio.Task] = None

    def compose(self) -> ComposeResult:
        yield Static("", id="status-left")
        yield Static("", id="status-center")
        yield Static("", id="status-right")

    def on_mount(self) -> None:
        self._update_task = asyncio.create_task(self._update_loop())
        self._refresh_display()

    async def _update_loop(self) -> None:
        while True:
            self.time = datetime.now().strftime("%H:%M")
            await asyncio.sleep(1)

    def watch_time(self, value: str) -> None:
        self._refresh_display()

    def _refresh_display(self) -> None:
        # Signal bars
        signal_icons = ["▁", "▂", "▄", "█"]
        signal_str = "".join(signal_icons[: self.signal])

        # WiFi icon
        wifi_icon = "📶" if self.wifi_connected else "📵"

        # Battery icon
        if self.battery > 50:
            batt_icon = "🔋"
        else:
            batt_icon = "🪫"

        left = self.query_one("#status-left", Static)
        center = self.query_one("#status-center", Static)
        right = self.query_one("#status-right", Static)

        left.update(f" {signal_str} {wifi_icon} R OS")
        center.update(self.time)
        right.update(f"{batt_icon} {self.battery}% ")


class AppIcon(Button):
    """Single app icon in the launcher."""

    def __init__(self, app_data: dict, **kwargs):
        self.app_data = app_data
        super().__init__(
            f"{app_data['icon']}\n{app_data['name']}",
            id=f"app-{app_data['id']}",
            **kwargs,
        )


class AppGrid(Grid):
    """Grid of app icons."""

    def compose(self) -> ComposeResult:
        for app in APPS:
            yield AppIcon(app)


class NavigationBar(Horizontal):
    """Android-style navigation bar."""

    def compose(self) -> ComposeResult:
        yield Button("◀", id="nav-back", classes="nav-btn")
        yield Button("●", id="nav-home", classes="nav-btn")
        yield Button("▢", id="nav-recent", classes="nav-btn")


class NotificationPanel(Vertical):
    """Notification/quick settings panel."""

    show_panel = reactive(False)

    def compose(self) -> ComposeResult:
        yield Static("Quick Settings", classes="panel-title")
        yield Horizontal(
            Button("📶 WiFi", id="qs-wifi"),
            Button("🔵 BT", id="qs-bt"),
            Button("🔦 Flash", id="qs-flash"),
            Button("✈️ Air", id="qs-airplane"),
            classes="quick-settings",
        )
        yield Static("Notifications", classes="panel-title")
        yield Static("No new notifications", id="notifications")


# ============================================================================
# Screens
# ============================================================================


class HomeScreen(Screen):
    """Main home screen with app grid."""

    BINDINGS = [
        Binding("escape", "go_back", "Back"),
        Binding("h", "go_home", "Home"),
        Binding("n", "toggle_notifications", "Notifications"),
        Binding("t", "cycle_theme", "Theme"),
    ]

    CSS = """
    HomeScreen {
        background: $background;
    }

    StatusBar {
        dock: top;
        height: 1;
        background: $surface;
        layout: horizontal;
    }

    StatusBar #status-left {
        width: 1fr;
        text-align: left;
    }

    StatusBar #status-center {
        width: auto;
        text-align: center;
        color: $text;
    }

    StatusBar #status-right {
        width: 1fr;
        text-align: right;
    }

    AppGrid {
        grid-size: 4 6;
        grid-gutter: 1;
        padding: 1 2;
        height: 1fr;
    }

    AppIcon {
        width: 100%;
        height: 100%;
        text-align: center;
        background: $surface;
        border: none;
        padding: 0;
    }

    AppIcon:hover {
        background: $primary 30%;
    }

    AppIcon:focus {
        background: $primary 50%;
        border: none;
    }

    NavigationBar {
        dock: bottom;
        height: 3;
        background: $surface;
        align: center middle;
    }

    .nav-btn {
        width: 10;
        height: 3;
        margin: 0 2;
        background: transparent;
        border: none;
    }

    .nav-btn:hover {
        background: $primary 30%;
    }

    NotificationPanel {
        dock: top;
        height: auto;
        max-height: 50%;
        background: $surface;
        padding: 1;
        display: none;
    }

    NotificationPanel.show {
        display: block;
    }

    .panel-title {
        text-style: bold;
        color: $primary;
        padding: 0 0 1 0;
    }

    .quick-settings {
        height: 3;
        margin-bottom: 1;
    }

    .quick-settings Button {
        margin-right: 1;
    }
    """

    def compose(self) -> ComposeResult:
        yield StatusBar()
        yield NotificationPanel()
        yield AppGrid()
        yield NavigationBar()

    @on(Button.Pressed)
    def handle_button(self, event: Button.Pressed) -> None:
        button_id = event.button.id or ""

        if button_id.startswith("app-"):
            app_id = button_id.replace("app-", "")
            app_data = next((a for a in APPS if a["id"] == app_id), None)
            if app_data:
                self.app.push_screen(AppScreen(app_data))

        elif button_id == "nav-back":
            self.action_go_back()
        elif button_id == "nav-home":
            self.action_go_home()
        elif button_id == "nav-recent":
            self.app.push_screen(RecentAppsScreen())

    def action_go_back(self) -> None:
        if len(self.app.screen_stack) > 1:
            self.app.pop_screen()

    def action_go_home(self) -> None:
        while len(self.app.screen_stack) > 1:
            self.app.pop_screen()

    def action_toggle_notifications(self) -> None:
        panel = self.query_one(NotificationPanel)
        panel.toggle_class("show")

    def action_cycle_theme(self) -> None:
        self.app.cycle_theme()


class AppScreen(Screen):
    """Generic app screen."""

    BINDINGS = [
        Binding("escape", "go_back", "Back"),
        Binding("h", "go_home", "Home"),
    ]

    CSS = """
    AppScreen {
        background: $background;
    }

    .app-header {
        dock: top;
        height: 3;
        background: $primary;
        padding: 1;
    }

    .app-header-title {
        text-style: bold;
        color: $text;
    }

    .app-content {
        padding: 2;
        height: 1fr;
    }

    .app-toolbar {
        dock: bottom;
        height: 3;
        background: $surface;
        align: center middle;
    }
    """

    def __init__(self, app_data: dict, **kwargs):
        super().__init__(**kwargs)
        self.app_data = app_data

    def compose(self) -> ComposeResult:
        yield Horizontal(
            Button("←", id="back-btn"),
            Static(
                f" {self.app_data['icon']} {self.app_data['name']}",
                classes="app-header-title",
            ),
            classes="app-header",
        )
        yield Container(
            Static(f"Skill: {self.app_data['skill']}", classes="info"),
            Static(f"Action: {self.app_data['action']}", classes="info"),
            Static("", id="app-output"),
            Button("Execute", id="execute-btn", variant="primary"),
            classes="app-content",
        )
        yield Horizontal(
            Button("◀", id="nav-back", classes="nav-btn"),
            Button("●", id="nav-home", classes="nav-btn"),
            classes="app-toolbar",
        )

    @on(Button.Pressed, "#back-btn")
    @on(Button.Pressed, "#nav-back")
    def go_back(self) -> None:
        self.app.pop_screen()

    @on(Button.Pressed, "#nav-home")
    def go_home(self) -> None:
        while len(self.app.screen_stack) > 1:
            self.app.pop_screen()

    @on(Button.Pressed, "#execute-btn")
    async def execute_skill(self) -> None:
        output = self.query_one("#app-output", Static)
        output.update("Executing...")

        # Simulate skill execution
        await asyncio.sleep(0.5)

        skill = self.app_data["skill"]
        action = self.app_data["action"]

        # Show result
        result = f"[{skill}.{action}] executed successfully\n\n"
        result += self._get_mock_output()
        output.update(result)

    def _get_mock_output(self) -> str:
        """Get mock output based on skill type."""
        skill = self.app_data["skill"]

        outputs = {
            "system": "CPU: 45%\nRAM: 2.1GB / 4GB\nTemp: 42°C\nUptime: 3h 24m",
            "wifi": "Networks found:\n  • Home_5G (signal: 90%)\n  • Neighbor (signal: 45%)",
            "bluetooth": "Devices:\n  • AirPods Pro (connected)\n  • Mi Band 6 (paired)",
            "gpio": "GPIO Status:\n  • Pin 17: HIGH\n  • Pin 27: LOW\n  • Pin 22: PWM 50%",
            "power": "Battery: 85%\nCharging: Yes\nScreen: 70%",
            "datetime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "network": "IP: 192.168.1.100\nGateway: 192.168.1.1\nDNS: 8.8.8.8",
        }

        return outputs.get(skill, "Operation completed")

    def action_go_back(self) -> None:
        self.app.pop_screen()

    def action_go_home(self) -> None:
        while len(self.app.screen_stack) > 1:
            self.app.pop_screen()


class RecentAppsScreen(Screen):
    """Recent apps screen."""

    BINDINGS = [
        Binding("escape", "go_back", "Back"),
    ]

    CSS = """
    RecentAppsScreen {
        background: $background 80%;
        align: center middle;
    }

    .recent-container {
        width: 80%;
        height: 80%;
        background: $surface;
        padding: 2;
    }

    .recent-title {
        text-style: bold;
        color: $primary;
        text-align: center;
        padding-bottom: 1;
    }

    .recent-item {
        height: 3;
        margin-bottom: 1;
    }
    """

    def compose(self) -> ComposeResult:
        yield Container(
            Static("Recent Apps", classes="recent-title"),
            Static("No recent apps", classes="recent-item"),
            Button("Clear All", id="clear-recent"),
            classes="recent-container",
        )

    def action_go_back(self) -> None:
        self.app.pop_screen()

    @on(Button.Pressed, "#clear-recent")
    def clear_recent(self) -> None:
        self.app.pop_screen()


# ============================================================================
# Main Application
# ============================================================================


class ROSSimulator(App):
    """R OS Android Simulator."""

    TITLE = "R OS"
    SUB_TITLE = "Android Simulator"

    CSS = """
    $background: #121212;
    $surface: #1e1e1e;
    $primary: #bb86fc;
    $secondary: #03dac6;
    $accent: #cf6679;
    $text: #ffffff;
    $text-dim: #888888;
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("t", "cycle_theme", "Theme"),
    ]

    current_theme = reactive("material")

    def __init__(self, theme: str = "material", **kwargs):
        super().__init__(**kwargs)
        self.current_theme = theme

    def on_mount(self) -> None:
        self.push_screen(HomeScreen())

    def cycle_theme(self) -> None:
        themes = list(THEMES.keys())
        idx = themes.index(self.current_theme)
        self.current_theme = themes[(idx + 1) % len(themes)]
        self.notify(f"Theme: {self.current_theme}")

    def action_cycle_theme(self) -> None:
        self.cycle_theme()


# ============================================================================
# Entry Point
# ============================================================================


def run_simulator(theme: str = "material") -> None:
    """Run the R OS simulator."""
    app = ROSSimulator(theme=theme)
    app.run()


if __name__ == "__main__":
    run_simulator()
