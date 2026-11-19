"""Cliente mínimo do Last.fm com cache em disco.

Classificação por faixa: tenta as tags da faixa, depois do álbum, depois do artista.
Cada resultado guarda de qual nível veio, para medir cobertura depois.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

API_URL = "https://ws.audioscrobbler.com/2.0/"
CACHE_DIR = Path(__file__).resolve().parents[2] / "data" / "cache" / "lastfm"
MIN_INTERVAL = 0.25  # segundos entre chamadas (~4/s, abaixo do limite de 5/s)
MIN_TAGS = 1  # nº mínimo de tags para aceitar um nível sem cair para o próximo

_last_call = 0.0


def _call(method: str, **params) -> dict:
    """Chama a API do Last.fm, usando cache em disco quando possível."""
    global _last_call
    params = {k: v for k, v in params.items() if v}
    key = hashlib.sha1(json.dumps([method, params], sort_keys=True).encode()).hexdigest()
    path = CACHE_DIR / method / f"{key}.json"
    if path.exists():
        return json.loads(path.read_text())

    wait = MIN_INTERVAL - (time.monotonic() - _last_call)
    if wait > 0:
        time.sleep(wait)
    resp = requests.get(
        API_URL,
        params={
            "method": method,
            "api_key": os.environ["LASTFM_API_KEY"],
            "format": "json",
            "autocorrect": 1,
            **params,
        },
        timeout=20,
    )
    _last_call = time.monotonic()
    resp.raise_for_status()
    data = resp.json()

    # Erro 6 = "não encontrado": guarda em cache também, para não repetir a chamada.
    if "error" in data and data["error"] != 6:
        raise RuntimeError(f"Last.fm {method}: {data}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))
    return data


def _parse_tags(data: dict) -> list[tuple[str, int]]:
    tags = data.get("toptags", {}).get("tag", [])
    if isinstance(tags, dict):  # a API devolve objeto quando há só uma tag
        tags = [tags]
    return [(t["name"], int(t.get("count", 0))) for t in tags]


def tags_da_faixa(artista: str, faixa: str, album: str | None = None) -> dict:
    """Retorna {'nivel': 'faixa'|'album'|'artista'|None, 'tags': [(nome, contagem), ...]}."""
    niveis = [
        ("faixa", "track.getTopTags", {"artist": artista, "track": faixa}),
        ("album", "album.getTopTags", {"artist": artista, "album": album}),
        ("artista", "artist.getTopTags", {"artist": artista}),
    ]
    for nivel, metodo, params in niveis:
        if nivel == "album" and not album:
            continue
        tags = _parse_tags(_call(metodo, **params))
        if len(tags) >= MIN_TAGS:
            return {"nivel": nivel, "tags": tags}
    return {"nivel": None, "tags": []}


if __name__ == "__main__":
    # Teste rápido: python -m mapa_generos.lastfm
    print(tags_da_faixa("Beyoncé", "TEXAS HOLD 'EM", "COWBOY CARTER"))
