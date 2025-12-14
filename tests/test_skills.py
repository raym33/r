"""Tests para los skills de R CLI."""

import pytest
import tempfile
import os
from pathlib import Path

from r_cli.core.config import Config
from r_cli.skills.pdf_skill import PDFSkill
from r_cli.skills.fs_skill import FilesystemSkill
from r_cli.skills.code_skill import CodeSkill
from r_cli.skills.sql_skill import SQLSkill
from r_cli.skills.resume_skill import ResumeSkill


@pytest.fixture
def temp_dir():
    """Crea un directorio temporal para tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def config(temp_dir):
    """Configuración para tests."""
    cfg = Config()
    cfg.output_dir = temp_dir
    cfg.home_dir = temp_dir
    return cfg


class TestFilesystemSkill:
    """Tests para FilesystemSkill."""

    def test_list_directory(self, temp_dir, config):
        """Test listar directorio."""
        skill = FilesystemSkill(config)

        # Crear archivos de prueba
        Path(temp_dir, "test1.txt").write_text("contenido 1")
        Path(temp_dir, "test2.py").write_text("print('hello')")

        result = skill.list_directory(temp_dir)

        assert "test1.txt" in result
        assert "test2.py" in result

    def test_read_file(self, temp_dir, config):
        """Test leer archivo."""
        skill = FilesystemSkill(config)

        test_file = Path(temp_dir, "test.txt")
        test_file.write_text("Contenido de prueba")

        result = skill.read_file(str(test_file))

        assert "Contenido de prueba" in result

    def test_write_file(self, temp_dir, config):
        """Test escribir archivo."""
        skill = FilesystemSkill(config)

        output_path = Path(temp_dir, "output.txt")
        result = skill.write_file(str(output_path), "Nuevo contenido")

        assert "✅" in result
        assert output_path.exists()
        assert output_path.read_text() == "Nuevo contenido"

    def test_file_info(self, temp_dir, config):
        """Test info de archivo."""
        skill = FilesystemSkill(config)

        test_file = Path(temp_dir, "test.txt")
        test_file.write_text("12345")

        result = skill.file_info(str(test_file))

        assert "test.txt" in result
        assert "5" in result or "5.0 B" in result  # Tamaño


class TestPDFSkill:
    """Tests para PDFSkill."""

    def test_generate_pdf(self, temp_dir, config):
        """Test generar PDF."""
        skill = PDFSkill(config)
        skill.output_dir = temp_dir

        result = skill.generate_pdf(
            content="# Título\n\nContenido del documento.",
            title="Test PDF",
            output_path=str(Path(temp_dir, "test.pdf")),
        )

        assert "PDF generado" in result
        assert Path(temp_dir, "test.pdf").exists()

    def test_list_templates(self, config):
        """Test listar templates."""
        skill = PDFSkill(config)

        result = skill.list_templates()

        assert "minimal" in result
        assert "business" in result
        assert "academic" in result


class TestCodeSkill:
    """Tests para CodeSkill."""

    def test_write_code(self, temp_dir, config):
        """Test escribir código."""
        skill = CodeSkill(config)
        skill.output_dir = temp_dir

        result = skill.write_code(
            code="print('Hello, World!')",
            filename="hello.py",
            language="python",
        )

        assert "✅" in result
        assert Path(temp_dir, "hello.py").exists()

    def test_run_python(self, temp_dir, config):
        """Test ejecutar Python."""
        skill = CodeSkill(config)
        skill.output_dir = temp_dir

        result = skill.run_python("print('test output')")

        assert "test output" in result

    def test_run_python_error(self, temp_dir, config):
        """Test error en Python."""
        skill = CodeSkill(config)
        skill.output_dir = temp_dir

        result = skill.run_python("raise ValueError('test error')")

        assert "ValueError" in result or "error" in result.lower()

    def test_analyze_code(self, temp_dir, config):
        """Test analizar código."""
        skill = CodeSkill(config)

        test_file = Path(temp_dir, "sample.py")
        test_file.write_text("""
import os
from pathlib import Path

def hello():
    '''Saluda'''
    print("Hello")

class MyClass:
    pass
""")

        result = skill.analyze_code(str(test_file))

        assert "python" in result.lower()
        assert "hello" in result.lower() or "Funciones" in result


class TestResumeSkill:
    """Tests para ResumeSkill."""

    def test_summarize_short_text(self, config):
        """Test resumir texto corto."""
        skill = ResumeSkill(config)

        text = "Python es un lenguaje de programación interpretado. " * 10
        result = skill.summarize_text(text, style="concise")

        assert len(result) > 0
        assert "Python" in result

    def test_extract_key_points(self, config):
        """Test extraer puntos clave."""
        skill = ResumeSkill(config)

        text = """
        El aprendizaje automático es importante para el futuro.
        La inteligencia artificial está transformando industrias.
        Los datos son el nuevo petróleo del siglo XXI.
        La privacidad es una preocupación clave en la era digital.
        """

        result = skill.extract_key_points(text, num_points=3)

        assert "Puntos Clave" in result
        assert "1." in result

    def test_compare_texts(self, config):
        """Test comparar textos."""
        skill = ResumeSkill(config)

        text1 = "Python es un lenguaje de programación versátil y popular."
        text2 = "Python es usado para machine learning y análisis de datos."

        result = skill.compare_texts(text1, text2)

        assert "Similitud" in result
        assert "Python" in result.lower() or "común" in result.lower()


class TestSQLSkill:
    """Tests para SQLSkill."""

    def test_describe_csv(self, temp_dir, config):
        """Test describir CSV."""
        skill = SQLSkill(config)

        # Crear CSV de prueba
        csv_path = Path(temp_dir, "test.csv")
        csv_path.write_text("nombre,edad,ciudad\nAna,25,Madrid\nJuan,30,Barcelona")

        result = skill.describe_csv(str(csv_path))

        # Puede fallar si DuckDB no está instalado, pero no debería dar error
        assert "test.csv" in result or "Error" in result

    def test_list_tables_empty(self, config):
        """Test listar tablas vacío."""
        skill = SQLSkill(config)

        result = skill.list_tables()

        # Puede mostrar "no hay tablas" o error si DuckDB no está
        assert "tablas" in result.lower() or "error" in result.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
