# Contexto para o Claude Code — mapa-generos

Projeto pessoal do Yaske: mapa interativo, estilo rede neural, dos gêneros e subgêneros das ~4.018 músicas curtidas no Spotify. Uso pessoal, roda no Mac (macOS, Apple Silicon). Responder em português.

## Decisões já tomadas (ver docs/decisoes.md)
- Classificar **por faixa**, com fallback faixa → álbum → artista (ex.: *Cowboy Carter* da Beyoncé deve cair em country, não R&B/pop).
- Gêneros vêm das **tags do Last.fm**, não do Spotify (API do Spotify restrita desde 2024–2026; gênero só no artista e muitas vezes vazio).
- **Todos os subgêneros** entram, sem corte mínimo de faixas; filtrar por peso só na interface.
- Hierarquia (via relações "subgenre of" do MusicBrainz) é desejada, mas pode cair para "só proximidade" se ficar complexa. Critério na Fase 4 do ROADMAP.
- Visualização: HTML simples com grafo de força (sigma.js ou Cytoscape, ForceAtlas2), publicável no GitHub Pages. Obsidian só como extra.
- Futuro (Fase 7): cruzar curtidas × scrobbles do Last.fm para achar "curti e nunca/quase nunca ouvi".
- O usuário quer números reais e verificados; não inventar métricas.

## Estado atual
- Fases 0 a 5 concluídas (primeira versão). Fase 2: `coletar_tags.py` coletou os 3 níveis das 4.018 faixas (tags de faixa 25,5%, álbum 75,8%, artista 98,4%; 63 sem nada) → `data/processed/tags_faixas.parquet` e `nivel_faixas.parquet` (não versionados; o cache em `data/cache/lastfm/` permite regerar sem novas chamadas). Correções manuais de gênero ficam em `data/manual/reclassificacao.json` (versionado; `reclassificacao.py`), editadas na aba Reclassificar da página; a antiga planilha `classificacao_manual.xlsx` (63 faixas preenchidas) foi migrada e removida em 20/11/2026. Fase 2b: `marcar_brasileiros.py` gera `tags_pais.parquet` (tag `brazilian` por faixa: 225 artistas, 781 faixas) e a revisão `data/manual/artistas_brasileiros.xlsx` (correções do usuário são mantidas). MusicBrainz já consultado para os 1.030 artistas (em cache); `--so-cache` evita a rede. Fase 3 (primeira versão): `generos.py` junta tags_faixas + planilha manual + tags_pais → `data/processed/generos_faixas.parquet` (track_id, genero, peso, contagem, nivel; não versionado). Cobertura 99,6%; 18 faixas sem gênero aparecem como pendentes na aba Reclassificar. Fase 4: `hierarquia.py` lê as relações das páginas web do MusicBrainz (a API não as expõe) → `generos_relacoes.parquet`; hierarquia mantida (13,4% sem pai, 0 ciclos). `familias.py`: 11 famílias de cor aprovadas → `generos_familias.parquet`. Fase 5: `grafo.py` → `web/grafo.json` + `web/faixas.json` (versionados). Fase 6 (primeira versão): `web/index.html` + `app.js` + `estilo.css` (sigma.js, ForceAtlas2 no navegador); servir com `python3 -m http.server 8765 --directory web`. Visual aprovado (20/11/2026); publicar no GitHub Pages só quando ele pedir. Ver ROADMAP.md. Fase 1b/6 (20/11/2026): `ingest_exportify.py` junta Curtidas + playlists próprias (`data/raw/playlists/`, dono pela coluna "Adicionado por") + `data/raw/avulsos/`, com `origens` por faixa; a página tem filtro por origem, CSV do Exportify por arrastar e a aba Reclassificar. Playlists exportadas (83, `owner:me`, `--todas`) e pipeline rodado: 5.990 faixas, 586 gêneros. `marcar_brasileiros.py` usa Wikidata (ID do Spotify) → Wikipédia pt (nome) → MusicBrainz/Last.fm → "?" para o usuário (`wikidata.py`). Pendentes: 151 artistas "?" na planilha de brasileiros e 93 faixas sem gênero. Se a porta 8765 estiver ocupada, use a configuração `mapa-web-livre` do `.claude/launch.json`.
- `data/raw/liked.csv`: export do Exportify (exportify.app, playlist "Liked"). **Não versionado.** O usuário tem uma cópia em `~/Downloads/liked.csv`.
- `python -m mapa_generos.ingest_exportify` → `data/processed/faixas.parquet` (4.018 faixas, 1.030 artistas principais por nome, 2.218 álbuns). Já testado.
- `src/mapa_generos/lastfm.py`: cliente com cache em disco (`data/cache/lastfm/`), ~4 req/s, fallback faixa → álbum → artista, registra o nível de origem. Já rodou em lote (19/11/2026).
- `ingest_spotifast.py`: lê o cache do app Spotifast, mas ele só guarda as 50 curtidas mais recentes; serve só para atualizações incrementais.

## Credenciais
- `.env` (não versionado) com `LASTFM_API_KEY` e `LASTFM_USER=yaskepalhares`. Modelo em `.env.example`.
- Nunca commitar `.env` nem imprimir a chave.

## Teste de referência do Last.fm (19/11/2026)
"TEXAS HOLD 'EM" (Beyoncé): faixa sem tags; álbum COWBOY CARTER → 2024, country, americana, AOTY, folk, country pop…; artista → rnb, pop, female vocalists, soul. Confirma o fallback e a necessidade de limpar tags que não são gênero (anos, "AOTY", "female vocalists", nome do artista, sinônimos como rnb/r&b).

## Próximos passos sugeridos (Fase 2)
1. Script `coletar_tags.py`: para cada faixa de `faixas.parquet`, chamar `tags_da_faixa(artista, faixa, album)`. Cache por álbum e por artista para não repetir chamadas (são 2.218 álbuns e 1.030 artistas). Retomável se interrompido. Barra de progresso.
2. Saída `data/processed/tags_faixas.parquet`: uma linha por (track_id, tag, contagem, nivel).
3. Relatório de cobertura: % de faixas com tag própria, herdada do álbum, herdada do artista e sem tag.
4. Rodar primeiro em ~50 faixas para validar, depois em tudo (~30 min no total).
5. Atualizar ROADMAP.md e docs/decisoes.md a cada etapa; commits pequenos em português.

## Convenções
- Python ≥ 3.11, pandas, parquet. Código e comentários em português.
- Commits pequenos e descritivos em português.
