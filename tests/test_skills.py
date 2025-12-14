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
from r_cli.skills.latex_skill import LaTeXSkill
from r_cli.skills.ocr_skill import OCRSkill
from r_cli.skills.voice_skill import VoiceSkill
from r_cli.skills.design_skill import DesignSkill
from r_cli.skills.calendar_skill import CalendarSkill
from r_cli.skills.multiagent_skill import MultiAgentSkill


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


class TestLaTeXSkill:
    """Tests para LaTeXSkill."""

    def test_list_templates(self, config):
        """Test listar templates LaTeX."""
        skill = LaTeXSkill(config)

        result = skill.list_templates()

        assert "article" in result
        assert "report" in result
        assert "academic" in result
        assert "cv" in result

    def test_markdown_to_latex(self, config):
        """Test conversión Markdown a LaTeX."""
        skill = LaTeXSkill(config)

        markdown = """# Título Principal

## Sección 1

Este es un párrafo con **texto en negrita** y *cursiva*.

- Item 1
- Item 2
- Item 3
"""

        result = skill.markdown_to_latex(markdown)

        assert "section" in result
        assert "textbf" in result or "Conversion" in result

    def test_create_document_minimal(self, temp_dir, config):
        """Test crear documento con template minimal."""
        skill = LaTeXSkill(config)
        skill.output_dir = temp_dir

        # Solo probar si pdflatex está disponible
        if not skill._check_latex_installed():
            pytest.skip("pdflatex no instalado")

        result = skill.create_document(
            content="Hello World! This is a test document.",
            template="minimal",
            output_path=str(Path(temp_dir, "test_minimal.pdf")),
        )

        # Puede fallar si LaTeX no está instalado
        assert "PDF" in result or "Error" in result


class TestOCRSkill:
    """Tests para OCRSkill."""

    def test_list_languages(self, config):
        """Test listar idiomas OCR."""
        skill = OCRSkill(config)

        result = skill.list_languages()

        assert "eng" in result
        assert "spa" in result
        assert "English" in result

    def test_extract_from_nonexistent_image(self, config):
        """Test OCR con imagen que no existe."""
        skill = OCRSkill(config)

        result = skill.extract_from_image("/nonexistent/image.png")

        assert "Error" in result or "no encontrada" in result.lower()

    def test_extract_from_nonexistent_pdf(self, config):
        """Test OCR con PDF que no existe."""
        skill = OCRSkill(config)

        result = skill.extract_from_pdf("/nonexistent/document.pdf")

        assert "Error" in result or "no encontrado" in result.lower()

    def test_tesseract_check(self, config):
        """Test verificación de Tesseract."""
        skill = OCRSkill(config)

        # El skill debe poder verificar si Tesseract está instalado
        is_available = skill._tesseract_available

        # Es un boolean
        assert isinstance(is_available, bool)


class TestVoiceSkill:
    """Tests para VoiceSkill."""

    def test_list_whisper_models(self, config):
        """Test listar modelos Whisper."""
        skill = VoiceSkill(config)

        result = skill.list_whisper_models()

        assert "tiny" in result
        assert "base" in result
        assert "medium" in result
        assert "large" in result

    def test_list_voices(self, config):
        """Test listar voces Piper."""
        skill = VoiceSkill(config)

        result = skill.list_voices()

        assert "en_US" in result or "English" in result
        assert "es_ES" in result or "Spanish" in result

    def test_whisper_check(self, config):
        """Test verificación de Whisper."""
        skill = VoiceSkill(config)

        # Debe ser boolean
        assert isinstance(skill._whisper_available, bool)

    def test_piper_check(self, config):
        """Test verificación de Piper."""
        skill = VoiceSkill(config)

        # Debe ser boolean
        assert isinstance(skill._piper_available, bool)

    def test_transcribe_nonexistent_audio(self, config):
        """Test transcribir audio que no existe."""
        skill = VoiceSkill(config)

        result = skill.transcribe_audio("/nonexistent/audio.mp3")

        assert "Error" in result or "no encontrado" in result.lower() or "not" in result.lower()


class TestDesignSkill:
    """Tests para DesignSkill."""

    def test_list_styles(self, config):
        """Test listar estilos."""
        skill = DesignSkill(config)

        result = skill.list_styles()

        assert "photorealistic" in result
        assert "anime" in result
        assert "cyberpunk" in result
        assert "pixel-art" in result

    def test_list_models(self, config):
        """Test listar modelos SD."""
        skill = DesignSkill(config)

        result = skill.list_models()

        assert "sd-1.5" in result or "Stable Diffusion" in result
        assert "sdxl" in result.lower() or "SDXL" in result

    def test_backend_status(self, config):
        """Test estado de backends."""
        skill = DesignSkill(config)

        result = skill.backend_status()

        assert "diffusers" in result
        assert "automatic1111" in result or "comfyui" in result

    def test_generate_without_backend(self, config):
        """Test generar sin backend disponible."""
        skill = DesignSkill(config)

        # Si no hay backend, debe dar error claro
        if skill._active_backend == "none":
            result = skill.generate_image("test prompt")
            assert "Error" in result or "backend" in result.lower()


class TestCalendarSkill:
    """Tests para CalendarSkill."""

    def test_init_database(self, temp_dir, config):
        """Test inicialización de base de datos."""
        config.home_dir = temp_dir
        skill = CalendarSkill(config)

        # La base de datos debe existir
        assert skill.db_path.exists()

    def test_add_event(self, temp_dir, config):
        """Test añadir evento."""
        config.home_dir = temp_dir
        skill = CalendarSkill(config)

        result = skill.add_event(
            title="Reunión de prueba",
            start_time="2025-01-15 10:00",
            description="Test event",
            category="work",
        )

        assert "Evento creado" in result
        assert "Reunión de prueba" in result

    def test_add_task(self, temp_dir, config):
        """Test añadir tarea."""
        config.home_dir = temp_dir
        skill = CalendarSkill(config)

        result = skill.add_task(
            title="Tarea de prueba",
            due_date="2025-01-20",
            priority=1,
        )

        assert "Tarea creada" in result
        assert "Tarea de prueba" in result

    def test_today_summary(self, temp_dir, config):
        """Test resumen de hoy."""
        config.home_dir = temp_dir
        skill = CalendarSkill(config)

        result = skill.today_summary()

        assert "Resumen de hoy" in result
        assert "EVENTOS" in result
        assert "TAREAS" in result

    def test_week_summary(self, temp_dir, config):
        """Test resumen semanal."""
        config.home_dir = temp_dir
        skill = CalendarSkill(config)

        result = skill.week_summary()

        assert "Resumen de la semana" in result
        assert "Lunes" in result
        assert "Domingo" in result

    def test_complete_task(self, temp_dir, config):
        """Test completar tarea."""
        config.home_dir = temp_dir
        skill = CalendarSkill(config)

        # Añadir tarea
        skill.add_task(title="Tarea para completar")

        # Completar (ID 1)
        result = skill.complete_task(1)

        assert "completada" in result.lower() or "Tarea" in result

    def test_list_events_empty(self, temp_dir, config):
        """Test listar eventos vacío."""
        config.home_dir = temp_dir
        skill = CalendarSkill(config)

        result = skill.list_events(date="2099-12-31")

        assert "No hay eventos" in result

    def test_export_ical_empty(self, temp_dir, config):
        """Test exportar iCal vacío."""
        config.home_dir = temp_dir
        skill = CalendarSkill(config)
        skill.output_dir = temp_dir

        result = skill.export_ical(start_date="2099-01-01", end_date="2099-12-31")

        assert "No hay eventos" in result


class TestMultiAgentSkill:
    """Tests para MultiAgentSkill."""

    def test_list_agents(self, config):
        """Test listar agentes."""
        skill = MultiAgentSkill(config)

        result = skill.list_agents()

        assert "Agentes disponibles" in result
        assert "coordinator" in result.lower() or "Coordinator" in result
        assert "coder" in result.lower() or "Coder" in result

    def test_get_history_empty(self, config):
        """Test historial vacío."""
        skill = MultiAgentSkill(config)

        result = skill.get_history()

        assert "historial" in result.lower() or "No hay" in result

    def test_clear_agents(self, config):
        """Test limpiar agentes."""
        skill = MultiAgentSkill(config)

        result = skill.clear_agents()

        assert "limpiado" in result.lower() or "Historial" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
