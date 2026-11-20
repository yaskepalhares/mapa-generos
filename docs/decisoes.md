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
| 2026-11-19 | Faixas sem tag nos 3 níveis vão para classificação manual (`data/manual/classificacao_manual.xlsx`) | Pedido do usuário |
| 2026-11-19 | Classificação manual em planilha Excel (`.xlsx`), fonte única; o CSV foi removido | Pedido do usuário: preencher no Excel, com uma só coluna a preencher |
| 2026-11-19 | Dropdown da planilha manual = tags existentes ∩ gêneros do MusicBrainz (+ indie, alternative, rap, r&b, hardcore) | Opções limpas a partir do que já existe; a mesma lista servirá de base para a Fase 3 |
| 2026-11-19 | Tag `brazilian` em todas as faixas de artista principal brasileiro | Pedido do usuário. País pelo MusicBrainz + tag de país do Last.fm + planilha manual; participações (feat.) não contam |
| 2026-11-20 | Gênero = tag na lista do MusicBrainz + EXTRAS, comparada sem acento/hífen/maiúsculas (lista branca, não lista de bloqueio) | Tags sujas são milhares (3.598 distintas); a lista branca elimina anos, países e nomes de artista de uma vez |
| 2026-11-20 | Nível por faixa = primeiro de faixa → álbum → artista que tenha gênero **depois** da limpeza | Álbuns só com "2020", "AOTY" não podem bloquear o artista |
| 2026-11-20 | Peso = contagem ÷ maior contagem entre os gêneros do nível (principal = 1); manual e `brazilian` = 1 | O 100 do Last.fm muitas vezes é de uma tag que não é gênero ("female vocalists") |
| 2026-11-20 | Variações nacionais escritas pelo usuário viram gênero próprio (brazilian rap, brazilian indie…), além da tag `brazilian` | Mantém os subgêneros que o usuário usa na planilha manual |
| 2026-11-20 | Faixas sem nenhum gênero após a limpeza também vão para a planilha manual | Mesma regra das faixas sem tag |
| 2026-11-20 | Visual principal: grafo escuro com nós brilhantes; cor = família (gênero-raiz), mistura de cores para gêneros entre famílias, opacidade/cor mudando com a distância da raiz | Referência enviada pelo usuário; a hierarquia (Fase 4) passa a servir também para colorir |

| 2026-11-20 | Hierarquia **mantida**, com "subgenre of" + "fusion of" como pais | Só 13,4% dos gêneros sem pai (limite era ~30%), 0 ciclos, 7,3% com vários pais |
| 2026-11-20 | Relações de gênero lidas da página web do MusicBrainz, com cache | A API ws/2 não expõe relações entre gêneros |
| 2026-11-20 | Tag "hardcore" = hardcore punk | Pedido do usuário: quase todo o hardcore das curtidas é o do rock |
| 2026-11-20 | 11 famílias de cor a partir das raízes da hierarquia; indie como família própria; "brasileira" separada da tag `brazilian` | Aprovado pelo usuário |
| 2026-11-20 | Grafo: coocorrência normalizada pelo cosseno, poda top-4 por gênero, mais todas as arestas de hierarquia | Evita a "bola de pelo" e mantém a estrutura de subgêneros |
| 2026-11-20 | `web/grafo.json` e `web/faixas.json` versionados | São a entrada do site (GitHub Pages); publicar continua sendo decisão do usuário |
| 2026-11-20 | Fase 6 com sigma.js 3 + graphology via CDN, sem etapa de build; layout ForceAtlas2 calculado no navegador com semente fixa | Página estática simples para o GitHub Pages; 509 nós calculam em ~1,5 s |
| 2026-11-20 | Mistura de cores padrão: OKLab com croma preservado (matiz da média OKLab, croma = média dos cromas); RGB e OKLab puro ficam no seletor | RGB fica barrento e OKLab puro fica cinza quando as famílias são opostas (trap soul) |
