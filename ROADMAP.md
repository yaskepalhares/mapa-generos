# Roadmap

Legenda: ✅ feito · 🔄 em andamento · ⬜ a fazer · ❓ decisão em aberto

## Fase 0 — Estrutura ✅
- ✅ Repositório, README, roadmap
- ✅ Levantamento de projetos parecidos e das fontes de dados ([`docs/fontes-de-dados.md`](docs/fontes-de-dados.md))
- ✅ Esqueleto do cliente Last.fm com cache em disco

## Fase 1 — Coletar as curtidas ✅
Meta: tabela `faixas` com as curtidas (título, artista(s), álbum, data em que curtiu, ID do Spotify).
- ✅ Fonte principal: CSV do [Exportify](https://exportify.app) → `ingest_exportify.py` → `data/processed/faixas.parquet`
- ✅ Checagem: 4.018 faixas, 0 duplicatas, 100% das IDs batem com a lista copiada do Spotifast
- ✅ Resultado: 1.030 artistas principais (por nome; 1.032 por ID do Spotify), 2.218 álbuns, curtidas de fev/2016 a nov/2026; 3 faixas sem nome de artista no Spotify
- ✅ `ingest_spotifast.py` mantido para atualizações rápidas (o cache do Spotifast só guarda as 50 curtidas mais recentes)
- ⬜ Mesclar curtidas novas do Spotifast com o CSV sem precisar reexportar

## Fase 2 — Tags por faixa (Last.fm) ✅
Meta: cada faixa com uma lista de tags ponderadas.
- ✅ `coletar_tags.py`: `track.getTopTags` → `album.getTopTags` → `artist.getTopTags`, nessa ordem de preferência
- ✅ Cache em disco por chamada + cache em memória de álbum e artista; ~4 req/s, com retentativas em erros temporários
- ✅ Retomável (`data/cache/coleta_tags.jsonl`) e com barra de progresso; testado offline com API simulada
- ✅ Registra de qual nível veio cada tag → `tags_faixas.parquet` e `nivel_faixas.parquet`
- ✅ Busca do álbum usa o artista do álbum (exceto "Various Artists"); 87 faixas têm artista do álbum diferente do da faixa
- ✅ Teste real em 50 faixas (`--amostra 50`, semente 42), 19/11/2026: faixa 19 (38%) · álbum 21 (42%) · artista 9 (18%) · sem tag 1 (2%); 0 erros; 93 chamadas em 63 s (~0,7 s/chamada, a latência domina)
- ✅ Problema achado no teste: alguns álbuns só têm tags que não são gênero (ITZY → "2020, itzy"; Emicida → "2010s, 14 tracks, 2015, Tags Ok") e bloqueavam a queda para o artista. **Decidido: coletar os 3 níveis para toda faixa**; a escolha do nível fica para a Fase 3
- ✅ Mesma amostra com os 3 níveis: tags de faixa em 19 (38%), de álbum em 39 (78%), de artista em 49 (98%); só 1 sem nada (Enversos, "Baile Black")
- ✅ Faixas sem tag nos 3 níveis vão para `data/manual/classificacao_manual.xlsx` (versionado) para classificação à mão; novas execuções só acrescentam e não apagam o que foi preenchido
- ⬜ Possível melhoria: títulos com " - Remastered 2009" ou "(feat. …)" caem para o álbum; limpar o título pode aumentar a cobertura no nível da faixa
- ✅ Coleta completa, 19/11/2026: 4.018 faixas, 0 erros, ~65 min (3.824 chamadas de faixa, 2.111 de álbum, 1.030 de artista)
- ✅ Cobertura (tem tag no nível, não exclusivo): faixa 1.026 (25,5%) · álbum 3.044 (75,8%) · artista 3.953 (98,4%)
- ✅ Melhor nível (primeiro com tag): faixa 25,5% · álbum 51,9% · artista 21,0% · sem tag 63 (1,6%)
- ✅ 72.975 linhas de tag, 3.598 tags distintas (antes da limpeza da Fase 3)
- 🔄 63 faixas sem tag (34 artistas, quase todos independentes/brasileiros; 3 sem artista/título no Spotify) em `data/manual/classificacao_manual.xlsx` — **classificação manual pelo usuário**

## Fase 3 — De tags para gêneros ⬜
Tags do Last.fm são sujas ("seen live", "favorites", "female vocalists", "2010s").
- ⬜ Lista de bloqueio de tags que não são gênero
- ⬜ Normalização (minúsculas, hífens, sinônimos: "hip hop" = "hip-hop" = "hiphop")
- ⬜ Filtrar contra a lista de gêneros do MusicBrainz (só fica o que é gênero reconhecido)
- ⬜ Sem corte mínimo de faixas por gênero (decidido); o filtro por peso fica na interface
- ⬜ Peso: combinar a contagem da tag no Last.fm com o nível de origem (faixa > álbum > artista)
- ⬜ Validação manual com casos conhecidos (ex.: faixas de *Cowboy Carter* → country)

## Fase 4 — Hierarquia ❓
- ⬜ Testar as relações "subgênero de" do MusicBrainz
- ⬜ Decidir: hierarquia explícita (rock → post-punk → darkwave) **ou** só proximidade
- Critério para desistir da hierarquia: se mais de ~30% dos seus gêneros não tiverem pai no MusicBrainz, ou se os ciclos/múltiplos pais deixarem o mapa confuso, fica só proximidade.

## Fase 5 — Grafo ⬜
- ⬜ Nós = gêneros (tamanho = nº de faixas); arestas = coocorrência na mesma faixa (peso = nº de faixas em comum)
- ⬜ Poda de arestas fracas (limiar ou backbone) para não virar uma bola de pelo
- ⬜ Detecção de comunidades (Louvain/Leiden) para colorir "famílias"
- ⬜ Exportar `web/grafo.json`

## Fase 6 — Visualização HTML ⬜
- ⬜ Layout de força (ForceAtlas2) com sigma.js ou Cytoscape
- ⬜ Clique no gênero → lista de faixas; busca; filtro por peso
- ⬜ Opcional: alternar entre visão hierárquica e por proximidade
- ⬜ Publicar via GitHub Pages

## Fase 7 — Comparativo com o Last.fm ⬜
- ⬜ Baixar o histórico de scrobbles (`user.getRecentTracks`)
- ⬜ Casar curtidas × plays (normalizando título/artista)
- ⬜ Destacar "curti e nunca/quase nunca ouvi" no mapa (ex.: opacidade = plays)

## Extras (talvez)
- ⬜ Exportar notas `.md` para navegar no Obsidian
- ⬜ Evolução no tempo: como o mapa muda por ano de curtida
- ⬜ GitHub Action para atualizar automaticamente
