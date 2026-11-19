"""Lê o CSV das Curtidas exportado pelo Exportify (exportify.app) e gera
data/processed/faixas.parquet, no mesmo esquema de ingest_spotifast.py.

Como exportar: exportify.app → entrar com o Spotify → linha "Liked" → Exportar.
Salve o arquivo como data/raw/liked.csv (ou passe o caminho como argumento).

O cabeçalho vem no idioma da interface do Exportify; o script aceita português e inglês.

Uso:
    python -m mapa_generos.ingest_exportify [data/raw/liked.csv]
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
PADRAO = ROOT / "data" / "raw" / "liked.csv"
OUT = ROOT / "data" / "processed" / "faixas.parquet"

COLUNAS = {
    # português (interface pt-BR)          inglês
    "URI da faixa": "track_uri",               "Track URI": "track_uri",
    "Nome da faixa": "faixa",                  "Track Name": "faixa",
    "URI(s) do artista": "artista_uris",       "Artist URI(s)": "artista_uris",
    "Nome(s) do artista": "artistas_str",      "Artist Name(s)": "artistas_str",
    "URI do álbum": "album_uri",               "Album URI": "album_uri",
    "Nome do álbum": "album",                  "Album Name": "album",
    "Nome(s) do artista do álbum": "album_artistas_str", "Album Artist Name(s)": "album_artistas_str",
    "Data de lançamento do álbum": "lancamento", "Album Release Date": "lancamento",
    "Duração da faixa (ms)": "duracao_ms",     "Track Duration (ms)": "duracao_ms",
    "Popularidade": "popularidade",            "Popularity": "popularidade",
    "ISRC": "isrc",
    "Adicionado em": "curtida_em",             "Added At": "curtida_em",
}


def separar_artistas(nomes: str) -> list[str]:
    """Separa "A, B". O Exportify escapa vírgulas internas ("Tyler\\, The Creator")."""
    if not isinstance(nomes, str):
        return []
    return [p.replace("\\,", ",") for p in re.split(r"(?<!\\), ", nomes)]


def ler(path: Path) -> pd.DataFrame:
    bruto = pd.read_csv(path)
    df = bruto.rename(columns=COLUNAS)[[c for c in dict.fromkeys(COLUNAS.values()) if c in bruto.rename(columns=COLUNAS)]]
    df["track_id"] = df["track_uri"].str.split(":").str[-1]
    df["album_id"] = df["album_uri"].str.split(":").str[-1]
    df["artistas"] = df["artistas_str"].apply(separar_artistas)
    df["artista_ids"] = df["artista_uris"].fillna("").str.split(", ").apply(
        lambda xs: [x.split(":")[-1] for x in xs if x])
    df["artista"] = df["artistas"].str[0]
    df["curtida_em"] = pd.to_datetime(df["curtida_em"])
    return df.drop(columns=["track_uri", "album_uri", "artista_uris", "artistas_str"])


def main() -> None:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else PADRAO
    df = ler(path)
    dup = df.duplicated("track_id").sum()
    df = df.drop_duplicates("track_id")
    print(f"Faixas: {len(df)} (duplicatas removidas: {dup})")
    print(f"Artistas principais distintos: {df.artista.nunique()} · álbuns distintos: {df.album_id.nunique()}")
    print(f"Curtidas de {df.curtida_em.min():%d/%m/%Y} a {df.curtida_em.max():%d/%m/%Y}")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUT, index=False)
    print(f"Salvo em {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
