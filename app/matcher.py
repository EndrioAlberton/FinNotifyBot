"""Normalizacao de texto e casamento de palavras-chave (exato + tolerante a erro)."""

import re
from typing import NamedTuple, Optional

from rapidfuzz import fuzz
from unidecode import unidecode

_NON_ALNUM = re.compile(r"[^a-z0-9]+")
_SPACES = re.compile(r"\s+")


class Match(NamedTuple):
    term: str
    term_norm: str
    kind: str   # "exato" ou "aproximado"
    score: int  # 100 para exato


def normalize(text: Optional[str]) -> str:
    """Minusculas, sem acento, sem pontuacao, espacos colapsados.

    'ARMANI-CODE!!!  Absolu' -> 'armani code absolu'
    """
    if not text:
        return ""
    lowered = unidecode(text).lower()
    cleaned = _NON_ALNUM.sub(" ", lowered)
    return _SPACES.sub(" ", cleaned).strip()


def _exact_pattern(term_norm: str) -> re.Pattern:
    """Casa 'armani code', 'armanicode' e 'armani   code'."""
    parts = [re.escape(word) for word in term_norm.split()]
    return re.compile(r"\b" + r"\s*".join(parts) + r"\b")


def _fuzzy_score(term_norm: str, text_norm: str) -> int:
    """Melhor similaridade entre o termo e janelas de palavras do texto."""
    words = text_norm.split()
    n_words = len(term_norm.split())
    best = 0
    for size in (n_words, n_words + 1):
        if size > len(words):
            continue
        for i in range(len(words) - size + 1):
            window = " ".join(words[i:i + size])
            score = fuzz.ratio(term_norm, window)
            if score > best:
                best = score
    # Tambem tenta a forma colada, para casos tipo "armanicode"
    glued = term_norm.replace(" ", "")
    for word in words:
        score = fuzz.ratio(glued, word)
        if score > best:
            best = score
    return int(best)


def find_matches(text_norm, keywords, threshold):
    """Retorna a lista de Match encontrados no texto ja normalizado.

    keywords: iteravel de linhas com as chaves 'term' e 'term_norm'.
    """
    results = []
    if not text_norm:
        return results

    for row in keywords:
        term_norm = row["term_norm"]
        if not term_norm:
            continue
        if _exact_pattern(term_norm).search(text_norm):
            results.append(Match(row["term"], term_norm, "exato", 100))
            continue
        score = _fuzzy_score(term_norm, text_norm)
        if score >= threshold:
            results.append(Match(row["term"], term_norm, "aproximado", score))
    return results
