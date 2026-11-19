# Fontes de dados e projetos de referência

Levantamento feito em 19/11/2026.

## Lista de curtidas

| Fonte | Prós | Contras |
|---|---|---|
| **Spotifast** (cache local) | Já está no Mac, atualiza sozinho, sem API | Formato interno, pode mudar entre versões |
| Exportação de dados da conta Spotify | Oficial, completa | Demora dias para chegar, não atualiza |
| Spotify Web API | Tempo real | Criação de novos apps suspensa desde dez/2025; restrições em fev/2026 |

**Spotifast no macOS** (segundo a [documentação](https://spotifast.rocks/settings-and-files/)):
- Cache: `~/Library/Caches/me.paolino.spotifast`
- Curtidas: pasta `liked-songs/`, um JSON por conta, só metadados
- Configurações e histórico de reprodução: `~/Library/Application Support/me.paolino.spotifast`

O Spotifast não faz scrobble no Last.fm nem tem comando de exportação (CLI só controla a reprodução).

## Gêneros

- **Spotify:** gênero só existe no objeto do artista, não na faixa; lista vazia quando o artista não foi classificado. Não serve para classificar por faixa.
- **Last.fm:** tags por faixa (`track.getTopTags`), álbum (`album.getTopTags`) e artista (`artist.getTopTags`). Tags são livres e sujas, precisam de limpeza.
- **MusicBrainz:** lista curada de gêneros e relações entre eles (ex.: "subgenre of"). Útil para filtrar tags e montar a hierarquia.

## Projetos parecidos

- [luisKisters/spotify-playlist-graph](https://github.com/luisKisters/spotify-playlist-graph) — rede playlist/faixa/artista/gênero (Next.js + vis-network)
- [lelabdev/spotify-graph](https://github.com/lelabdev/spotify-graph) — Last.fm como fonte principal, SQLite, Cytoscape.js
- [Atlas of Electronic Music](https://scottw2.github.io/2022/08/22/atlas-of-electronic-music) — ForceAtlas2 + detecção de comunidades (referência visual)
- [Shiroizu/VocaDB-Tag-Graph](https://github.com/Shiroizu/VocaDB-Tag-Graph) — tags como notas markdown no Graph View do Obsidian
- [SarcevicAntonio/last.fm-historic-tag-ranking](https://github.com/sarcevicantonio/last.fm-historic-tag-ranking) — tag principal por artista via Last.fm
- [0xroko/melomap](https://github.com/0xroko/melomap) — grafo de força 3D (react-force-graph)
