"""Fase 5: grafo de gêneros → web/grafo.json e web/faixas.json.

Nós = gêneros (sem a tag de país "brazilian", que vira atributo: % de faixas
brasileiras do gênero). Tamanho = nº de faixas.

Arestas:
- "coocorrencia": dois gêneros na mesma faixa. Força = soma, nas faixas em comum,
  do menor dos dois pesos; normalizada pelo cosseno (força / √(P_a·P_b), P = soma
  dos pesos do gênero), para gêneros grandes não engolirem tudo.
- "hierarquia": "subgenre of"/"fusion of" entre gêneros presentes (Fase 4).

Poda: cada gênero mantém só as K arestas de coocorrência mais fortes (pela força
normalizada); as de hierarquia ficam todas. Comunidades por Louvain (semente 42)
no grafo podado, para conferir as famílias.

Uso:
    python -m mapa_generos.grafo
"""

from __future__ import annotations

import json
import math
from collections import defaultdict
from itertools import combinations
from pathlib import Path

import networkx as nx
import pandas as pd

from .familias import COR, misturar
from .hierarquia import NAO_GENERO, PAIS_RELACOES

ROOT = Path(__file__).resolve().parents[2]
PROC = ROOT / "data" / "processed"
WEB = ROOT / "web"
K = 4  # arestas de coocorrência mantidas por gênero


def carregar():
    gf = pd.read_parquet(PROC / "generos_faixas.parquet")
    fam = pd.read_parquet(PROC / "generos_familias.parquet")
    rel = pd.read_parquet(PROC / "generos_relacoes.parquet")
    faixas = pd.read_parquet(PROC / "faixas.parquet", columns=["track_id", "faixa", "artista", "album"])
    return gf, fam, rel, faixas


def coocorrencia(gf: pd.DataFrame) -> pd.DataFrame:
    forca, comum = defaultdict(float), defaultdict(int)
    for _, g in gf.groupby("track_id"):
        pesos = dict(zip(g.genero, g.peso))
        for a, b in combinations(sorted(pesos), 2):
            forca[a, b] += min(pesos[a], pesos[b])
            comum[a, b] += 1
    P = gf.groupby("genero").peso.sum()
    linhas = [(a, b, comum[a, b], f, f / math.sqrt(P[a] * P[b])) for (a, b), f in forca.items()]
    return pd.DataFrame(linhas, columns=["a", "b", "faixas_em_comum", "forca", "cosseno"])


def podar(co: pd.DataFrame, k: int = K) -> pd.DataFrame:
    """Mantém a aresta se ela está entre as k mais fortes de pelo menos uma ponta."""
    longo = pd.concat([co.assign(no=co.a), co.assign(no=co.b)])
    longo["rank"] = longo.groupby("no").cosseno.rank(ascending=False, method="first")
    manter = longo[longo["rank"] <= k][["a", "b"]].drop_duplicates()
    return co.merge(manter, on=["a", "b"])


def gerar() -> dict:
    gf, fam, rel, faixas = carregar()
    br = set(gf.track_id[gf.genero.isin(NAO_GENERO)])
    gf = gf[~gf.genero.isin(NAO_GENERO)]
    n = gf.groupby("genero").track_id.nunique()
    pct_br = gf.assign(br=gf.track_id.isin(br)).groupby("genero").br.mean()
    vet = fam.groupby("genero").apply(lambda d: dict(zip(d.familia, d.fracao)), include_groups=False)
    prof = fam.drop_duplicates("genero").set_index("genero").profundidade

    co = coocorrencia(gf)
    podadas = podar(co)
    presentes = set(n.index)
    hier = rel[rel.relacao.isin(PAIS_RELACOES) & rel.origem.isin(presentes) & rel.destino.isin(presentes)]
    hier = hier.drop_duplicates(["origem", "destino"])

    G = nx.Graph()
    G.add_nodes_from(presentes)
    G.add_weighted_edges_from(zip(podadas.a, podadas.b, podadas.cosseno))
    comunidades = nx.community.louvain_communities(G, weight="weight", seed=42)
    com = {g: i for i, c in enumerate(sorted(comunidades, key=len, reverse=True)) for g in c}

    nos = [{
        "id": g,
        "faixas": int(n[g]),
        "familias": vet[g],
        "familia": max(vet[g], key=vet[g].get),
        "cor": misturar(vet[g]),
        "profundidade": int(prof[g]),
        "comunidade": com[g],
        "pct_brasileiro": round(float(pct_br[g]), 3),
    } for g in sorted(presentes, key=lambda g: -n[g])]
    arestas = (
        [{"source": r.a, "target": r.b, "tipo": "coocorrencia", "peso": round(r.cosseno, 4),
          "faixas_em_comum": int(r.faixas_em_comum)} for r in podadas.itertuples()]
        + [{"source": r.origem, "target": r.destino, "tipo": "hierarquia", "relacao": r.relacao}
           for r in hier.itertuples()]
    )
    return {"familias": COR, "nos": nos, "arestas": arestas,
            "_estat": {"co_total": len(co), "co_podadas": len(podadas), "hier": len(hier),
                       "comunidades": len(comunidades), "componentes": nx.number_connected_components(G)}}


def exportar_faixas(path: Path) -> int:
    gf, _, _, faixas = carregar()
    br = set(gf.track_id[gf.genero.isin(NAO_GENERO)])
    gf = gf[~gf.genero.isin(NAO_GENERO)]
    gen = gf.groupby("track_id").apply(
        lambda d: [[g, round(p, 3)] for g, p in zip(d.genero, d.peso)], include_groups=False)
    lista = [{"id": r.track_id, "faixa": r.faixa, "artista": r.artista, "album": r.album,
              "brasileiro": r.track_id in br, "generos": gen.get(r.track_id, [])}
             for r in faixas.fillna("").itertuples()]
    path.write_text(json.dumps(lista, ensure_ascii=False, separators=(",", ":")))
    return len(lista)


def main() -> None:
    WEB.mkdir(exist_ok=True)
    g = gerar()
    est = g.pop("_estat")
    (WEB / "grafo.json").write_text(json.dumps(g, ensure_ascii=False, separators=(",", ":")))
    nf = exportar_faixas(WEB / "faixas.json")
    print(f"web/grafo.json: {len(g['nos'])} gêneros, {len(g['arestas'])} arestas "
          f"(coocorrência {est['co_podadas']} de {est['co_total']} após a poda K={K}; hierarquia {est['hier']})")
    print(f"  comunidades (Louvain): {est['comunidades']} · componentes conexos: {est['componentes']}")
    print(f"web/faixas.json: {nf} faixas")


if __name__ == "__main__":
    main()
