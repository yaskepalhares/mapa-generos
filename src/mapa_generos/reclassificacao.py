"""Correções de gênero feitas à mão: data/manual/reclassificacao.json (versionado).

Substitui a planilha classificacao_manual.xlsx. As correções são feitas na aba
"Reclassificar" da página (web/), que baixa um reclassificacao.json; basta salvá-lo em
data/manual/ (substituindo o anterior) e rodar o pipeline a partir de generos.py.

Formato:
    {"versao": 1,
     "correcoes": [
       {"nivel": "faixa",   "chave": "<track_id>",  "generos": ["funk carioca", "trap"],
        "rotulo": "Enversos — Baile Black", "em": "2026-11-20"},
       {"nivel": "album",   "chave": "<album_id>",  "generos": ["country"], ...},
       {"nivel": "artista", "chave": "<nome do artista principal>", "generos": [...], ...}
     ]}

Regras ao aplicar:
- Precedência faixa > álbum > artista: a correção mais específica que casa com a faixa
  vale, e substitui todos os gêneros do Last.fm dessa faixa (nivel="manual", peso 1).
- Álbum casa pelo ID do Spotify; artista, pelo nome do artista principal (1º da faixa).
- "generos" vazio = correção desativada (ignorada).
- "rotulo" e "em" são só para leitura humana.

Uso:
    python -m mapa_generos.reclassificacao                    # resumo do que será aplicado
    python -m mapa_generos.reclassificacao --migrar-planilha  # importa a planilha antiga
"""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
ARQUIVO = ROOT / "data" / "manual" / "reclassificacao.json"
FAIXAS = ROOT / "data" / "processed" / "faixas.parquet"
NIVEIS = ["faixa", "album", "artista"]  # ordem de precedência


def ler(path: Path = ARQUIVO) -> pd.DataFrame:
    """Correções ativas: colunas nivel, chave, generos (lista), rotulo, em."""
    cols = ["nivel", "chave", "generos", "rotulo", "em"]
    if not path.exists():
        return pd.DataFrame(columns=cols)
    dados = json.loads(path.read_text())
    linhas = []
    for c in dados.get("correcoes", []):
        if c.get("nivel") not in NIVEIS or not c.get("chave"):
            raise ValueError(f"correção inválida em {path.name}: {c}")
        gens = [g.strip() for g in c.get("generos", []) if g and g.strip()]
        if gens:
            linhas.append({"nivel": c["nivel"], "chave": c["chave"], "generos": gens,
                           "rotulo": c.get("rotulo", ""), "em": c.get("em", "")})
    df = pd.DataFrame(linhas, columns=cols)
    return df.drop_duplicates(["nivel", "chave"], keep="last")


def escrever(df: pd.DataFrame, path: Path = ARQUIVO) -> None:
    ordem = {n: i for i, n in enumerate(NIVEIS)}
    df = df.assign(_o=df.nivel.map(ordem)).sort_values(["_o", "rotulo", "chave"])
    correcoes = [{"nivel": r.nivel, "chave": r.chave, "generos": list(r.generos),
                  "rotulo": r.rotulo, "em": r.em} for r in df.itertuples()]
    path.parent.mkdir(parents=True, exist_ok=True)
    # Uma correção por linha: fica legível e o diff do git mostra só o que mudou.
    corpo = ",\n".join("  " + json.dumps(c, ensure_ascii=False) for c in correcoes)
    path.write_text('{"versao": 1, "correcoes": [\n' + corpo + "\n]}\n")


def aplicar(faixas: pd.DataFrame, corr: pd.DataFrame | None = None) -> pd.DataFrame:
    """Uma linha por (track_id, genero digitado), com o nível da correção que venceu.

    `faixas` precisa de track_id, album_id e artista.
    """
    corr = ler() if corr is None else corr
    vencedora: dict[str, tuple[str, list[str]]] = {}
    campo = {"faixa": "track_id", "album": "album_id", "artista": "artista"}
    for nivel in reversed(NIVEIS):  # artista primeiro; os mais específicos sobrescrevem
        mapa = {r.chave: r.generos for r in corr[corr.nivel == nivel].itertuples()}
        if not mapa:
            continue
        for tid, k in zip(faixas.track_id, faixas[campo[nivel]]):
            if k in mapa:
                vencedora[tid] = (nivel, mapa[k])
    linhas = [(tid, g, nv) for tid, (nv, gens) in vencedora.items() for g in gens]
    return pd.DataFrame(linhas, columns=["track_id", "genero_digitado", "nivel_correcao"])


def migrar_planilha() -> int:
    """Copia as linhas preenchidas de classificacao_manual.xlsx (nível faixa)."""
    from .manual import ler_manual  # só para a migração

    m = ler_manual()
    m = m[m.generos.str.strip().ne("")]
    atual = ler()
    hoje = date.today().isoformat()
    novas = pd.DataFrame({
        "nivel": "faixa", "chave": m.track_id,
        "generos": m.generos.map(lambda t: [g.strip() for g in t.split(";") if g.strip()]),
        "rotulo": (m.artista + " — " + m.faixa).str.strip(" —"), "em": hoje,
    })
    novas = novas[~novas.chave.isin(atual.chave[atual.nivel == "faixa"])]
    escrever(pd.concat([atual, novas], ignore_index=True))
    return len(novas)


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="Correções de gênero (reclassificacao.json).")
    ap.add_argument("--migrar-planilha", action="store_true",
                    help="importa as faixas preenchidas de classificacao_manual.xlsx")
    args = ap.parse_args(argv)
    if args.migrar_planilha:
        n = migrar_planilha()
        print(f"{n} correções importadas da planilha → {ARQUIVO.relative_to(ROOT)}")
    corr = ler()
    print(f"{ARQUIVO.relative_to(ROOT)}: {len(corr)} correções ativas "
          + " · ".join(f"{n} {int((corr.nivel == n).sum())}" for n in NIVEIS))
    if FAIXAS.exists():
        faixas = pd.read_parquet(FAIXAS, columns=["track_id", "album_id", "artista"])
        ap_ = aplicar(faixas, corr)
        por = ap_.drop_duplicates("track_id").nivel_correcao.value_counts()
        print(f"Faixas afetadas: {ap_.track_id.nunique()} "
              + " · ".join(f"{n} {int(por.get(n, 0))}" for n in NIVEIS))


if __name__ == "__main__":
    main()
