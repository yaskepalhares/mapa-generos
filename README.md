# Mapa de gêneros

Mapa interativo, no estilo rede neural, dos gêneros e subgêneros das minhas músicas curtidas no Spotify.

A classificação é feita **por faixa**, não só por artista: *Cowboy Carter* da Beyoncé deve cair em country, mesmo que a artista seja majoritariamente pop.

## Como funciona (visão geral)

```
Spotifast (cache local das Curtidas)  ──┐
Exportação de dados do Spotify (reserva) ┤──► faixas.parquet
                                         │
Last.fm: tags de faixa → álbum → artista ──► tags por faixa ──► gêneros normalizados
MusicBrainz: relações "subgênero de"     ──► hierarquia (opcional)
                                         │
                                         ▼
                           grafo (nós = gêneros, arestas = coocorrência)
                                         │
                                         ▼
                              web/index.html (sigma.js / Cytoscape)
```

- **Por que não a API do Spotify?** Desde 2024–2026 o Spotify restringiu a Web API: gêneros existem só no artista, muitas vezes vêm vazios, e a criação de novos apps foi suspensa. Ver [`docs/fontes-de-dados.md`](docs/fontes-de-dados.md).
- **Por que Last.fm?** Tem tags por faixa, por álbum e por artista, e é onde já está o histórico de plays (útil para o comparativo "curti, mas nunca ouvi").

## Estrutura

```
data/raw/         dados brutos (não versionados)
data/cache/       respostas da API do Last.fm em cache (não versionado)
data/processed/   tabelas intermediárias (não versionado)
docs/             decisões e notas de método
src/mapa_generos/ código Python
web/              visualização HTML (o JSON do grafo é gerado aqui)
```

## Status

Fases 0 a 6 concluídas (primeira versão do mapa em `web/`). Ver [`ROADMAP.md`](ROADMAP.md).

## Atualizar com playlists e correções

1. No [exportify.app](https://exportify.app), exporte "Liked" para `data/raw/liked.csv` e use "Export All" para as playlists; descompacte em `data/raw/playlists/` (só entram as playlists criadas por você).
2. Rode o pipeline (só faixas e artistas novos consultam o Last.fm/MusicBrainz):

```bash
python -m mapa_generos.ingest_exportify
python -m mapa_generos.coletar_tags
python -m mapa_generos.marcar_brasileiros
python -m mapa_generos.generos && python -m mapa_generos.hierarquia && python -m mapa_generos.familias && python -m mapa_generos.grafo
```

3. Na página, a aba **Reclassificar** corrige gêneros por faixa, álbum ou artista; baixe o `reclassificacao.json`, salve em `data/manual/` e rode a última linha acima.
4. Soltar um CSV do Exportify na página mostra as faixas dele no mapa; as que ainda não estão no mapa saem num `pendentes_<lista>.csv`, que vai para `data/raw/avulsos/`.

## Configuração

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .
cp .env.example .env   # preencher LASTFM_API_KEY e LASTFM_USER
```
