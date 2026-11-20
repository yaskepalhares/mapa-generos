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

## Fase 1b — Playlists além das Curtidas 🔄
`python -m mapa_generos.ingest_exportify` junta `data/raw/liked.csv`, `data/raw/playlists/*.csv` e `data/raw/avulsos/*.csv` em `faixas.parquet`.
- ✅ Deduplicação por ID do Spotify; cada faixa guarda `origens` (Curtidas e/ou nomes das playlists), `curtida`, `curtida_em` e `adicionada_em`
- ✅ Só playlists criadas pelo usuário: entra a playlist em que ≥ 50% das faixas foram adicionadas pelo dono (coluna "Adicionado por"); dono detectado como o "Adicionado por" mais frequente ou fixado com `--dono`. Playlists do Spotify e de outras pessoas ficam de fora e aparecem no relatório
- ✅ `data/raw/avulsos/` entra sempre (é onde vai o `pendentes_<lista>.csv` baixado pela página); arquivos locais e episódios são ignorados; faixas com o mesmo ISRC de uma curtida mas outro ID são mantidas e contadas no relatório
- ✅ Testado: só com `liked.csv` o resultado é idêntico ao anterior (4.018 faixas, mesmas colunas); com playlists sintéticas, a própria entra, a de outra pessoa e a do Spotify ficam de fora
- ✅ O cache do Last.fm (`coleta_tags.jsonl`, por `track_id`) e do MusicBrainz faz as etapas seguintes só consultarem faixas e artistas novos
- ✅ Export real (20/11/2026, filtro `owner:me` no Exportify): 83 playlists, todas incluídas com `--todas` (3 colaborativas ficariam de fora pela regra dos 50%). Nomes de arquivo do zip vinham sem a marca UTF-8 e foram corrigidos na extração
- ✅ Resultado: **5.990 faixas** (4.018 curtidas + 1.972 só em playlists; 100 delas têm o mesmo ISRC de uma curtida com outro ID), 1.684 artistas principais, 3.636 álbuns
- ✅ Coleta das 1.972 novas (~45 min, 0 erros): faixa 360 · álbum 812 · artista 765 · sem tag 35. Total: faixa 1.386 · álbum 2.896 · artista 1.610 · sem tag 98
- ✅ Brasileiros com nova ordem de fontes (Fase 2b): **396 de 1.684 artistas (23,5%), 1.358 de 5.990 faixas (22,7%)**; 151 artistas sem país em nenhuma fonte foram decididos pelo usuário (15 sim, 136 não) → **411 artistas (24,4%), 1.378 faixas (23,0%)**
- ✅ Gêneros: faixa 22,9% · álbum 41,9% · artista 32,6% · manual 1,1% · sem gênero 93 (1,6%); 31.898 linhas, 586 gêneros. Hierarquia: 13,0% sem pai, 0 ciclos. Grafo: 586 nós, 2.190 arestas (1.655 coocorrência + 535 hierarquia), 25 comunidades
- ⬜ 93 faixas sem gênero → aba Reclassificar

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
- ✅ 63 faixas sem tag (34 artistas, quase todos independentes/brasileiros; 3 sem artista/título no Spotify) classificadas pelo usuário na planilha; migradas para `data/manual/reclassificacao.json` em 20/11/2026

## Fase 2b — Tag de país (brazilian) ✅
- ✅ `marcar_brasileiros.py`: artista principal brasileiro → tag `brazilian` em todas as faixas dele (`data/processed/tags_pais.parquet`)
- ✅ Sinais: país no MusicBrainz (homônimos desempatados pelo link do Spotify), tag de país no Last.fm, gêneros BR na planilha manual. Gênero sozinho (bossa nova) não conta: pegaria Laufey e Stan Getz
- ✅ MusicBrainz completo para os 1.030 artistas (19/11/2026; ~1h25 por causa de respostas 503)
- ✅ Resultado: **225 de 1.030 artistas (21,8%), 781 de 4.018 faixas (19,4%)**, incluindo 8 marcados à mão (Linguini, DJ Wallace, MC Vitin LC, Prod.Nifour, Gustavo Vaz, Artwo, ogoin, Supercombo — homônimo estoniano no MusicBrainz). BIA e Alissic ficam como não brasileiros
- ✅ Correções manuais: só contam quando diferem da coluna "Decisão do script" gravada na planilha (antes, decisões antigas do próprio script viravam "correção")
- ⬜ Revisão do usuário: 3 conflitos (Supercombo: MusicBrainz diz EE, provável homônimo; Alissic: GB; BIA: US)
- ✅ Nova ordem de fontes (20/11/2026, pedido do usuário): 1) Wikidata pelo ID de artista do Spotify (P1902), em lote, sem homônimos; 2) página da Wikipédia em português com o nome exato do artista, só se o item for de músico/banda; 3) método antigo (MusicBrainz + tag do Last.fm + correções) só para o resto; 4) nenhuma fonte → "?" na planilha para o usuário. Caches em `data/cache/wikidata/`
- ✅ Validação contra a revisão antiga: Wikidata pelo ID 617/617 iguais (cobertura 56% dos artistas, mas só 58 dos 225 brasileiros); Wikipédia pt pelo nome 57/58 (a divergência, Alissic, já era conflito). Wikipédia pelo nome que discorda da tag do Last.fm vai para revisão
- ✅ Com 1.684 artistas: Wikidata resolveu 949, Wikipédia pt mais 107, MusicBrainz consultado para 628 (antes seriam todos os ~650 novos, ~5 s cada)

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
- 🔄 18 faixas cujas tags não têm nenhum gênero (só "brazil", "acoustic" etc.) — **classificar na aba Reclassificar da página**
- ✅ Correções manuais em `data/manual/reclassificacao.json` (`reclassificacao.py`): por faixa, álbum (ID do Spotify) ou artista (nome do artista principal), com precedência faixa > álbum > artista; substituem as tags do Last.fm da faixa (nível manual, peso 1). A planilha `classificacao_manual.xlsx` foi migrada (`--migrar-planilha`) e removida; `generos_faixas.parquet` e `tags_pais.parquet` saíram idênticos
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
- ✅ Famílias de cor (aprovadas em 20/11/2026): `familias.py` agrupa as 39 raízes em 11 famílias (rock, hip hop, pop, r&b/soul, brasileira, eletrônica, indie, folk/country, jazz/blues, latina/reggae, outros), cada uma com uma cor; gênero herda o vetor dos pais dividido igualmente → `generos_familias.parquet`
- ✅ Resultado: 509 de 509 gêneros com família (472 pela hierarquia, 37 encaixados à mão em `MANUAL`: sertanejo, choro, ska…); 36 gêneros misturam famílias (pop rock, trap soul, emo rap, country pop…); profundidade 0: 39 · 1: 265 · 2: 133 · 3: 64 · 4: 8

## Fase 5 — Grafo ✅ (primeira versão)
`python -m mapa_generos.grafo` → `web/grafo.json` (nós, arestas, cores das famílias) e `web/faixas.json` (faixas com gêneros e pesos).
- ✅ Nós = 509 gêneros; tamanho = nº de faixas; atributos: vetor de famílias, cor misturada, profundidade, comunidade, % de faixas brasileiras (a tag `brazilian` vira atributo, não nó)
- ✅ Arestas de coocorrência: força = soma do menor peso nas faixas em comum, normalizada pelo cosseno; 7.473 pares no total
- ✅ Poda: cada gênero mantém suas 4 arestas mais fortes → 1.439 de coocorrência + 459 de hierarquia = 1.898 arestas
- ✅ Louvain (semente 42): 23 comunidades, que batem com as famílias (hip hop, rock, pop, r&b/soul, brasileira, emo/punk, metal, eletrônica…); 4 gêneros isolados de uma faixa só (brega funk, macumba, christmas music, pagodão), ligados só pela hierarquia
- ⬜ Mistura de cor em RGB fica barrenta em alguns casos (trap soul = roxo + amarelo → #C89691); testar mistura em OKLab na Fase 6

## Fase 6 — Visualização HTML ✅ (primeira versão aprovada)
`web/index.html` + `app.js` + `estilo.css`, lendo `grafo.json` e `faixas.json`. Para ver localmente: `python3 -m http.server 8765 --directory web` (ou a configuração `mapa-web` em `.claude/launch.json`) e abrir http://localhost:8765.
- ✅ sigma.js 3.0.2 + graphology 0.25.4 + @sigma/edge-curve 3.1.0, via jsDelivr (sem build)
- ✅ ForceAtlas2 calculado no navegador (1.500 iterações, ~1,5 s), posição inicial por família com semente fixa → layout reprodutível. LinLog embolava tudo; `scalingRatio` 30 + gravidade 0,3 separa as famílias
- ✅ Visual escuro: fundo preto, brilho por nó (gradiente radial somado num canvas 2D por baixo do WebGL), tamanho ∝ √faixas, rótulos só nos maiores (aparecem mais com zoom), arestas de coocorrência finas e curvas
- ✅ Cores do WebGL pré-multiplicadas pelo alfa (sem isso as transparências somavam e as arestas ficavam brancas)
- ✅ Cor = mistura das famílias em OKLab; seletor para comparar 3 modos. trap soul: RGB #C89791 (barrento) · OKLab #C39EAE (acinzentado) · **OKLab com croma preservado #FA75B7 (padrão, aprovado pelo usuário em 20/11/2026)**
- ✅ Profundidade: croma × máx(0,45; 1 − 0,16·prof.) e opacidade máx(0,5; 1 − 0,12·prof.)
- ✅ Clique no gênero → painel com família, profundidade, % brasileiro, pais/subgêneros, vizinhos e lista de faixas por peso, com link para o Spotify; clique nos nomes navega pelo grafo
- ✅ Busca (lista de sugestões), filtro de peso mínimo do gênero na faixa (recalcula o tamanho dos nós), mínimo de faixas por gênero, alternar arestas de coocorrência e de hierarquia, destacar família pela legenda
- ✅ Conferido: contagem de faixas por gênero recalculada de `faixas.json` = `faixas` do `grafo.json` nos 509 nós; peso ≥ 0,5 deixa 303 gêneros visíveis
- ✅ Visual aprovado pelo usuário (20/11/2026)
- ✅ Saída do `grafo.py` reprodutível: nós ordenados com desempate por nome e Louvain com ordem fixa (antes, a ordem de um `set` mudava a cada execução e, com ela, as posições iniciais do layout)
- ✅ Filtro "Origem das faixas" (todas, Curtidas ou uma playlist); `faixas.json` ganhou `al` (ID do álbum), `o` (origens) e `n` (nível dos gêneros); `grafo.json` ganhou `origens`
- ✅ CSV do Exportify solto na página (ou escolhido no painel): o mapa passa a mostrar só as faixas da lista; o painel conta as faixas com gênero, sem gênero, novas, arquivos locais e repetidas, lista as novas e as sem gênero e baixa `pendentes_<lista>.csv` (mesmo cabeçalho) para `data/raw/avulsos/`. Conferido no navegador com um CSV de teste (vírgulas e aspas nos campos, "Tyler\\, The Creator") e o arquivo baixado lido pelo `ingest_exportify`
- ✅ Aba **Reclassificar** (substitui a planilha Excel): busca por faixa/artista/álbum, filtros "Sem gênero" (18) / "Corrigidas" (63) / "Todas", gêneros atuais com peso e nível de origem, correção por faixa, álbum ou artista (mostra quantas faixas cada nível afeta), gêneros com autocompletar (novos ficam tracejados); edições guardadas no localStorage até baixar `reclassificacao.json`; "Carregar JSON…" ou soltar o JSON na página importa um arquivo
- ✅ Conferido: correção por artista (MLQ 2N, 3 faixas) baixou o selo de 18 para 15 pendentes; o JSON exportado é idêntico byte a byte ao que o `reclassificacao.py` grava; rodando o pipeline com ele, as 3 faixas saem com os gêneros corrigidos (nível manual) e restam 15 sem gênero. Precedência faixa > álbum > artista testada com *Cowboy Carter* (correção de teste revertida depois)
- 🧪 Vista 3D (experimento) em `web/mapa3d.html` (3d-force-graph, núcleo com os gêneros maiores, setores por família), integrada com o seletor 2D/3D no topo da página; abre sempre em 2D. A 3D mostra todas as faixas (sem os filtros da 2D)
- ⬜ Opcional: alternar entre visão hierárquica e por proximidade
- ⬜ Publicar via GitHub Pages (só quando o usuário pedir)

## Fase 7 — Comparativo com o Last.fm ⬜
- ⬜ Baixar o histórico de scrobbles (`user.getRecentTracks`)
- ⬜ Casar curtidas × plays (normalizando título/artista)
- ⬜ Destacar "curti e nunca/quase nunca ouvi" no mapa (ex.: opacidade = plays)

## Extras (talvez)
- ⬜ Exportar notas `.md` para navegar no Obsidian
- ⬜ Evolução no tempo: como o mapa muda por ano de curtida
- ⬜ GitHub Action para atualizar automaticamente
