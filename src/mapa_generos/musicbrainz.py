"""Lista de gêneros reconhecidos pelo MusicBrainz, com cache em disco.

Fonte: https://musicbrainz.org/ws/2/genre/all?fmt=txt (um gênero por linha, minúsculas).
Usada para separar tags do Last.fm que são gênero das que não são ("2024",
"female vocalists"). Base da Fase 3.
"""

from __future__ import annotations

import re
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "data" / "cache" / "musicbrainz" / "generos.txt"
URL = "https://musicbrainz.org/ws/2/genre/all?fmt=txt"
USER_AGENT = "mapa-generos/0.0.1 (uso pessoal)"


def chave(nome: str) -> str:
    """Chave de comparação: minúsculas, sem espaços, hífens ou sublinhados.

    Assim "Hip-Hop", "hip hop" e "hiphop" viram a mesma coisa.
    """
    return re.sub(r"[\s\-_]+", "", nome.lower())


def generos_musicbrainz(atualizar: bool = False) -> list[str]:
    if atualizar or not CACHE.exists():
        resp = requests.get(URL, headers={"User-Agent": USER_AGENT}, timeout=30)
        resp.raise_for_status()
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        CACHE.write_text(resp.text)
    return [linha.strip() for linha in CACHE.read_text().splitlines() if linha.strip()]


def mapa_canonico() -> dict[str, str]:
    """chave → nome canônico do MusicBrainz."""
    return {chave(g): g for g in generos_musicbrainz()}
