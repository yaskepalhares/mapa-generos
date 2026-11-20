"""País de artistas pelo Wikidata, casando pelo ID de artista do Spotify (P1902).

Uma consulta SPARQL resolve até LOTE artistas de uma vez, sem ambiguidade de nome.
Países (código ISO, P297) vêm de: país de origem (P495), local de formação (P740 → país),
cidadania (P27) e local de nascimento (P19 → país). Junta todos.

Cache: data/cache/wikidata/paises.json, {spotify_id: [códigos ISO]} ([] = consultado e
sem país no Wikidata). Só IDs fora do cache vão para a rede.

Teste (20/11/2026): nos 617 artistas antigos com país no Wikidata, 100% de concordância
com a revisão de artistas_brasileiros.xlsx (58 BR, 559 não); cobertura 56% dos artistas,
mas só 58 de 225 brasileiros — por isso o MusicBrainz continua como reserva.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "data" / "cache" / "wikidata" / "paises.json"
URL = "https://query.wikidata.org/sparql"
LOTE = 200
CABECALHO = {"User-Agent": "mapa-generos/0.1 (projeto pessoal)"}
SO_CACHE = False  # True: não chama a rede

CONSULTA = """SELECT DISTINCT ?sid ?iso WHERE {
  VALUES ?sid { %s }
  ?item wdt:P1902 ?sid .
  { ?item wdt:P495 ?pais } UNION { ?item wdt:P27 ?pais } UNION
  { ?item wdt:P740 ?l . ?l wdt:P17 ?pais } UNION { ?item wdt:P19 ?l . ?l wdt:P17 ?pais }
  ?pais wdt:P297 ?iso .
}"""


class ErroWikidata(RuntimeError):
    pass


def _ler_cache() -> dict[str, list[str]]:
    return json.loads(CACHE.read_text()) if CACHE.exists() else {}


def _consultar(ids: list[str]) -> dict[str, list[str]]:
    q = CONSULTA % " ".join(json.dumps(i) for i in ids)
    for tentativa in range(5):
        try:
            r = requests.post(URL, data={"query": q, "format": "json"}, headers=CABECALHO, timeout=120)
        except requests.RequestException:
            time.sleep(2 ** tentativa)
            continue
        if r.status_code in (429, 500, 502, 503, 504):
            time.sleep(int(r.headers.get("Retry-After", 2 ** tentativa)))
            continue
        r.raise_for_status()
        res: dict[str, set[str]] = {i: set() for i in ids}
        for b in r.json()["results"]["bindings"]:
            res[b["sid"]["value"]].add(b["iso"]["value"].upper())
        return {k: sorted(v) for k, v in res.items()}
    raise ErroWikidata(f"Wikidata não respondeu ({len(ids)} artistas)")


def paises(spotify_ids) -> dict[str, list[str]]:
    """{spotify_id: [códigos ISO]} para os IDs pedidos (com cache)."""
    cache = _ler_cache()
    faltam = sorted({i for i in spotify_ids if isinstance(i, str) and i and i not in cache})
    if faltam and not SO_CACHE:
        for k in range(0, len(faltam), LOTE):
            cache.update(_consultar(faltam[k:k + LOTE]))
            CACHE.parent.mkdir(parents=True, exist_ok=True)
            CACHE.write_text(json.dumps(cache, ensure_ascii=False, sort_keys=True))
            time.sleep(1)
    return {i: cache[i] for i in spotify_ids if i in cache}


# ---------------------------------------------------------------- pela Wikipédia em português

CACHE_PTWIKI = ROOT / "data" / "cache" / "wikidata" / "ptwiki_nomes.json"
LOTE_NOMES = 80

# Página da pt.wikipedia com o título exato = nome do artista, ligada a um item que é
# músico/banda (desambiguações e outras coisas com o mesmo nome ficam de fora).
CONSULTA_PTWIKI = """SELECT ?nome ?iso ?musico WHERE {
  VALUES ?nome { %s }
  ?art schema:isPartOf <https://pt.wikipedia.org/> ; schema:name ?nome ; schema:about ?it .
  FILTER NOT EXISTS { ?it wdt:P31 wd:Q4167410 }
  OPTIONAL { { ?it wdt:P495 ?p } UNION { ?it wdt:P27 ?p } UNION
             { ?it wdt:P740 ?l . ?l wdt:P17 ?p } UNION { ?it wdt:P19 ?l . ?l wdt:P17 ?p }
             ?p wdt:P297 ?iso }
  BIND(EXISTS { { ?it wdt:P31/wdt:P279* wd:Q215380 } UNION { ?it wdt:P106/wdt:P279* wd:Q639669 }
                UNION { ?it wdt:P106 ?o . VALUES ?o { wd:Q177220 wd:Q753110 wd:Q2252262 wd:Q130857
                                                      wd:Q183945 wd:Q855091 wd:Q36834 } } } AS ?musico)
}"""


def _consultar_nomes(nomes: list[str]) -> dict[str, list[str]]:
    q = CONSULTA_PTWIKI % " ".join(json.dumps(n) + "@pt" for n in nomes)
    for tentativa in range(5):
        try:
            r = requests.post(URL, data={"query": q, "format": "json"}, headers=CABECALHO, timeout=180)
        except requests.RequestException:
            time.sleep(2 ** tentativa)
            continue
        if r.status_code in (429, 500, 502, 503, 504):
            time.sleep(int(r.headers.get("Retry-After", 2 ** tentativa)))
            continue
        r.raise_for_status()
        paises_: dict[str, set[str]] = {n: set() for n in nomes}
        musico: dict[str, bool] = {}
        for b in r.json()["results"]["bindings"]:
            n = b["nome"]["value"]
            musico[n] = musico.get(n, False) or b["musico"]["value"] == "true"
            if "iso" in b:
                paises_[n].add(b["iso"]["value"].upper())
        return {n: sorted(v) if musico.get(n) else [] for n, v in paises_.items()}
    raise ErroWikidata(f"Wikidata não respondeu ({len(nomes)} nomes)")


def paises_por_nome_ptwiki(nomes) -> dict[str, list[str]]:
    """{nome: [códigos ISO]} pela página da pt.wikipedia com esse título (com cache)."""
    cache = json.loads(CACHE_PTWIKI.read_text()) if CACHE_PTWIKI.exists() else {}
    faltam = sorted({n for n in nomes if isinstance(n, str) and n and n not in cache})
    if faltam and not SO_CACHE:
        for k in range(0, len(faltam), LOTE_NOMES):
            cache.update(_consultar_nomes(faltam[k:k + LOTE_NOMES]))
            CACHE_PTWIKI.parent.mkdir(parents=True, exist_ok=True)
            CACHE_PTWIKI.write_text(json.dumps(cache, ensure_ascii=False, sort_keys=True))
            time.sleep(1)
    return {n: cache[n] for n in nomes if n in cache}
