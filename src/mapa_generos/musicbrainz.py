"""Lista de gêneros reconhecidos pelo MusicBrainz, com cache em disco.

Fonte: https://musicbrainz.org/ws/2/genre/all?fmt=txt (um gênero por linha, minúsculas).
Usada para separar tags do Last.fm que são gênero das que não são ("2024",
"female vocalists"). Base da Fase 3.
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "data" / "cache" / "musicbrainz" / "generos.txt"
URL = "https://musicbrainz.org/ws/2/genre/all?fmt=txt"
USER_AGENT = "mapa-generos/0.0.1 (uso pessoal)"


def chave(nome: str) -> str:
    """Chave de comparação: minúsculas, sem acentos, espaços, hífens ou sublinhados.

    Assim "Hip-Hop", "hip hop" e "hiphop" viram a mesma coisa, "forro" = "forró",
    "rnb" = "r'n'b" = "r&b" e "drum & bass" = "drum and bass".
    """
    s = unicodedata.normalize("NFKD", nome.lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"\b(?:rnb|r ?n ?b|r'n'b|r and b|rhythm and blues)\b", "r&b", s)
    s = re.sub(r"\s+(?:and|n|'n')\s+", " & ", s)
    return re.sub(r"[\s\-_]+", "", s)


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


# ---------------------------------------------------------------------------
# País dos artistas
# ---------------------------------------------------------------------------
import hashlib
import json
import time

API = "https://musicbrainz.org/ws/2/"
CACHE_ARTISTAS = ROOT / "data" / "cache" / "musicbrainz" / "api"
INTERVALO = 1.5  # o MusicBrainz pede no máximo 1 req/s; folga porque ele devolve 503 quando cheio
TENTATIVAS = 8  # esperas crescentes: 2, 3, 5, 9, 17, 33, 60, 60 s
_ultima = 0.0
SO_CACHE = False  # True: não chama a rede, usa só o que já está em cache


class ErroMusicBrainz(RuntimeError):
    """Falha persistente (servidor ocupado etc.); nada é gravado em cache."""


def _get(caminho: str, **params) -> dict:
    """GET na API do MusicBrainz com cache em disco e respeito ao limite de taxa."""
    global _ultima
    params = {**params, "fmt": "json"}
    k = hashlib.sha1(json.dumps([caminho, params], sort_keys=True).encode()).hexdigest()
    arq = CACHE_ARTISTAS / caminho.strip("/").replace("/", "_") / f"{k}.json"
    if arq.exists():
        return json.loads(arq.read_text())
    if SO_CACHE:
        raise ErroMusicBrainz(f"MusicBrainz {caminho}: fora do cache (modo só-cache)")
    for tentativa in range(TENTATIVAS):
        espera = INTERVALO - (time.monotonic() - _ultima)
        if espera > 0:
            time.sleep(espera)
        try:
            resp = requests.get(API + caminho, params=params, headers={"User-Agent": USER_AGENT}, timeout=30)
        except requests.RequestException:
            _ultima = time.monotonic()
            time.sleep(min(60, 2 ** tentativa + 1))
            continue
        _ultima = time.monotonic()
        if resp.status_code in (429, 503) or resp.status_code >= 500:
            time.sleep(min(60, 2 ** tentativa + 1))
            continue
        if resp.status_code == 404:
            data = {"_404": True}
        else:
            resp.raise_for_status()
            data = resp.json()
        arq.parent.mkdir(parents=True, exist_ok=True)
        arq.write_text(json.dumps(data))
        return data
    raise ErroMusicBrainz(f"MusicBrainz {caminho}: falhou {TENTATIVAS}x (servidor ocupado?)")


def _norm(nome: str) -> str:
    """Nome para comparar: minúsculas, sem acentos e sem pontuação."""
    s = unicodedata.normalize("NFKD", nome.lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^\w]+", "", s)


def _pais(a: dict) -> str | None:
    if a.get("country"):
        return a["country"]
    area = a.get("area") or {}
    codigos = area.get("iso-3166-1-codes") or []
    return codigos[0] if codigos else None


def pais_do_artista(nome: str, spotify_id: str | None = None) -> dict:
    """Retorna {'pais': 'BR'|…|None, 'mbid', 'nome_mb', 'como'} para um artista.

    1) busca pelo nome; fica com os candidatos de nome idêntico (sem acento/pontuação);
    2) se houver mais de um com países diferentes, tenta desempatar pelo link do
       Spotify cadastrado no MusicBrainz;
    3) se o candidato não tiver país, consulta a ficha completa (área/begin-area).
    """
    vazio = {"pais": None, "mbid": None, "nome_mb": None, "como": "não encontrado"}
    q = 'artist:"' + nome.replace("\\", "\\\\").replace('"', '\\"') + '"'
    res = _get("artist", query=q, limit=10).get("artists", [])
    iguais = [a for a in res if _norm(a.get("name", "")) == _norm(nome)
              or any(_norm(al.get("name", "")) == _norm(nome) for al in a.get("aliases", []))]
    if not iguais:
        return vazio
    escolhido, como = iguais[0], "nome"
    paises = {_pais(a) for a in iguais}
    if len(iguais) > 1 and len(paises) > 1:
        como = "nome (ambíguo)"
        if spotify_id:
            u = _get("url", resource=f"https://open.spotify.com/artist/{spotify_id}", inc="artist-rels")
            ids = [r["artist"]["id"] for r in u.get("relations", []) if "artist" in r]
            achou = [a for a in iguais if a["id"] in ids]
            if achou:
                escolhido, como = achou[0], "link do Spotify"
            elif ids:
                escolhido, como = {"id": ids[0], "name": nome}, "link do Spotify"
        if como == "nome (ambíguo)":
            # homônimos com países diferentes e sem link do Spotify: não dá para confiar
            cands = sorted(p for p in paises if p)
            return {**vazio, "como": "ambíguo: " + ", ".join(cands)}
    pais = _pais(escolhido)
    if pais is None:
        ficha = _get(f"artist/{escolhido['id']}", inc="")
        pais = _pais(ficha)
        if pais is None:
            for campo in ("area", "begin-area"):
                area = ficha.get(campo) or {}
                if area.get("id"):
                    # sobe a hierarquia de áreas até achar um país
                    det = _get(f"area/{area['id']}", inc="area-rels")
                    pais = (det.get("iso-3166-1-codes") or [None])[0]
                    for r in det.get("relations", []):
                        if pais:
                            break
                        if r.get("direction") == "backward" and r.get("type") == "part of":
                            pais = (r["area"].get("iso-3166-1-codes") or [None])[0]
                if pais:
                    break
    return {"pais": pais, "mbid": escolhido["id"], "nome_mb": escolhido.get("name"), "como": como}
