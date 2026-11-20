// Mapa de gêneros — Fase 6.
// Lê grafo.json e faixas.json, calcula o layout ForceAtlas2 no navegador e
// desenha com sigma.js. O brilho dos nós é uma camada 2D por baixo do WebGL.
// Extras: filtro por origem (Curtidas/playlists), CSV do Exportify solto na
// página e aba Reclassificar, que exporta data/manual/reclassificacao.json.

import Graph from "https://cdn.jsdelivr.net/npm/graphology@0.25.4/+esm";
import forceAtlas2 from "https://cdn.jsdelivr.net/npm/graphology-layout-forceatlas2@0.10.1/+esm";
import Sigma from "https://cdn.jsdelivr.net/npm/sigma@3.0.2/+esm";
import { EdgeLineProgram } from "https://cdn.jsdelivr.net/npm/sigma@3.0.2/rendering/+esm";
import EdgeCurveProgram from "https://cdn.jsdelivr.net/npm/@sigma/edge-curve@3.1.0/+esm";

// ---------------------------------------------------------------- cores (OKLab)

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

// Mistura as cores das famílias na proporção do vetor do gênero.
function misturar(vetor, coresFamilia, modo) {
  const itens = Object.entries(vetor);
  if (modo === "rgb") {
    const soma = [0, 0, 0];
    for (const [f, p] of itens) hexParaRgb(coresFamilia[f]).forEach((c, i) => (soma[i] += c * p));
    return rgbParaHex(soma);
  }
  const lab = [0, 0, 0];
  let croma = 0;
  for (const [f, p] of itens) {
    const c = hexParaOklab(coresFamilia[f]);
    c.forEach((v, i) => (lab[i] += v * p));
    croma += Math.hypot(c[1], c[2]) * p;
  }
  if (modo === "oklab-croma") {
    // Cores opostas se anulam no plano a/b e a mistura fica cinza;
    // aqui o matiz vem da média em OKLab e o croma é a média dos cromas.
    const atual = Math.hypot(lab[1], lab[2]);
    if (atual > 1e-4) {
      lab[1] *= croma / atual;
      lab[2] *= croma / atual;
    }
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

const comAlfa = (hex, alfa) => {
  const [r, g, b] = hexParaRgb(hex).map((c) => Math.round(c * 255));
  return `rgba(${r},${g},${b},${alfa})`;
};

// O WebGL do sigma mistura com (1, 1 − alfa): a cor precisa vir pré-multiplicada
// pelo alfa, senão as transparências somam e tudo tende ao branco.
const paraGl = (hex, alfa) => {
  const [r, g, b] = hexParaRgb(hex).map((c) => Math.round(c * 255 * alfa));
  return `rgba(${r},${g},${b},${alfa})`;
};

// ---------------------------------------------------------------- utilidades

function aleatorio(semente) {
  // mulberry32: layout reprodutível entre recarregamentos
  return () => {
    semente |= 0;
    semente = (semente + 0x6d2b79f5) | 0;
    let t = Math.imul(semente ^ (semente >>> 15), 1 | semente);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const fmt = (n) => n.toLocaleString("pt-BR");
const esc = (t) => String(t ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
const pct = (x) => (x * 100).toLocaleString("pt-BR", { maximumFractionDigits: 1 }) + "%";
const tamanho = (n) => (n > 0 ? 1.6 + 0.62 * Math.sqrt(n) : 0);
const $ = (id) => document.getElementById(id);

// ---------------------------------------------------------------- dados

const [dados, faixas, reclassBase] = await Promise.all([
  fetch("grafo.json").then((r) => r.json()),
  fetch("faixas.json").then((r) => r.json()),
  // correções já aplicadas pelo pipeline (cópia de data/manual/reclassificacao.json)
  fetch("reclassificacao.json").then((r) => (r.ok ? r.json() : { correcoes: [] })).catch(() => ({ correcoes: [] })),
]);
const origens = dados.origens ?? [{ nome: "Curtidas", faixas: faixas.length }];
const coresFamilia = dados.familias;

// Índice gênero → [(índice da faixa, peso)], para o filtro e o painel.
const porGenero = new Map();
faixas.forEach((f, i) => {
  for (const [g, p] of f.generos) {
    if (!porGenero.has(g)) porGenero.set(g, []);
    porGenero.get(g).push([i, p]);
  }
});

const graph = new Graph({ type: "undirected", multi: true });
const familiasOrdem = Object.keys(coresFamilia);
const sorteio = aleatorio(42);

for (const no of dados.nos) {
  // Posição inicial: cada família num setor do círculo, para o ForceAtlas2
  // partir de algo parecido com o resultado final.
  const ang = (familiasOrdem.indexOf(no.familia) / familiasOrdem.length) * 2 * Math.PI + sorteio() * 0.5;
  const raio = 50 + sorteio() * 50;
  graph.addNode(no.id, {
    ...no,
    label: no.id,
    x: Math.cos(ang) * raio,
    y: Math.sin(ang) * raio,
    size: tamanho(no.faixas),
    contagem: no.faixas,
  });
}

for (const a of dados.arestas) {
  if (!graph.hasNode(a.source) || !graph.hasNode(a.target)) continue;
  const cooc = a.tipo === "coocorrencia";
  graph.addEdge(a.source, a.target, {
    tipo: a.tipo,
    relacao: a.relacao,
    peso: a.peso ?? null,
    faixas_em_comum: a.faixas_em_comum ?? null,
    weight: cooc ? a.peso : 0.15,
    type: cooc ? "curve" : "line",
    size: cooc ? 0.25 + 1.4 * a.peso : 0.4,
  });
}

// Parâmetros escolhidos comparando no navegador: LinLog embolava tudo;
// scalingRatio alto com gravidade baixa separa as famílias (~1,5 s).
forceAtlas2.assign(graph, {
  iterations: 1500,
  getEdgeWeight: "weight",
  settings: {
    ...forceAtlas2.inferSettings(graph),
    barnesHutOptimize: true,
    linLogMode: false,
    gravity: 0.3,
    scalingRatio: 30,
    slowDown: 1,
    edgeWeightInfluence: 1,
  },
});

// ---------------------------------------------------------------- estado

const estado = {
  pesoMin: 0,
  minFaixas: 1,
  cooc: true,
  hier: false,
  mistura: "oklab-croma",
  selecionado: null,
  vizinhos: new Set(),
  familia: null,
  hover: null,
  origem: -1, // índice em `origens`; -1 = todas
  csv: null, // lista do Exportify solta na página
  sub: null, // Set de índices de faixas na seleção atual (null = todas)
};

const naSelecao = (i) => !estado.sub || estado.sub.has(i);

function recolorir() {
  graph.forEachNode((id, a) => {
    const base = misturar(a.familias, coresFamilia, estado.mistura);
    const { hex, alfa } = aplicarProfundidade(base, a.profundidade);
    graph.mergeNodeAttributes(id, { corBase: base, corHex: hex, alfa, color: paraGl(hex, alfa) });
  });
  graph.forEachEdge((e, a, s, t) => {
    const cs = graph.getNodeAttribute(s, "corHex");
    const ct = graph.getNodeAttribute(t, "corHex");
    const meio = oklabParaHex(hexParaOklab(cs).map((v, i) => (v + hexParaOklab(ct)[i]) / 2));
    const [corAresta, alfaAresta] = a.tipo === "coocorrencia" ? [meio, 0.22] : ["#ffffff", 0.18];
    graph.mergeEdgeAttributes(e, { corAresta, alfaAresta, color: paraGl(corAresta, alfaAresta) });
  });
}

function recontar() {
  graph.forEachNode((id) => {
    const lista = porGenero.get(id) ?? [];
    const n = lista.reduce((acc, [i, p]) => acc + (p >= estado.pesoMin - 1e-9 && naSelecao(i) ? 1 : 0), 0);
    graph.mergeNodeAttributes(id, { contagem: n, size: tamanho(n) });
  });
}

const visivel = (id) => {
  const n = graph.getNodeAttribute(id, "contagem");
  return n > 0 && n >= estado.minFaixas;
};

// ---------------------------------------------------------------- desenho

function desenharRotulo(ctx, d, settings) {
  if (!d.label) return;
  const fonte = Math.max(11, Math.min(20, 8 + d.size * 0.45));
  ctx.font = `500 ${fonte}px Inter, system-ui, sans-serif`;
  ctx.shadowColor = "rgba(0,0,0,0.9)";
  ctx.shadowBlur = 4;
  ctx.fillStyle = "rgba(240,240,248,0.92)";
  ctx.fillText(d.label, d.x + d.size + 4, d.y + fonte / 3);
  ctx.shadowBlur = 0;
}

function desenharHover(ctx, d, settings) {
  const fonte = Math.max(12, Math.min(20, 8 + d.size * 0.45));
  ctx.font = `600 ${fonte}px Inter, system-ui, sans-serif`;
  const largura = ctx.measureText(d.label).width;
  ctx.fillStyle = "rgba(10,10,16,0.88)";
  ctx.strokeStyle = "rgba(255,255,255,0.25)";
  ctx.lineWidth = 1;
  const x = d.x + d.size + 2, y = d.y - fonte * 0.8, h = fonte * 1.6;
  ctx.beginPath();
  ctx.roundRect(x, y, largura + 12, h, 6);
  ctx.fill();
  ctx.stroke();
  ctx.beginPath();
  ctx.arc(d.x, d.y, d.size + 2, 0, 2 * Math.PI);
  ctx.strokeStyle = "rgba(255,255,255,0.8)";
  ctx.stroke();
  ctx.fillStyle = "#fff";
  ctx.fillText(d.label, x + 6, d.y + fonte / 3);
}

const destacado = (id) => {
  if (estado.selecionado) return id === estado.selecionado || estado.vizinhos.has(id);
  if (estado.familia) return graph.getNodeAttribute(id, "familia") === estado.familia;
  return true;
};

const renderer = new Sigma(graph, $("mapa"), {
  defaultEdgeType: "curve",
  edgeProgramClasses: { curve: EdgeCurveProgram, line: EdgeLineProgram },
  labelRenderedSizeThreshold: 10,
  labelDensity: 0.6,
  labelGridCellSize: 110,
  defaultDrawNodeLabel: desenharRotulo,
  defaultDrawNodeHover: desenharHover,
  minCameraRatio: 0.05,
  maxCameraRatio: 4,
  zIndex: true,
  // A página pode abrir numa aba ainda sem tamanho; o ResizeObserver abaixo corrige.
  allowInvalidContainer: true,
  nodeReducer: (id, a) => {
    const r = { ...a };
    if (!visivel(id)) return { ...r, hidden: true };
    if (!destacado(id)) {
      r.color = paraGl("#464650", 0.18);
      r.label = "";
      r.zIndex = 0;
    } else {
      r.zIndex = 1;
      // Gênero selecionado, ou seleção pequena (CSV/playlist): todos os rótulos.
      if (estado.selecionado || (estado.sub && estado.sub.size <= 300)) r.forceLabel = true;
    }
    return r;
  },
  edgeReducer: (id, a) => {
    const [s, t] = graph.extremities(id);
    const ligada = a.tipo === "coocorrencia" ? estado.cooc : estado.hier;
    if (!ligada || !visivel(s) || !visivel(t)) return { ...a, hidden: true };
    if (estado.selecionado) {
      if (s !== estado.selecionado && t !== estado.selecionado) return { ...a, hidden: true };
      return { ...a, color: paraGl(a.corAresta, 0.7), size: a.size + 0.6 };
    }
    if (estado.familia && !(destacado(s) && destacado(t))) return { ...a, hidden: true };
    return a;
  },
});

// Camada de brilho: gradiente radial por nó, somado ("lighter") num canvas 2D
// colocado antes dos canvas do sigma.
const brilho = document.createElement("canvas");
$("mapa").prepend(brilho);
const ctxBrilho = brilho.getContext("2d");

function desenharBrilho() {
  const dpr = window.devicePixelRatio || 1;
  const { width, height } = renderer.getDimensions();
  if (brilho.width !== width * dpr || brilho.height !== height * dpr) {
    brilho.width = width * dpr;
    brilho.height = height * dpr;
    brilho.style.width = width + "px";
    brilho.style.height = height + "px";
  }
  ctxBrilho.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctxBrilho.clearRect(0, 0, width, height);
  ctxBrilho.globalCompositeOperation = "lighter";
  graph.forEachNode((id, a) => {
    if (!visivel(id)) return;
    const d = renderer.getNodeDisplayData(id);
    if (!d) return;
    const p = renderer.framedGraphToViewport(d);
    const r = renderer.scaleSize(d.size);
    const raio = r * 3 + 4;
    if (p.x < -raio || p.y < -raio || p.x > width + raio || p.y > height + raio) return;
    const forte = destacado(id) ? a.alfa * 0.38 : 0.02;
    const g = ctxBrilho.createRadialGradient(p.x, p.y, r * 0.3, p.x, p.y, raio);
    g.addColorStop(0, comAlfa(a.corHex, forte));
    g.addColorStop(1, comAlfa(a.corHex, 0));
    ctxBrilho.fillStyle = g;
    ctxBrilho.fillRect(p.x - raio, p.y - raio, raio * 2, raio * 2);
  });
}
renderer.on("afterRender", desenharBrilho);
new ResizeObserver(() => renderer.refresh()).observe($("mapa"));

// ---------------------------------------------------------------- painel

function selecionar(id, centralizar = false) {
  estado.selecionado = id;
  estado.vizinhos = new Set(id ? graph.neighbors(id) : []);
  if (id) {
    estado.familia = null;
    document.querySelectorAll("#legenda li").forEach((li) => li.classList.remove("ativa"));
    mostrarPainel(id);
    if (centralizar) {
      const d = renderer.getNodeDisplayData(id);
      renderer.getCamera().animate({ x: d.x, y: d.y, ratio: 0.35 }, { duration: 600 });
    }
  } else {
    $("painel").hidden = true;
  }
  renderer.refresh({ skipIndexation: true });
}

function linkGenero(g) {
  return `<a data-genero="${g.replace(/"/g, "&quot;")}">${g}</a>`;
}

function mostrarPainel(id) {
  const a = graph.getNodeAttributes(id);
  const lista = (porGenero.get(id) ?? [])
    .filter(([i, p]) => p >= estado.pesoMin - 1e-9 && naSelecao(i))
    .sort((x, y) => y[1] - x[1] || faixas[x[0]].artista.localeCompare(faixas[y[0]].artista));

  $("p-nome").textContent = id;
  $("p-meta").innerHTML =
    `${fmt(a.faixas)} faixas · família ${a.familia} · profundidade ${a.profundidade}` +
    ` · ${pct(a.pct_brasileiro)} de faixas brasileiras`;
  $("p-familias").innerHTML = Object.entries(a.familias)
    .sort((x, y) => y[1] - x[1])
    .map(([f, p]) => `<span title="${f} ${pct(p)}" style="flex:${p};background:${coresFamilia[f]}"></span>`)
    .join("");

  const pais = [], filhos = [], cooc = [];
  graph.forEachEdge(id, (e, ea, s, t) => {
    if (ea.tipo === "hierarquia") (s === id ? pais : filhos).push(s === id ? t : s);
    else cooc.push([s === id ? t : s, ea.peso]);
  });
  cooc.sort((x, y) => y[1] - x[1]);
  $("p-pais").innerHTML =
    (pais.length ? `Pais: ${pais.map(linkGenero).join(", ")}` : "Sem pai (raiz)") +
    (filhos.length ? `<br>Subgêneros: ${filhos.map(linkGenero).join(", ")}` : "");
  $("p-vizinhos").innerHTML = cooc.length
    ? `Aparece junto com: ${cooc.map(([g]) => linkGenero(g)).join(", ")}`
    : "";

  $("p-titulo-faixas").textContent =
    (estado.pesoMin > 0
      ? `${fmt(lista.length)} faixas com peso ≥ ${estado.pesoMin.toLocaleString("pt-BR")}`
      : `${fmt(lista.length)} faixas`) + (estado.sub ? " na seleção" : "");
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

$("painel").addEventListener("click", (ev) => {
  const g = ev.target.closest("a[data-genero]")?.dataset.genero;
  if (g && graph.hasNode(g)) selecionar(g, true);
});
$("fechar").addEventListener("click", () => selecionar(null));

renderer.on("clickNode", ({ node }) => selecionar(node));
renderer.on("clickStage", () => selecionar(null));
renderer.on("enterNode", () => ($("mapa").style.cursor = "pointer"));
renderer.on("leaveNode", () => ($("mapa").style.cursor = ""));

// ---------------------------------------------------------------- controles

$("lista-generos").innerHTML = graph
  .nodes()
  .sort((a, b) => a.localeCompare(b))
  .map((g) => `<option value="${g.replace(/"/g, "&quot;")}">`)
  .join("");

$("busca").addEventListener("change", (ev) => {
  const termo = ev.target.value.trim().toLowerCase();
  const alvo = graph.nodes().find((n) => n.toLowerCase() === termo) ??
    graph.nodes().filter((n) => n.toLowerCase().includes(termo))
      .sort((a, b) => graph.getNodeAttribute(b, "faixas") - graph.getNodeAttribute(a, "faixas"))[0];
  if (alvo) {
    if (!visivel(alvo)) {
      // Se o filtro esconde o gênero buscado, zera os filtros.
      $("peso").value = 0;
      $("min-faixas").value = 0;
      atualizarFiltros();
    }
    selecionar(alvo, true);
  }
});

// Escala do controle de mínimo de faixas: 0–100 → 1–500 (quadrática).
const minFaixasDe = (v) => Math.max(1, Math.round(1 + 499 * (v / 100) ** 2));

function atualizarContagem() {
  const nos = graph.filterNodes((id) => visivel(id)).length;
  $("contagem").textContent = `${fmt(nos)} de ${fmt(graph.order)} gêneros visíveis`;
}

function atualizarFiltros() {
  estado.pesoMin = parseFloat($("peso").value);
  estado.minFaixas = minFaixasDe(parseInt($("min-faixas").value, 10));
  $("v-peso").textContent = estado.pesoMin.toLocaleString("pt-BR", { minimumFractionDigits: 2 });
  $("v-min").textContent = fmt(estado.minFaixas);
  recontar();
  if (estado.selecionado && !visivel(estado.selecionado)) selecionar(null);
  else if (estado.selecionado) mostrarPainel(estado.selecionado);
  atualizarContagem();
  renderer.refresh();
}

$("peso").addEventListener("input", atualizarFiltros);
$("min-faixas").addEventListener("input", atualizarFiltros);
$("ar-cooc").addEventListener("change", (e) => { estado.cooc = e.target.checked; renderer.refresh({ skipIndexation: true }); });
$("ar-hier").addEventListener("change", (e) => { estado.hier = e.target.checked; renderer.refresh({ skipIndexation: true }); });
$("mistura").addEventListener("change", (e) => {
  estado.mistura = e.target.value;
  recolorir();
  renderer.refresh();
});

// Legenda com o nº de gêneros cuja família dominante é cada uma.
const porFamilia = {};
graph.forEachNode((id, a) => (porFamilia[a.familia] = (porFamilia[a.familia] ?? 0) + 1));
$("legenda").innerHTML = familiasOrdem
  .map((f) => `<li data-familia="${f}"><span class="ponto" style="background:${coresFamilia[f]};box-shadow:0 0 8px ${coresFamilia[f]}"></span>${f}<span class="n">${porFamilia[f] ?? 0}</span></li>`)
  .join("");
$("legenda").addEventListener("click", (ev) => {
  const li = ev.target.closest("li");
  if (!li) return;
  const f = li.dataset.familia;
  estado.familia = estado.familia === f ? null : f;
  document.querySelectorAll("#legenda li").forEach((x) => x.classList.toggle("ativa", x.dataset.familia === estado.familia));
  if (estado.selecionado) selecionar(null);
  renderer.refresh({ skipIndexation: true });
});

// ---------------------------------------------------------------- seleção (origem e CSV)

// Seleção = faixas da origem escolhida ∩ faixas do CSV solto na página.
function atualizarSelecao() {
  let sub = null;
  if (estado.origem >= 0) {
    sub = new Set();
    faixas.forEach((f, i) => { if ((f.o ?? [0]).includes(estado.origem)) sub.add(i); });
  }
  if (estado.csv) {
    const doCsv = estado.csv.indices;
    sub = sub ? new Set([...sub].filter((i) => doCsv.has(i))) : new Set(doCsv);
  }
  estado.sub = sub;
  atualizarFiltros();
}

$("origem").innerHTML =
  `<option value="-1">Todas (${fmt(faixas.length)} faixas)</option>` +
  origens.map((o, i) => `<option value="${i}">${esc(o.nome)} (${fmt(o.faixas)})</option>`).join("");
$("origem").addEventListener("change", (e) => {
  estado.origem = parseInt(e.target.value, 10);
  atualizarSelecao();
});

// ---------------------------------------------------------------- CSV do Exportify

// CSV com aspas (RFC 4180): campos entre aspas podem ter vírgulas, "" e quebras de linha.
function lerCsv(texto) {
  const linhas = [];
  let campo = "", linha = [], aspas = false;
  texto = texto.replace(/^﻿/, "");
  for (let i = 0; i < texto.length; i++) {
    const c = texto[i];
    if (aspas) {
      if (c === '"' && texto[i + 1] === '"') { campo += '"'; i++; }
      else if (c === '"') aspas = false;
      else campo += c;
    } else if (c === '"') aspas = true;
    else if (c === ",") { linha.push(campo); campo = ""; }
    else if (c === "\n" || c === "\r") {
      if (c === "\r" && texto[i + 1] === "\n") i++;
      linha.push(campo); campo = "";
      if (linha.length > 1 || linha[0] !== "") linhas.push(linha);
      linha = [];
    } else campo += c;
  }
  if (campo !== "" || linha.length) { linha.push(campo); linhas.push(linha); }
  return linhas;
}

const paraCsv = (linhas) =>
  linhas.map((l) => l.map((c) => `"${String(c).replace(/"/g, '""')}"`).join(",")).join("\n") + "\n";

function baixar(nome, conteudo, tipo) {
  const url = URL.createObjectURL(new Blob([conteudo], { type: tipo }));
  const a = Object.assign(document.createElement("a"), { href: url, download: nome });
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

const indicePorId = new Map(faixas.map((f, i) => [f.id, i]));

function carregarCsv(nomeArquivo, texto) {
  const linhas = lerCsv(texto);
  const cab = linhas[0] ?? [];
  const col = (...nomes) => cab.findIndex((c) => nomes.includes(c.trim()));
  const cUri = col("URI da faixa", "Track URI");
  if (cUri < 0) {
    alert(`${nomeArquivo}: não parece um CSV do Exportify (falta a coluna "URI da faixa" / "Track URI").`);
    return;
  }
  const cNome = col("Nome da faixa", "Track Name");
  const cArt = col("Nome(s) do artista", "Artist Name(s)");
  const indices = new Set(), novas = [], vistas = new Set();
  let ignoradas = 0, repetidas = 0;
  for (const l of linhas.slice(1)) {
    const uri = (l[cUri] ?? "").trim();
    if (!uri.startsWith("spotify:track:")) { ignoradas++; continue; } // arquivo local, episódio
    const id = uri.split(":").pop();
    if (vistas.has(id)) { repetidas++; continue; }
    vistas.add(id);
    const i = indicePorId.get(id);
    if (i === undefined) novas.push({ id, linha: l, faixa: l[cNome], artista: (l[cArt] ?? "").split(/(?<!\\), /)[0].replace(/\\,/g, ",") });
    else indices.add(i);
  }
  const sem = [...indices].filter((i) => !faixas[i].generos.length);
  estado.csv = {
    nome: nomeArquivo.replace(/\.csv$/i, ""),
    cabecalho: cab, total: vistas.size, indices, novas, sem, ignoradas, repetidas,
  };
  mostrarCsv();
  atualizarSelecao();
  if (estado.selecionado) selecionar(null);
}

function itemFaixa(f, extra = "") {
  return `<li><span><a href="https://open.spotify.com/track/${esc(f.id)}" target="_blank" rel="noopener">${esc(f.faixa || "(sem título)")}</a>
    <span class="art">${esc(f.artista || "(sem artista)")}${f.album ? " — " + esc(f.album) : ""}</span></span>${extra}</li>`;
}

function mostrarCsv() {
  const c = estado.csv;
  $("csv-vazio").hidden = !!c;
  $("csv-cheio").hidden = !c;
  if (!c) return;
  const comGen = c.indices.size - c.sem.length;
  $("csv-resumo").innerHTML =
    `<b>${esc(c.nome)}</b>: ${fmt(c.total)} faixas · <b>${fmt(comGen)}</b> no mapa com gênero · ` +
    `${fmt(c.sem.length)} no mapa sem gênero · <b>${fmt(c.novas.length)}</b> novas (fora do mapa)` +
    (c.ignoradas ? ` · ${fmt(c.ignoradas)} ignoradas (arquivo local/episódio)` : "") +
    (c.repetidas ? ` · ${fmt(c.repetidas)} repetidas` : "");
  $("csv-baixar").disabled = !c.novas.length;
  $("csv-baixar").textContent = `Baixar pendentes (${fmt(c.novas.length)})`;
  $("csv-dica").innerHTML = c.novas.length
    ? `O mapa mostra só as faixas da lista. As novas precisam do pipeline: salve o arquivo baixado em <code>data/raw/avulsos/</code> e rode a ingestão e a coleta de tags.`
    : "O mapa mostra só as faixas da lista.";
  $("csv-det-novas").hidden = !c.novas.length;
  $("csv-t-novas").textContent = `Novas, sem gênero ainda (${fmt(c.novas.length)})`;
  $("csv-novas").innerHTML = c.novas
    .map((n) => itemFaixa(n))
    .join("");
  $("csv-det-sem").hidden = !c.sem.length;
  $("csv-t-sem").textContent = `No mapa, mas sem gênero (${fmt(c.sem.length)})`;
  $("csv-sem").innerHTML = c.sem
    .map((i) => itemFaixa(faixas[i], ` <a class="acao" data-reclass="${i}">corrigir</a>`))
    .join("");
}

$("csv-baixar").addEventListener("click", () => {
  const c = estado.csv;
  baixar(`pendentes_${c.nome}.csv`, paraCsv([c.cabecalho, ...c.novas.map((n) => n.linha)]), "text/csv;charset=utf-8");
});
$("csv-limpar").addEventListener("click", () => {
  estado.csv = null;
  mostrarCsv();
  atualizarSelecao();
});
$("csv-arquivo").addEventListener("change", async (e) => {
  const f = e.target.files[0];
  if (f) carregarCsv(f.name, await f.text());
  e.target.value = "";
});
$("csv-sem").addEventListener("click", (e) => {
  const i = e.target.closest("[data-reclass]")?.dataset.reclass;
  if (i !== undefined) { abrirAba("reclass"); escolherFaixa(parseInt(i, 10)); }
});

// Arrastar e soltar em qualquer parte da página.
let arrastando = 0;
window.addEventListener("dragenter", (e) => {
  if (![...e.dataTransfer.types].includes("Files")) return;
  arrastando++;
  $("soltar").hidden = false;
});
window.addEventListener("dragleave", () => { if (--arrastando <= 0) { arrastando = 0; $("soltar").hidden = true; } });
window.addEventListener("dragover", (e) => e.preventDefault());
window.addEventListener("drop", async (e) => {
  e.preventDefault();
  arrastando = 0;
  $("soltar").hidden = true;
  for (const f of e.dataTransfer.files) {
    const texto = await f.text();
    if (/\.json$/i.test(f.name)) importarJson(f.name, texto);
    else carregarCsv(f.name, texto);
  }
});

// ---------------------------------------------------------------- reclassificação

// Correções = base (já aplicadas pelo pipeline) + edições deste navegador, guardadas
// no localStorage até o JSON ser baixado e salvo em data/manual/.
const CHAVE_LS = "mapa-generos:reclassificacao";
const NIVEIS = ["faixa", "album", "artista"];
const NOME_NIVEL = { faixa: "esta faixa", album: "todo o álbum", artista: "todo o artista" };
const idCorr = (c) => `${c.nivel}|${c.chave}`;
const base = new Map((reclassBase.correcoes ?? []).map((c) => [idCorr(c), c]));
let edicoes = {};
try { edicoes = JSON.parse(localStorage.getItem(CHAVE_LS) ?? "{}") ?? {}; } catch { edicoes = {}; }
const gravarEdicoes = () => { try { localStorage.setItem(CHAVE_LS, JSON.stringify(edicoes)); } catch { /* sem armazenamento */ } };

function correcoes() {
  const m = new Map(base);
  for (const [k, v] of Object.entries(edicoes)) (v ? m.set(k, v) : m.delete(k));
  return m;
}

const chaveDe = (f, nivel) => (nivel === "faixa" ? f.id : nivel === "album" ? f.al : f.artista);

// Correção que vale para a faixa (faixa > álbum > artista), como em reclassificacao.py.
function correcaoDaFaixa(f, m = correcoes()) {
  for (const n of NIVEIS) {
    const k = chaveDe(f, n);
    const c = k && m.get(`${n}|${k}`);
    if (c?.generos?.length) return c;
  }
  return null;
}

const rel = { filtro: "pendentes", busca: "", atual: null, escopo: "faixa", chips: [] };
const semAcento = (t) => (t ?? "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
const textoBusca = faixas.map((f) => semAcento(`${f.faixa} ${f.artista} ${f.album}`));
const generosConhecidos = new Set(graph.nodes());
const contar = (campo, valor) => faixas.reduce((n, f) => n + (f[campo] === valor ? 1 : 0), 0);

function listaGeneros() {
  const todos = new Set(generosConhecidos);
  for (const c of correcoes().values()) c.generos.forEach((g) => todos.add(g));
  $("r-lista-generos").innerHTML = [...todos].sort((a, b) => a.localeCompare(b))
    .map((g) => `<option value="${esc(g)}">`).join("");
}

function atualizarContadores() {
  const m = correcoes();
  const pend = faixas.filter((f) => !f.generos.length && !correcaoDaFaixa(f, m)).length;
  const corr = faixas.filter((f) => correcaoDaFaixa(f, m)).length;
  $("n-pendentes").textContent = pend ? fmt(pend) : "";
  $("r-n-pendentes").textContent = `(${fmt(pend)})`;
  $("r-n-corrigidas").textContent = `(${fmt(corr)})`;
  const n = Object.keys(edicoes).length;
  $("r-estado").innerHTML = n
    ? `<b>${fmt(n)} alteraç${n === 1 ? "ão" : "ões"} não exportada${n === 1 ? "" : "s"}</b> (guardadas neste navegador) · ${fmt(m.size)} correções no total`
    : `${fmt(m.size)} correções, todas já em <code>reclassificacao.json</code>`;
  $("r-descartar").disabled = !n;
}

function renderLista() {
  const m = correcoes();
  const termo = semAcento(rel.busca.trim());
  const res = [];
  faixas.forEach((f, i) => {
    if (termo && !textoBusca[i].includes(termo)) return;
    const c = correcaoDaFaixa(f, m);
    if (rel.filtro === "pendentes" && (f.generos.length || c)) return;
    if (rel.filtro === "corrigidas" && !c) return;
    res.push(i);
  });
  res.sort((a, b) => (faixas[a].artista || "~").localeCompare(faixas[b].artista || "~") || (faixas[a].album ?? "").localeCompare(faixas[b].album ?? ""));
  const LIM = 300;
  $("r-lista").innerHTML = res.slice(0, LIM).map((i) => {
    const f = faixas[i], c = correcaoDaFaixa(f, m);
    const marca = c ? `<span class="tag corr" title="correção por ${c.nivel}">${esc(c.generos.join(", "))}</span>`
      : f.generos.length ? `<span class="tag">${esc(f.generos[0][0])}</span>` : `<span class="tag pend">sem gênero</span>`;
    return `<li data-i="${i}" class="${i === rel.atual ? "ativa" : ""}"><span>${esc(f.faixa || "(sem título)")}
      <span class="art">${esc(f.artista || "(sem artista)")} — ${esc(f.album)}</span></span>${marca}</li>`;
  }).join("");
  $("r-mais").textContent = res.length > LIM ? `Mostrando ${fmt(LIM)} de ${fmt(res.length)}; refine a busca.`
    : res.length ? `${fmt(res.length)} faixas` : "Nenhuma faixa.";
}

function escolherFaixa(i) {
  rel.atual = i;
  const f = faixas[i];
  const c = correcaoDaFaixa(f);
  rel.escopo = c?.nivel ?? "faixa";
  rel.chips = c ? [...c.generos] : f.generos.map(([g]) => g);
  $("r-vazio").hidden = true;
  $("r-editor").hidden = false;
  $("r-faixa").innerHTML = `<a href="https://open.spotify.com/track/${esc(f.id)}" target="_blank" rel="noopener">${esc(f.faixa || "(sem título)")}</a>`;
  const ori = (f.o ?? [0]).map((k) => origens[k]?.nome).filter(Boolean).join(", ");
  $("r-meta").innerHTML = `${esc(f.artista || "(sem artista)")} — ${esc(f.album)}<br>Origem: ${esc(ori)}` +
    (f.brasileiro ? " · artista brasileiro" : "");
  const NOME_N = { faixa: "tags da faixa", album: "tags do álbum", artista: "tags do artista", manual: "correção manual" };
  $("r-atuais").innerHTML = f.generos.length
    ? `<p class="nota">Vindos de: ${NOME_N[f.n] ?? f.n}</p>` + f.generos.map(([g, p]) =>
      `<span class="tag" title="peso ${p.toLocaleString("pt-BR")}">${esc(g)} <small>${p.toLocaleString("pt-BR", { maximumFractionDigits: 2 })}</small></span>`).join(" ")
    : `<p class="nota">Nenhum gênero (sem tags no Last.fm ou só tags que não são gênero).</p>`;
  renderEditor();
  renderLista();
}

function renderEditor() {
  const f = faixas[rel.atual];
  const m = correcoes();
  $("r-escopo").innerHTML = NIVEIS.map((n) => {
    const k = chaveDe(f, n);
    if (!k) return "";
    const qtd = n === "faixa" ? 1 : contar(n === "album" ? "al" : "artista", k);
    const tem = m.has(`${n}|${k}`) ? " •" : "";
    return `<button data-escopo="${n}" class="${rel.escopo === n ? "ativa" : ""}" title="${tem ? "já tem correção neste nível" : ""}">
      Aplicar a ${NOME_NIVEL[n]}${n === "faixa" ? "" : ` (${fmt(qtd)} faixa${qtd === 1 ? "" : "s"})`}${tem}</button>`;
  }).join("");
  $("r-chips").innerHTML = rel.chips.map((g, j) =>
    `<span class="tag ${generosConhecidos.has(g) ? "" : "novo"}" title="${generosConhecidos.has(g) ? "" : "gênero que ainda não está no mapa"}">${esc(g)}<button data-tirar="${j}" aria-label="tirar">×</button></span>`).join("")
    || `<span class="nota">Nenhum gênero escolhido.</span>`;
  const atualNivel = m.get(`${rel.escopo}|${chaveDe(f, rel.escopo)}`);
  const vence = correcaoDaFaixa(f, m);
  const avisos = [];
  if (atualNivel) avisos.push(`Já existe correção para ${NOME_NIVEL[rel.escopo]}: ${esc(atualNivel.generos.join(", "))}.`);
  if (vence && NIVEIS.indexOf(vence.nivel) < NIVEIS.indexOf(rel.escopo))
    avisos.push(`Esta faixa tem correção mais específica (${vence.nivel}), que continua valendo para ela.`);
  if (rel.escopo !== "faixa") avisos.push(`Faixas com correção própria (por faixa${rel.escopo === "artista" ? " ou álbum" : ""}) não são afetadas.`);
  $("r-aviso").innerHTML = avisos.join(" ");
  $("r-remover").disabled = !atualNivel;
  $("r-salvar").disabled = !rel.chips.length;
}

function adicionarChips(texto) {
  for (const g of texto.split(/[,;]/).map((x) => x.trim().toLowerCase()).filter(Boolean))
    if (!rel.chips.includes(g)) rel.chips.push(g);
  renderEditor();
}

function salvarCorrecao(remover = false) {
  const f = faixas[rel.atual];
  const n = rel.escopo, k = chaveDe(f, n);
  const rotulo = n === "faixa" ? `${f.artista} — ${f.faixa}` : n === "album" ? `${f.artista} — ${f.album}` : f.artista;
  const id = `${n}|${k}`;
  const novo = remover ? null : { nivel: n, chave: k, generos: [...rel.chips], rotulo, em: new Date().toISOString().slice(0, 10) };
  // Se voltou a ser igual ao arquivo, não é mais uma alteração pendente.
  const igualBase = remover ? !base.has(id) : base.has(id) && JSON.stringify(base.get(id).generos) === JSON.stringify(novo.generos);
  if (igualBase) delete edicoes[id];
  else edicoes[id] = novo;
  gravarEdicoes();
  listaGeneros();
  atualizarContadores();
  escolherFaixa(rel.atual);
}

// Mesmo formato de reclassificacao.py: uma correção por linha, ordenadas por nível e rótulo.
function exportarJson() {
  // Comparação por código de caractere, igual ao sorted() do Python.
  const cmp = (x, y) => (x < y ? -1 : x > y ? 1 : 0);
  const lista = [...correcoes().values()].sort((a, b) =>
    NIVEIS.indexOf(a.nivel) - NIVEIS.indexOf(b.nivel) || cmp(a.rotulo ?? "", b.rotulo ?? "") || cmp(a.chave, b.chave));
  const corpo = lista.map((c) => "  " + JSON.stringify({ nivel: c.nivel, chave: c.chave, generos: c.generos, rotulo: c.rotulo ?? "", em: c.em ?? "" })).join(",\n");
  return `{"versao": 1, "correcoes": [\n${corpo}\n]}\n`;
}

function importarJson(nome, texto) {
  let d;
  try { d = JSON.parse(texto); } catch { alert(`${nome}: JSON inválido.`); return; }
  if (!Array.isArray(d.correcoes)) { alert(`${nome}: não é um reclassificacao.json.`); return; }
  // O arquivo carregado vira o estado desejado: diferenças em relação à base viram edições.
  const novo = new Map(d.correcoes.filter((c) => NIVEIS.includes(c.nivel) && c.chave).map((c) => [idCorr(c), c]));
  edicoes = {};
  for (const [k, c] of novo) if (JSON.stringify(base.get(k)?.generos) !== JSON.stringify(c.generos)) edicoes[k] = c;
  for (const k of base.keys()) if (!novo.has(k)) edicoes[k] = null;
  gravarEdicoes();
  listaGeneros();
  atualizarContadores();
  abrirAba("reclass");
  renderLista();
}

function abrirAba(qual) {
  const r = qual === "reclass";
  $("reclass").hidden = !r;
  $("aba-reclass").classList.toggle("ativa", r);
  $("aba-mapa").classList.toggle("ativa", !r);
  $("controles").classList.toggle("escondido", r);
  if (r) { selecionar(null); renderLista(); }
}

$("aba-mapa").addEventListener("click", () => abrirAba("mapa"));
$("aba-reclass").addEventListener("click", () => abrirAba("reclass"));
$("r-busca").addEventListener("input", (e) => { rel.busca = e.target.value; renderLista(); });
$("r-filtros").addEventListener("click", (e) => {
  const b = e.target.closest("button");
  if (!b) return;
  rel.filtro = b.dataset.filtro;
  document.querySelectorAll("#r-filtros button").forEach((x) => x.classList.toggle("ativa", x === b));
  renderLista();
});
$("r-lista").addEventListener("click", (e) => {
  const li = e.target.closest("li[data-i]");
  if (li) escolherFaixa(parseInt(li.dataset.i, 10));
});
$("r-escopo").addEventListener("click", (e) => {
  const b = e.target.closest("button[data-escopo]");
  if (!b) return;
  rel.escopo = b.dataset.escopo;
  const c = correcoes().get(`${rel.escopo}|${chaveDe(faixas[rel.atual], rel.escopo)}`);
  if (c) rel.chips = [...c.generos];
  renderEditor();
});
$("r-chips").addEventListener("click", (e) => {
  const j = e.target.closest("[data-tirar]")?.dataset.tirar;
  if (j !== undefined) { rel.chips.splice(parseInt(j, 10), 1); renderEditor(); }
});
$("r-novo").addEventListener("keydown", (e) => {
  if (e.key === "Enter" || e.key === ",") {
    e.preventDefault();
    adicionarChips(e.target.value);
    e.target.value = "";
  } else if (e.key === "Backspace" && !e.target.value && rel.chips.length) {
    rel.chips.pop();
    renderEditor();
  }
});
// Escolher uma opção do datalist dispara "input" sem tecla: adiciona direto se for gênero conhecido.
$("r-novo").addEventListener("input", (e) => {
  if (e.inputType === "insertReplacementText" || (!e.inputType && generosConhecidos.has(e.target.value))) {
    adicionarChips(e.target.value);
    e.target.value = "";
  }
});
$("r-salvar").addEventListener("click", () => {
  if ($("r-novo").value.trim()) { adicionarChips($("r-novo").value); $("r-novo").value = ""; }
  salvarCorrecao(false);
});
$("r-remover").addEventListener("click", () => salvarCorrecao(true));
$("r-baixar").addEventListener("click", () => baixar("reclassificacao.json", exportarJson(), "application/json"));
$("r-carregar").addEventListener("change", async (e) => {
  const f = e.target.files[0];
  if (f) importarJson(f.name, await f.text());
  e.target.value = "";
});
$("r-descartar").addEventListener("click", () => {
  if (!confirm("Descartar as alterações deste navegador que ainda não foram exportadas?")) return;
  edicoes = {};
  gravarEdicoes();
  atualizarContadores();
  renderLista();
  if (rel.atual !== null) escolherFaixa(rel.atual);
});

listaGeneros();
atualizarContadores();
mostrarCsv();

// ---------------------------------------------------------------- início

recolorir();
recontar();
atualizarContagem();
renderer.refresh();

// Câmera inicial: afasta um pouco e empurra o grafo para a direita do painel de controles.
function enquadrar() {
  const { width } = renderer.getDimensions();
  if (!width) return;
  const painel = width > 760 ? 332 / width : 0;
  renderer.getCamera().setState({ x: 0.5 - painel / 2, y: 0.5, ratio: 1 + painel });
}
enquadrar();

const comGenero = faixas.filter((f) => f.generos.length).length;
const curtidas = faixas.filter((f) => f.o?.includes(0) ?? true).length;
$("resumo").textContent =
  `${fmt(graph.order)} gêneros · ${fmt(faixas.length)} faixas (${fmt(curtidas)} curtidas` +
  (faixas.length > curtidas ? `, ${fmt(faixas.length - curtidas)} só em playlists` : "") +
  `) · ${fmt(comGenero)} com gênero`;

// Os controles começam logo abaixo do topo (que cresce com as abas).
function posicionarControles() {
  const fim = $("topo").getBoundingClientRect().bottom + 8;
  $("controles").style.top = `${fim}px`;
  $("controles").style.maxHeight = `calc(100vh - ${fim + 16}px)`;
  // No celular a aba Reclassificar fica embaixo do topo, em vez de ao lado.
  $("reclass").style.top = window.innerWidth <= 760 ? `${fim}px` : "";
}
posicionarControles();
window.addEventListener("resize", posicionarControles);

// ---------------------------------------------------------------- vista 2D/3D
// A vista 3D é a página mapa3d.html num iframe por cima de tudo, criada na
// primeira vez que for escolhida. A página sempre abre em 2D.

function mostrarVista(vista) {
  const quadro = $("vista3d");
  const tresD = vista === "3d";
  if (tresD && !quadro.src) quadro.src = "mapa3d.html?embutido=1";
  quadro.hidden = !tresD;
  // Em 2D, a animação do 3D fica pausada para não gastar GPU escondida.
  const m3d = quadro.contentWindow?.mapa3d?.mapa;
  if (m3d) tresD ? m3d.resumeAnimation() : m3d.pauseAnimation();
  for (const b of document.querySelectorAll(".vista button")) b.classList.toggle("ativa", b.dataset.vista === vista);
  if (tresD) quadro.focus();
}
for (const b of document.querySelectorAll(".vista button")) b.addEventListener("click", () => mostrarVista(b.dataset.vista));
window.mostrarVista = mostrarVista; // chamado pelo seletor dentro do iframe

// Exposto para inspeção no console.
window.mapa = { graph, renderer, estado, misturar, coresFamilia, porGenero, forceAtlas2, faixas, correcoes, carregarCsv, exportarJson, importarJson };
