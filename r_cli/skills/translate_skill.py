"""
Translation Skill for R CLI.

Text translation using:
- Argos Translate (offline)
- Deep Translator (online as fallback)
"""

from pathlib import Path
from typing import Optional

from r_cli.core.agent import Skill
from r_cli.core.llm import Tool


class TranslateSkill(Skill):
    """Skill for text translation."""

    name = "translate"
    description = "Text translation between languages (offline with Argos or online)"

    # Most common languages
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
                description="Translate text between languages",
                parameters={
                    "type": "object",
                    "properties": {
                        "text": {
                            "type": "string",
                            "description": "Text to translate",
                        },
                        "source_lang": {
                            "type": "string",
                            "description": "Source language (ISO code, e.g.: en, es, fr)",
                        },
                        "target_lang": {
                            "type": "string",
                            "description": "Target language (ISO code)",
                        },
                        "offline": {
                            "type": "boolean",
                            "description": "Use only offline translation (Argos)",
                        },
                    },
                    "required": ["text", "target_lang"],
                },
                handler=self.translate_text,
            ),
            Tool(
                name="detect_language",
                description="Detect the language of a text",
                parameters={
                    "type": "object",
                    "properties": {
                        "text": {
                            "type": "string",
                            "description": "Text to detect language",
                        },
                    },
                    "required": ["text"],
                },
                handler=self.detect_language,
            ),
            Tool(
                name="list_languages",
                description="List available languages for translation",
                parameters={
                    "type": "object",
                    "properties": {
                        "installed_only": {
                            "type": "boolean",
                            "description": "Show only installed languages (Argos)",
                        },
                    },
                },
                handler=self.list_languages,
            ),
            Tool(
                name="translate_file",
                description="Translate the content of a text file",
                parameters={
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "Path to file to translate",
                        },
                        "target_lang": {
                            "type": "string",
                            "description": "Target language",
                        },
                        "source_lang": {
                            "type": "string",
                            "description": "Source language (auto-detected if not specified)",
                        },
                    },
                    "required": ["file_path", "target_lang"],
                },
                handler=self.translate_file,
            ),
        ]

    def _translate_with_argos(self, text: str, source: str, target: str) -> tuple[bool, str]:
        """Try to translate with Argos Translate."""
        try:
            import argostranslate.package
            import argostranslate.translate

            # Get installed languages
            installed_languages = argostranslate.translate.get_installed_languages()

            source_lang = None
            target_lang = None

            for lang in installed_languages:
                if lang.code == source:
                    source_lang = lang
                if lang.code == target:
                    target_lang = lang

            if not source_lang or not target_lang:
                return False, "Languages not installed in Argos"

            # Find translation
            translation = source_lang.get_translation(target_lang)
            if not translation:
                return False, f"No translation installed from {source} to {target}"

            result = translation.translate(text)
            return True, result

        except ImportError:
            return False, "Argos Translate not installed"
        except Exception as e:
            return False, str(e)

    def _translate_with_deep_translator(
        self, text: str, source: str, target: str
    ) -> tuple[bool, str]:
        """Try to translate with Deep Translator (online)."""
        try:
            from deep_translator import GoogleTranslator

            translator = GoogleTranslator(source=source, target=target)

            # Split long text into chunks
            max_chars = 4500
            if len(text) > max_chars:
                chunks = [text[i : i + max_chars] for i in range(0, len(text), max_chars)]
                results = [translator.translate(chunk) for chunk in chunks]
                return True, "".join(results)

            result = translator.translate(text)
            return True, result

        except ImportError:
            return False, "deep-translator not installed"
        except Exception as e:
            return False, str(e)

    def translate_text(
        self,
        text: str,
        target_lang: str,
        source_lang: str = "auto",
        offline: bool = False,
    ) -> str:
        """Translate text."""
        if not text.strip():
            return "Error: Empty text"

        # Normalize language codes
        target = target_lang.lower()[:2]
        source = source_lang.lower()[:2] if source_lang != "auto" else "auto"

        # Try Argos first if available
        if source != "auto":
            success, result = self._translate_with_argos(text, source, target)
            if success:
                return f"[Argos - Offline]\n\n{result}"

        # If offline forced and Argos failed
        if offline:
            return "Error: Offline translation not available. Install Argos Translate:\n  pip install argostranslate\n  argos-translate-gui  # To download language packages"

        # Try Deep Translator (online)
        if source == "auto":
            source = "auto"

        success, result = self._translate_with_deep_translator(text, source, target)
        if success:
            return f"[Google Translate - Online]\n\n{result}"

        return f"Error: Could not translate. {result}\n\nInstall a translation library:\n  pip install deep-translator  # Online\n  pip install argostranslate   # Offline"

    def detect_language(self, text: str) -> str:
        """Detect the language of text."""
        if not text.strip():
            return "Error: Empty text"

        try:
            from langdetect import detect, detect_langs

            # Detect main language
            lang_code = detect(text)

            # Get probabilities
            probabilities = detect_langs(text)

            result = [f"Detected language: {lang_code}"]

            if lang_code in self.COMMON_LANGUAGES:
                result[0] += f" ({self.COMMON_LANGUAGES[lang_code]})"

            result.append("\nProbabilities:")
            for prob in probabilities[:5]:
                lang_name = self.COMMON_LANGUAGES.get(prob.lang, prob.lang)
                result.append(f"  {prob.lang} ({lang_name}): {prob.prob:.1%}")

            return "\n".join(result)

        except ImportError:
            # Simple character-based fallback
            return self._simple_detect(text)
        except Exception as e:
            return f"Error detecting language: {e}"

    def _simple_detect(self, text: str) -> str:
        """Simple character-based detection."""
        # Count character types
        latin = sum(1 for c in text if c.isalpha() and ord(c) < 256)
        cyrillic = sum(1 for c in text if "\u0400" <= c <= "\u04ff")
        chinese = sum(1 for c in text if "\u4e00" <= c <= "\u9fff")
        japanese = sum(1 for c in text if "\u3040" <= c <= "\u30ff")
        korean = sum(1 for c in text if "\uac00" <= c <= "\ud7af")
        arabic = sum(1 for c in text if "\u0600" <= c <= "\u06ff")

        max_count = max(latin, cyrillic, chinese, japanese, korean, arabic)

        if max_count == 0:
            return "Could not detect language"

        if max_count == chinese:
            return "Detected language: zh (Chinese)"
        elif max_count == japanese:
            return "Detected language: ja (Japanese)"
        elif max_count == korean:
            return "Detected language: ko (Korean)"
        elif max_count == cyrillic:
            return "Detected language: ru (Russian/Cyrillic)"
        elif max_count == arabic:
            return "Detected language: ar (Arabic)"
        else:
            return "Detected language: Latin alphabet (install langdetect for better accuracy)"

    def list_languages(self, installed_only: bool = False) -> str:
        """List available languages."""
        result = ["Available languages:\n"]

        if installed_only:
            try:
                import argostranslate.translate

                installed = argostranslate.translate.get_installed_languages()

                if not installed:
                    return "No languages installed in Argos Translate.\n\nInstall packages:\n  argos-translate-gui"

                result.append("Installed languages (Argos - Offline):\n")
                for lang in installed:
                    result.append(f"  {lang.code}: {lang.name}")

                return "\n".join(result)

            except ImportError:
                return (
                    "Argos Translate not installed.\n\nInstall with:\n  pip install argostranslate"
                )

        # Show common languages
        result.append("Common supported languages:\n")
        for code, name in sorted(self.COMMON_LANGUAGES.items()):
            result.append(f"  {code}: {name}")

        result.append("\n\nFor offline translation, install Argos Translate:")
        result.append("  pip install argostranslate")
        result.append("  argos-translate-gui  # To download packages")

        return "\n".join(result)

    def translate_file(
        self,
        file_path: str,
        target_lang: str,
        source_lang: Optional[str] = None,
    ) -> str:
        """Translate the content of a file."""
        try:
            path = Path(file_path).expanduser()

            if not path.exists():
                return f"Error: File not found: {file_path}"

            # Check size
            if path.stat().st_size > 1_000_000:  # 1MB
                return "Error: File too large (>1MB)"

            # Read file
            with open(path, encoding="utf-8", errors="replace") as f:
                text = f.read()

            # Translate
            source = source_lang or "auto"
            result = self.translate_text(text, target_lang, source)

            # Save result
            output_path = path.parent / f"{path.stem}_{target_lang}{path.suffix}"

            # Extract only translated text (without header)
            translated_text = result
            if result.startswith("["):
                lines = result.split("\n", 2)
                if len(lines) > 2:
                    translated_text = lines[2]

            with open(output_path, "w", encoding="utf-8") as f:
                f.write(translated_text)

            return f"Translated file saved to: {output_path}"

        except Exception as e:
            return f"Error translating file: {e}"

    def execute(self, **kwargs) -> str:
        """Direct skill execution."""
        action = kwargs.get("action", "translate")

        if action == "translate":
            text = kwargs.get("text", "")
            target = kwargs.get("target", "")
            if not text or not target:
                return "Error: text and target required"
            return self.translate_text(text, target, kwargs.get("source", "auto"))
        elif action == "detect":
            return self.detect_language(kwargs.get("text", ""))
        elif action == "languages":
            return self.list_languages(kwargs.get("installed", False))
        else:
            return f"Unrecognized action: {action}"
