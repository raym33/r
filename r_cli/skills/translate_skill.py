"""
Skill de Traducción para R CLI.

Traducción de texto usando:
- Argos Translate (offline)
- Deep Translator (online como fallback)
"""

from pathlib import Path
from typing import Optional

from r_cli.core.agent import Skill
from r_cli.core.llm import Tool


class TranslateSkill(Skill):
    """Skill para traducción de texto."""

    name = "translate"
    description = "Traducción de texto entre idiomas (offline con Argos o online)"

    # Idiomas más comunes
    COMMON_LANGUAGES = {
        "en": "English",
        "es": "Spanish",
        "fr": "French",
        "de": "German",
        "it": "Italian",
        "pt": "Portuguese",
        "ru": "Russian",
        "zh": "Chinese",
        "ja": "Japanese",
        "ko": "Korean",
        "ar": "Arabic",
        "hi": "Hindi",
    }

    def get_tools(self) -> list[Tool]:
        return [
            Tool(
                name="translate_text",
                description="Traduce texto entre idiomas",
                parameters={
                    "type": "object",
                    "properties": {
                        "text": {
                            "type": "string",
                            "description": "Texto a traducir",
                        },
                        "source_lang": {
                            "type": "string",
                            "description": "Idioma origen (código ISO, ej: en, es, fr)",
                        },
                        "target_lang": {
                            "type": "string",
                            "description": "Idioma destino (código ISO)",
                        },
                        "offline": {
                            "type": "boolean",
                            "description": "Usar solo traducción offline (Argos)",
                        },
                    },
                    "required": ["text", "target_lang"],
                },
                handler=self.translate_text,
            ),
            Tool(
                name="detect_language",
                description="Detecta el idioma de un texto",
                parameters={
                    "type": "object",
                    "properties": {
                        "text": {
                            "type": "string",
                            "description": "Texto para detectar idioma",
                        },
                    },
                    "required": ["text"],
                },
                handler=self.detect_language,
            ),
            Tool(
                name="list_languages",
                description="Lista los idiomas disponibles para traducción",
                parameters={
                    "type": "object",
                    "properties": {
                        "installed_only": {
                            "type": "boolean",
                            "description": "Mostrar solo idiomas instalados (Argos)",
                        },
                    },
                },
                handler=self.list_languages,
            ),
            Tool(
                name="translate_file",
                description="Traduce el contenido de un archivo de texto",
                parameters={
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "Ruta del archivo a traducir",
                        },
                        "target_lang": {
                            "type": "string",
                            "description": "Idioma destino",
                        },
                        "source_lang": {
                            "type": "string",
                            "description": "Idioma origen (auto-detectado si no se especifica)",
                        },
                    },
                    "required": ["file_path", "target_lang"],
                },
                handler=self.translate_file,
            ),
        ]

    def _translate_with_argos(self, text: str, source: str, target: str) -> tuple[bool, str]:
        """Intenta traducir con Argos Translate."""
        try:
            import argostranslate.package
            import argostranslate.translate

            # Obtener idiomas instalados
            installed_languages = argostranslate.translate.get_installed_languages()

            source_lang = None
            target_lang = None

            for lang in installed_languages:
                if lang.code == source:
                    source_lang = lang
                if lang.code == target:
                    target_lang = lang

            if not source_lang or not target_lang:
                return False, "Idiomas no instalados en Argos"

            # Buscar traducción
            translation = source_lang.get_translation(target_lang)
            if not translation:
                return False, f"No hay traducción instalada de {source} a {target}"

            result = translation.translate(text)
            return True, result

        except ImportError:
            return False, "Argos Translate no instalado"
        except Exception as e:
            return False, str(e)

    def _translate_with_deep_translator(
        self, text: str, source: str, target: str
    ) -> tuple[bool, str]:
        """Intenta traducir con Deep Translator (online)."""
        try:
            from deep_translator import GoogleTranslator

            translator = GoogleTranslator(source=source, target=target)

            # Dividir texto largo en chunks
            max_chars = 4500
            if len(text) > max_chars:
                chunks = [text[i : i + max_chars] for i in range(0, len(text), max_chars)]
                results = [translator.translate(chunk) for chunk in chunks]
                return True, "".join(results)

            result = translator.translate(text)
            return True, result

        except ImportError:
            return False, "deep-translator no instalado"
        except Exception as e:
            return False, str(e)

    def translate_text(
        self,
        text: str,
        target_lang: str,
        source_lang: str = "auto",
        offline: bool = False,
    ) -> str:
        """Traduce texto."""
        if not text.strip():
            return "Error: Texto vacío"

        # Normalizar códigos de idioma
        target = target_lang.lower()[:2]
        source = source_lang.lower()[:2] if source_lang != "auto" else "auto"

        # Intentar con Argos primero si está disponible
        if source != "auto":
            success, result = self._translate_with_argos(text, source, target)
            if success:
                return f"[Argos - Offline]\n\n{result}"

        # Si offline forzado y Argos falló
        if offline:
            return "Error: Traducción offline no disponible. Instala Argos Translate:\n  pip install argostranslate\n  argos-translate-gui  # Para descargar paquetes de idiomas"

        # Intentar con Deep Translator (online)
        if source == "auto":
            source = "auto"

        success, result = self._translate_with_deep_translator(text, source, target)
        if success:
            return f"[Google Translate - Online]\n\n{result}"

        return f"Error: No se pudo traducir. {result}\n\nInstala una librería de traducción:\n  pip install deep-translator  # Online\n  pip install argostranslate   # Offline"

    def detect_language(self, text: str) -> str:
        """Detecta el idioma del texto."""
        if not text.strip():
            return "Error: Texto vacío"

        try:
            from langdetect import detect, detect_langs

            # Detectar idioma principal
            lang_code = detect(text)

            # Obtener probabilidades
            probabilities = detect_langs(text)

            result = [f"Idioma detectado: {lang_code}"]

            if lang_code in self.COMMON_LANGUAGES:
                result[0] += f" ({self.COMMON_LANGUAGES[lang_code]})"

            result.append("\nProbabilidades:")
            for prob in probabilities[:5]:
                lang_name = self.COMMON_LANGUAGES.get(prob.lang, prob.lang)
                result.append(f"  {prob.lang} ({lang_name}): {prob.prob:.1%}")

            return "\n".join(result)

        except ImportError:
            # Fallback simple basado en caracteres
            return self._simple_detect(text)
        except Exception as e:
            return f"Error detectando idioma: {e}"

    def _simple_detect(self, text: str) -> str:
        """Detección simple basada en caracteres."""
        # Contar tipos de caracteres
        latin = sum(1 for c in text if c.isalpha() and ord(c) < 256)
        cyrillic = sum(1 for c in text if "\u0400" <= c <= "\u04ff")
        chinese = sum(1 for c in text if "\u4e00" <= c <= "\u9fff")
        japanese = sum(1 for c in text if "\u3040" <= c <= "\u30ff")
        korean = sum(1 for c in text if "\uac00" <= c <= "\ud7af")
        arabic = sum(1 for c in text if "\u0600" <= c <= "\u06ff")

        max_count = max(latin, cyrillic, chinese, japanese, korean, arabic)

        if max_count == 0:
            return "No se pudo detectar el idioma"

        if max_count == chinese:
            return "Idioma detectado: zh (Chinese)"
        elif max_count == japanese:
            return "Idioma detectado: ja (Japanese)"
        elif max_count == korean:
            return "Idioma detectado: ko (Korean)"
        elif max_count == cyrillic:
            return "Idioma detectado: ru (Russian/Cyrillic)"
        elif max_count == arabic:
            return "Idioma detectado: ar (Arabic)"
        else:
            return "Idioma detectado: Alfabeto latino (instala langdetect para mejor precisión)"

    def list_languages(self, installed_only: bool = False) -> str:
        """Lista idiomas disponibles."""
        result = ["🌐 Idiomas disponibles:\n"]

        if installed_only:
            try:
                import argostranslate.translate

                installed = argostranslate.translate.get_installed_languages()

                if not installed:
                    return "No hay idiomas instalados en Argos Translate.\n\nInstala paquetes:\n  argos-translate-gui"

                result.append("Idiomas instalados (Argos - Offline):\n")
                for lang in installed:
                    result.append(f"  {lang.code}: {lang.name}")

                return "\n".join(result)

            except ImportError:
                return "Argos Translate no instalado.\n\nInstala con:\n  pip install argostranslate"

        # Mostrar idiomas comunes
        result.append("Idiomas comunes soportados:\n")
        for code, name in sorted(self.COMMON_LANGUAGES.items()):
            result.append(f"  {code}: {name}")

        result.append("\n\nPara traducción offline, instala Argos Translate:")
        result.append("  pip install argostranslate")
        result.append("  argos-translate-gui  # Para descargar paquetes")

        return "\n".join(result)

    def translate_file(
        self,
        file_path: str,
        target_lang: str,
        source_lang: Optional[str] = None,
    ) -> str:
        """Traduce el contenido de un archivo."""
        try:
            path = Path(file_path).expanduser()

            if not path.exists():
                return f"Error: Archivo no encontrado: {file_path}"

            # Verificar tamaño
            if path.stat().st_size > 1_000_000:  # 1MB
                return "Error: Archivo demasiado grande (>1MB)"

            # Leer archivo
            with open(path, encoding="utf-8", errors="replace") as f:
                text = f.read()

            # Traducir
            source = source_lang or "auto"
            result = self.translate_text(text, target_lang, source)

            # Guardar resultado
            output_path = path.parent / f"{path.stem}_{target_lang}{path.suffix}"

            # Extraer solo el texto traducido (sin el encabezado)
            translated_text = result
            if result.startswith("["):
                lines = result.split("\n", 2)
                if len(lines) > 2:
                    translated_text = lines[2]

            with open(output_path, "w", encoding="utf-8") as f:
                f.write(translated_text)

            return f"✅ Archivo traducido guardado en: {output_path}"

        except Exception as e:
            return f"Error traduciendo archivo: {e}"

    def execute(self, **kwargs) -> str:
        """Ejecución directa del skill."""
        action = kwargs.get("action", "translate")

        if action == "translate":
            text = kwargs.get("text", "")
            target = kwargs.get("target", "")
            if not text or not target:
                return "Error: Se requiere text y target"
            return self.translate_text(text, target, kwargs.get("source", "auto"))
        elif action == "detect":
            return self.detect_language(kwargs.get("text", ""))
        elif action == "languages":
            return self.list_languages(kwargs.get("installed", False))
        else:
            return f"Acción no reconocida: {action}"
