"""Cliente mínimo do Last.fm com cache em disco.

Classificação por faixa: tenta as tags da faixa, depois do álbum, depois do artista.
Cada resultado guarda de qual nível veio, para medir cobertura depois.

Dois níveis de cache:
- em disco (data/cache/lastfm/<método>/<sha1>.json): toda resposta, inclusive "não encontrado";
- em memória (lru_cache): álbum e artista, que se repetem entre faixas.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from functools import lru_cache
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

API_URL = "https://ws.audioscrobbler.com/2.0/"
CACHE_DIR = ROOT / "data" / "cache" / "lastfm"
MIN_INTERVAL = 0.25  # segundos entre chamadas (~4/s, abaixo do limite de 5/s)
MIN_TAGS = 1  # nº mínimo de tags para aceitar um nível sem cair para o próximo
TENTATIVAS = 4
ERROS_TEMPORARIOS = {8, 11, 16, 29}  # falha interna, serviço offline, temporário, limite de taxa

_last_call = 0.0


class ErroLastfm(RuntimeError):
    """Erro que não deve ser gravado em cache (a faixa será tentada de novo)."""


def _chave_api() -> str:
    chave = os.environ.get("LASTFM_API_KEY", "").strip()
    if not chave:
        raise ErroLastfm("LASTFM_API_KEY vazia: preencha o .env (modelo em .env.example)")
    return chave


def _caminho_cache(method: str, params: dict) -> Path:
    key = hashlib.sha1(json.dumps([method, params], sort_keys=True).encode()).hexdigest()
    return CACHE_DIR / method / f"{key}.json"


def _call(method: str, **params) -> dict:
    """Chama a API do Last.fm, usando cache em disco quando possível."""
    global _last_call
    params = {k: v for k, v in params.items() if v}
    path = _caminho_cache(method, params)
    if path.exists():
        return json.loads(path.read_text())

    ultimo_erro: Exception | None = None
    for tentativa in range(TENTATIVAS):
        wait = MIN_INTERVAL - (time.monotonic() - _last_call)
        if wait > 0:
            time.sleep(wait)
        try:
            resp = requests.get(
                API_URL,
                params={
                    "method": method,
                    "api_key": _chave_api(),
                    "format": "json",
                    "autocorrect": 1,
                    **params,
                },
                timeout=20,
            )
            _last_call = time.monotonic()
            if resp.status_code >= 500 or resp.status_code == 429:
                raise ErroLastfm(f"HTTP {resp.status_code}")
            data = resp.json()
        except (requests.RequestException, ValueError, ErroLastfm) as e:
            if isinstance(e, ErroLastfm) and "LASTFM_API_KEY" in str(e):
                raise
            ultimo_erro = e
            time.sleep(2 ** tentativa)
            continue

        erro = data.get("error")
        if erro in ERROS_TEMPORARIOS:
            ultimo_erro = ErroLastfm(f"Last.fm {method}: erro {erro} ({data.get('message')})")
            time.sleep(2 ** tentativa)
            continue
        # Erro 6 = "não encontrado": guarda em cache também, para não repetir a chamada.
        if erro is not None and erro != 6:
            raise ErroLastfm(f"Last.fm {method}: erro {erro} ({data.get('message')})")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data))
        return data

    raise ErroLastfm(f"Last.fm {method}: falhou {TENTATIVAS}x ({ultimo_erro})")


def _parse_tags(data: dict) -> list[tuple[str, int]]:
    tags = data.get("toptags", {}).get("tag", [])
    if isinstance(tags, dict):  # a API devolve objeto quando há só uma tag
        tags = [tags]
    return [(t["name"], int(t.get("count", 0))) for t in tags]


def tags_faixa(artista: str, faixa: str) -> list[tuple[str, int]]:
    return _parse_tags(_call("track.getTopTags", artist=artista, track=faixa))


@lru_cache(maxsize=None)
def tags_album(artista: str, album: str) -> tuple[tuple[str, int], ...]:
    return tuple(_parse_tags(_call("album.getTopTags", artist=artista, album=album)))


@lru_cache(maxsize=None)
def tags_artista(artista: str) -> tuple[tuple[str, int], ...]:
    return tuple(_parse_tags(_call("artist.getTopTags", artist=artista)))


def tags_da_faixa(
    artista: str, faixa: str, album: str | None = None, artista_album: str | None = None
) -> dict:
    """Retorna {'nivel': 'faixa'|'album'|'artista'|None, 'tags': [(nome, contagem), ...]}.

    `artista_album` (opcional) é usado na busca do álbum; se faltar, usa `artista`.
    """
    tags = tags_faixa(artista, faixa)
    if len(tags) >= MIN_TAGS:
        return {"nivel": "faixa", "tags": list(tags)}
    if album:
        tags = tags_album(artista_album or artista, album)
        if len(tags) >= MIN_TAGS:
            return {"nivel": "album", "tags": list(tags)}
    tags = tags_artista(artista)
    if len(tags) >= MIN_TAGS:
        return {"nivel": "artista", "tags": list(tags)}
    return {"nivel": None, "tags": []}


if __name__ == "__main__":
    # Teste rápido: python -m mapa_generos.lastfm
    print(tags_da_faixa("Beyoncé", "TEXAS HOLD 'EM", "COWBOY CARTER"))
