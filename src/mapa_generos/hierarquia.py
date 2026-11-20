"""Fase 4: hierarquia de gêneros pelas relações do MusicBrainz.

A API (ws/2) não devolve relações entre gêneros (inc=genre-rels é ignorado), então
as relações são lidas da página web de cada gênero (musicbrainz.org/genre/<id>),
na tabela "Relationships": "subgenre of", "fusion of", "influenced by" etc.

Parte dos gêneros das suas faixas (generos_faixas.parquet) e sobe pelos pais
("subgenre of" e "fusion of") até não haver mais pais, consultando cada página
uma vez. Tudo fica em cache (data/cache/musicbrainz/genero_rels/), então rodar de
novo não chama a rede.

Saídas:
- data/processed/generos_relacoes.parquet: (origem, relacao, destino), todas as
  relações das páginas visitadas, mais os pais dos EXTRAS definidos à mão (relacao
  "subgenre of", fonte "manual").

Critério do ROADMAP para desistir da hierarquia: mais de ~30% dos seus gêneros sem
pai, ou ciclos/múltiplos pais que deixem o mapa confuso. O relatório mede isso.

Uso:
    python -m mapa_generos.hierarquia             # consulta o MusicBrainz (lento, ~1,5 s/página)
    python -m mapa_generos.hierarquia --so-cache  # só o que já está em cache
"""

from __future__ import annotations

import argparse
import html
import json
import re
import time
from pathlib import Path

import networkx as nx
import pandas as pd
import requests
from tqdm import tqdm

from . import musicbrainz
from .musicbrainz import USER_AGENT, chave

ROOT = Path(__file__).resolve().parents[2]
PROC = ROOT / "data" / "processed"
GENEROS_FAIXAS = PROC / "generos_faixas.parquet"
SAIDA = PROC / "generos_relacoes.parquet"
CACHE = ROOT / "data" / "cache" / "musicbrainz"
CACHE_IDS = CACHE / "generos_ids.json"
CACHE_RELS = CACHE / "genero_rels"
PAIS_RELACOES = ("subgenre of", "fusion of")  # relações que contam como "pai"

# Pais dos gêneros que não existem no MusicBrainz (EXTRAS da Fase 3).
PAIS_EXTRAS = {
    "indie": [],  # raiz própria
    "alternative": [],  # raiz própria
    "rap": ["hip hop"],
    "alt-pop": ["pop"],
    "sadcore": ["slowcore"],
    "nova mpb": ["mpb"],
    "brazilian rap": ["hip hop"],
    "brazilian indie": ["indie"],
    "brazilian rock": ["rock"],
    "brazilian pop": ["pop"],
    "brazilian trap": ["trap"],
    "brazilian hardcore": ["hardcore punk"],
    "k-indie": ["indie"],
    "k-rock": ["rock"],
    "k-r&b": ["r&b"],
    "k-hip hop": ["hip hop"],
    "uk hip hop": ["hip hop"],
    "emo revival": ["emo"],
    "emo trap": ["emo rap"],
    "jazz hop": ["jazz rap"],
    "indie punk": ["indie rock", "punk"],
    "orchestral pop": ["chamber pop"],
    "dark pop": ["pop"],
}
NAO_GENERO = {"brazilian"}  # tag de país (Fase 2b), fica fora da hierarquia

_ultima = 0.0
SO_CACHE = False


def _baixar(url: str) -> requests.Response:
    """GET respeitando ~1 req/s e esperando quando o MusicBrainz responde 503."""
    global _ultima
    for tentativa in range(musicbrainz.TENTATIVAS):
        espera = musicbrainz.INTERVALO - (time.monotonic() - _ultima)
        if espera > 0:
            time.sleep(espera)
        try:
            resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
        except requests.RequestException:
            resp = None
        _ultima = time.monotonic()
        if resp is not None and resp.status_code < 500 and resp.status_code != 429:
            # a API às vezes responde 200 com {"error": "...busy..."}
            if "currently busy" not in resp.text[:300]:
                return resp
        time.sleep(min(60, 2 ** tentativa + 1))
    raise musicbrainz.ErroMusicBrainz(f"{url}: falhou {musicbrainz.TENTATIVAS}x")


def ids_generos() -> dict[str, str]:
    """nome do gênero no MusicBrainz → MBID (lista completa, em cache)."""
    if CACHE_IDS.exists():
        return json.loads(CACHE_IDS.read_text())
    if SO_CACHE:
        raise musicbrainz.ErroMusicBrainz("lista de IDs de gêneros fora do cache")
    ids, offset = {}, 0
    while True:
        d = _baixar(f"{musicbrainz.API}genre/all?fmt=json&limit=100&offset={offset}").json()
        for g in d["genres"]:
            ids[g["name"]] = g["id"]
        offset += len(d["genres"])
        if not d["genres"] or offset >= d["genre-count"]:
            break
    CACHE_IDS.parent.mkdir(parents=True, exist_ok=True)
    CACHE_IDS.write_text(json.dumps(ids, ensure_ascii=False))
    return ids


LINHA = re.compile(r"<tr><th>([^<]+?):</th><td[^>]*>(.*?)</td></tr>", re.S)
LINK = re.compile(r'href="/genre/([0-9a-f-]{36})"><bdi>(.*?)</bdi>')


def relacoes_da_pagina(mbid: str) -> list[dict]:
    """Relações de um gênero lidas da página web: [{relacao, destino, destino_id}]."""
    arq = CACHE_RELS / f"{mbid}.json"
    if arq.exists():
        return json.loads(arq.read_text())
    if SO_CACHE:
        raise musicbrainz.ErroMusicBrainz(f"gênero {mbid} fora do cache")
    resp = _baixar(f"https://musicbrainz.org/genre/{mbid}")
    resp.raise_for_status()
    texto = resp.text
    ini = texto.find('<h2 class="relationships">')
    rels = []
    if ini >= 0:
        # várias tabelas (ex.: "from: United States" vem antes); vai até a barra lateral
        fim = texto.find('<div id="sidebar"', ini)
        bloco = texto[ini:fim if fim > 0 else None]
        for rotulo, celula in LINHA.findall(bloco):
            for gid, nome in LINK.findall(celula):
                rels.append({"relacao": html.unescape(rotulo.strip()),
                             "destino": html.unescape(nome), "destino_id": gid})
    arq.parent.mkdir(parents=True, exist_ok=True)
    arq.write_text(json.dumps(rels, ensure_ascii=False))
    return rels


def coletar(generos: list[str]) -> tuple[pd.DataFrame, list[str]]:
    """Visita os gêneros e sobe pelos pais. Retorna (relações, gêneros fora do MusicBrainz)."""
    ids = ids_generos()
    por_chave = {chave(n): n for n in ids}
    fila = []
    fora = []
    for g in generos:
        n = por_chave.get(chave(g))
        (fila.append(n) if n else fora.append(g))
    vistos: set[str] = set()
    linhas = []
    barra = tqdm(total=len(fila), desc="gêneros", unit="pág")
    while fila:
        nome = fila.pop()
        if nome in vistos:
            continue
        vistos.add(nome)
        for r in relacoes_da_pagina(ids[nome]):
            linhas.append({"origem": nome, "relacao": r["relacao"], "destino": r["destino"], "fonte": "musicbrainz"})
            if r["relacao"] in PAIS_RELACOES and r["destino"] not in vistos and r["destino"] in ids:
                fila.append(r["destino"])
                barra.total += 1
        barra.update(1)
    barra.close()
    for g, pais in PAIS_EXTRAS.items():
        for p in pais:
            linhas.append({"origem": g, "relacao": "subgenre of", "destino": p, "fonte": "manual"})
    rel = pd.DataFrame(linhas, columns=["origem", "relacao", "destino", "fonte"]).drop_duplicates()
    return rel, [g for g in fora if g not in PAIS_EXTRAS]


def relatorio(rel: pd.DataFrame, gf: pd.DataFrame, fora: list[str]) -> None:
    faixas_por = gf.groupby("genero").track_id.nunique()
    meus = [g for g in faixas_por.index if g not in NAO_GENERO]
    tot_faixas = lambda gs: int(faixas_por.reindex(list(gs)).sum())
    print(f"\n== Relações coletadas ==\n  {len(rel):,} relações, {rel.origem.nunique():,} gêneros visitados".replace(",", "."))
    print("  por tipo: " + " · ".join(f"{k} {v}" for k, v in rel.relacao.value_counts().items()))

    for nome, tipos in [("só 'subgenre of'", ("subgenre of",)), ("'subgenre of' ou 'fusion of'", PAIS_RELACOES)]:
        pais = rel[rel.relacao.isin(tipos)]
        G = nx.DiGraph()
        G.add_edges_from(zip(pais.origem, pais.destino))
        com_pai = [g for g in meus if g in G and G.out_degree(g) > 0]
        sem_pai = [g for g in meus if g not in com_pai]
        multi = [g for g in com_pai if G.out_degree(g) > 1]
        ciclos = list(nx.simple_cycles(G))
        print(f"\n== Pais por {nome} ==")
        print(f"  seus gêneros: {len(meus)} · com pai: {len(com_pai)} ({len(com_pai)/len(meus):.1%})"
              f" · sem pai: {len(sem_pai)} ({len(sem_pai)/len(meus):.1%})")
        print(f"  ponderado por faixas (soma de faixas por gênero): sem pai = "
              f"{tot_faixas(sem_pai)/tot_faixas(meus):.1%}")
        print(f"  com mais de um pai: {len(multi)} ({len(multi)/len(meus):.1%}) · ciclos: {len(ciclos)}")
        if ciclos:
            print("  exemplos de ciclo: " + " | ".join(" → ".join(c) for c in ciclos[:5]))
        raizes = sorted({r for g in com_pai for r in nx.descendants(G, g) if G.out_degree(r) == 0},
                        key=lambda r: -tot_faixas([r]) if r in faixas_por else 0)
        print(f"  raízes alcançadas: {len(raizes)} → " + ", ".join(raizes[:30]))
        sem_ord = sorted(sem_pai, key=lambda g: -faixas_por[g])
        print("  sem pai, com mais faixas: " + ", ".join(f"{g} {faixas_por[g]}" for g in sem_ord[:30]))
        if multi:
            ex = sorted(multi, key=lambda g: -faixas_por[g])[:8]
            print("  vários pais (ex.): " + " | ".join(f"{g} → {', '.join(G.successors(g))}" for g in ex))
    if fora:
        print(f"\n  gêneros fora do MusicBrainz e sem pai manual: {', '.join(fora)}")

    print("\n== Exemplos de caminho até a raiz (subgenre of + fusion of) ==")
    pais = rel[rel.relacao.isin(PAIS_RELACOES)]
    G = nx.DiGraph(list(zip(pais.origem, pais.destino)))
    for g in ["post-punk revival", "alternative r&b", "pop rap", "tropicália", "midwest emo", "bedroom pop",
              "country pop", "brazilian rap", "funk carioca", "dream pop"]:
        if g in G:
            caminhos = [" → ".join(nx.shortest_path(G, g, r)) for r in nx.descendants(G, g) if G.out_degree(r) == 0]
            print(f"  {g}: " + " | ".join(sorted(caminhos, key=len)[:3]))


def main(argv: list[str] | None = None) -> None:
    global SO_CACHE
    ap = argparse.ArgumentParser(description="Hierarquia de gêneros pelas relações do MusicBrainz.")
    ap.add_argument("--so-cache", action="store_true", help="não chama a rede")
    args = ap.parse_args(argv)
    SO_CACHE = args.so_cache
    gf = pd.read_parquet(GENEROS_FAIXAS)
    generos = sorted(set(gf.genero) - NAO_GENERO)
    rel, fora = coletar(generos)
    rel.to_parquet(SAIDA, index=False)
    print(f"{SAIDA.relative_to(ROOT)}: {len(rel):,} relações".replace(",", "."))
    relatorio(rel, gf, fora)


if __name__ == "__main__":
    main()
