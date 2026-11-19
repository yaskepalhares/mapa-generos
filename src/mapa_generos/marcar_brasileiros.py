"""Marca com a tag "brazilian" todas as faixas cujo artista principal é brasileiro.

Sinais, por artista principal (o 1º artista da faixa no Spotify):
1. MusicBrainz: país do artista (busca por nome; homônimos são desempatados pelo link
   do Spotify; se continuar ambíguo, o MusicBrainz não decide).
2. Last.fm: tag de país no nível do artista ("brazilian", "brazil", "brasil"…).
   Mesmo com peso baixo ela é confiável (Don L, BK, Froid têm peso 1–4).
3. Planilha manual: gêneros preenchidos pelo usuário que indicam Brasil
   ("brazilian rap", "funk brasileiro", "forró"…).

Regra: brasileiro se o MusicBrainz diz BR, ou se o Last.fm/planilha dizem Brasil e o
MusicBrainz não aponta outro país. Conflitos e casos sem nenhum sinal, mas com títulos
que parecem português, ficam marcados para revisão.

A decisão fica em data/manual/artistas_brasileiros.xlsx (versionada). A coluna
"Brasileiro?" pode ser corrigida à mão no Excel; correções são mantidas nas próximas
execuções (coluna "Corrigido à mão" = sim).

Saída: data/processed/tags_pais.parquet, uma linha (track_id, tag="brazilian",
contagem=100, nivel="pais") por faixa de artista brasileiro. A Fase 3 junta isso a
tags_faixas.parquet e à classificação manual.

Uso:
    python -m mapa_generos.marcar_brasileiros             # consulta o MusicBrainz (lento)
    python -m mapa_generos.marcar_brasileiros --so-cache  # só o que já está em cache
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation
from tqdm import tqdm

from . import musicbrainz
from .manual import FONTE, FONTE_TITULO, FUNDO_PREENCHER, FUNDO_TITULO, FUNDO_TITULO_PREENCHER, ler_manual

ROOT = Path(__file__).resolve().parents[2]
FAIXAS = ROOT / "data" / "processed" / "faixas.parquet"
TAGS = ROOT / "data" / "processed" / "tags_faixas.parquet"
SAIDA = ROOT / "data" / "processed" / "tags_pais.parquet"
REVISAO = ROOT / "data" / "manual" / "artistas_brasileiros.xlsx"
ABA = "Artistas"

TAG_PAIS_LASTFM = re.compile(
    r"brazil|brazilian|brasil|brasileiro|brasileira|brazilian music|musica brasileira|música brasileira")
GENERO_BR_MANUAL = re.compile(r"brazil|brasil|forr[oó]|macumba|funk carioca|\bmpb\b", re.I)
# Indícios de português nos títulos (só para sugerir revisão, nunca decide sozinho).
PORTUGUES = re.compile(
    r"[ãõç]|\b(?:não|nao|você|voce|pra|meu|minha|amor|saudade|coração|coracao|que|sem|nós|nos|"
    r"dia|noite|vida|tudo|nada|uma|ela|ele|baile|favela|quebrada|mano)\b", re.I)

COLUNAS = [  # (campo, título, largura)
    ("artista", "Artista", 32),
    ("brasileiro", "Brasileiro? (pode corrigir)", 24),
    ("revisar", "Revisar", 34),
    ("faixas", "Nº de faixas", 12),
    ("pais_mb", "País no MusicBrainz", 22),
    ("tag_lastfm", "Tag de país no Last.fm", 22),
    ("manual", "Gênero BR na planilha manual", 26),
    ("exemplo", "Exemplo de faixa", 40),
    ("corrigido", "Corrigido à mão", 16),
]
TITULOS = {c: t for c, t, _ in COLUNAS}


def sinais_por_artista(faixas: pd.DataFrame) -> pd.DataFrame:
    art = (faixas.dropna(subset=["artista"])
           .assign(spotify_id=lambda d: d.artista_ids.str[0])
           .groupby("artista")
           .agg(faixas=("track_id", "size"), spotify_id=("spotify_id", "first"),
                exemplo=("faixa", "first"), titulos=("faixa", lambda s: " | ".join(s.dropna())))
           .reset_index())

    # 1) MusicBrainz (com cache; a 1ª execução leva 30–50 min). Falhas não interrompem:
    #    o artista fica como "erro" e é consultado de novo na próxima execução.
    mb = []
    for row in tqdm(art.itertuples(index=False), total=len(art), unit="artista", desc="MusicBrainz"):
        try:
            mb.append(musicbrainz.pais_do_artista(row.artista, row.spotify_id))
        except musicbrainz.ErroMusicBrainz:
            mb.append({"pais": None, "como": "erro"})
    art["pais_mb"] = [r["pais"] or "" for r in mb]
    art["como_mb"] = [r["como"] for r in mb]
    art.attrs["erros_mb"] = sum(r["como"] == "erro" for r in mb)

    # 2) Last.fm: maior peso de uma tag de país BR no nível do artista
    t = pd.read_parquet(TAGS)
    t = t[t.nivel == "artista"].merge(faixas[["track_id", "artista"]], on="track_id")
    t = t[t.tag.str.lower().str.fullmatch(TAG_PAIS_LASTFM.pattern)]
    lf = t.groupby("artista").apply(
        lambda g: g.loc[g.contagem.idxmax(), "tag"] + f" ({g.contagem.max()})", include_groups=False)
    art["tag_lastfm"] = art.artista.map(lf).fillna("")

    # 3) Planilha manual
    m = ler_manual()
    m = m[m.generos.str.contains(GENERO_BR_MANUAL)]
    art["manual"] = art.artista.map(m.groupby("artista").generos.first()).fillna("")
    return art


def decidir(art: pd.DataFrame) -> pd.DataFrame:
    br_mb = art.pais_mb.eq("BR")
    outro_mb = art.pais_mb.ne("") & ~br_mb
    br_outros = art.tag_lastfm.ne("") | art.manual.ne("")
    art["brasileiro"] = (br_mb | (br_outros & ~outro_mb)).map({True: "sim", False: "não"})

    rev = pd.Series("", index=art.index)
    rev[br_outros & outro_mb] = "conflito: Last.fm/planilha dizem Brasil, MusicBrainz diz " + art.pais_mb
    sem_sinal = ~br_mb & ~br_outros & art.pais_mb.eq("")
    pt = art.titulos.str.contains(PORTUGUES)
    rev[sem_sinal & pt] = "sem dados de país; títulos parecem português"
    rev[art.como_mb.eq("erro") & rev.eq("")] = "MusicBrainz falhou: rode de novo"
    art["revisar"] = rev
    return art


def mesclar_correcoes(art: pd.DataFrame) -> pd.DataFrame:
    """Mantém o que o usuário corrigiu à mão na planilha de revisão."""
    art["corrigido"] = ""
    if not REVISAO.exists():
        return art
    ant = pd.read_excel(REVISAO, sheet_name=ABA, dtype=str, keep_default_na=False)
    ant = ant.rename(columns={t: c for c, t in TITULOS.items()})
    ant = ant.set_index("artista")
    for i, row in art.iterrows():
        if row.artista not in ant.index:
            continue
        antes = ant.loc[row.artista]
        valor = str(antes["brasileiro"]).strip().lower()
        valor = {"s": "sim", "n": "não", "nao": "não", "yes": "sim", "no": "não"}.get(valor, valor)
        # correção = já marcada antes, ou valor diferente do que o script decidiria agora
        if valor in ("sim", "não") and (antes.get("corrigido") == "sim" or valor != row.brasileiro):
            art.at[i, "brasileiro"], art.at[i, "corrigido"] = valor, "sim"
    return art


def escrever_revisao(art: pd.DataFrame) -> None:
    ordem = art.assign(
        _o=art.revisar.ne("").map({True: 0, False: 1}) * 2 + art.brasileiro.ne("sim").astype(int))
    ordem = ordem.sort_values(["_o", "artista"], key=lambda s: s if s.name == "_o" else s.str.lower())
    campos = [c for c, _, _ in COLUNAS]
    wb = Workbook()
    ws = wb.active
    ws.title = ABA
    ws.append([TITULOS[c] for c in campos])
    for cel in ws[1]:
        cel.font, cel.fill = FONTE_TITULO, FUNDO_TITULO
        cel.alignment = Alignment(vertical="center", wrap_text=True)
    col_br = campos.index("brasileiro") + 1
    ws.cell(1, col_br).fill = FUNDO_TITULO_PREENCHER
    for row in ordem[campos].itertuples(index=False):
        ws.append([int(v) if c == "faixas" else v for c, v in zip(campos, row)])
        for cel in ws[ws.max_row]:
            cel.font = FONTE
        ws.cell(ws.max_row, col_br).fill = FUNDO_PREENCHER
    for i, (_, _, w) in enumerate(COLUNAS, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w
    letra = get_column_letter(col_br)
    dv = DataValidation(type="list", formula1='"sim,não"', allow_blank=False)
    dv.add(f"{letra}2:{letra}{ws.max_row}")
    ws.add_data_validation(dv)
    ws.freeze_panes = "B2"
    ws.auto_filter.ref = ws.dimensions

    leg = wb.create_sheet("Como revisar")
    for t, b in [
        ("Como revisar", True),
        ("Primeiro vêm os artistas marcados em \"Revisar\" (conflitos e casos sem dados de país), depois os brasileiros, depois os demais.", False),
        ("Para corrigir, mude a coluna amarela \"Brasileiro?\" para sim ou não. O resto é gerado pelo script.", False),
        ("Rodar de novo (python -m mapa_generos.marcar_brasileiros) mantém suas correções (\"Corrigido à mão\" = sim).", False),
        ("Vale o artista principal (o 1º artista da faixa no Spotify). Participações (feat.) não contam.", False),
    ]:
        leg.append([t])
        leg.cell(leg.max_row, 1).font = Font(name="Arial", size=10, bold=b)
    leg.column_dimensions["A"].width = 120
    REVISAO.parent.mkdir(parents=True, exist_ok=True)
    wb.save(REVISAO)


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="Marca faixas de artistas brasileiros com a tag brazilian.")
    ap.add_argument("--so-cache", action="store_true",
                    help="não consulta o MusicBrainz; usa só respostas já em cache")
    args = ap.parse_args(argv)
    musicbrainz.SO_CACHE = args.so_cache
    faixas = pd.read_parquet(FAIXAS)
    art = mesclar_correcoes(decidir(sinais_por_artista(faixas)))
    escrever_revisao(art)

    br = set(art.artista[art.brasileiro == "sim"])
    sel = faixas[faixas.artista.isin(br)]
    pd.DataFrame({"track_id": sel.track_id, "tag": "brazilian", "contagem": 100, "nivel": "pais"}) \
        .to_parquet(SAIDA, index=False)

    print(f"\nArtistas principais: {len(art)} · brasileiros: {len(br)} ({100 * len(br) / len(art):.1f}%)")
    print(f"Faixas com a tag brazilian: {len(sel)} de {len(faixas)} ({100 * len(sel) / len(faixas):.1f}%)")
    origem = art[art.brasileiro == "sim"]
    print("Por fonte (um artista pode ter mais de uma):")
    print(f"  MusicBrainz = BR:      {int(origem.pais_mb.eq('BR').sum())}")
    print(f"  tag de país Last.fm:   {int(origem.tag_lastfm.ne('').sum())}")
    print(f"  planilha manual:       {int(origem.manual.ne('').sum())}")
    print(f"  corrigido à mão:       {int(origem.corrigido.eq('sim').sum())}")
    n_erro = int(art.como_mb.eq("erro").sum())
    if n_erro:
        print(f"ATENÇÃO: {n_erro} artistas sem resposta do MusicBrainz; rode de novo para completar.")
    n_rev = int(art.revisar.ne("").sum())
    print(f"Para revisar: {n_rev} artistas → {REVISAO.relative_to(ROOT)}")
    print(f"Salvo em {SAIDA.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
