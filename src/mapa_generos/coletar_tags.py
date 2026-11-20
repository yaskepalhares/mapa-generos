"""Fase 2: coleta as tags do Last.fm para cada faixa de faixas.parquet.

Para cada faixa coleta os TRÊS níveis (track.getTopTags, album.getTopTags,
artist.getTopTags), sem parar no primeiro com tags: alguns álbuns só têm tags que
não são gênero ("2020", "14 tracks") e a escolha do nível fica para a Fase 3,
depois da limpeza. O "melhor nível" (primeiro com alguma tag) é guardado só para
medir cobertura.

- Cache: toda resposta fica em data/cache/lastfm/ (ver lastfm.py); álbuns e
  artistas repetidos também ficam em memória durante a execução.
- Retomável: cada faixa concluída é anotada em data/cache/coleta_tags.jsonl.
  Se a execução for interrompida (Ctrl+C, queda de rede), basta rodar de novo.
  Faixas que deram erro não são anotadas e serão tentadas na próxima execução.

Saídas:
- data/processed/tags_faixas.parquet   uma linha por (track_id, tag, contagem, nivel), dos 3 níveis
- data/processed/nivel_faixas.parquet  uma linha por faixa: track_id, nivel (melhor nível ou
  None = sem tag), n_faixa, n_album, n_artista (nº de tags em cada nível)
Com --amostra, os arquivos ganham o sufixo _amostra.

Faixas sem nenhuma tag nos três níveis são listadas no fim; elas aparecem como
pendentes na aba "Reclassificar" da página (ver reclassificacao.py).

Uso:
    python -m mapa_generos.coletar_tags --amostra 50   # teste
    python -m mapa_generos.coletar_tags                # todas as faixas
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd
from tqdm import tqdm

from . import lastfm
from .ingest_exportify import separar_artistas

ROOT = Path(__file__).resolve().parents[2]
FAIXAS = ROOT / "data" / "processed" / "faixas.parquet"
CHECKPOINT = ROOT / "data" / "cache" / "coleta_tags.jsonl"
SAIDA = ROOT / "data" / "processed"

NIVEIS_API = ["faixa", "album", "artista"]
NIVEIS = NIVEIS_API + ["sem tag"]
# Em coletâneas o "artista do álbum" é genérico; aí a busca do álbum usa o artista da faixa.
ARTISTAS_GENERICOS = {"various artists", "vários artistas", "varios artistas"}


def artista_do_album(row) -> str | None:
    nomes = row.album_artistas_str
    if not isinstance(nomes, str) or not nomes:
        return None
    primeiro = separar_artistas(nomes)[0]
    return None if primeiro.lower() in ARTISTAS_GENERICOS else primeiro


def ler_checkpoint() -> dict[str, dict]:
    feitos: dict[str, dict] = {}
    if CHECKPOINT.exists():
        for linha in CHECKPOINT.read_text().splitlines():
            if not linha.strip():
                continue
            try:
                reg = json.loads(linha)
            except json.JSONDecodeError:  # última linha cortada por interrupção
                continue
            if "niveis" in reg:  # ignora registros do formato antigo (só um nível)
                feitos[reg["track_id"]] = reg
    return feitos


def coletar_uma(row) -> dict:
    if not isinstance(row.artista, str) or not isinstance(row.faixa, str):
        niveis = {n: [] for n in NIVEIS_API}
        return {"track_id": row.track_id, "niveis": niveis, "motivo": "sem artista/título"}
    album = row.album if isinstance(row.album, str) else None
    niveis = lastfm.tags_todos_niveis(row.artista, row.faixa, album, artista_do_album(row))
    return {"track_id": row.track_id, "niveis": niveis}


def melhor_nivel(niveis: dict) -> str | None:
    return next((n for n in NIVEIS_API if len(niveis[n]) >= lastfm.MIN_TAGS), None)


def relatorio(niveis: pd.Series) -> pd.DataFrame:
    cont = niveis.fillna("sem tag").value_counts().reindex(NIVEIS, fill_value=0)
    tab = pd.DataFrame({"faixas": cont, "%": (100 * cont / cont.sum()).round(1)})
    tab.index.name = "nível"
    return tab


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--amostra", type=int, help="sorteia N faixas (para teste)")
    ap.add_argument("--semente", type=int, default=42, help="semente do sorteio (padrão 42)")
    args = ap.parse_args(argv)

    faixas = pd.read_parquet(FAIXAS)
    sufixo = ""
    if args.amostra:
        faixas = faixas.sample(n=min(args.amostra, len(faixas)), random_state=args.semente)
        sufixo = "_amostra"

    feitos = ler_checkpoint()
    pendentes = faixas[~faixas.track_id.isin(feitos)]
    print(f"Faixas: {len(faixas)} · já coletadas: {len(faixas) - len(pendentes)} · pendentes: {len(pendentes)}")

    erros: list[tuple[str, str]] = []
    CHECKPOINT.parent.mkdir(parents=True, exist_ok=True)
    try:
        with CHECKPOINT.open("a") as ck:
            for row in tqdm(pendentes.itertuples(index=False), total=len(pendentes), unit="faixa"):
                try:
                    reg = coletar_uma(row)
                except lastfm.ErroLastfm as e:
                    if "LASTFM_API_KEY" in str(e):
                        sys.exit(str(e))
                    erros.append((row.track_id, str(e)))
                    continue
                ck.write(json.dumps(reg, ensure_ascii=False) + "\n")
                ck.flush()
                feitos[reg["track_id"]] = reg
    except KeyboardInterrupt:
        print("\nInterrompido. O progresso foi salvo; rode de novo para continuar.")

    regs = [feitos[t] for t in faixas.track_id if t in feitos]
    nivel = pd.DataFrame(
        [{"track_id": r["track_id"], "nivel": melhor_nivel(r["niveis"]),
          **{f"n_{n}": len(r["niveis"][n]) for n in NIVEIS_API}} for r in regs]
    )
    tags = pd.DataFrame(
        [(r["track_id"], nome, cont, n) for r in regs for n in NIVEIS_API for nome, cont in r["niveis"][n]],
        columns=["track_id", "tag", "contagem", "nivel"],
    )
    SAIDA.mkdir(parents=True, exist_ok=True)
    tags.to_parquet(SAIDA / f"tags_faixas{sufixo}.parquet", index=False)
    nivel.to_parquet(SAIDA / f"nivel_faixas{sufixo}.parquet", index=False)

    print(f"\nCobertura ({len(regs)} de {len(faixas)} faixas coletadas):")
    print(relatorio(nivel.nivel).to_string())
    print("\nFaixas com tags em cada nível (não exclusivo):")
    for n in NIVEIS_API:
        k = int((nivel[f"n_{n}"] > 0).sum())
        print(f"  {n:<8} {k:>5}  ({100 * k / max(len(nivel), 1):.1f}%)")
    print(f"\nLinhas de tag: {len(tags)} · tags distintas: {tags.tag.str.lower().nunique()}")
    motivos = {r["track_id"]: r.get("motivo", "nenhuma tag nos 3 níveis") for r in regs}
    sem_tag = (faixas[faixas.track_id.isin(nivel.track_id[nivel.nivel.isna()])]
               [["track_id", "artista", "faixa", "album"]]
               .assign(motivo=lambda d: d.track_id.map(motivos)))
    if len(sem_tag):
        print(f"\nSem tag em nenhum nível ({len(sem_tag)}); classifique na aba Reclassificar da página:")
        print(sem_tag[["artista", "faixa", "album", "motivo"]].fillna("—").to_string(index=False))
    if erros:
        print(f"\n{len(erros)} faixas com erro (serão tentadas de novo na próxima execução). Ex.: {erros[0][1]}")
    print(f"Salvo em data/processed/tags_faixas{sufixo}.parquet e nivel_faixas{sufixo}.parquet")


if __name__ == "__main__":
    main()
