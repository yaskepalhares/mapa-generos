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

## Fase 2b — Tag de país (brazilian) ✅
- ✅ `marcar_brasileiros.py`: artista principal brasileiro → tag `brazilian` em todas as faixas dele (`data/processed/tags_pais.parquet`)
- ✅ Sinais: país no MusicBrainz (homônimos desempatados pelo link do Spotify), tag de país no Last.fm, gêneros BR na planilha manual. Gênero sozinho (bossa nova) não conta: pegaria Laufey e Stan Getz
- ✅ MusicBrainz completo para os 1.030 artistas (19/11/2026; ~1h25 por causa de respostas 503)
- ✅ Resultado: **225 de 1.030 artistas (21,8%), 781 de 4.018 faixas (19,4%)**, incluindo 8 marcados à mão (Linguini, DJ Wallace, MC Vitin LC, Prod.Nifour, Gustavo Vaz, Artwo, ogoin, Supercombo — homônimo estoniano no MusicBrainz). BIA e Alissic ficam como não brasileiros
- ✅ Correções manuais: só contam quando diferem da coluna "Decisão do script" gravada na planilha (antes, decisões antigas do próprio script viravam "correção")
- ⬜ Revisão do usuário: 3 conflitos (Supercombo: MusicBrainz diz EE, provável homônimo; Alissic: GB; BIA: US)

## Fase 3 — De tags para gêneros ✅ (primeira versão)
`python -m mapa_generos.generos` → `data/processed/generos_faixas.parquet` (track_id, genero, peso, contagem, nivel).
- ✅ Filtro por lista branca: só fica tag reconhecida como gênero (MusicBrainz, 2.226 gêneros, + EXTRAS). Anos, "AOTY", "female vocalists", países e nomes de artista caem sozinhos; nenhum gênero aceito coincide com nome de artista das curtidas
- ✅ Normalização em `musicbrainz.chave()`: sem maiúsculas, acentos, espaços e hífens; rnb = r'n'b = r&b; "and" = "&" (tropicalia → tropicália, alternative rnb → alternative r&b, forro → forró)
- ✅ EXTRAS (gêneros fora do MusicBrainz) e SINONIMOS em `generos.py` (ex.: rap nacional → brazilian rap, baile funk → funk carioca, trap rap → trap, alt rock → alternative rock)
- ✅ Nível: faixa → álbum → artista, pulando o nível que fica vazio depois da limpeza (306 faixas, 7,6%, pularam um nível)
- ✅ Peso: contagem do Last.fm ÷ maior contagem entre os gêneros do nível escolhido (gênero principal = 1); planilha manual e `brazilian` com peso 1
- ✅ Sem corte mínimo de faixas por gênero
- ✅ Validação: *Cowboy Carter* → country 1,00, americana 0,39; ITZY → k-pop; Elis Regina → bossa nova, mpb
- ✅ Resultado (20/11/2026): faixa 1.014 (25,2%) · álbum 1.812 (45,1%) · artista 1.111 (27,7%) · manual 63 (1,6%) · sem gênero 18 (0,4%); 22.817 linhas, 511 gêneros distintos (com `brazilian`), mediana de 6 gêneros por faixa
- 🔄 18 faixas cujas tags não têm nenhum gênero (só "brazil", "acoustic" etc.) foram acrescentadas a `classificacao_manual.xlsx` — **preenchimento pelo usuário**
- ⬜ Revisar ambiguidades: "freestyle" (no MusicBrainz é o gênero latino de dança; no Emicida é rap), "hardcore" (punk × eletrônico)
- ⬜ Decidir se "acoustic", "soundtrack" e "girl group" entram como gênero (hoje ficam de fora)

## Fase 4 — Hierarquia ✅ (mantida)
`python -m mapa_generos.hierarquia` → `data/processed/generos_relacoes.parquet` (origem, relacao, destino, fonte).
- ✅ A API do MusicBrainz não devolve relações entre gêneros (`inc=genre-rels` é ignorado); as relações são lidas da página web de cada gênero, com cache em `data/cache/musicbrainz/genero_rels/` (`--so-cache` evita a rede)
- ✅ Bug achado na 1ª coleta: a tabela "from: <país>" vem antes da de gêneros e o parser parava nela (142 páginas vazias); corrigido e recoletado
- ✅ Coleta (20/11/2026): 511 gêneros visitados (os seus + ancestrais), 3.535 relações; 10 páginas sem nenhuma relação
- ✅ Pais por "subgenre of": 408 de 509 gêneros (80,2%) têm pai; sem pai 19,8%
- ✅ Pais por "subgenre of" + "fusion of": 441 (86,6%) têm pai; **sem pai 13,4%** (abaixo do limite de ~30%); vários pais 37 (7,3%); **0 ciclos**
- ✅ Os sem pai são quase todos raízes naturais (rock, pop, hip hop, r&b, soul, mpb, jazz, samba…); ponderado por faixas, 39,4% das ocorrências são dessas raízes
- ✅ Pais à mão para os EXTRAS (`PAIS_EXTRAS`, ex.: brazilian rap → hip hop, k-indie → indie); faltam "black music" e "macumba"
- ✅ **Decisão: manter a hierarquia** (grafo acíclico com vários pais permitidos); "fusion of" serve para a mistura de cores
- 🔄 Famílias de cor: agrupar as ~39 raízes em ~11 famílias e calcular o vetor de família de cada gênero (pais divididos igualmente). Teste: 472 de 509 gêneros e 3.995 de 4.018 faixas ganham família; 37 gêneros pequenos sem família (sertanejo, choro, gospel, ska…)

## Fase 5 — Grafo ⬜
- ⬜ Nós = gêneros (tamanho = nº de faixas); arestas = coocorrência na mesma faixa (peso = nº de faixas em comum)
- ⬜ Poda de arestas fracas (limiar ou backbone) para não virar uma bola de pelo
- ⬜ Detecção de comunidades (Louvain/Leiden) para colorir "famílias"
- ⬜ Exportar `web/grafo.json`

## Fase 6 — Visualização HTML ⬜
- ⬜ Layout de força (ForceAtlas2) com sigma.js ou Cytoscape
- ⬜ Visual de referência (20/11/2026): fundo escuro, nós com brilho, tamanho = nº de faixas, rótulos nos maiores, arestas finas e curvas
- ⬜ Cor por família: cada gênero-raiz (rock, hip hop, pop, r&b, eletrônica, MPB…) tem uma cor; o subgênero herda a cor da família e, quanto mais longe da raiz, mais muda a opacidade/saturação; quem fica entre famílias (fusões, ex.: pop rap, trap soul) mistura as cores na proporção das famílias. Exige da Fase 4 um vetor "quanto de cada família" por gênero (pais + fusões e/ou coocorrência)
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
