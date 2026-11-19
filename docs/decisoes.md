# Registro de decisões

| Data | Decisão | Motivo |
|---|---|---|
| 2026-11-19 | Classificar por **faixa**, com álbum e artista como reserva | Discos fora do gênero habitual do artista (ex.: *Cowboy Carter*) |
| 2026-11-19 | Last.fm como fonte de gêneros, não o Spotify | Gêneros do Spotify só no artista, frequentemente vazios, API restrita |
| 2026-11-19 | Spotifast como fonte das curtidas | Cache local em JSON, sem depender da API |
| 2026-11-19 | Visualização em HTML; Obsidian só como extra | Grafo do Obsidian não tem peso nas arestas nem hierarquia |
| 2026-11-19 | Hierarquia em aberto (ver Fase 4 do roadmap) | Depende da cobertura do MusicBrainz para os seus gêneros |
| 2026-11-19 | Uso pessoal, rodado localmente e versionado no GitHub | — |
| 2026-11-19 | Manter **todos** os subgêneros, sem corte mínimo de faixas | Preferência do usuário; filtro de peso fica só na visualização |
| 2026-11-19 | Exportify como fonte principal das curtidas | O cache do Spotifast só guarda a primeira página (50 faixas) |
| 2026-11-19 | Coletar tags dos **3 níveis** (faixa, álbum e artista) para toda faixa | No teste de 50 faixas, álbuns com só tags que não são gênero ("2020", "14 tracks") impediam a queda para o artista; o nível é escolhido na Fase 3, depois da limpeza |
| 2026-11-19 | Faixas sem tag nos 3 níveis vão para classificação manual (`data/manual/classificacao_manual.csv`) | Pedido do usuário |
