"""
OCR Skill for R CLI.

Extract text from:
- Images (PNG, JPG, etc.)
- Scanned PDFs
- Screenshots
- Photographed documents

Uses Tesseract OCR (open source, offline).
"""

import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from r_cli.core.agent import Skill
from r_cli.core.llm import Tool


class OCRSkill(Skill):
    """Skill for text extraction with OCR."""

    name = "ocr"
    description = "Extract text from images and scanned PDFs using Tesseract OCR"

    # Languages supported by Tesseract
    LANGUAGES = {
        "eng": "English",
        "spa": "Spanish",
        "fra": "French",
        "deu": "German",
        "ita": "Italian",
        "por": "Portuguese",
        "chi_sim": "Chinese (Simplified)",
        "chi_tra": "Chinese (Traditional)",
        "jpn": "Japanese",
        "kor": "Korean",
        "ara": "Arabic",
        "rus": "Russian",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._tesseract_available = self._check_tesseract()

    def _check_tesseract(self) -> bool:
        """Check if Tesseract is installed."""
        return shutil.which("tesseract") is not None

    def _check_poppler(self) -> bool:
        """Check if Poppler (pdftoppm) is installed for PDFs."""
        return shutil.which("pdftoppm") is not None

    def get_tools(self) -> list[Tool]:
        return [
            Tool(
                name="extract_text_from_image",
                description="Extract text from an image using OCR",
                parameters={
                    "type": "object",
                    "properties": {
                        "image_path": {
                            "type": "string",
                            "description": "Path to the image (PNG, JPG, TIFF, etc.)",
                        },
                        "language": {
                            "type": "string",
                            "description": "Text language (eng, spa, fra, deu, etc.)",
                        },
                        "output_file": {
                            "type": "string",
                            "description": "Path to save extracted text (optional)",
                        },
                    },
                    "required": ["image_path"],
                },
                handler=self.extract_from_image,
            ),
            Tool(
                name="extract_text_from_pdf",
                description="Extract text from a PDF (including scanned)",
                parameters={
                    "type": "object",
                    "properties": {
                        "pdf_path": {
                            "type": "string",
                            "description": "Path to the PDF file",
                        },
                        "language": {
                            "type": "string",
                            "description": "Text language (eng, spa, fra, etc.)",
                        },
                        "pages": {
                            "type": "string",
                            "description": "Pages to process (e.g., '1-5', 'all')",
                        },
                        "output_file": {
                            "type": "string",
                            "description": "Path to save extracted text",
                        },
                    },
                    "required": ["pdf_path"],
                },
                handler=self.extract_from_pdf,
            ),
            Tool(
                name="ocr_to_searchable_pdf",
                description="Convert a scanned PDF to PDF with selectable text",
                parameters={
                    "type": "object",
                    "properties": {
                        "pdf_path": {
                            "type": "string",
                            "description": "Path to the scanned PDF",
                        },
                        "language": {
                            "type": "string",
                            "description": "Text language",
                        },
                        "output_path": {
                            "type": "string",
                            "description": "Path for the output PDF",
                        },
                    },
                    "required": ["pdf_path"],
                },
                handler=self.create_searchable_pdf,
            ),
            Tool(
                name="batch_ocr",
                description="Process multiple images in a directory",
                parameters={
                    "type": "object",
                    "properties": {
                        "directory": {
                            "type": "string",
                            "description": "Directory with images",
                        },
                        "pattern": {
                            "type": "string",
                            "description": "File pattern (e.g., *.png, *.jpg)",
                        },
                        "language": {
                            "type": "string",
                            "description": "Text language",
                        },
                        "output_file": {
                            "type": "string",
                            "description": "File to concatenate all text",
                        },
                    },
                    "required": ["directory"],
                },
                handler=self.batch_ocr,
            ),
            Tool(
                name="list_ocr_languages",
                description="List available languages for OCR",
                parameters={"type": "object", "properties": {}},
                handler=self.list_languages,
            ),
        ]

    def extract_from_image(
        self,
        image_path: str,
        language: str = "eng",
        output_file: Optional[str] = None,
    ) -> str:
        """Extract text from an image."""
        if not self._tesseract_available:
            return self._install_instructions()

        try:
            path = Path(image_path)

            if not path.exists():
                return f"Error: Image not found: {image_path}"

            # Check format
            valid_extensions = [".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp", ".gif", ".webp"]
            if path.suffix.lower() not in valid_extensions:
                return f"Error: Unsupported format. Use: {', '.join(valid_extensions)}"

            # Run Tesseract
            result = subprocess.run(
                [
                    "tesseract",
                    str(path),
                    "stdout",
                    "-l",
                    language,
                    "--psm",
                    "3",  # Automatic page segmentation
                ],
                check=False,
                capture_output=True,
                text=True,
                timeout=120,
            )

            if result.returncode != 0:
                error = result.stderr or "Unknown error"
                if "Tesseract couldn't load any languages" in error:
                    return f"Error: Language '{language}' not installed. Run: brew install tesseract-lang"
                return f"OCR error: {error}"

            text = result.stdout.strip()

            if not text:
                return "No text detected in the image."

            # Save to file if specified
            if output_file:
                out_path = Path(output_file)
                out_path.parent.mkdir(parents=True, exist_ok=True)
                with open(out_path, "w", encoding="utf-8") as f:
                    f.write(text)
                return f"Text extracted and saved to: {out_path}\n\n{text[:1000]}{'...' if len(text) > 1000 else ''}"

            return f"Text extracted ({len(text)} characters):\n\n{text}"

        except subprocess.TimeoutExpired:
            return "Error: Timeout processing image (>120s)"
        except Exception as e:
            return f"OCR error: {e}"

    def extract_from_pdf(
        self,
        pdf_path: str,
        language: str = "eng",
        pages: str = "all",
        output_file: Optional[str] = None,
    ) -> str:
        """Extract text from a PDF."""
        if not self._tesseract_available:
            return self._install_instructions()

        try:
            path = Path(pdf_path)

            if not path.exists():
                return f"Error: PDF not found: {pdf_path}"

            # First try direct extraction (for PDFs with text)
            direct_text = self._extract_pdf_text_direct(path)
            if direct_text and len(direct_text.strip()) > 100:
                if output_file:
                    Path(output_file).write_text(direct_text)
                    return f"Text extracted directly and saved to: {output_file}"
                return f"Text extracted directly ({len(direct_text)} chars):\n\n{direct_text[:2000]}..."

            # If no text, use OCR
            if not self._check_poppler():
                return "Error: Poppler not installed. Required for scanned PDFs.\nInstall: brew install poppler"

            all_text = []

            with tempfile.TemporaryDirectory() as tmpdir:
                # Convert PDF to images
                subprocess.run(
                    [
                        "pdftoppm",
                        "-png",
                        "-r",
                        "300",  # 300 DPI for better OCR
                        str(path),
                        f"{tmpdir}/page",
                    ],
                    check=False,
                    capture_output=True,
                    timeout=300,
                )

                # Process each page
                page_images = sorted(Path(tmpdir).glob("page-*.png"))

                if not page_images:
                    return "Error: Could not extract pages from PDF"

                for i, img_path in enumerate(page_images, 1):
                    result = subprocess.run(
                        [
                            "tesseract",
                            str(img_path),
                            "stdout",
                            "-l",
                            language,
                        ],
                        check=False,
                        capture_output=True,
                        text=True,
                        timeout=60,
                    )

                    if result.stdout.strip():
                        all_text.append(f"--- Page {i} ---\n{result.stdout.strip()}")

            if not all_text:
                return "No text detected in the PDF."

            full_text = "\n\n".join(all_text)

            if output_file:
                Path(output_file).write_text(full_text)
                return f"OCR text extracted from {len(page_images)} pages. Saved to: {output_file}"

            return f"OCR text ({len(page_images)} pages, {len(full_text)} chars):\n\n{full_text[:3000]}..."

        except subprocess.TimeoutExpired:
            return "Error: Timeout processing PDF"
        except Exception as e:
            return f"Error processing PDF: {e}"

    def _extract_pdf_text_direct(self, pdf_path: Path) -> str:
        """Try to extract text directly from PDF (without OCR)."""
        try:
            from pypdf import PdfReader

            reader = PdfReader(str(pdf_path))
            text_parts = []

            for page in reader.pages:
                text = page.extract_text()
                if text:
                    text_parts.append(text)

            return "\n\n".join(text_parts)
        except Exception:
            return ""

    def create_searchable_pdf(
        self,
        pdf_path: str,
        language: str = "eng",
        output_path: Optional[str] = None,
    ) -> str:
        """Create a PDF with selectable text layer."""
        if not self._tesseract_available:
            return self._install_instructions()

        try:
            path = Path(pdf_path)

            if not path.exists():
                return f"Error: PDF not found: {pdf_path}"

            # Determine output
            if output_path:
                out_path = Path(output_path)
            else:
                out_path = path.with_stem(f"{path.stem}_searchable")

            # Use Tesseract to create PDF with OCR
            with tempfile.TemporaryDirectory() as tmpdir:
                # Convert to images first
                subprocess.run(
                    ["pdftoppm", "-png", "-r", "300", str(path), f"{tmpdir}/page"],
                    check=False,
                    capture_output=True,
                    timeout=300,
                )

                page_images = sorted(Path(tmpdir).glob("page-*.png"))

                if not page_images:
                    return "Error: Could not extract pages"

                # Create PDF with OCR for each page
                pdf_parts = []
                for img in page_images:
                    pdf_out = img.with_suffix("")
                    subprocess.run(
                        [
                            "tesseract",
                            str(img),
                            str(pdf_out),
                            "-l",
                            language,
                            "pdf",
                        ],
                        check=False,
                        capture_output=True,
                        timeout=60,
                    )
                    pdf_parts.append(f"{pdf_out}.pdf")

                # Merge PDFs if multiple
                if len(pdf_parts) == 1:
                    shutil.copy(pdf_parts[0], out_path)
                # Use pdfunite if available
                elif shutil.which("pdfunite"):
                    subprocess.run(
                        ["pdfunite"] + pdf_parts + [str(out_path)],
                        check=False,
                        capture_output=True,
                    )
                else:
                    # Fallback: only copy first page
                    shutil.copy(pdf_parts[0], out_path)
                    return f"Searchable PDF created (first page only, install poppler-utils to merge): {out_path}"

            return f"Searchable PDF created: {out_path}"

        except Exception as e:
            return f"Error creating searchable PDF: {e}"

    def batch_ocr(
        self,
        directory: str,
        pattern: str = "*.png",
        language: str = "eng",
        output_file: Optional[str] = None,
    ) -> str:
        """Process multiple images."""
        if not self._tesseract_available:
            return self._install_instructions()

        try:
            dir_path = Path(directory)

            if not dir_path.exists():
                return f"Error: Directory not found: {directory}"

            images = list(dir_path.glob(pattern))

            if not images:
                return f"No images found with pattern '{pattern}' in {directory}"

            all_text = []
            processed = 0
            errors = 0

            for img_path in sorted(images):
                result = subprocess.run(
                    [
                        "tesseract",
                        str(img_path),
                        "stdout",
                        "-l",
                        language,
                    ],
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=60,
                )

                if result.returncode == 0 and result.stdout.strip():
                    all_text.append(f"--- {img_path.name} ---\n{result.stdout.strip()}")
                    processed += 1
                else:
                    errors += 1

            if not all_text:
                return f"No text extracted from any image ({errors} errors)"

            full_text = "\n\n".join(all_text)

            if output_file:
                Path(output_file).write_text(full_text)
                return (
                    f"Processed {processed} images ({errors} errors). Text saved to: {output_file}"
                )

            return f"Processed {processed} images ({errors} errors):\n\n{full_text[:3000]}..."

        except Exception as e:
            return f"Batch OCR error: {e}"

    def list_languages(self) -> str:
        """List available languages."""
        result = ["Languages supported by Tesseract OCR:\n"]

        for code, name in self.LANGUAGES.items():
            result.append(f"  - {code}: {name}")

        result.append("\nNote: Some languages require additional installation.")
        result.append("macOS: brew install tesseract-lang")
        result.append("Ubuntu: apt install tesseract-ocr-[lang]")

        # Check installed languages
        if self._tesseract_available:
            try:
                installed = subprocess.run(
                    ["tesseract", "--list-langs"],
                    check=False,
                    capture_output=True,
                    text=True,
                )
                if installed.returncode == 0:
                    langs = installed.stdout.strip().split("\n")[1:]  # Skip header
                    result.append(f"\nInstalled on this system: {', '.join(langs)}")
            except Exception:
                pass

        return "\n".join(result)

    def _install_instructions(self) -> str:
        """Tesseract installation instructions."""
        return """Error: Tesseract OCR is not installed.

Installation instructions:

macOS:
  brew install tesseract
  brew install tesseract-lang  # For more languages

Ubuntu/Debian:
  sudo apt install tesseract-ocr
  sudo apt install tesseract-ocr-spa  # Spanish

Windows:
  Download from: https://github.com/UB-Mannheim/tesseract/wiki
"""

    def execute(self, **kwargs) -> str:
        """Direct skill execution."""
        image = kwargs.get("image")
        pdf = kwargs.get("pdf")
        language = kwargs.get("language", "eng")

        if image:
            return self.extract_from_image(image, language, kwargs.get("output"))
        elif pdf:
            return self.extract_from_pdf(pdf, language, output_file=kwargs.get("output"))
        else:
            return "Error: An image or PDF is required for OCR"
