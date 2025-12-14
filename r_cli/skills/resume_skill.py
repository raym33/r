"""
Skill de resumen de documentos para R CLI.

Funcionalidades:
- Resumir documentos largos (PDFs, texto)
- Resumen iterativo/jerárquico para docs muy largos
- Extracción de puntos clave
- Generación de flashcards para estudio
"""

import os
from pathlib import Path
from typing import Optional

from r_cli.core.agent import Skill
from r_cli.core.llm import Tool


class ResumeSkill(Skill):
    """Skill para resumir documentos largos."""

    name = "resume"
    description = "Resume documentos largos, extrae puntos clave, genera flashcards"

    # Configuración de chunking
    CHUNK_SIZE = 3000  # caracteres por chunk
    CHUNK_OVERLAP = 200

    def get_tools(self) -> list[Tool]:
        return [
            Tool(
                name="summarize_text",
                description="Resume un texto largo",
                parameters={
                    "type": "object",
                    "properties": {
                        "text": {
                            "type": "string",
                            "description": "Texto a resumir",
                        },
                        "style": {
                            "type": "string",
                            "enum": ["concise", "detailed", "bullets", "academic"],
                            "description": "Estilo del resumen",
                        },
                        "max_length": {
                            "type": "integer",
                            "description": "Longitud máxima del resumen en palabras",
                        },
                    },
                    "required": ["text"],
                },
                handler=self.summarize_text,
            ),
            Tool(
                name="summarize_file",
                description="Resume un archivo de texto o PDF",
                parameters={
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "Ruta al archivo a resumir",
                        },
                        "style": {
                            "type": "string",
                            "enum": ["concise", "detailed", "bullets", "academic"],
                            "description": "Estilo del resumen",
                        },
                    },
                    "required": ["file_path"],
                },
                handler=self.summarize_file,
            ),
            Tool(
                name="extract_key_points",
                description="Extrae los puntos clave de un texto",
                parameters={
                    "type": "object",
                    "properties": {
                        "text": {
                            "type": "string",
                            "description": "Texto del cual extraer puntos clave",
                        },
                        "num_points": {
                            "type": "integer",
                            "description": "Número de puntos a extraer (default: 10)",
                        },
                    },
                    "required": ["text"],
                },
                handler=self.extract_key_points,
            ),
            Tool(
                name="generate_flashcards",
                description="Genera flashcards de estudio desde un texto",
                parameters={
                    "type": "object",
                    "properties": {
                        "text": {
                            "type": "string",
                            "description": "Texto del cual generar flashcards",
                        },
                        "num_cards": {
                            "type": "integer",
                            "description": "Número de flashcards (default: 20)",
                        },
                        "format": {
                            "type": "string",
                            "enum": ["text", "anki", "csv"],
                            "description": "Formato de salida",
                        },
                    },
                    "required": ["text"],
                },
                handler=self.generate_flashcards,
            ),
            Tool(
                name="compare_texts",
                description="Compara dos textos y muestra diferencias/similitudes",
                parameters={
                    "type": "object",
                    "properties": {
                        "text1": {
                            "type": "string",
                            "description": "Primer texto",
                        },
                        "text2": {
                            "type": "string",
                            "description": "Segundo texto",
                        },
                    },
                    "required": ["text1", "text2"],
                },
                handler=self.compare_texts,
            ),
        ]

    def summarize_text(
        self,
        text: str,
        style: str = "concise",
        max_length: int = 500,
    ) -> str:
        """
        Resume un texto.

        Para textos muy largos, usa resumen iterativo:
        1. Divide en chunks
        2. Resume cada chunk
        3. Resume los resúmenes
        """
        try:
            # Si el texto es corto, resumen directo
            if len(text) < self.CHUNK_SIZE * 2:
                return self._generate_summary(text, style, max_length)

            # Resumen iterativo para textos largos
            chunks = self._split_into_chunks(text)

            # Primera pasada: resumir cada chunk
            chunk_summaries = []
            for i, chunk in enumerate(chunks):
                summary = self._generate_summary(chunk, "concise", max_length // len(chunks))
                chunk_summaries.append(f"[Sección {i+1}] {summary}")

            # Segunda pasada: resumir los resúmenes
            combined = "\n\n".join(chunk_summaries)

            if len(combined) > self.CHUNK_SIZE * 2:
                # Necesita otra pasada
                return self._generate_summary(combined, style, max_length)
            else:
                final_summary = self._generate_summary(combined, style, max_length)
                return f"📝 Resumen ({len(chunks)} secciones procesadas):\n\n{final_summary}"

        except Exception as e:
            return f"Error resumiendo texto: {e}"

    def _split_into_chunks(self, text: str) -> list[str]:
        """Divide texto en chunks con overlap."""
        chunks = []
        start = 0

        while start < len(text):
            end = start + self.CHUNK_SIZE

            # Intentar cortar en un punto o párrafo
            if end < len(text):
                # Buscar fin de párrafo
                paragraph_end = text.rfind("\n\n", start, end)
                if paragraph_end > start + self.CHUNK_SIZE // 2:
                    end = paragraph_end + 2
                else:
                    # Buscar fin de oración
                    sentence_end = text.rfind(". ", start, end)
                    if sentence_end > start + self.CHUNK_SIZE // 2:
                        end = sentence_end + 2

            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)

            start = end - self.CHUNK_OVERLAP

        return chunks

    def _generate_summary(self, text: str, style: str, max_length: int) -> str:
        """
        Genera resumen usando el LLM.

        Nota: En una implementación real, esto llamaría al LLM.
        Por ahora retorna un resumen básico para demostración.
        """
        # Placeholder: En la versión completa, esto llama al LLM
        # Por ahora, hacemos un resumen extractivo simple

        sentences = text.replace("\n", " ").split(". ")
        sentences = [s.strip() for s in sentences if len(s.strip()) > 20]

        if style == "bullets":
            # Top sentences como bullets
            top_n = min(10, len(sentences))
            bullets = ["• " + s for s in sentences[:top_n]]
            return "\n".join(bullets)

        elif style == "concise":
            # Primeras y últimas oraciones
            if len(sentences) <= 5:
                return ". ".join(sentences) + "."
            else:
                summary = sentences[:3] + ["..."] + sentences[-2:]
                return ". ".join(summary)

        elif style == "detailed":
            # Más oraciones
            top_n = min(15, len(sentences))
            return ". ".join(sentences[:top_n]) + "."

        else:  # academic
            # Estructura: intro, puntos principales, conclusión
            if len(sentences) < 6:
                return ". ".join(sentences) + "."

            intro = sentences[0]
            main_points = sentences[1:-1][:5]
            conclusion = sentences[-1]

            return f"{intro}.\n\nPuntos principales:\n" + "\n".join(
                [f"• {p}" for p in main_points]
            ) + f"\n\nConclusión: {conclusion}."

    def summarize_file(self, file_path: str, style: str = "concise") -> str:
        """Resume un archivo."""
        try:
            path = Path(file_path)

            if not path.exists():
                return f"Error: Archivo no encontrado: {file_path}"

            # Leer contenido según tipo
            if path.suffix.lower() == ".pdf":
                text = self._extract_pdf_text(path)
            elif path.suffix.lower() in [".txt", ".md", ".rst"]:
                with open(path, "r", encoding="utf-8", errors="replace") as f:
                    text = f.read()
            else:
                # Intentar leer como texto
                try:
                    with open(path, "r", encoding="utf-8", errors="replace") as f:
                        text = f.read()
                except Exception:
                    return f"Error: No se puede leer el archivo: {file_path}"

            if not text.strip():
                return "Error: El archivo está vacío o no se pudo extraer texto."

            # Agregar info del archivo
            result = [
                f"📄 Resumen de: {path.name}",
                f"   Tamaño: {len(text):,} caracteres",
                f"   Palabras: ~{len(text.split()):,}",
                "",
            ]

            summary = self.summarize_text(text, style)
            result.append(summary)

            return "\n".join(result)

        except Exception as e:
            return f"Error resumiendo archivo: {e}"

    def _extract_pdf_text(self, pdf_path: Path) -> str:
        """Extrae texto de un PDF."""
        try:
            from pypdf import PdfReader

            reader = PdfReader(str(pdf_path))
            text_parts = []

            for page in reader.pages:
                text = page.extract_text()
                if text:
                    text_parts.append(text)

            return "\n\n".join(text_parts)

        except ImportError:
            return "Error: pypdf no instalado. Ejecuta: pip install pypdf"
        except Exception as e:
            return f"Error extrayendo PDF: {e}"

    def extract_key_points(self, text: str, num_points: int = 10) -> str:
        """Extrae puntos clave del texto."""
        try:
            # Dividir en oraciones
            sentences = text.replace("\n", " ").split(". ")
            sentences = [s.strip() + "." for s in sentences if len(s.strip()) > 30]

            if len(sentences) == 0:
                return "No se encontraron puntos clave."

            # Seleccionar las oraciones más "importantes"
            # (simplificación: las más largas y diversas)
            scored = []
            for s in sentences:
                # Score basado en longitud y presencia de palabras clave
                score = len(s.split())
                if any(kw in s.lower() for kw in ["importante", "clave", "principal", "debe", "necesario"]):
                    score *= 1.5
                if any(kw in s.lower() for kw in ["primero", "segundo", "finalmente", "además"]):
                    score *= 1.3
                scored.append((score, s))

            # Ordenar por score y tomar los top
            scored.sort(reverse=True, key=lambda x: x[0])
            top_points = [s for _, s in scored[:num_points]]

            result = [f"🔑 {num_points} Puntos Clave:\n"]
            for i, point in enumerate(top_points, 1):
                result.append(f"{i}. {point}")

            return "\n".join(result)

        except Exception as e:
            return f"Error extrayendo puntos clave: {e}"

    def generate_flashcards(
        self,
        text: str,
        num_cards: int = 20,
        format: str = "text",
    ) -> str:
        """Genera flashcards para estudio."""
        try:
            # Extraer oraciones con información factual
            sentences = text.replace("\n", " ").split(". ")
            sentences = [s.strip() for s in sentences if len(s.strip()) > 40]

            if len(sentences) < 5:
                return "Error: Texto muy corto para generar flashcards."

            cards = []

            for i, sentence in enumerate(sentences[:num_cards]):
                # Crear pregunta simple (placeholder - el LLM haría esto mejor)
                words = sentence.split()
                if len(words) > 5:
                    # Ocultar una parte clave
                    mid = len(words) // 2
                    question_words = words[:mid] + ["___"] + words[mid+2:]
                    answer = " ".join(words[mid:mid+2])

                    question = " ".join(question_words) + "?"
                    cards.append({"q": question, "a": answer, "full": sentence})

            if not cards:
                return "No se pudieron generar flashcards."

            # Formatear salida
            if format == "csv":
                output = ["pregunta,respuesta"]
                for card in cards:
                    output.append(f'"{card["q"]}","{card["a"]}"')
                return "\n".join(output)

            elif format == "anki":
                # Formato tab-separated para Anki
                output = []
                for card in cards:
                    output.append(f'{card["q"]}\t{card["a"]}')
                return "\n".join(output)

            else:  # text
                output = [f"📚 {len(cards)} Flashcards Generadas:\n"]
                for i, card in enumerate(cards, 1):
                    output.append(f"Card {i}:")
                    output.append(f"  Q: {card['q']}")
                    output.append(f"  A: {card['a']}")
                    output.append("")
                return "\n".join(output)

        except Exception as e:
            return f"Error generando flashcards: {e}"

    def compare_texts(self, text1: str, text2: str) -> str:
        """Compara dos textos."""
        try:
            # Estadísticas básicas
            words1 = set(text1.lower().split())
            words2 = set(text2.lower().split())

            common = words1 & words2
            only1 = words1 - words2
            only2 = words2 - words1

            similarity = len(common) / max(len(words1 | words2), 1) * 100

            result = [
                "📊 Comparación de Textos:",
                "",
                f"Texto 1: {len(text1):,} caracteres, {len(words1):,} palabras únicas",
                f"Texto 2: {len(text2):,} caracteres, {len(words2):,} palabras únicas",
                "",
                f"Similitud (Jaccard): {similarity:.1f}%",
                f"Palabras en común: {len(common):,}",
                f"Solo en texto 1: {len(only1):,}",
                f"Solo en texto 2: {len(only2):,}",
            ]

            # Mostrar algunas palabras únicas
            if only1:
                sample1 = list(only1)[:10]
                result.append(f"\nPalabras únicas texto 1: {', '.join(sample1)}...")

            if only2:
                sample2 = list(only2)[:10]
                result.append(f"Palabras únicas texto 2: {', '.join(sample2)}...")

            return "\n".join(result)

        except Exception as e:
            return f"Error comparando textos: {e}"

    def execute(self, **kwargs) -> str:
        """Ejecución directa del skill."""
        text = kwargs.get("text", "")
        file_path = kwargs.get("file")

        if file_path:
            return self.summarize_file(file_path, kwargs.get("style", "concise"))
        elif text:
            return self.summarize_text(text, kwargs.get("style", "concise"))
        else:
            return "Error: Se requiere texto o archivo para resumir"
