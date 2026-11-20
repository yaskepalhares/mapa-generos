// Mapa de gêneros em 3D — experimento.
// Lê os mesmos grafo.json e faixas.json da versão 2D (app.js) e desenha com
// 3d-force-graph (three.js + d3-force-3d). Os gêneros com mais faixas ficam no
// centro, como um núcleo; os demais se espalham para fora em todas as direções,
// cada família puxada para um setor do globo. Brilho com UnrealBloomPass.

import ForceGraph3D from "https://cdn.jsdelivr.net/npm/3d-force-graph@1.80.2/+esm";
import * as THREE from "https://cdn.jsdelivr.net/npm/three@0.186.1/+esm";
import { UnrealBloomPass } from "https://cdn.jsdelivr.net/npm/three@0.186.1/examples/jsm/postprocessing/UnrealBloomPass.js/+esm";
import { CSS2DRenderer, CSS2DObject } from "https://cdn.jsdelivr.net/npm/three@0.186.1/examples/jsm/renderers/CSS2DRenderer.js/+esm";

// ---------------------------------------------------------------- cores (OKLab)
// Mesma lógica de app.js: mistura das famílias em OKLab com croma preservado e
// croma/opacidade caindo com a profundidade na hierarquia.

const paraLinear = (c) => (c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4);
const paraSrgb = (c) => (c <= 0.0031308 ? 12.92 * c : 1.055 * c ** (1 / 2.4) - 0.055);

function hexParaRgb(hex) {
  const n = parseInt(hex.slice(1), 16);
  return [(n >> 16) / 255, ((n >> 8) & 255) / 255, (n & 255) / 255];
}

function rgbParaHex([r, g, b]) {
  const f = (c) => Math.round(Math.min(1, Math.max(0, c)) * 255).toString(16).padStart(2, "0");
  return "#" + f(r) + f(g) + f(b);
}

function hexParaOklab(hex) {
  const [r, g, b] = hexParaRgb(hex).map(paraLinear);
  const l = Math.cbrt(0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b);
  const m = Math.cbrt(0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b);
  const s = Math.cbrt(0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b);
  return [
    0.2104542553 * l + 0.793617785 * m - 0.0040720468 * s,
    1.9779984951 * l - 2.428592205 * m + 0.4505937099 * s,
    0.0259040371 * l + 0.7827717662 * m - 0.808675766 * s,
  ];
}

function oklabParaHex([L, a, b]) {
  const l = (L + 0.3963377774 * a + 0.2158037573 * b) ** 3;
  const m = (L - 0.1055613458 * a - 0.0638541728 * b) ** 3;
  const s = (L - 0.0894841775 * a - 1.291485548 * b) ** 3;
  return rgbParaHex([
    4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
    -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
    -0.0041960863 * l - 0.7034186147 * m + 1.707614701 * s,
  ].map((c) => paraSrgb(Math.min(1, Math.max(0, c)))));
}

// Mistura as cores das famílias na proporção do vetor do gênero (OKLab com
// croma preservado: o matiz vem da média em OKLab e o croma é a média dos cromas,
// para cores opostas não se anularem em cinza).
function misturar(vetor, coresFamilia) {
  const lab = [0, 0, 0];
  let croma = 0;
  for (const [f, p] of Object.entries(vetor)) {
    const c = hexParaOklab(coresFamilia[f]);
    c.forEach((v, i) => (lab[i] += v * p));
    croma += Math.hypot(c[1], c[2]) * p;
  }
  const atual = Math.hypot(lab[1], lab[2]);
  if (atual > 1e-4) {
    lab[1] *= croma / atual;
    lab[2] *= croma / atual;
  }
  return oklabParaHex(lab);
}

// Distância da raiz: menos croma, menos opacidade.
function aplicarProfundidade(hex, profundidade) {
  const [L, a, b] = hexParaOklab(hex);
  const k = Math.max(0.45, 1 - 0.16 * profundidade);
  const alfa = Math.max(0.5, 1 - 0.12 * profundidade);
  return { hex: oklabParaHex([L * (0.92 + 0.08 * k), a * k, b * k]), alfa };
}

const meioOklab = (h1, h2) => {
  const a = hexParaOklab(h1), b = hexParaOklab(h2);
  return oklabParaHex(a.map((v, i) => (v + b[i]) / 2));
};

// ---------------------------------------------------------------- utilidades

const $ = (id) => document.getElementById(id);
const fmt = (n) => n.toLocaleString("pt-BR");
const pct = (x) => `${Math.round((x ?? 0) * 100)}%`;
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);

// Gerador pseudoaleatório com semente fixa: o layout sai igual a cada carga.
function aleatorio(semente) {
  let s = semente >>> 0;
  return () => {
    s = (s + 0x6d2b79f5) >>> 0;
    let t = s;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// Pontos espalhados por igual na esfera (espiral de Fibonacci).
function direcoesNaEsfera(n) {
  const ouro = Math.PI * (3 - Math.sqrt(5));
  return Array.from({ length: n }, (_, i) => {
    const y = 1 - (2 * (i + 0.5)) / n;
    const r = Math.sqrt(1 - y * y);
    return new THREE.Vector3(Math.cos(ouro * i) * r, y, Math.sin(ouro * i) * r);
  });
}

// ---------------------------------------------------------------- dados

const [grafo, faixas] = await Promise.all([
  fetch("grafo.json").then((r) => r.json()),
  fetch("faixas.json").then((r) => r.json()),
]);
await document.fonts.load("600 40px Inter").catch(() => {});

const coresFamilia = grafo.familias;
const nomesFamilia = Object.keys(coresFamilia);

// Faixas por gênero: [índice da faixa, peso].
const porGenero = new Map();
faixas.forEach((f, i) => {
  for (const [g, p] of f.generos) {
    if (!porGenero.has(g)) porGenero.set(g, []);
    porGenero.get(g).push([i, p]);
  }
});

// ---------------------------------------------------------------- layout radial
// Raio-alvo pela posição no ranking de faixas: o 1º fica no centro e o último na
// casca. Expoente < 1/3 adensa o núcleo; > 1/3 adensa a casca.
const RAIO = 400;
const EXPOENTE = 0.8;
const tamanho = (n) => 1.4 + 0.55 * Math.sqrt(n); // ∝ √faixas, como na 2D (um pouco menor)

const nos = grafo.nos.map((n) => ({ ...n }));
const ordem = [...nos].sort((a, b) => b.faixas - a.faixas || a.id.localeCompare(b.id));
ordem.forEach((n, i) => (n.rank = i));

// Cada família aponta para um setor do globo; o gênero mira a média ponderada
// das direções das suas famílias.
const dirFamilia = Object.fromEntries(direcoesNaEsfera(nomesFamilia.length).map((d, i) => [nomesFamilia[i], d]));
const sorteio = aleatorio(42);
for (const n of nos) {
  const base = misturar(n.familias, coresFamilia);
  Object.assign(n, aplicarProfundidade(base, n.profundidade));
  n.raio = tamanho(n.faixas);
  n.alvo = 55 + (RAIO - 55) * (n.rank / (nos.length - 1)) ** EXPOENTE + n.raio * 0.8;

  const d = new THREE.Vector3();
  for (const [f, p] of Object.entries(n.familias)) d.addScaledVector(dirFamilia[f], p);
  if (d.length() < 0.2) d.add(dirFamilia[n.familia]);
  // Um pouco de ruído para o setor não virar um raio fino.
  d.normalize().add(new THREE.Vector3(sorteio() - 0.5, sorteio() - 0.5, sorteio() - 0.5).multiplyScalar(0.7)).normalize();
  n.dir = d;
  // Posição inicial já no setor e no raio certos.
  n.x = d.x * n.alvo; n.y = d.y * n.alvo; n.z = d.z * n.alvo;
}

const porId = new Map(nos.map((n) => [n.id, n]));
const arestas = grafo.arestas
  .filter((a) => porId.has(a.source) && porId.has(a.target))
  .map((a) => ({ ...a }));

// Força radial + âncora de setor (d3-force aceita uma função força(alfa)).
function forcaGlobo(forcaRaio = 0.25, forcaSetor = 0.035) {
  let lista = [];
  const forca = (alfa) => {
    for (const n of lista) {
      const r = Math.hypot(n.x, n.y, n.z) || 1e-6;
      const k = ((n.alvo - r) / r) * forcaRaio * alfa;
      n.vx += n.x * k; n.vy += n.y * k; n.vz += n.z * k;
      n.vx += (n.dir.x * n.alvo - n.x) * forcaSetor * alfa;
      n.vy += (n.dir.y * n.alvo - n.y) * forcaSetor * alfa;
      n.vz += (n.dir.z * n.alvo - n.z) * forcaSetor * alfa;
    }
  };
  forca.initialize = (ns) => (lista = ns);
  return forca;
}

// ---------------------------------------------------------------- objetos 3D

const geoEsfera = new THREE.SphereGeometry(1, 20, 14);
const N_ROTULOS = 120; // candidatos a rótulo (os de mais faixas)
const RAIO_TELA_ROTULO = 12; // px: raio mínimo do nó na tela para mostrar o nome

// Rótulos em HTML (CSS2DRenderer): ficam nítidos e fora do brilho, que
// transformava texto branco em mancha no núcleo.
function rotuloHtml(n) {
  const el = document.createElement("div");
  el.className = "rotulo";
  el.textContent = n.id;
  el.style.fontSize = `${Math.round(10 + n.raio * 0.12)}px`;
  n.elRotulo = el;
  const obj = new CSS2DObject(el);
  obj.center.set(0.5, 1); // texto logo acima do nó
  n.objRotulo = obj;
  return obj;
}

function objetoNo(n) {
  const grupo = new THREE.Group();
  const mat = new THREE.MeshBasicMaterial({
    color: new THREE.Color(n.hex),
    transparent: true,
    opacity: n.alfa,
    depthWrite: n.alfa > 0.95,
  });
  const esfera = new THREE.Mesh(geoEsfera, mat);
  esfera.scale.setScalar(n.raio);
  grupo.add(esfera);
  if (n.rank < N_ROTULOS) {
    const rotulo = rotuloHtml(n);
    rotulo.position.set(0, n.raio + 4, 0);
    grupo.add(rotulo);
  }
  n.mat = mat;
  return grupo;
}

// ---------------------------------------------------------------- grafo

const estado = { arestas: "coocorrencia", selecionado: null, vizinhos: new Set() };

const corAresta = (l) => {
  const s = typeof l.source === "object" ? l.source : porId.get(l.source);
  const t = typeof l.target === "object" ? l.target : porId.get(l.target);
  const realce = estado.selecionado && (s.id === estado.selecionado || t.id === estado.selecionado);
  const cor = l.tipo === "coocorrencia" ? meioOklab(s.hex, t.hex) : "#ffffff";
  const alfa = realce ? 0.85 : estado.selecionado ? 0.05 : l.tipo === "coocorrencia" ? 0.2 : 0.16;
  const [r, g, b] = hexParaRgb(cor).map((c) => Math.round(c * 255));
  return `rgba(${r},${g},${b},${alfa})`;
};

const mapa = ForceGraph3D({ controlType: "trackball", extraRenderers: [new CSS2DRenderer()] })($("mapa"))
  .backgroundColor("#000000")
  .showNavInfo(false)
  .numDimensions(3)
  .graphData({ nodes: nos, links: arestas })
  .nodeId("id")
  .nodeThreeObject(objetoNo)
  .nodeLabel((n) => `<b>${esc(n.id)}</b><br><small>${fmt(n.faixas)} faixas · ${esc(n.familia)}</small>`)
  .linkVisibility((l) => l.tipo === estado.arestas)
  .linkColor(corAresta)
  .linkOpacity(1)
  .linkWidth(0)
  .enableNodeDrag(false)
  .warmupTicks(260)
  .cooldownTicks(0);

// Forças: a radial/setor domina; as arestas de coocorrência aproximam os
// vizinhos de verdade; a repulsão evita que os nós se sobreponham.
mapa.d3Force("center", null);
mapa.d3Force("charge").strength((n) => -15 - n.raio * 3).distanceMax(200);
mapa.d3Force("link")
  .distance((l) => 18 + (porId.get(l.source.id ?? l.source)?.raio ?? 0) + (porId.get(l.target.id ?? l.target)?.raio ?? 0))
  .strength((l) => (l.tipo === "coocorrencia" ? 0.04 + 0.5 * (l.peso ?? 0) : 0.02));
mapa.d3Force("globo", forcaGlobo());
// Reaquece para o warmup rodar com as forças novas.
mapa.graphData({ nodes: nos, links: arestas });

// Brilho.
const BRILHO = 0.6;
const brilho = new UnrealBloomPass(new THREE.Vector2(innerWidth, innerHeight), BRILHO, 0.1, 0.2);
mapa.postProcessingComposer().addPass(brilho);

// Câmera inicial: vê o globo inteiro.
const DIST_INICIAL = RAIO * 2.4;
mapa.cameraPosition({ x: 0, y: 0, z: DIST_INICIAL }, { x: 0, y: 0, z: 0 });

// ---------------------------------------------------------------- seleção e painel

function selecionar(id) {
  estado.selecionado = id;
  mapa.linkColor(corAresta);
  for (const n of nos) n.mat.opacity = !id || n.id === id ? n.alfa : n.alfa * 0.15;
  if (!id) {
    $("painel").hidden = true;
    for (const n of nos) {
      n.mat.opacity = n.alfa;
      n.elRotulo?.classList.remove("apagado");
    }
    return;
  }
  const n = porId.get(id);
  const viz = new Set([id]);
  for (const l of arestas) {
    if (l.source.id === id) viz.add(l.target.id);
    if (l.target.id === id) viz.add(l.source.id);
  }
  for (const m of nos) {
    if (viz.has(m.id)) m.mat.opacity = m.alfa;
    m.elRotulo?.classList.toggle("apagado", !viz.has(m.id));
  }

  // Centraliza: câmera do lado de fora do globo, olhando para o gênero.
  const p = new THREE.Vector3(n.x, n.y, n.z);
  const cam = mapa.camera().position.clone();
  const dir = p.length() > 40 ? p.clone().normalize() : cam.clone().sub(p).normalize();
  const dist = 230 + n.raio * 8;
  mapa.cameraPosition(p.clone().addScaledVector(dir, dist), p, 900);
  mostrarPainel(id);
}

const linkGenero = (g) => `<a data-genero="${esc(g)}">${esc(g)}</a>`;

function mostrarPainel(id) {
  const n = porId.get(id);
  const lista = (porGenero.get(id) ?? [])
    .slice()
    .sort((x, y) => y[1] - x[1] || faixas[x[0]].artista.localeCompare(faixas[y[0]].artista));

  $("p-nome").textContent = id;
  $("p-meta").textContent =
    `${fmt(n.faixas)} faixas · família ${n.familia} · profundidade ${n.profundidade}` +
    ` · ${pct(n.pct_brasileiro)} de faixas brasileiras`;
  $("p-familias").innerHTML = Object.entries(n.familias)
    .sort((x, y) => y[1] - x[1])
    .map(([f, p]) => `<span title="${f} ${pct(p)}" style="flex:${p};background:${coresFamilia[f]}"></span>`)
    .join("");

  const pais = [], filhos = [], cooc = [];
  for (const l of arestas) {
    const s = l.source.id, t = l.target.id;
    if (s !== id && t !== id) continue;
    if (l.tipo === "hierarquia") (s === id ? pais : filhos).push(s === id ? t : s);
    else cooc.push([s === id ? t : s, l.peso]);
  }
  cooc.sort((x, y) => y[1] - x[1]);
  $("p-rel").innerHTML =
    (pais.length ? `Pais: ${pais.map(linkGenero).join(", ")}` : "Sem pai (raiz)") +
    (filhos.length ? `<br>Subgêneros: ${filhos.map(linkGenero).join(", ")}` : "") +
    (cooc.length ? `<br>Aparece junto com: ${cooc.map(([g]) => linkGenero(g)).join(", ")}` : "");

  $("p-titulo").textContent = `${fmt(lista.length)} faixas`;
  $("p-faixas").innerHTML = lista
    .map(([i, p]) => {
      const f = faixas[i];
      return `<li><span class="peso" title="peso ${p.toLocaleString("pt-BR")}"><i style="width:${p * 100}%"></i></span>
        <span><a href="https://open.spotify.com/track/${f.id}" target="_blank" rel="noopener">${esc(f.faixa || "(sem título)")}</a>
        <span class="art">${esc(f.artista || "(sem artista)")} — ${esc(f.album)}</span></span></li>`;
    })
    .join("");
  $("painel").hidden = false;
  $("painel").scrollTop = 0;
}

mapa.onNodeClick((n) => selecionar(n.id));
mapa.onBackgroundClick(() => selecionar(null));
mapa.onNodeHover((n) => ($("mapa").style.cursor = n ? "pointer" : ""));
$("fechar").addEventListener("click", () => selecionar(null));
$("painel").addEventListener("click", (ev) => {
  const g = ev.target.closest("a[data-genero]")?.dataset.genero;
  if (g && porId.has(g)) selecionar(g);
});

// ---------------------------------------------------------------- controles

function mostrarArestas(tipo) {
  estado.arestas = tipo;
  mapa.linkVisibility((l) => l.tipo === estado.arestas);
  for (const [b, t] of [["ar-cooc", "coocorrencia"], ["ar-hier", "hierarquia"], ["ar-nada", null]]) {
    $(b).classList.toggle("ativa", t === tipo);
  }
}
$("ar-cooc").addEventListener("click", () => mostrarArestas("coocorrencia"));
$("ar-hier").addEventListener("click", () => mostrarArestas("hierarquia"));
$("ar-nada").addEventListener("click", () => mostrarArestas(null));

$("lista-generos").innerHTML = ordem.map((n) => `<option value="${esc(n.id)}">`).join("");
$("busca").addEventListener("change", (ev) => {
  const termo = ev.target.value.trim().toLowerCase();
  const alvo = porId.get(termo) ?? ordem.find((n) => n.id.toLowerCase().includes(termo));
  if (termo && alvo) selecionar(alvo.id);
});

$("legenda").innerHTML = nomesFamilia.map((f) => `<span style="--c:${coresFamilia[f]}">${esc(f)}</span>`).join("");
$("resumo").textContent =
  `${fmt(nos.length)} gêneros · ${fmt(faixas.length)} faixas · ` +
  `${fmt(arestas.filter((a) => a.tipo === "coocorrencia").length)} coocorrências`;

addEventListener("resize", () => {
  mapa.width(innerWidth).height(innerHeight);
  brilho.setSize(innerWidth, innerHeight);
});

// Rótulos: como na 2D, aparecem conforme o tamanho do nó na tela (mais nomes
// com zoom); os que estão atrás do globo, do ponto de vista da câmera, apagam.
// Os objetos dos nós são criados de forma assíncrona pelo 3d-force-graph; por
// isso a lista é montada no primeiro quadro em que eles já existem.
let comRotulo = [];
const _p = new THREE.Vector3();
(function atualizarRotulos() {
  if (!comRotulo.length) comRotulo = nos.filter((n) => n.objRotulo);
  const cam = mapa.camera();
  const alvo = mapa.controls().target ?? new THREE.Vector3();
  const dCentro = cam.position.distanceTo(alvo);
  // De perto os discos ficam grandes na tela e o brilho os satura em branco:
  // a intensidade cai junto com a distância da câmera.
  brilho.strength = BRILHO * Math.min(1, Math.max(0.2, dCentro / DIST_INICIAL));
  const pxPorUnidade = innerHeight / 2 / Math.tan((cam.fov * Math.PI) / 360);
  for (const n of comRotulo) {
    const d = cam.position.distanceTo(_p.set(n.x, n.y, n.z));
    const raioTela = (n.raio * pxPorUnidade) / Math.max(d, 1);
    const mostrar = n.id === estado.selecionado || n.rank < 8 || raioTela >= RAIO_TELA_ROTULO;
    n.objRotulo.visible = mostrar; // o CSS2DRenderer cuida do display
    if (!mostrar) continue;
    // −1 (bem na frente) … +1 (bem atrás), em unidades do raio do globo.
    const t = Math.max(-1, Math.min(1, (d - dCentro) / RAIO));
    n.elRotulo.style.opacity = (0.95 - 0.7 * Math.max(0, t + 0.2)).toFixed(2);
  }
  requestAnimationFrame(atualizarRotulos);
})();

// Para inspeção no console.
window.mapa3d = { mapa, nos, arestas, THREE };
