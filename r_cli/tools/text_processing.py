"""
Utilidades de procesamiento de texto.
"""

import re
from typing import Optional


def chunk_text(
    text: str,
    chunk_size: int = 2000,
    overlap: int = 200,
    separator: Optional[str] = None,
) -> list[str]:
    """
    Divide texto en chunks con overlap.

    Args:
        text: Texto a dividir
        chunk_size: Tamaño máximo de cada chunk
        overlap: Solapamiento entre chunks
        separator: Separador preferido (default: párrafo o oración)

    Returns:
        Lista de chunks
    """
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0

    while start < len(text):
        end = start + chunk_size

        if end < len(text):
            # Buscar mejor punto de corte
            chunk = text[start:end]

            # Intentar cortar en párrafo
            last_para = chunk.rfind("\n\n")
            if last_para > chunk_size // 2:
                end = start + last_para + 2
            else:
                # Intentar cortar en oración
                last_sentence = max(
                    chunk.rfind(". "),
                    chunk.rfind("? "),
                    chunk.rfind("! "),
                )
                if last_sentence > chunk_size // 2:
                    end = start + last_sentence + 2

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        start = end - overlap

    return chunks


def extract_sentences(text: str, min_length: int = 10) -> list[str]:
    """
    Extrae oraciones de un texto.

    Args:
        text: Texto a procesar
        min_length: Longitud mínima de oración

    Returns:
        Lista de oraciones
    """
    # Limpiar texto
    text = text.replace("\n", " ").replace("\r", " ")
    text = re.sub(r"\s+", " ", text)

    # Dividir por puntos, signos de interrogación y exclamación
    # Pero mantener abreviaciones comunes
    pattern = r'(?<=[.!?])\s+(?=[A-ZÁÉÍÓÚ])'
    sentences = re.split(pattern, text)

    # Filtrar y limpiar
    result = []
    for s in sentences:
        s = s.strip()
        if len(s) >= min_length:
            result.append(s)

    return result


def word_count(text: str) -> dict:
    """
    Cuenta palabras y estadísticas de texto.

    Returns:
        Dict con: words, chars, sentences, paragraphs, avg_word_length
    """
    words = text.split()
    sentences = extract_sentences(text)
    paragraphs = [p for p in text.split("\n\n") if p.strip()]

    avg_word_len = sum(len(w) for w in words) / max(len(words), 1)

    return {
        "words": len(words),
        "chars": len(text),
        "chars_no_spaces": len(text.replace(" ", "").replace("\n", "")),
        "sentences": len(sentences),
        "paragraphs": len(paragraphs),
        "avg_word_length": round(avg_word_len, 1),
    }


def find_keywords(text: str, top_n: int = 10) -> list[tuple[str, int]]:
    """
    Encuentra las palabras clave más frecuentes.

    Args:
        text: Texto a analizar
        top_n: Número de keywords a retornar

    Returns:
        Lista de (palabra, frecuencia)
    """
    # Stopwords básicos en español e inglés
    stopwords = {
        "el", "la", "los", "las", "un", "una", "unos", "unas",
        "de", "del", "a", "al", "en", "con", "por", "para",
        "que", "y", "o", "es", "son", "fue", "ser", "como",
        "se", "su", "sus", "le", "les", "lo", "nos", "me",
        "the", "a", "an", "of", "to", "in", "is", "are", "was",
        "for", "on", "with", "as", "it", "be", "this", "that",
        "and", "or", "not", "but", "from", "by", "at", "have",
    }

    # Extraer palabras
    words = re.findall(r'\b[a-záéíóúüñ]+\b', text.lower())

    # Contar frecuencias
    freq = {}
    for word in words:
        if word not in stopwords and len(word) > 3:
            freq[word] = freq.get(word, 0) + 1

    # Ordenar y retornar top N
    sorted_words = sorted(freq.items(), key=lambda x: x[1], reverse=True)
    return sorted_words[:top_n]


def clean_text(text: str) -> str:
    """
    Limpia texto: normaliza espacios, elimina caracteres extraños.
    """
    # Normalizar saltos de línea
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Eliminar espacios múltiples
    text = re.sub(r" +", " ", text)

    # Eliminar líneas con solo espacios
    lines = [line.strip() for line in text.split("\n")]
    text = "\n".join(lines)

    # Reducir saltos de línea múltiples a máximo 2
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def truncate_text(text: str, max_length: int = 1000, suffix: str = "...") -> str:
    """
    Trunca texto a longitud máxima, cortando en palabra.
    """
    if len(text) <= max_length:
        return text

    truncated = text[:max_length]

    # Cortar en última palabra completa
    last_space = truncated.rfind(" ")
    if last_space > max_length // 2:
        truncated = truncated[:last_space]

    return truncated.rstrip() + suffix
