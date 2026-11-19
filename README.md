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

Fase 0 — estrutura e roadmap. Ver [`ROADMAP.md`](ROADMAP.md).

## Configuração

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .
cp .env.example .env   # preencher LASTFM_API_KEY e LASTFM_USER
```
