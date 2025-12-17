"""Tests for R OS hardware skills and simulator."""

import tempfile

import pytest

from r_cli.core.config import Config


@pytest.fixture
def temp_dir():
    """Create temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def config(temp_dir):
    """Configuration for tests."""
    cfg = Config()
    cfg.output_dir = temp_dir
    cfg.home_dir = temp_dir
    return cfg


# =============================================================================
# R OS Hardware Skill Import Tests
# =============================================================================


class TestROSSkillImports:
    """Test that R OS hardware skills can be imported."""

    def test_gpio_skill_import(self):
        from r_cli.skills.gpio_skill import GPIOSkill
        assert GPIOSkill is not None

    def test_bluetooth_skill_import(self):
        from r_cli.skills.bluetooth_skill import BluetoothSkill
        assert BluetoothSkill is not None

    def test_wifi_skill_import(self):
        from r_cli.skills.wifi_skill import WiFiSkill
        assert WiFiSkill is not None

    def test_power_skill_import(self):
        from r_cli.skills.power_skill import PowerSkill
        assert PowerSkill is not None

    def test_android_skill_import(self):
        from r_cli.skills.android_skill import AndroidSkill
        assert AndroidSkill is not None


# =============================================================================
# R OS Hardware Skill Instantiation Tests
# =============================================================================


class TestROSSkillInstantiation:
    """Test that R OS skills can be instantiated."""

    def test_gpio_skill(self):
        from r_cli.skills.gpio_skill import GPIOSkill
        skill = GPIOSkill()
        assert skill is not None
        assert skill.name == "gpio"

    def test_bluetooth_skill(self):
        from r_cli.skills.bluetooth_skill import BluetoothSkill
        skill = BluetoothSkill()
        assert skill is not None
        assert skill.name == "bluetooth"

    def test_wifi_skill(self):
        from r_cli.skills.wifi_skill import WiFiSkill
        skill = WiFiSkill()
        assert skill is not None
        assert skill.name == "wifi"

    def test_power_skill(self):
        from r_cli.skills.power_skill import PowerSkill
        skill = PowerSkill()
        assert skill is not None
        assert skill.name == "power"

    def test_android_skill(self):
        from r_cli.skills.android_skill import AndroidSkill
        skill = AndroidSkill()
        assert skill is not None
        assert skill.name == "android"


# =============================================================================
# R OS Hardware Skill Tools Tests
# =============================================================================


class TestROSSkillTools:
    """Test that R OS skills provide tools."""

    def test_gpio_skill_tools(self):
        from r_cli.skills.gpio_skill import GPIOSkill
        skill = GPIOSkill()
        tools = skill.get_tools()
        assert len(tools) > 0

    def test_bluetooth_skill_tools(self):
        from r_cli.skills.bluetooth_skill import BluetoothSkill
        skill = BluetoothSkill()
        tools = skill.get_tools()
        assert len(tools) > 0

    def test_wifi_skill_tools(self):
        from r_cli.skills.wifi_skill import WiFiSkill
        skill = WiFiSkill()
        tools = skill.get_tools()
        assert len(tools) > 0

    def test_power_skill_tools(self):
        from r_cli.skills.power_skill import PowerSkill
        skill = PowerSkill()
        tools = skill.get_tools()
        assert len(tools) > 0

    def test_android_skill_tools(self):
        from r_cli.skills.android_skill import AndroidSkill
        skill = AndroidSkill()
        tools = skill.get_tools()
        assert len(tools) > 0


# =============================================================================
# R OS Simulator Tests
# =============================================================================

# Check if textual is available
try:
    import textual
    HAS_TEXTUAL = True
except ImportError:
    HAS_TEXTUAL = False


@pytest.mark.skipif(not HAS_TEXTUAL, reason="textual not installed")
class TestROSSimulator:
    """Tests for R OS Simulator."""

    def test_import_app(self):
        """Test simulator app can be imported."""
        from r_os.simulator.app import ROSSimulator
        assert ROSSimulator is not None

    def test_import_themes(self):
        """Test themes are defined."""
        from r_os.simulator.app import THEMES
        assert "material" in THEMES
        assert "amoled" in THEMES
        assert "light" in THEMES

    def test_import_apps(self):
        """Test apps are defined."""
        from r_os.simulator.app import APPS
        assert len(APPS) > 0

    def test_app_has_required_fields(self):
        """Test each app has required fields."""
        from r_os.simulator.app import APPS
        for app in APPS:
            assert "id" in app
            assert "icon" in app
            assert "name" in app
            assert "skill" in app

    def test_themes_have_required_colors(self):
        """Test each theme has required colors."""
        from r_os.simulator.app import THEMES
        required_colors = ["background", "surface", "primary", "text"]
        for theme_name, theme in THEMES.items():
            for color in required_colors:
                assert color in theme, f"{theme_name} missing {color}"

    def test_status_bar_widget(self):
        """Test StatusBar widget can be imported."""
        from r_os.simulator.app import StatusBar
        assert StatusBar is not None

    def test_app_icon_widget(self):
        """Test AppIcon widget can be imported."""
        from r_os.simulator.app import AppIcon
        assert AppIcon is not None

    def test_home_screen(self):
        """Test HomeScreen can be imported."""
        from r_os.simulator.app import HomeScreen
        assert HomeScreen is not None

    def test_run_simulator_function(self):
        """Test run_simulator function exists."""
        from r_os.simulator.app import run_simulator
        assert callable(run_simulator)


# =============================================================================
# Voice Interface Tests
# =============================================================================


class TestVoiceInterface:
    """Tests for Voice Interface."""

    def test_import(self):
        """Test voice interface can be imported."""
        from r_cli.core.voice_interface import VoiceInterface
        assert VoiceInterface is not None

    def test_create_voice_interface_import(self):
        """Test create_voice_interface can be imported."""
        from r_cli.core.voice_interface import create_voice_interface
        assert create_voice_interface is not None
