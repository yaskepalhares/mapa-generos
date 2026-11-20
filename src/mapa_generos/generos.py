"""Fase 3: de tags do Last.fm para gêneros por faixa.

Entradas:
- data/processed/tags_faixas.parquet   (track_id, tag, contagem, nivel ∈ faixa/album/artista)
- data/manual/classificacao_manual.xlsx (63 faixas sem tag, gêneros separados por ";")
- data/processed/tags_pais.parquet     (track_id, "brazilian", 100, "pais")

Passos:
1. Limpeza: só fica tag reconhecida como gênero (lista do MusicBrainz + EXTRAS),
   comparada pela chave de musicbrainz.chave() (sem maiúsculas, acentos, espaços,
   hífens; rnb = r&b). Anos, "AOTY", "female vocalists", nomes de artista etc. caem
   por não estarem na lista. SINONIMOS manda variações para um nome canônico.
2. Nível: faixa → álbum → artista, o primeiro que ainda tiver algum gênero depois
   da limpeza (um nível só com "2024, AOTY" é pulado).
3. Peso: dentro do nível escolhido, contagem do Last.fm dividida pela maior contagem
   entre os gêneros desse nível (o gênero principal da faixa tem peso 1). Se várias
   tags viram o mesmo gênero, vale a maior contagem.
4. Classificação manual (nivel="manual", peso 1) substitui as tags da faixa.
5. Tag de país "brazilian" (nivel="pais", peso 1) é acrescentada à parte.

Saída: data/processed/generos_faixas.parquet, uma linha por (track_id, genero) com
peso, contagem e nivel.

Uso:
    python -m mapa_generos.generos
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from .manual import EXTRAS as EXTRAS_MANUAL
from .manual import atualizar_manual, ler_manual
from .musicbrainz import chave, mapa_canonico

ROOT = Path(__file__).resolve().parents[2]
PROC = ROOT / "data" / "processed"
TAGS = PROC / "tags_faixas.parquet"
PAIS = PROC / "tags_pais.parquet"
FAIXAS = PROC / "faixas.parquet"
SAIDA = PROC / "generos_faixas.parquet"
NIVEIS = ["faixa", "album", "artista"]

# Gêneros fora da lista do MusicBrainz que aparecem nas suas tags (ou na planilha
# manual) e são gênero de fato. chave → nome canônico.
EXTRAS = {
    **EXTRAS_MANUAL,  # indie, alternative, rap, r&b, hardcore
    "alt-pop": "alt-pop",
    "sadcore": "sadcore",
    "nova mpb": "nova mpb",
    "brazilian rap": "brazilian rap",
    "brazilian indie": "brazilian indie",
    "brazilian rock": "brazilian rock",
    "brazilian pop": "brazilian pop",
    "brazilian trap": "brazilian trap",
    "brazilian hardcore": "brazilian hardcore",
    "k-indie": "k-indie",
    "k-rock": "k-rock",
    "k-r&b": "k-r&b",
    "k-hip hop": "k-hip hop",
    "uk hip hop": "uk hip hop",
    "emo revival": "emo revival",
    "emo trap": "emo trap",
    "jazz hop": "jazz hop",
    "indie punk": "indie punk",
    "orchestral pop": "orchestral pop",
    "dark pop": "dark pop",
}

# Variações → nome canônico (que precisa estar no MusicBrainz ou nos EXTRAS).
SINONIMOS = {
    "alt pop": "alt-pop",
    "alt rock": "alternative rock",
    "alt-country": "alternative country",
    "prog rock": "progressive rock",
    "trap rap": "trap",
    "underground rap": "underground hip hop",
    "alternative rap": "alternative hip hop",
    "east coast rap": "east coast hip hop",
    "west coast rap": "west coast hip hop",
    "southern rap": "southern hip hop",
    "baile funk": "funk carioca",
    # "hardcore" é ambíguo (punk × eletrônico); nas suas faixas é quase sempre o punk
    "hardcore": "hardcore punk",
    "tropicalismo": "tropicália",
    "electronic dance music": "edm",
    "rap nacional": "brazilian rap",
    "trap br": "brazilian trap",
    "trap nacional": "brazilian trap",
    "indie brasileiro": "brazilian indie",
    "rock brasileiro": "brazilian rock",
    "rock brasil": "brazilian rock",
    "funk bh": "funk de bh",
    "pagode baiano": "pagodão",
    "korean indie": "k-indie",
    "krnb": "k-r&b",
    "korean hip hop": "k-hip hop",
    "uk hiphop": "uk hip hop",
}

# Tags que batem com um gênero do MusicBrainz mas, nas suas faixas, não são gênero.
# (Preenchida a partir da conferência da Fase 3; ver relatório "nomes de artista".)
BLOQUEIO: set[str] = set()


def normalizador() -> dict[str, str]:
    """chave da tag → gênero canônico."""
    canon = mapa_canonico()
    canon.update({chave(k): v for k, v in EXTRAS.items()})
    for var, alvo in SINONIMOS.items():
        alvo_canon = canon.get(chave(alvo))
        if alvo_canon is None:
            raise ValueError(f"sinônimo {var!r} aponta para {alvo!r}, que não é gênero conhecido")
        canon[chave(var)] = alvo_canon
    for b in BLOQUEIO:
        canon.pop(chave(b), None)
    return canon


def limpar(tags: pd.DataFrame, canon: dict[str, str]) -> pd.DataFrame:
    """Troca tag por gênero canônico; descarta o que não é gênero."""
    t = tags.assign(genero=tags.tag.map(lambda x: canon.get(chave(x))))
    t = t.dropna(subset=["genero"])
    # várias tags → mesmo gênero (ex.: "hip hop" e "Hip-Hop"): fica a maior contagem
    return t.groupby(["track_id", "nivel", "genero"], as_index=False).contagem.max()


def escolher_nivel(limpas: pd.DataFrame) -> pd.DataFrame:
    """Para cada faixa, fica só o primeiro nível (faixa → álbum → artista) com gênero."""
    ordem = {n: i for i, n in enumerate(NIVEIS)}
    melhor = limpas.assign(o=limpas.nivel.map(ordem)).groupby("track_id").o.min()
    escolhido = melhor.map(dict(enumerate(NIVEIS))).rename("nivel_escolhido")
    t = limpas.join(escolhido, on="track_id")
    t = t[t.nivel == t.nivel_escolhido].drop(columns="nivel_escolhido")
    t["peso"] = t.contagem / t.groupby("track_id").contagem.transform("max")
    return t


def generos_manuais(canon: dict[str, str]) -> pd.DataFrame:
    m = ler_manual()
    linhas = []
    for tid, txt in zip(m.track_id, m.generos):
        for g in (p.strip() for p in str(txt).split(";")):
            if g:
                # gênero digitado à mão fora da lista é mantido como escrito (minúsculas)
                linhas.append((tid, canon.get(chave(g), g.lower()), 100, "manual", 1.0))
    df = pd.DataFrame(linhas, columns=["track_id", "genero", "contagem", "nivel", "peso"])
    return df.drop_duplicates(["track_id", "genero"])


def gerar() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Retorna (generos_faixas, tags_limpas_todos_os_niveis)."""
    canon = normalizador()
    tags = pd.read_parquet(TAGS)
    limpas = limpar(tags, canon)
    lastfm = escolher_nivel(limpas)
    manual = generos_manuais(canon)
    lastfm = lastfm[~lastfm.track_id.isin(manual.track_id)]  # o manual manda
    pais = pd.read_parquet(PAIS).rename(columns={"tag": "genero"}).assign(peso=1.0)
    cols = ["track_id", "genero", "peso", "contagem", "nivel"]
    out = pd.concat([lastfm[cols], manual[cols], pais[cols]], ignore_index=True)
    out = out.sort_values(["track_id", "peso"], ascending=[True, False]).reset_index(drop=True)
    return out, limpas


def relatorio(out: pd.DataFrame, limpas: pd.DataFrame) -> None:
    faixas = pd.read_parquet(FAIXAS, columns=["track_id", "faixa", "artista", "album"])
    tags = pd.read_parquet(TAGS)
    total = len(faixas)
    pct = lambda n: f"{n:,} ({n / total:.1%})".replace(",", ".")

    sem_pais = out[out.nivel != "pais"]
    nivel_faixa = sem_pais.groupby("track_id").nivel.first().reindex(faixas.track_id)
    print(f"\n== Cobertura ({total:,} faixas) ==".replace(",", "."))
    for n in NIVEIS + ["manual"]:
        print(f"  {n:8s} {pct(int((nivel_faixa == n).sum()))}")
    print(f"  sem gênero {pct(int(nivel_faixa.isna().sum()))}")

    # Quantas faixas pularam um nível que tinha tag mas ficou vazio após a limpeza
    bruto = tags.groupby("track_id").nivel.agg(set)
    limpo = limpas.groupby("track_id").nivel.agg(set).reindex(bruto.index)
    ordem = {n: i for i, n in enumerate(NIVEIS)}
    def pulou(tid):
        b = min((ordem[n] for n in bruto[tid]), default=None)
        l = limpo[tid]
        return b is not None and (not isinstance(l, set) or min(ordem[n] for n in l) > b)
    n_pulou = sum(pulou(t) for t in bruto.index)
    print(f"  faixas que pularam um nível esvaziado pela limpeza: {pct(n_pulou)}")

    print(f"\n== Tamanho ==\n  {len(out):,} linhas · {out.genero.nunique():,} gêneros distintos".replace(",", "."))
    print(f"  gêneros por faixa (sem 'brazilian'): mediana {sem_pais.groupby('track_id').size().median():.0f}")
    print(f"  tags brutas distintas: {tags.tag.str.lower().nunique():,}".replace(",", "."))

    print("\n== 25 gêneros com mais faixas (qualquer peso) ==")
    top = out.groupby("genero").track_id.nunique().sort_values(ascending=False).head(25)
    print("  " + " · ".join(f"{g} {n}" for g, n in top.items()))

    print("\n== Tags descartadas com mais faixas (conferir se alguma é gênero) ==")
    canon = normalizador()
    fora = tags[tags.tag.map(lambda x: chave(x) not in canon)]
    fora = fora.groupby(fora.tag.str.lower()).track_id.nunique().sort_values(ascending=False).head(40)
    print("  " + " · ".join(f"{g} {n}" for g, n in fora.items()))

    print("\n== Gêneros aceitos que coincidem com nome de artista ==")
    nomes = {chave(a) for a in faixas.artista.dropna()}
    coinc = sorted({g for g in out.genero.unique() if chave(g) in nomes})
    print("  " + (", ".join(coinc) or "nenhum"))

    def mostra(titulo, filtro):
        ids = faixas[filtro].track_id.head(3)
        print(f"\n-- {titulo}")
        for tid in ids:
            f = faixas.set_index("track_id").loc[tid]
            g = out[out.track_id == tid]
            gs = ", ".join(f"{r.genero} {r.peso:.2f}" for r in g.itertuples())
            nv = g[g.nivel != "pais"].nivel.iloc[0] if (g.nivel != "pais").any() else "—"
            print(f"  {f.artista} — {f.faixa} [{f.album}] ({nv}): {gs}")

    print("\n== Exemplos ==")
    mostra("Beyoncé, COWBOY CARTER", faixas.album.str.contains("COWBOY CARTER", case=False, na=False))
    mostra("Emicida", faixas.artista.eq("Emicida"))
    mostra("ITZY", faixas.artista.eq("ITZY"))
    mostra("Classificação manual", faixas.track_id.isin(out.track_id[out.nivel == "manual"]))
    amostra = faixas.sample(4, random_state=42).track_id
    mostra("Amostra aleatória (semente 42)", faixas.track_id.isin(amostra))


def mandar_para_manual(out: pd.DataFrame) -> tuple[int, int]:
    """Faixas sem nenhum gênero depois da limpeza vão para a planilha manual."""
    faixas = pd.read_parquet(FAIXAS, columns=["track_id", "artista", "faixa", "album"])
    com = out.track_id[out.nivel != "pais"]
    return atualizar_manual(faixas[~faixas.track_id.isin(com)])


def main() -> None:
    out, limpas = gerar()
    novas, pendentes = mandar_para_manual(out)
    if novas:
        print(f"planilha manual: {novas} faixas sem gênero acrescentadas ({pendentes} a preencher)")
    out.to_parquet(SAIDA, index=False)
    print(f"{SAIDA.relative_to(ROOT)}: {len(out):,} linhas".replace(",", "."))
    relatorio(out, limpas)


if __name__ == "__main__":
    main()
