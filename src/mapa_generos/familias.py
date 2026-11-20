"""Famílias de cor: quanto de cada família (rock, pop, hip hop…) há em cada gênero.

Regra:
1. As raízes da hierarquia (Fase 4) são agrupadas em FAMILIAS (aprovado em 20/11/2026).
2. Gênero que não é raiz herda o vetor dos pais ("subgenre of" + "fusion of"),
   dividido igualmente entre eles: pop rock = ½ pop + ½ rock.
3. Gêneros que não chegam a nenhuma raiz usam MANUAL (encaixe à mão).
4. O que ainda sobrar usa a coocorrência nas suas faixas: média dos vetores dos
   gêneros que aparecem junto, ponderada pelo nº de faixas em comum.

Profundidade = menor nº de passos até uma raiz com família (raiz = 0; manual = 1;
coocorrência = 2). Serve para a opacidade no visual.

Saída: data/processed/generos_familias.parquet (genero, familia, fracao,
profundidade, origem), uma linha por (gênero, família) com fração > 0.

Uso:
    python -m mapa_generos.familias
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import networkx as nx
import pandas as pd

from .hierarquia import NAO_GENERO, PAIS_RELACOES

ROOT = Path(__file__).resolve().parents[2]
PROC = ROOT / "data" / "processed"
RELACOES = PROC / "generos_relacoes.parquet"
GENEROS_FAIXAS = PROC / "generos_faixas.parquet"
SAIDA = PROC / "generos_familias.parquet"

# família → (cor, raízes). Cores pensadas para fundo escuro.
FAMILIAS = {
    "rock": ("#F28C28", ["rock", "punk", "metal", "psychedelic", "alternative", "grunge"]),
    "hip hop": ("#F2C230", ["hip hop"]),
    "pop": ("#F25CA2", ["pop"]),
    "r&b/soul": ("#9D6BF2", ["r&b", "soul", "funk", "disco"]),
    "brasileira": ("#2FBF71", ["mpb", "samba", "forró", "funk brasileiro", "brega", "tropicália", "bossa nova"]),
    "eletrônica": ("#2EB8E6", ["electronic", "dance", "ambient", "industrial", "chillout"]),
    "indie": ("#EADBC8", ["indie"]),
    "folk/country": ("#B98A5E", ["folk", "country", "americana", "singer-songwriter"]),
    "jazz/blues": ("#4C7DF0", ["jazz", "blues"]),
    "latina/reggae": ("#E5484D", ["latin", "reggaeton", "reggae"]),
    "outros": ("#9AA0A6", ["experimental", "classical", "musical", "instrumental", "ballad"]),
}
COR = {f: c for f, (c, _) in FAMILIAS.items()}
RAIZ = {g: f for f, (_, gs) in FAMILIAS.items() for g in gs}

# Gêneros que não chegam a nenhuma raiz pela hierarquia: encaixe à mão.
MANUAL = {
    **{g: {"brasileira": 1} for g in ["sertanejo", "sertanejo universitário", "choro", "baião", "frevo",
                                      "afoxê", "arrocha", "moda de viola", "batucada", "macumba"]},
    "black music": {"r&b/soul": 1},  # no Brasil, soul/funk
    "gospel": {"r&b/soul": 1},
    **{g: {"latina/reggae": 1} for g in ["bolero", "tango", "flamenco", "dembow", "sierreño", "corrido",
                                         "plena", "ska"]},
    **{g: {"rock": 1} for g in ["gothic", "dark wave", "ethereal wave", "neoclassical dark wave", "progressive"]},
    "folkhop": {"folk/country": 0.5, "hip hop": 0.5},
    "afrobeats": {"pop": 0.5, "r&b/soul": 0.5},
    **{g: {"outros": 1} for g in ["spoken word", "klezmer", "orchestral", "avant-garde", "comedy",
                                  "chanson française", "whistling", "new age", "church music", "christmas music"]},
}


def grafo_pais() -> nx.DiGraph:
    r = pd.read_parquet(RELACOES)
    p = r[r.relacao.isin(PAIS_RELACOES)]
    return nx.DiGraph(list(zip(p.origem, p.destino)))


def vetores(generos: list[str], G: nx.DiGraph, gf: pd.DataFrame) -> dict[str, tuple[Counter, int, str]]:
    """gênero → (vetor de famílias, profundidade, origem)."""
    memo: dict[str, tuple[Counter, int]] = {}

    def pela_hierarquia(g: str, caminho: frozenset = frozenset()) -> tuple[Counter, int]:
        if g in RAIZ:
            return Counter({RAIZ[g]: 1.0}), 0
        if g in memo:
            return memo[g]
        pais = [p for p in (G.successors(g) if g in G else []) if p not in caminho]
        vet, prof = Counter(), None
        res = [pela_hierarquia(p, caminho | {g}) for p in pais]
        res = [(v, d) for v, d in res if v]  # pais que não chegam a família não dividem o peso
        for v, d in res:
            for k, x in v.items():
                vet[k] += x / len(res)
            prof = d + 1 if prof is None else min(prof, d + 1)
        memo[g] = (vet, prof if prof is not None else -1)
        return memo[g]

    out = {}
    for g in generos:
        v, d = pela_hierarquia(g)
        if v:
            out[g] = (v, d, "hierarquia")
        elif g in MANUAL:
            out[g] = (Counter(MANUAL[g]), 1, "manual")

    # coocorrência para o resto
    faltam = [g for g in generos if g not in out]
    if faltam:
        por_faixa = gf.groupby("track_id").genero.agg(set)
        for g in faltam:
            vet = Counter()
            for gs in por_faixa[por_faixa.map(lambda s: g in s)]:
                for o in gs - {g}:
                    if o in out:
                        for k, x in out[o][0].items():
                            vet[k] += x
            tot = sum(vet.values())
            if tot:
                out[g] = (Counter({k: x / tot for k, x in vet.items()}), 2, "coocorrencia")
    return out


def misturar(vet: dict[str, float]) -> str:
    """Cor hex da mistura das famílias (média RGB ponderada)."""
    tot = sum(vet.values())
    rgb = [0.0, 0.0, 0.0]
    for f, x in vet.items():
        c = COR[f]
        for i in range(3):
            rgb[i] += int(c[1 + 2 * i:3 + 2 * i], 16) * x / tot
    return "#" + "".join(f"{round(v):02X}" for v in rgb)


def gerar() -> pd.DataFrame:
    gf = pd.read_parquet(GENEROS_FAIXAS)
    gf = gf[~gf.genero.isin(NAO_GENERO)]
    generos = sorted(gf.genero.unique())
    res = vetores(generos, grafo_pais(), gf)
    linhas = [(g, f, round(x, 4), d, o) for g, (v, d, o) in res.items() for f, x in v.items() if x > 0]
    return pd.DataFrame(linhas, columns=["genero", "familia", "fracao", "profundidade", "origem"])


def main() -> None:
    df = gerar()
    df.to_parquet(SAIDA, index=False)
    gf = pd.read_parquet(GENEROS_FAIXAS)
    todos = sorted(set(gf.genero) - NAO_GENERO)
    por = df.drop_duplicates("genero")
    print(f"{SAIDA.relative_to(ROOT)}: {len(df)} linhas, {por.genero.nunique()} de {len(todos)} gêneros com família")
    print("  origem: " + " · ".join(f"{k} {v}" for k, v in por.origem.value_counts().items()))
    print("  profundidade: " + " · ".join(f"{k}: {v}" for k, v in por.profundidade.value_counts().sort_index().items()))
    sem = [g for g in todos if g not in set(por.genero)]
    if sem:
        print("  sem família: " + ", ".join(sem))
    misto = df.groupby("genero").familia.nunique()
    print(f"  gêneros com mais de uma família: {int((misto > 1).sum())}")


if __name__ == "__main__":
    main()
