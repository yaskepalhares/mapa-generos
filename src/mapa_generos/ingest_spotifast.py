"""Lê o cache de Músicas Curtidas do Spotifast e gera data/processed/faixas.parquet.

Formato observado (version 1, nov/2026), em
~/Library/Caches/me.paolino.spotifast/liked-songs/<account_id_hex>.json:

    {"version": 1, "account_id": ..., "total": 4018, "next_offset": 50,
     "refreshed_at": <unix>, "changes": {...},
     "items": [{"added_at": "...", "track": {<objeto de faixa da Web API>}}]}

Atenção: o Spotifast só grava as páginas que já carregou. Se `len(items) < total`,
o script avisa; role as Curtidas até o fim no app e rode de novo.

Uso:
    python -m mapa_generos.ingest_spotifast            # usa SPOTIFAST_CACHE do .env
    python -m mapa_generos.ingest_spotifast arquivo.json
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "processed" / "faixas.parquet"


def localizar_arquivo() -> Path:
    cache = Path(os.path.expanduser(os.environ.get(
        "SPOTIFAST_CACHE", "~/Library/Caches/me.paolino.spotifast")))
    arquivos = sorted((cache / "liked-songs").glob("*.json"))
    if not arquivos:
        sys.exit(f"Nenhum JSON em {cache / 'liked-songs'}")
    if len(arquivos) > 1:
        print(f"Aviso: {len(arquivos)} contas encontradas, usando {arquivos[0].name}")
    return arquivos[0]


def ler(path: Path) -> tuple[pd.DataFrame, dict]:
    dados = json.loads(path.read_text())
    if dados.get("version") != 1:
        print(f"Aviso: versão do cache {dados.get('version')} não testada")

    linhas = []
    for item in dados["items"]:
        t = item["track"]
        album = t.get("album") or {}
        linhas.append({
            "track_id": t["id"],
            "faixa": t["name"],
            "artista": t["artists"][0]["name"] if t["artists"] else None,
            "artistas": [a["name"] for a in t["artists"]],
            "artista_ids": [a["id"] for a in t["artists"]],
            "album": album.get("name"),
            "album_id": album.get("id"),
            "album_tipo": album.get("album_type"),
            "lancamento": album.get("release_date"),
            "isrc": (t.get("external_ids") or {}).get("isrc"),
            "duracao_ms": t.get("duration_ms"),
            "popularidade": t.get("popularity"),
            "is_local": t.get("is_local"),
            "curtida_em": pd.to_datetime(item["added_at"]),
        })
    meta = {k: dados.get(k) for k in ("total", "next_offset", "refreshed_at")}
    return pd.DataFrame(linhas), meta


def main() -> None:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else localizar_arquivo()
    df, meta = ler(path)
    dup = df.duplicated("track_id").sum()
    df = df.drop_duplicates("track_id")

    print(f"Arquivo: {path}")
    print(f"Faixas lidas: {len(df)} de {meta['total']} (duplicatas removidas: {dup})")
    if meta["total"] and len(df) < meta["total"]:
        print("⚠ Cache incompleto: role as Músicas Curtidas até o fim no Spotifast e rode de novo.")
    print(f"Curtidas de {df.curtida_em.min():%d/%m/%Y} a {df.curtida_em.max():%d/%m/%Y}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUT, index=False)
    print(f"Salvo em {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
