"""OBSOLETO desde 20/11/2026: as correções agora ficam em data/manual/reclassificacao.json
(ver reclassificacao.py; a planilha foi migrada com --migrar-planilha e removida).
O módulo continua por causa de EXTRAS, dos estilos do Excel e de ler_manual(), usado na migração.

Planilha de classificação manual: data/manual/classificacao_manual.xlsx.

Faixas sem tag do Last.fm em nenhum nível (faixa, álbum, artista) entram aqui para o
usuário preencher a coluna "generos" no Excel, separando com ";".

A planilha é a fonte única (versionada). Ao ser atualizada, as linhas existentes são
lidas com o que já foi preenchido, as faixas novas são acrescentadas e o arquivo é
reescrito em ordem de artista/álbum. Nada que foi preenchido é apagado.

Uso direto (regera a planilha a partir de nivel_faixas.parquet, sem chamar a API):
    python -m mapa_generos.manual
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

from .musicbrainz import chave, mapa_canonico

ROOT = Path(__file__).resolve().parents[2]
MANUAL = ROOT / "data" / "manual" / "classificacao_manual.xlsx"
ABA = "Classificação"
ABA_LISTA = "Lista de gêneros"
TAGS = ROOT / "data" / "processed" / "tags_faixas.parquet"
# Termos muito usados nas suas tags que não estão na lista do MusicBrainz, mas são
# quase gênero. Entram no dropdown (rnb aparece como "r&b").
EXTRAS = {"indie": "indie", "alternative": "alternative", "rap": "rap", "rnb": "r&b",
          "r&b": "r&b", "hardcore": "hardcore"}

# (coluna, título no Excel, largura)
# Só "generos" é para preencher; fica por último. track_id fica oculta (é a chave).
COLUNAS = [
    ("artista", "Artista", 28),
    ("faixa", "Faixa", 40),
    ("album", "Álbum", 40),
    ("link", "Spotify", 10),
    ("generos", "Gêneros (preencher)", 40),
    ("track_id", "track_id", 25),
]
SEM_NOME = "(sem nome no Spotify)"
TITULOS = {c: t for c, t, _ in COLUNAS}
CAMPOS = [c for c, _, _ in COLUNAS]

FONTE = Font(name="Arial", size=10)
FONTE_TITULO = Font(name="Arial", size=10, bold=True, color="FFFFFF")
FONTE_LINK = Font(name="Arial", size=10, color="0563C1", underline="single")
FUNDO_TITULO = PatternFill("solid", fgColor="404040")
FUNDO_PREENCHER = PatternFill("solid", fgColor="FFFF00")
FUNDO_TITULO_PREENCHER = PatternFill("solid", fgColor="BF8F00")
FUNDO_FAIXA_ALTERNADA = PatternFill("solid", fgColor="F2F2F2")


def link_spotify(track_id: str) -> str:
    return f"https://open.spotify.com/track/{track_id}"


def opcoes_generos(tags_path: Path = TAGS) -> pd.DataFrame:
    """Gêneros já presentes nas tags das suas faixas, com o nº de faixas de cada um.

    Só entram tags reconhecidas como gênero pelo MusicBrainz (mais os EXTRAS),
    comparadas sem diferenciar maiúsculas, hífens e espaços. Ordem alfabética.
    """
    if not tags_path.exists():
        return pd.DataFrame(columns=["genero", "faixas"])
    t = pd.read_parquet(tags_path, columns=["track_id", "tag"])
    canon = mapa_canonico()
    canon.update({chave(k): v for k, v in EXTRAS.items()})
    t["genero"] = t.tag.map(lambda x: canon.get(chave(x)))
    por = t.dropna(subset=["genero"]).groupby("genero").track_id.nunique()
    return (por.rename("faixas").reset_index()
            .sort_values("genero", key=lambda s: s.str.lower()).reset_index(drop=True))


def ler_manual(path: Path = MANUAL) -> pd.DataFrame:
    """Lê a planilha (colunas internas: artista, faixa, album, link, generos, track_id)."""
    if not path.exists():
        return pd.DataFrame(columns=CAMPOS)
    df = pd.read_excel(path, sheet_name=ABA, dtype=str, keep_default_na=False)
    df = df.rename(columns={t: c for c, t in TITULOS.items()})
    return df[[c for c in CAMPOS if c in df.columns]]


def escrever_manual(df: pd.DataFrame, path: Path = MANUAL) -> None:
    df = df.copy()
    df["link"] = df.track_id.map(link_spotify)
    df.loc[df.faixa.eq("") & df.artista.eq(""), "faixa"] = SEM_NOME
    # Ordem: por artista e álbum (faixas sem artista no fim), para classificar em bloco.
    df["_sem_artista"] = df.artista.eq("")
    df = df.sort_values(["_sem_artista", "artista", "album", "faixa"], key=lambda s: s if s.name == "_sem_artista" else s.str.lower())
    df = df[CAMPOS]

    wb = Workbook()
    ws = wb.active
    ws.title = ABA
    ws.append([TITULOS[c] for c in CAMPOS])
    col_gen = CAMPOS.index("generos") + 1
    col_link = CAMPOS.index("link") + 1
    for cel in ws[1]:
        cel.font, cel.fill = FONTE_TITULO, FUNDO_TITULO
        cel.alignment = Alignment(vertical="center")
    ws.cell(1, col_gen).fill = FUNDO_TITULO_PREENCHER
    grupo, artista_ant = 0, None
    for linha in df.itertuples(index=False):
        ws.append(list(linha))
        r = ws.max_row
        if linha.artista != artista_ant:  # alterna o fundo a cada artista
            grupo, artista_ant = grupo + 1, linha.artista
        for cel in ws[r]:
            cel.font = FONTE
            if grupo % 2 == 0:
                cel.fill = FUNDO_FAIXA_ALTERNADA
        ws.cell(r, col_gen).fill = FUNDO_PREENCHER
        c = ws.cell(r, col_link)
        c.hyperlink, c.value, c.font = c.value, "abrir", FONTE_LINK
    for i, (_, _, largura) in enumerate(COLUNAS, start=1):
        ws.column_dimensions[get_column_letter(i)].width = largura
    ws.column_dimensions[get_column_letter(CAMPOS.index("track_id") + 1)].hidden = True
    ws.freeze_panes = "B2"
    ws.auto_filter.ref = ws.dimensions

    # Dropdown na coluna de gêneros, com a lista da aba "Lista de gêneros".
    opcoes = opcoes_generos()
    if len(opcoes):
        lista = wb.create_sheet(ABA_LISTA)
        lista.append(["Gênero", "Nº de faixas suas com essa tag"])
        for cel in lista[1]:
            cel.font, cel.fill = FONTE_TITULO, FUNDO_TITULO
        for g, n in opcoes.itertuples(index=False):
            lista.append([g, int(n)])
            for cel in lista[lista.max_row]:
                cel.font = FONTE
        lista.column_dimensions["A"].width = 32
        lista.column_dimensions["B"].width = 30
        lista.freeze_panes = "A2"
        lista.auto_filter.ref = lista.dimensions
        # Sem mensagem de erro: o dropdown sugere, mas aceita texto livre
        # (vários gêneros com ";" ou um gênero que não esteja na lista).
        dv = DataValidation(type="list", formula1=f"'{ABA_LISTA}'!$A$2:$A${len(opcoes) + 1}",
                            allow_blank=True, showErrorMessage=False, showInputMessage=True,
                            promptTitle="Gêneros", prompt="Escolha da lista ou digite; vários: separe com ;")
        letra = get_column_letter(col_gen)
        dv.add(f"{letra}2:{letra}{max(ws.max_row, 2)}")
        ws.add_data_validation(dv)

    leg = wb.create_sheet("Como preencher")
    texto = [
        ("Como preencher", True),
        ("Edite só a coluna amarela \"Gêneros (preencher)\" da aba Classificação. As outras são geradas pelo script.", False),
        ("Clique na célula e use a setinha do dropdown: as opções são os gêneros que já aparecem nas suas outras faixas.", False),
        ("A aba \"Lista de gêneros\" mostra as mesmas opções com o nº de faixas de cada uma (use Ctrl+F para procurar).", False),
        ("Vários gêneros na mesma célula: escolha um e complete digitando \"; outro\". Texto livre também é aceito.", False),
        ("Deixe em branco se não souber: a faixa continua na lista de pendentes.", False),
        ("Dica: preencha a primeira faixa do artista e arraste/copie para as outras.", False),
        ("Faixas de um mesmo artista ficam juntas, com fundo alternado entre artistas.", False),
        ("O link \"abrir\" leva à faixa no Spotify (útil para as faixas \"(sem nome no Spotify)\").", False),
        ("Rodar a coleta de novo só acrescenta faixas novas; o que você preencheu é mantido.", False),
        ("", False),
        ("Exemplo (formato esperado):", True),
        ("Artista: Enversos  ·  Faixa: Baile Black  ·  Gêneros: funk carioca; trap", False),
    ]
    for t, negrito in texto:
        leg.append([t])
        leg.cell(leg.max_row, 1).font = Font(name="Arial", size=10, bold=negrito)
    leg.column_dimensions["A"].width = 110

    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)


def atualizar_manual(sem_tag: pd.DataFrame, path: Path = MANUAL) -> tuple[int, int]:
    """Acrescenta à planilha as faixas sem tag que ainda não estão lá.

    `sem_tag` precisa das colunas track_id, artista, faixa, album.
    Retorna (novas, pendentes): faixas acrescentadas agora e total ainda sem gêneros.
    """
    atual = ler_manual(path)
    novas = sem_tag[~sem_tag.track_id.isin(atual.track_id)].assign(generos="")
    cols = ["track_id", "artista", "faixa", "album", "generos"]
    tudo = pd.concat([atual[cols], novas[cols].fillna("")], ignore_index=True).fillna("")
    if len(tudo):
        escrever_manual(tudo, path)
    return len(novas), int((tudo.generos.str.strip() == "").sum())


def main() -> None:
    faixas = pd.read_parquet(ROOT / "data" / "processed" / "faixas.parquet")
    nivel = pd.read_parquet(ROOT / "data" / "processed" / "nivel_faixas.parquet")
    sem = faixas[faixas.track_id.isin(nivel.track_id[nivel.nivel.isna()])][["track_id", "artista", "faixa", "album"]]
    novas, pendentes = atualizar_manual(sem)
    print(f"{MANUAL.relative_to(ROOT)}: {novas} novas, {pendentes} ainda sem gêneros")


if __name__ == "__main__":
    main()
