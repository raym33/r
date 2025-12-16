"""Tests for tools utilities."""

import os
import tempfile
from pathlib import Path

import pytest

from r_cli.tools.file_utils import (
    ensure_dir,
    format_size,
    get_file_type,
    list_files_recursive,
    read_file_safe,
    safe_path,
)
from r_cli.tools.text_processing import (
    chunk_text,
    clean_text,
    extract_sentences,
    find_keywords,
    truncate_text,
    word_count,
)


class TestSafePath:
    """Tests for safe_path function."""

    def test_simple_path(self):
        result = safe_path("/tmp/test.txt")
        assert result == Path("/tmp/test.txt").resolve()

    def test_expand_home(self):
        result = safe_path("~/test.txt")
        assert str(result).startswith(str(Path.home()))

    def test_base_dir_valid(self, tmp_path):
        test_file = tmp_path / "subdir" / "file.txt"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.touch()

        result = safe_path(str(test_file), base_dir=str(tmp_path))
        assert result == test_file.resolve()

    def test_base_dir_invalid(self, tmp_path):
        with pytest.raises(ValueError, match="fuera del directorio"):
            safe_path("/etc/passwd", base_dir=str(tmp_path))

    def test_relative_path(self):
        result = safe_path(".")
        assert result == Path(".").resolve()


class TestEnsureDir:
    """Tests for ensure_dir function."""

    def test_create_new_dir(self, tmp_path):
        new_dir = tmp_path / "new" / "nested" / "dir"
        result = ensure_dir(str(new_dir))
        assert result.exists()
        assert result.is_dir()

    def test_existing_dir(self, tmp_path):
        existing = tmp_path / "existing"
        existing.mkdir()
        result = ensure_dir(str(existing))
        assert result == existing

    def test_with_home_expansion(self):
        result = ensure_dir("~/.r_cli_test_dir")
        assert result.exists()
        # Cleanup
        result.rmdir()


class TestGetFileType:
    """Tests for get_file_type function."""

    def test_python_file(self):
        result = get_file_type("test.py")
        assert result["extension"] == ".py"
        assert result["category"] == "Python"
        assert result["is_text"] is True

    def test_javascript_file(self):
        result = get_file_type("app.js")
        assert result["category"] == "JavaScript"
        assert result["is_text"] is True

    def test_typescript_file(self):
        result = get_file_type("component.tsx")
        # .tsx might not be in the list, check behavior
        assert result["extension"] == ".tsx"

    def test_image_file(self):
        result = get_file_type("photo.jpg")
        assert result["category"] == "Image"
        assert result["is_text"] is False

    def test_pdf_file(self):
        result = get_file_type("document.pdf")
        assert result["category"] == "PDF"
        assert result["is_text"] is False

    def test_markdown_file(self):
        result = get_file_type("README.md")
        assert result["category"] == "Markdown"
        assert result["is_text"] is True

    def test_json_file(self):
        result = get_file_type("config.json")
        assert result["category"] == "JSON"
        assert result["is_text"] is True

    def test_unknown_extension(self):
        result = get_file_type("file.xyz123")
        assert result["extension"] == ".xyz123"
        # Category depends on MIME detection

    def test_no_extension(self):
        result = get_file_type("Makefile")
        assert result["extension"] == ""


class TestFormatSize:
    """Tests for format_size function."""

    def test_bytes(self):
        assert format_size(500) == "500.0 B"

    def test_kilobytes(self):
        assert format_size(1024) == "1.0 KB"
        assert format_size(2048) == "2.0 KB"

    def test_megabytes(self):
        assert format_size(1024 * 1024) == "1.0 MB"

    def test_gigabytes(self):
        assert format_size(1024 * 1024 * 1024) == "1.0 GB"

    def test_terabytes(self):
        assert format_size(1024 * 1024 * 1024 * 1024) == "1.0 TB"

    def test_fractional(self):
        result = format_size(1536)  # 1.5 KB
        assert "KB" in result


class TestListFilesRecursive:
    """Tests for list_files_recursive function."""

    @pytest.fixture
    def test_dir(self, tmp_path):
        # Create test structure
        (tmp_path / "file1.py").touch()
        (tmp_path / "file2.py").touch()
        (tmp_path / "file3.txt").touch()
        (tmp_path / "subdir").mkdir()
        (tmp_path / "subdir" / "file4.py").touch()
        (tmp_path / "subdir" / "nested").mkdir()
        (tmp_path / "subdir" / "nested" / "file5.py").touch()
        (tmp_path / ".hidden").touch()
        return tmp_path

    def test_list_all_files(self, test_dir):
        files = list_files_recursive(str(test_dir))
        assert len(files) >= 5

    def test_pattern_filter(self, test_dir):
        files = list_files_recursive(str(test_dir), pattern="*.py")
        assert all(f.suffix == ".py" for f in files)
        assert len(files) == 4

    def test_max_depth(self, test_dir):
        files = list_files_recursive(str(test_dir), max_depth=1)
        # Should not include nested/file5.py
        nested_files = [f for f in files if "nested" in str(f)]
        assert len(nested_files) == 0

    def test_include_hidden(self, test_dir):
        files_no_hidden = list_files_recursive(str(test_dir), include_hidden=False)
        files_with_hidden = list_files_recursive(str(test_dir), include_hidden=True)
        assert len(files_with_hidden) >= len(files_no_hidden)

    def test_nonexistent_dir(self):
        files = list_files_recursive("/nonexistent/path/12345")
        assert files == []


class TestReadFileSafe:
    """Tests for read_file_safe function."""

    def test_read_text_file(self, tmp_path):
        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello, World!")

        content, error = read_file_safe(str(test_file))
        assert content == "Hello, World!"
        assert error is None

    def test_file_not_found(self):
        content, error = read_file_safe("/nonexistent/file.txt")
        assert content == ""
        assert "no encontrado" in error

    def test_not_a_file(self, tmp_path):
        content, error = read_file_safe(str(tmp_path))  # Directory
        assert content == ""
        assert "No es un archivo" in error

    def test_file_too_large(self, tmp_path):
        test_file = tmp_path / "large.txt"
        test_file.write_text("x" * 100)

        content, error = read_file_safe(str(test_file), max_size=50)
        assert content == ""
        assert "muy grande" in error

    def test_binary_file(self, tmp_path):
        test_file = tmp_path / "image.png"
        test_file.write_bytes(b"\x89PNG\r\n\x1a\n")

        content, error = read_file_safe(str(test_file))
        assert content == ""
        assert "No es un archivo de texto" in error

    def test_python_file(self, tmp_path):
        test_file = tmp_path / "script.py"
        test_file.write_text("print('hello')")

        content, error = read_file_safe(str(test_file))
        assert content == "print('hello')"
        assert error is None


class TestChunkText:
    """Tests for chunk_text function."""

    def test_short_text(self):
        text = "Short text"
        chunks = chunk_text(text, chunk_size=100)
        assert len(chunks) == 1
        assert chunks[0] == text

    def test_long_text_split(self):
        text = "A" * 5000
        chunks = chunk_text(text, chunk_size=1000, overlap=100)
        assert len(chunks) > 1
        assert all(len(c) <= 1000 for c in chunks)

    def test_paragraph_boundary(self):
        text = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."
        chunks = chunk_text(text, chunk_size=30, overlap=5)
        # Should try to split at paragraph boundaries
        assert len(chunks) >= 1

    def test_sentence_boundary(self):
        text = "First sentence. Second sentence. Third sentence."
        chunks = chunk_text(text, chunk_size=25, overlap=5)
        assert len(chunks) >= 1

    def test_overlap(self):
        text = "Word " * 100
        chunks = chunk_text(text, chunk_size=50, overlap=10)
        # With overlap, we should have content repeated between chunks
        assert len(chunks) > 1


class TestExtractSentences:
    """Tests for extract_sentences function."""

    def test_simple_sentences(self):
        text = "First sentence. Second sentence. Third sentence."
        sentences = extract_sentences(text)
        assert len(sentences) >= 2

    def test_question_mark(self):
        text = "Is this a question? Yes it is."
        sentences = extract_sentences(text)
        assert len(sentences) >= 1

    def test_exclamation(self):
        text = "What a day! It was amazing."
        sentences = extract_sentences(text)
        assert len(sentences) >= 1

    def test_min_length_filter(self):
        text = "Hi. This is a longer sentence."
        sentences = extract_sentences(text, min_length=10)
        assert all(len(s) >= 10 for s in sentences)

    def test_newlines_removed(self):
        text = "First line\nsecond line\nthird line."
        sentences = extract_sentences(text)
        # Newlines should be normalized to spaces
        for s in sentences:
            assert "\n" not in s


class TestWordCount:
    """Tests for word_count function."""

    def test_basic_count(self):
        text = "Hello world. This is a test."
        result = word_count(text)
        assert result["words"] == 6
        assert result["chars"] == len(text)
        assert result["paragraphs"] >= 1

    def test_multiple_paragraphs(self):
        text = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."
        result = word_count(text)
        assert result["paragraphs"] == 3

    def test_avg_word_length(self):
        text = "cat dog bird"
        result = word_count(text)
        assert result["avg_word_length"] > 0

    def test_chars_no_spaces(self):
        text = "Hello World"
        result = word_count(text)
        assert result["chars_no_spaces"] == 10  # "HelloWorld"

    def test_empty_text(self):
        result = word_count("")
        assert result["words"] == 0


class TestFindKeywords:
    """Tests for find_keywords function."""

    def test_basic_keywords(self):
        text = "python python python java java ruby"
        keywords = find_keywords(text, top_n=3)
        assert keywords[0][0] == "python"
        assert keywords[0][1] == 3

    def test_stopwords_filtered(self):
        text = "the the the python python"
        keywords = find_keywords(text)
        keyword_words = [k[0] for k in keywords]
        assert "the" not in keyword_words
        assert "python" in keyword_words

    def test_short_words_filtered(self):
        text = "a an the python programming"
        keywords = find_keywords(text)
        keyword_words = [k[0] for k in keywords]
        # Words with 3 or fewer chars should be filtered
        assert "a" not in keyword_words
        assert "an" not in keyword_words

    def test_top_n_limit(self):
        text = " ".join([f"word{i}" * (10 - i) for i in range(10)])
        keywords = find_keywords(text, top_n=5)
        assert len(keywords) <= 5


class TestCleanText:
    """Tests for clean_text function."""

    def test_normalize_newlines(self):
        text = "line1\r\nline2\rline3\nline4"
        result = clean_text(text)
        assert "\r" not in result
        assert "\n" in result

    def test_remove_multiple_spaces(self):
        text = "hello    world"
        result = clean_text(text)
        assert "    " not in result
        assert "hello world" in result

    def test_strip_line_whitespace(self):
        text = "  line1  \n  line2  "
        result = clean_text(text)
        assert result.startswith("line1")

    def test_reduce_multiple_newlines(self):
        text = "para1\n\n\n\n\npara2"
        result = clean_text(text)
        assert "\n\n\n" not in result

    def test_strip_result(self):
        text = "  \n  content  \n  "
        result = clean_text(text)
        assert result == "content"


class TestTruncateText:
    """Tests for truncate_text function."""

    def test_short_text_unchanged(self):
        text = "Short text"
        result = truncate_text(text, max_length=100)
        assert result == text

    def test_truncate_with_suffix(self):
        text = "This is a long text that needs to be truncated"
        result = truncate_text(text, max_length=20, suffix="...")
        assert len(result) <= 23  # 20 + suffix
        assert result.endswith("...")

    def test_truncate_at_word_boundary(self):
        text = "word1 word2 word3 word4"
        result = truncate_text(text, max_length=12)
        # Should not cut in middle of a word
        assert not result.endswith("wor...")

    def test_custom_suffix(self):
        text = "Long text here"
        result = truncate_text(text, max_length=8, suffix=" [more]")
        assert result.endswith("[more]")

    def test_exact_length(self):
        text = "Exact"
        result = truncate_text(text, max_length=5)
        assert result == "Exact"
