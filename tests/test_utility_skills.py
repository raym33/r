"""Tests for utility skills - verifies imports and tool registration."""

import tempfile
from pathlib import Path

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
# Skill Import Tests
# =============================================================================


class TestSkillImports:
    """Test that all utility skills can be imported."""

    def test_datetime_skill_import(self):
        from r_cli.skills.datetime_skill import DateTimeSkill
        assert DateTimeSkill is not None

    def test_json_skill_import(self):
        from r_cli.skills.json_skill import JSONSkill
        assert JSONSkill is not None

    def test_yaml_skill_import(self):
        from r_cli.skills.yaml_skill import YAMLSkill
        assert YAMLSkill is not None

    def test_text_skill_import(self):
        from r_cli.skills.text_skill import TextSkill
        assert TextSkill is not None

    def test_math_skill_import(self):
        from r_cli.skills.math_skill import MathSkill
        assert MathSkill is not None

    def test_archive_skill_import(self):
        from r_cli.skills.archive_skill import ArchiveSkill
        assert ArchiveSkill is not None

    def test_regex_skill_import(self):
        from r_cli.skills.regex_skill import RegexSkill
        assert RegexSkill is not None

    def test_crypto_skill_import(self):
        from r_cli.skills.crypto_skill import CryptoSkill
        assert CryptoSkill is not None

    def test_csv_skill_import(self):
        from r_cli.skills.csv_skill import CSVSkill
        assert CSVSkill is not None

    def test_diff_skill_import(self):
        from r_cli.skills.diff_skill import DiffSkill
        assert DiffSkill is not None

    def test_git_skill_import(self):
        from r_cli.skills.git_skill import GitSkill
        assert GitSkill is not None


# =============================================================================
# Skill Instantiation Tests
# =============================================================================


class TestSkillInstantiation:
    """Test that skills can be instantiated."""

    def test_datetime_skill(self, config):
        from r_cli.skills.datetime_skill import DateTimeSkill
        skill = DateTimeSkill(config)
        assert skill is not None
        assert skill.name == "datetime"

    def test_json_skill(self, config):
        from r_cli.skills.json_skill import JSONSkill
        skill = JSONSkill(config)
        assert skill is not None
        assert skill.name == "json"

    def test_yaml_skill(self, config):
        from r_cli.skills.yaml_skill import YAMLSkill
        skill = YAMLSkill(config)
        assert skill is not None
        assert skill.name == "yaml"

    def test_text_skill(self, config):
        from r_cli.skills.text_skill import TextSkill
        skill = TextSkill(config)
        assert skill is not None
        assert skill.name == "text"

    def test_math_skill(self, config):
        from r_cli.skills.math_skill import MathSkill
        skill = MathSkill(config)
        assert skill is not None
        assert skill.name == "math"

    def test_archive_skill(self, config):
        from r_cli.skills.archive_skill import ArchiveSkill
        skill = ArchiveSkill(config)
        assert skill is not None
        assert skill.name == "archive"

    def test_regex_skill(self, config):
        from r_cli.skills.regex_skill import RegexSkill
        skill = RegexSkill(config)
        assert skill is not None
        assert skill.name == "regex"

    def test_crypto_skill(self, config):
        from r_cli.skills.crypto_skill import CryptoSkill
        skill = CryptoSkill(config)
        assert skill is not None
        assert skill.name == "crypto"

    def test_csv_skill(self, config):
        from r_cli.skills.csv_skill import CSVSkill
        skill = CSVSkill(config)
        assert skill is not None
        assert skill.name == "csv"


# =============================================================================
# Skill Tools Tests
# =============================================================================


class TestSkillTools:
    """Test that skills provide tools."""

    def test_datetime_skill_tools(self, config):
        from r_cli.skills.datetime_skill import DateTimeSkill
        skill = DateTimeSkill(config)
        tools = skill.get_tools()
        assert len(tools) > 0
        assert all(hasattr(t, 'name') for t in tools)

    def test_json_skill_tools(self, config):
        from r_cli.skills.json_skill import JSONSkill
        skill = JSONSkill(config)
        tools = skill.get_tools()
        assert len(tools) > 0

    def test_yaml_skill_tools(self, config):
        from r_cli.skills.yaml_skill import YAMLSkill
        skill = YAMLSkill(config)
        tools = skill.get_tools()
        assert len(tools) > 0

    def test_text_skill_tools(self, config):
        from r_cli.skills.text_skill import TextSkill
        skill = TextSkill(config)
        tools = skill.get_tools()
        assert len(tools) > 0

    def test_math_skill_tools(self, config):
        from r_cli.skills.math_skill import MathSkill
        skill = MathSkill(config)
        tools = skill.get_tools()
        assert len(tools) > 0

    def test_archive_skill_tools(self, config):
        from r_cli.skills.archive_skill import ArchiveSkill
        skill = ArchiveSkill(config)
        tools = skill.get_tools()
        assert len(tools) > 0

    def test_regex_skill_tools(self, config):
        from r_cli.skills.regex_skill import RegexSkill
        skill = RegexSkill(config)
        tools = skill.get_tools()
        assert len(tools) > 0

    def test_crypto_skill_tools(self, config):
        from r_cli.skills.crypto_skill import CryptoSkill
        skill = CryptoSkill(config)
        tools = skill.get_tools()
        assert len(tools) > 0


# =============================================================================
# Functional Tests - DateTimeSkill
# =============================================================================


class TestDateTimeSkillFunctional:
    """Functional tests for DateTimeSkill."""

    def test_datetime_now(self, config):
        from r_cli.skills.datetime_skill import DateTimeSkill
        skill = DateTimeSkill(config)
        result = skill.datetime_now()
        assert len(result) > 0
        assert "20" in result  # Year starts with 20

    def test_datetime_now_with_format(self, config):
        from r_cli.skills.datetime_skill import DateTimeSkill
        skill = DateTimeSkill(config)
        result = skill.datetime_now(format="%Y-%m-%d")
        assert len(result) == 10
        assert "-" in result

    def test_datetime_parse(self, config):
        from r_cli.skills.datetime_skill import DateTimeSkill
        skill = DateTimeSkill(config)
        result = skill.datetime_parse("2024-12-17")
        assert "2024" in result


# =============================================================================
# Functional Tests - JSONSkill
# =============================================================================


class TestJSONSkillFunctional:
    """Functional tests for JSONSkill."""

    def test_json_parse(self, config):
        from r_cli.skills.json_skill import JSONSkill
        skill = JSONSkill(config)
        result = skill.json_parse('{"name": "test", "value": 123}')
        assert "name" in result
        assert "test" in result

    def test_json_format(self, config):
        from r_cli.skills.json_skill import JSONSkill
        skill = JSONSkill(config)
        result = skill.json_format('{"a":1,"b":2}')
        assert "\n" in result  # Pretty printed

    def test_json_to_yaml(self, config):
        from r_cli.skills.json_skill import JSONSkill
        skill = JSONSkill(config)
        result = skill.json_to_yaml('{"name": "test"}')
        assert "name" in result


# =============================================================================
# Functional Tests - TextSkill
# =============================================================================


class TestTextSkillFunctional:
    """Functional tests for TextSkill."""

    def test_text_count(self, config):
        from r_cli.skills.text_skill import TextSkill
        skill = TextSkill(config)
        result = skill.text_count("hello world foo bar")
        # Contains word count info
        assert "4" in result or "word" in result.lower()

    def test_text_case_upper(self, config):
        from r_cli.skills.text_skill import TextSkill
        skill = TextSkill(config)
        result = skill.text_case("hello world", "upper")
        assert "HELLO WORLD" in result

    def test_text_case_lower(self, config):
        from r_cli.skills.text_skill import TextSkill
        skill = TextSkill(config)
        result = skill.text_case("HELLO WORLD", "lower")
        assert "hello world" in result

    def test_text_slug(self, config):
        from r_cli.skills.text_skill import TextSkill
        skill = TextSkill(config)
        result = skill.text_slug("Hello World Test")
        assert "hello-world-test" in result.lower()

    def test_text_reverse(self, config):
        from r_cli.skills.text_skill import TextSkill
        skill = TextSkill(config)
        result = skill.text_reverse("hello")
        assert "olleh" in result


# =============================================================================
# Functional Tests - MathSkill
# =============================================================================


class TestMathSkillFunctional:
    """Functional tests for MathSkill."""

    def test_math_calculate(self, config):
        from r_cli.skills.math_skill import MathSkill
        skill = MathSkill(config)
        result = skill.calculate("2 + 2")
        assert "4" in result

    def test_math_calculate_complex(self, config):
        from r_cli.skills.math_skill import MathSkill
        skill = MathSkill(config)
        result = skill.calculate("(10 + 5) * 2")
        assert "30" in result

    def test_math_factorial(self, config):
        from r_cli.skills.math_skill import MathSkill
        skill = MathSkill(config)
        result = skill.factorial(5)
        assert "120" in result


# =============================================================================
# Functional Tests - CryptoSkill
# =============================================================================


class TestCryptoSkillFunctional:
    """Functional tests for CryptoSkill."""

    def test_hash_md5(self, config):
        from r_cli.skills.crypto_skill import CryptoSkill
        skill = CryptoSkill(config)
        result = skill.hash_text("hello", algorithm="md5")
        assert "5d41402abc4b2a76b9719d911017c592" in result.lower()

    def test_hash_sha256(self, config):
        from r_cli.skills.crypto_skill import CryptoSkill
        skill = CryptoSkill(config)
        result = skill.hash_text("hello", algorithm="sha256")
        assert "2cf24dba" in result.lower()

    def test_base64_encode(self, config):
        from r_cli.skills.crypto_skill import CryptoSkill
        skill = CryptoSkill(config)
        result = skill.base64_encode("hello")
        assert "aGVsbG8=" in result

    def test_base64_decode(self, config):
        from r_cli.skills.crypto_skill import CryptoSkill
        skill = CryptoSkill(config)
        result = skill.base64_decode("aGVsbG8=")
        assert "hello" in result


# =============================================================================
# Functional Tests - ArchiveSkill
# =============================================================================


class TestArchiveSkillFunctional:
    """Functional tests for ArchiveSkill."""

    def test_list_archive(self, temp_dir, config):
        import zipfile
        from r_cli.skills.archive_skill import ArchiveSkill

        skill = ArchiveSkill(config)

        # Create test zip
        zip_path = Path(temp_dir, "test.zip")
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("file1.txt", "content1")
            zf.writestr("file2.txt", "content2")

        result = skill.list_archive(str(zip_path))
        assert "file1.txt" in result
        assert "file2.txt" in result


# =============================================================================
# Functional Tests - DiffSkill
# =============================================================================


class TestDiffSkillFunctional:
    """Functional tests for DiffSkill."""

    def test_diff_files(self, temp_dir, config):
        from r_cli.skills.diff_skill import DiffSkill

        skill = DiffSkill(config)

        file1 = Path(temp_dir, "file1.txt")
        file2 = Path(temp_dir, "file2.txt")
        file1.write_text("line1\nline2\nline3")
        file2.write_text("line1\nmodified\nline3")

        result = skill.diff_files(str(file1), str(file2))
        assert "line2" in result or "modified" in result or "-" in result
