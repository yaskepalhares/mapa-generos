// Mapa de gêneros — Fase 6.
// Lê grafo.json e faixas.json, calcula o layout ForceAtlas2 no navegador e
// desenha com sigma.js. O brilho dos nós é uma camada 2D por baixo do WebGL.

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
const pct = (x) => (x * 100).toLocaleString("pt-BR", { maximumFractionDigits: 1 }) + "%";
const tamanho = (n) => (n > 0 ? 1.6 + 0.62 * Math.sqrt(n) : 0);
const $ = (id) => document.getElementById(id);

// ---------------------------------------------------------------- dados

const [dados, faixas] = await Promise.all([
  fetch("grafo.json").then((r) => r.json()),
  fetch("faixas.json").then((r) => r.json()),
]);
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
};

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
    const n = lista.reduce((acc, [, p]) => acc + (p >= estado.pesoMin - 1e-9 ? 1 : 0), 0);
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
      if (estado.selecionado) r.forceLabel = true;
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
    .filter(([, p]) => p >= estado.pesoMin - 1e-9)
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
    estado.pesoMin > 0
      ? `${fmt(lista.length)} faixas com peso ≥ ${estado.pesoMin.toLocaleString("pt-BR")}`
      : `${fmt(lista.length)} faixas`;
  $("p-faixas").innerHTML = lista
    .map(([i, p]) => {
      const f = faixas[i];
      return `<li><span class="peso" title="peso ${p.toLocaleString("pt-BR")}"><i style="width:${p * 100}%"></i></span>
        <span><a href="https://open.spotify.com/track/${f.id}" target="_blank" rel="noopener">${f.faixa ?? "(sem título)"}</a>
        <span class="art">${f.artista ?? "(sem artista)"} — ${f.album ?? ""}</span></span></li>`;
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
$("resumo").textContent =
  `${fmt(graph.order)} gêneros · ${fmt(faixas.length)} faixas curtidas (${fmt(comGenero)} com gênero)`;

// Exposto para inspeção no console.
window.mapa = { graph, renderer, estado, misturar, coresFamilia, porGenero, forceAtlas2 };
