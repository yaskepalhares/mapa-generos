"""Lê os CSVs exportados pelo Exportify (exportify.app) e gera data/processed/faixas.parquet.

Fontes (todas no formato do Exportify, cabeçalho em português ou inglês):
- data/raw/liked.csv            Curtidas (linha "Liked" no Exportify)
- data/raw/playlists/*.csv      playlists ("Export All" baixa um .zip; descompacte aqui).
                                Só entram as playlists criadas por você (ver abaixo).
- data/raw/avulsos/*.csv        listas que entram sempre, sem checar o dono (ex.: o CSV de
                                pendentes baixado pela página ao soltar um CSV no mapa)

Playlist "sua" = a maioria das faixas foi adicionada pelo seu usuário do Spotify (coluna
"Adicionado por"). O seu usuário é detectado como o "Adicionado por" mais frequente entre
todas as playlists; use --dono para fixá-lo. Playlists do Spotify (sem "Adicionado por") e
de outras pessoas ficam de fora e aparecem no relatório.

Deduplicação por ID do Spotify. Cada faixa guarda de onde veio:
- origens: lista com "Curtidas" e/ou nomes das playlists (nome = nome do arquivo)
- curtida: se está nas Curtidas
- curtida_em: data em que curtiu (vazia se não está nas Curtidas)
- adicionada_em: primeira data em que entrou em alguma das fontes

Arquivos locais (spotify:local:…) e episódios de podcast são ignorados.

Uso:
    python -m mapa_generos.ingest_exportify                    # liked.csv + playlists + avulsos
    python -m mapa_generos.ingest_exportify --dono SEU_USUARIO
    python -m mapa_generos.ingest_exportify --so-curtidas      # como antes
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
PADRAO = RAW / "liked.csv"
PLAYLISTS = RAW / "playlists"
AVULSOS = RAW / "avulsos"
OUT = ROOT / "data" / "processed" / "faixas.parquet"
CURTIDAS = "Curtidas"
LIMIAR_DONO = 0.5  # fração mínima de faixas adicionadas por você para a playlist contar

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
    "Adicionado por": "adicionado_por",        "Added By": "adicionado_por",
    "Adicionado em": "adicionada_em",          "Added At": "adicionada_em",
}


def separar_artistas(nomes: str) -> list[str]:
    """Separa "A, B". O Exportify escapa vírgulas internas ("Tyler\\, The Creator")."""
    if not isinstance(nomes, str):
        return []
    return [p.replace("\\,", ",") for p in re.split(r"(?<!\\), ", nomes)]


def nome_da_lista(path: Path) -> str:
    """O Exportify nomeia o arquivo como o nome da playlist, com "_" no lugar de espaço."""
    return path.stem.replace("_", " ").strip()


def ler(path: Path) -> pd.DataFrame:
    bruto = pd.read_csv(path, dtype={"Adicionado por": str, "Added By": str})
    df = bruto.rename(columns=COLUNAS)
    df = df[[c for c in dict.fromkeys(COLUNAS.values()) if c in df.columns]].copy()
    # Só faixas do catálogo (fora: arquivos locais, episódios, linhas vazias)
    df = df[df.track_uri.fillna("").str.startswith("spotify:track:")].copy()
    if "adicionado_por" not in df:
        df["adicionado_por"] = ""
    df["adicionado_por"] = df.adicionado_por.fillna("").str.replace("spotify:user:", "", regex=False)
    df["track_id"] = df["track_uri"].str.split(":").str[-1]
    df["album_id"] = df["album_uri"].str.split(":").str[-1]
    df["artistas"] = df["artistas_str"].apply(separar_artistas)
    df["artista_ids"] = df["artista_uris"].fillna("").str.split(", ").apply(
        lambda xs: [x.split(":")[-1] for x in xs if x])
    df["artista"] = df["artistas"].str[0]
    df["adicionada_em"] = pd.to_datetime(df["adicionada_em"], utc=True, errors="coerce")
    return df.drop(columns=["track_uri", "album_uri", "artista_uris", "artistas_str"])


def detectar_dono(listas: dict[str, pd.DataFrame]) -> str | None:
    todos = pd.concat([d.adicionado_por for d in listas.values()], ignore_index=True)
    todos = todos[todos.ne("")]
    return todos.value_counts().index[0] if len(todos) else None


def classificar_playlists(listas: dict[str, pd.DataFrame], dono: str | None) -> pd.DataFrame:
    """Uma linha por playlist: faixas, fração adicionada pelo dono e se entra."""
    linhas = []
    for nome, d in listas.items():
        frac = float(d.adicionado_por.eq(dono).mean()) if len(d) and dono else 0.0
        linhas.append({"playlist": nome, "faixas": len(d), "frac_dono": frac,
                       "entra": bool(dono) and frac >= LIMIAR_DONO})
    return pd.DataFrame(linhas, columns=["playlist", "faixas", "frac_dono", "entra"])


def juntar(fontes: list[tuple[str, pd.DataFrame]]) -> pd.DataFrame:
    """Empilha as fontes (Curtidas primeiro) e deduplica por track_id."""
    pilha = pd.concat([d.assign(origem=o) for o, d in fontes], ignore_index=True)
    origens = pilha.groupby("track_id").origem.agg(lambda s: list(dict.fromkeys(s)))
    primeira = pilha.groupby("track_id").adicionada_em.min()
    curtida_em = pilha[pilha.origem.eq(CURTIDAS)].groupby("track_id").adicionada_em.min()
    # Metadados da primeira ocorrência (das Curtidas, se estiver lá)
    df = pilha.drop_duplicates("track_id").drop(columns=["origem", "adicionado_por", "adicionada_em"])
    df = df.set_index("track_id")
    df["origens"] = origens
    df["curtida"] = df.index.isin(curtida_em.index)
    df["curtida_em"] = curtida_em
    df["adicionada_em"] = primeira
    return df.reset_index()


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="Junta Curtidas e playlists do Exportify em faixas.parquet.")
    ap.add_argument("liked", nargs="?", type=Path, default=PADRAO, help="CSV das Curtidas")
    ap.add_argument("--playlists", type=Path, default=PLAYLISTS, help="pasta com os CSVs de playlist")
    ap.add_argument("--avulsos", type=Path, default=AVULSOS, help="pasta com CSVs que entram sempre")
    ap.add_argument("--dono", help="seu usuário do Spotify (padrão: detectado)")
    ap.add_argument("--so-curtidas", action="store_true", help="ignora playlists e avulsos")
    args = ap.parse_args(argv)

    curtidas = ler(args.liked)
    dup = curtidas.duplicated("track_id").sum()
    fontes: list[tuple[str, pd.DataFrame]] = [(CURTIDAS, curtidas)]
    print(f"Curtidas: {len(curtidas)} faixas ({dup} repetidas no CSV)")

    if not args.so_curtidas:
        listas = {nome_da_lista(p): ler(p) for p in sorted(args.playlists.glob("*.csv"))}
        listas.pop(CURTIDAS, None)
        listas = {n: d for n, d in listas.items() if n.lower() not in {"liked", "curtidas", "liked songs", "músicas curtidas"}}
        if listas:
            dono = args.dono or detectar_dono(listas)
            tab = classificar_playlists(listas, dono)
            quem = pd.concat([d.adicionado_por for d in listas.values()]).replace("", "(Spotify/sem dono)")
            print("Quem mais adicionou faixas: " + " · ".join(f"{u} {n}" for u, n in quem.value_counts().head(3).items()))
            print(f"\nPlaylists em {args.playlists.relative_to(ROOT) if args.playlists.is_relative_to(ROOT) else args.playlists}: "
                  f"{len(tab)} · dono {'informado' if args.dono else 'detectado'}: {dono}")
            for r in tab.sort_values(["entra", "faixas"], ascending=[False, False]).itertuples():
                marca = "entra " if r.entra else "fora  "
                print(f"  {marca} {r.playlist[:50]:<50} {r.faixas:>5} faixas · {r.frac_dono:5.0%} adicionadas por você")
            fontes += [(n, listas[n]) for n in tab.playlist[tab.entra]]
        else:
            print(f"\nNenhuma playlist em {args.playlists} (exportify.app → Export All → descompactar aí).")
        for p in sorted(args.avulsos.glob("*.csv")):
            d = ler(p)
            nome = re.sub(r"^pendentes ", "", nome_da_lista(p))
            print(f"Avulso: {p.name} → origem \"{nome}\", {len(d)} faixas")
            fontes.append((nome, d))

    df = juntar(fontes)
    so_playlist = int((~df.curtida).sum())
    print(f"\nFaixas: {len(df)} (curtidas {int(df.curtida.sum())} · só em playlist/avulso {so_playlist})")
    if so_playlist:
        # mesma gravação (ISRC) com outro ID do Spotify: não é deduplicada, só avisada
        isrc_curt = set(df.isrc[df.curtida].dropna())
        mesmo_isrc = int(df[~df.curtida].isrc.isin(isrc_curt).sum())
        print(f"  das só em playlist, {mesmo_isrc} têm o mesmo ISRC de uma curtida (outro ID; mantidas)")
    print(f"Artistas principais distintos: {df.artista.nunique()} · álbuns distintos: {df.album_id.nunique()}")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUT, index=False)
    print(f"Salvo em {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
