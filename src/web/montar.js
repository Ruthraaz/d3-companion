// D3 Companion — Montar build. O mesmo código no app (aba Montar) e no site
// (docs/montar.js é cópia): a pessoa escolhe itens de cada espaço, afixos,
// gemas, cubo, habilidades e paragon. Os dados do jogo vêm de dados/jogo.json
// (gerado da API da Blizzard por ferramentas/dados_do_site.py); os ícones, do
// servidor da Blizzard.
//
// A build sai no formato do app (builds/*.json):
//   - no app, "Salvar no app" grava em builds/ (o Python confere tudo antes);
//   - no site, vai num link: o JSON é comprimido e fica depois do "#", que o
//     navegador nunca manda pra servidor nenhum. No app: "+ Colar link".
// Avaliar item é só no app.
//
// Tudo fica dentro do elemento [data-montador] (os data-m="..." de dentro), pra
// não se misturar com o resto da janela do app.

"use strict";

(() => {

const CLASSES = {
  Barbarian: "Bárbaro", Crusader: "Cruzado", "Demon Hunter": "Caçador de Demônios", Monk: "Monge",
  Necromancer: "Necromante", "Witch Doctor": "Feiticeiro", Wizard: "Arcanista",
};
const ICONE_DA_CLASSE = {
  Barbarian: "barbarian_whirlwind", Crusader: "x1_crusader_blessedhammer", "Demon Hunter": "demonhunter_multishot",
  Monk: "monk_waveoflight", Necromancer: "p6_necro_bonespear", "Witch Doctor": "witchdoctor_zombiecharger",
  Wizard: "wizard_meteor",
};
const ICONES = "https://blzmedia-a.akamaihd.net/d3/icons";
const ICONE_HAB = i => `${ICONES}/skills/64/${i}.png`;
const ICONE_ITEM = i => `${ICONES}/items/large/${i}.png`;

// Lugares do boneco (os dois anéis separados aqui; no app viram um "Finger" com os dois).
const LUGARES_DO_BONECO = {
  esq: ["Head", "Shoulders", "Torso", "Hands", "Wrists", "Legs", "Feet"],
  dir: ["Neck", "Waist", "FingerL", "FingerR", "Weapon", "Off-Hand"],
};
const NOMES = {
  Head: "Cabeça", Shoulders: "Ombros", Neck: "Amuleto", Torso: "Peito", Hands: "Mãos", Wrists: "Braçadeiras",
  Waist: "Cintura", Legs: "Pernas", Feet: "Pés", FingerL: "Anel 1", FingerR: "Anel 2", Weapon: "Arma",
  "Off-Hand": "Mão secundária",
};
const LISTA_DO_LUGAR = l => (l.startsWith("Finger") ? "Finger" : l);
const PARTES_DO_CUBO = { arma: "Arma", armadura: "Armadura", joia: "Joia" };
const CUBO_ACEITA = {
  arma: ["Weapon"],
  armadura: ["Head", "Shoulders", "Torso", "Hands", "Wrists", "Waist", "Legs", "Feet", "Off-Hand"],
  joia: ["Neck", "Finger"],
};
const LUGARES_DAS_HABILIDADES = [["Primária", "Botão esquerdo"], ["Secundária", "Botão direito"],
  ["Tecla 1", "1"], ["Tecla 2", "2"], ["Tecla 3", "3"], ["Tecla 4", "4"]];
const PARAGON = [
  ["Principal", [null, "Vitalidade", "Velocidade de movimento", "Recurso máximo"]],
  ["Ataque", ["Vel. de ataque", "Redução de recarga", "Chance de crítico", "Dano crítico"]],
  ["Defesa", ["Vida %", "Armadura", "Resistência total", "Regeneração de vida"]],
  ["Utilidade", ["Dano em área", "Redução de custo", "Vida por acerto", "Achar ouro"]],
];
const GUARDADO = "d3c-montar-v2";      // rascunho por classe (só neste navegador)
const GUARDADOS_ANTIGOS = ["d3c-montar-v1"];
const MAXIMO_DO_LINK = 20000;          // caracteres depois de "#b="
const SITE = "https://ruthraaz.github.io/d3-companion/montar.html";

// Idioma (idioma.js): t() traduz a frase pelo dados/en.json. Em inglês, os nomes
// do jogo (classes, habilidades, runas) vêm do próprio jogo em inglês.
const t = (texto, vars) => (window.Idioma ? window.Idioma.t(texto, vars) : texto);
const emIngles = () => Boolean(window.Idioma) && window.Idioma.atual === "en";
const nomeDaClasse = cl => (emIngles() ? cl : CLASSES[cl]);
const nomeDaHab = h => (emIngles() ? h.n : h.p);
const nomeDaRuna = r => (emIngles() && r[3] ? r[3] : r[1]);

// Onde o montador está e o que ele pode fazer:
//   modo "site": carregar() traz o jogo.json;
//   modo "app":  carregar() e salvar(build, id) vão pro Python; aoSalvar(id) avisa o app.
let raiz = null;
let opcoes = { modo: "site" };
const $ = nome => raiz.querySelector(`[data-m="${nome}"]`);
const noApp = () => opcoes.modo === "app";

const estado = {
  jogo: null,
  classe: "Demon Hunter",
  rascunhos: {},          // classe -> build sendo montada (formato do editor)
  alvo: { tipo: "espaco", lugar: "Head" },  // o que o painel da direita está editando
  sub: "equipamento",
  busca: "",
};

// ------------------------------------------------------------ utilidades

function el(tag, props = {}, ...filhos) {
  const no = document.createElement(tag);
  for (const [k, v] of Object.entries(props)) {
    if (k === "class") no.className = v;
    else if (k.startsWith("on")) no.addEventListener(k.slice(2), v);
    else if (v !== false && v !== null && v !== undefined) no.setAttribute(k, v);
  }
  for (const f of filhos.flat(Infinity)) {
    if (f !== null && f !== undefined && f !== false && f !== "") no.append(f);
  }
  return no;
}
const trocar = (no, ...filhos) => no.replaceChildren(...filhos.flat(Infinity).filter(Boolean));
const normalizar = t => t.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();

function icone(url, classe = "") {
  const caixa = el("span", { class: `icone ${classe}`, "aria-hidden": "true" });
  if (url) {
    const img = el("img", { src: url, alt: "", loading: "lazy", draggable: "false" });
    img.addEventListener("error", () => img.remove());
    caixa.append(img);
  }
  return caixa;
}

// Guardar no navegador pode falhar (janela anônima, site bloqueado): o site segue sem.
// Só fica guardado rascunho que tem alguma coisa: classe só visitada continua "nova".
function lerGuardado() {
  try {
    for (const antigo of GUARDADOS_ANTIGOS) localStorage.removeItem(antigo);  // rascunhos de versões velhas
    return JSON.parse(localStorage.getItem(GUARDADO) || "{}") || {};
  } catch { return {}; }
}
function guardar() {
  const rascunhos = Object.fromEntries(Object.entries(estado.rascunhos).filter(([, b]) => temConteudo(b)));
  try {
    if (Object.keys(rascunhos).length) localStorage.setItem(GUARDADO, JSON.stringify({ classe: estado.classe, rascunhos }));
    else localStorage.removeItem(GUARDADO);
  } catch { /* sem */ }
}
const PARAGON_INICIAL = JSON.stringify(buildVazia().paragon);
function temConteudo(b) {
  if (!b || !b.lugares) return false;
  return Boolean(b.id || (b.apelido || "").trim()
    || Object.values(b.lugares).some(l => l && (l.item || (l.afixos || []).length || l.ancient))
    || (b.gemas || []).some(Boolean) || Object.values(b.cubo || {}).some(Boolean)
    || (b.ativas || []).some(Boolean) || (b.passivas || []).some(Boolean)
    || JSON.stringify(b.paragon) !== PARAGON_INICIAL);
}

// ------------------------------------------------------------ a build

function buildVazia() {
  return {
    id: "",                            // no app: a build de builds/ que este rascunho altera ("" = nova)
    // nuvem: no site com conta, a id da build salva na nuvem que este rascunho altera (nuvem.js)
    apelido: "",
    lugares: {},                      // lugar -> {item, afixos: [modelo], ancient}
    gemas: [null, null, null],
    cubo: {},
    ativas: [null, null, null, null, null, null],  // {s, r}
    passivas: [null, null, null, null],
    paragon: { nivel: 0, pontos: [[0, 0, 50, 50], [50, 50, 50, 50], [50, 50, 50, 50], [50, 50, 50, 50]] },
  };
}
const atual = () => (estado.rascunhos[estado.classe] ||= buildVazia());
const lugar = nome => (atual().lugares[nome] ||= { item: null, afixos: [], ancient: false });
const daClasse = () => estado.jogo.classes[estado.classe];

function mudou() {
  guardar();
  desenhar();
}

// Itens que a classe pode usar num lugar (os do tipo de outra classe ficam de fora).
function itensDoLugar(nome) {
  const lista = estado.jogo.espacos[LISTA_DO_LUGAR(nome)] || [];
  const extra = nome === "Off-Hand" ? (estado.jogo.espacos.Weapon || []).filter(i => !i.m2) : [];
  return [...lista, ...extra].filter(i => !i.c.length || i.c.includes(estado.classe));
}
const itemPorNome = nome => {
  for (const lista of Object.values(estado.jogo.espacos)) {
    const achado = lista.find(i => i.n === nome);
    if (achado) return achado;
  }
  return null;
};
const gemaPorNome = nome => estado.jogo.gemas.find(g => g.n === nome) || null;
const habPorSlug = (lista, s) => lista.find(h => h.s === s) || null;

// Afixos que o painel oferece: os comuns, o "dano de habilidades da classe" e
// o dano de cada habilidade (no mesmo formato que o app usa ao importar do Maxroll).
function afixosDaClasse() {
  const c = daClasse();
  return [
    ...estado.jogo.afixos,
    ...(c.afixo ? [c.afixo] : []),
    ...c.ativas.map(h => ({ modelo: `Increases ${h.n} Damage by #% *`, rotulo: t("Dano de {hab}", { hab: nomeDaHab(h) }), habilidade: true })),
  ];
}

// Editor -> formato do app (builds/*.json).
function paraBuild() {
  const b = atual();
  const c = daClasse();
  const regras = Object.fromEntries(afixosDaClasse().map(a => [a.modelo, { modelo: a.modelo, rotulo: a.rotulo }]));
  const espacos = {};
  for (const [nome, l] of Object.entries(b.lugares)) {
    if (!l.item && !l.afixos.length && !l.ancient) continue;
    const chave = LISTA_DO_LUGAR(nome);
    const e = (espacos[chave] ||= {});
    if (l.item) (e.itens ||= []).includes(l.item) || e.itens.push(l.item);
    for (const m of l.afixos) {
      if (regras[m] && !(e.desejaveis ||= []).some(r => r.modelo === m)) e.desejaveis.push(regras[m]);
    }
    if (l.ancient) e.exige_ancient = true;
  }
  const apelido = (b.apelido.trim() || t("Minha build de {classe}", { classe: nomeDaClasse(estado.classe) })).slice(0, 40);
  const build = {
    formato: 1,
    nome: apelido,
    apelido,
    classe: estado.classe,
    exige_ancient: false,
    fonte: { site: "montar" },
    todos_os_espacos: { obrigatorios: [c.atributo] },
    espacos,
    gemas: b.gemas.filter(Boolean),
    cubo: Object.fromEntries(Object.entries(b.cubo).filter(([, v]) => v)),
    habilidades: {
      ativas: b.ativas.filter(Boolean).map(a => ({ habilidade: a.s, runa: a.r || "" })),
      passivas: b.passivas.filter(Boolean),
    },
  };
  if (b.paragon.pontos.flat().some(n => n > 0)) build.paragon = { nivel: b.paragon.nivel, pontos: b.paragon.pontos };
  return build;
}

// Formato do app -> editor (ao abrir um link). Só aceita o que conhece.
function doBuild(build) {
  if (!build || typeof build !== "object" || !CLASSES[build.classe]) throw new Error("build de classe desconhecida");
  const b = buildVazia();
  const texto = v => (typeof v === "string" ? v.slice(0, 120) : null);
  b.apelido = texto(build.apelido) || "";
  for (const [chave, e] of Object.entries(build.espacos || {})) {
    if (!e || typeof e !== "object") continue;
    const itens = Array.isArray(e.itens) ? e.itens.map(texto).filter(Boolean) : [];
    const afixos = Array.isArray(e.desejaveis) ? e.desejaveis.map(r => r && texto(r.modelo)).filter(Boolean) : [];
    const nomes = chave === "Finger" ? ["FingerL", "FingerR"] : [chave];
    nomes.forEach((nome, i) => {
      if (!NOMES[nome]) return;
      b.lugares[nome] = { item: itens[chave === "Finger" ? i : 0] || null, afixos, ancient: e.exige_ancient === true };
    });
  }
  (Array.isArray(build.gemas) ? build.gemas : []).slice(0, 3).forEach((g, i) => { b.gemas[i] = texto(g); });
  for (const parte of Object.keys(PARTES_DO_CUBO)) b.cubo[parte] = texto((build.cubo || {})[parte]);
  const hab = build.habilidades || {};
  (Array.isArray(hab.ativas) ? hab.ativas : []).slice(0, 6).forEach((a, i) => {
    if (a && typeof a.habilidade === "string") b.ativas[i] = { s: texto(a.habilidade), r: /^[a-e]?$/.test(a.runa || "") ? a.runa || "" : "" };
  });
  (Array.isArray(hab.passivas) ? hab.passivas : []).slice(0, 4).forEach((p, i) => { b.passivas[i] = texto(p); });
  const p = build.paragon;
  if (p && Array.isArray(p.pontos) && p.pontos.length === 4 && p.pontos.every(g => Array.isArray(g) && g.length === 4)) {
    b.paragon = { nivel: Math.max(0, Math.min(99999, Number(p.nivel) || 0)),
                  pontos: p.pontos.map(g => g.map(n => Math.max(0, Math.min(99999, Math.floor(Number(n) || 0))))) };
  }
  return b;
}

// ------------------------------------------------------------ link da build

const paraBase64 = bytes => btoa(String.fromCharCode(...bytes)).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
const deBase64 = t => Uint8Array.from(atob(t.replace(/-/g, "+").replace(/_/g, "/")), c => c.charCodeAt(0));

async function comprimir(texto) {
  const fluxo = new Blob([texto]).stream().pipeThrough(new CompressionStream("deflate-raw"));
  return new Uint8Array(await new Response(fluxo).arrayBuffer());
}
async function descomprimir(bytes) {
  const fluxo = new Blob([bytes]).stream().pipeThrough(new DecompressionStream("deflate-raw"));
  const texto = await new Response(fluxo).text();
  if (texto.length > 200000) throw new Error("build grande demais");
  return texto;
}

async function linkDaBuild() {
  return `${SITE}#b=${paraBase64(await comprimir(JSON.stringify(paraBuild())))}`;
}

async function abrirLinkDoEndereco() {
  const m = location.hash.match(/^#b=([A-Za-z0-9_-]+)$/);
  if (!m) return false;
  if (m[1].length > MAXIMO_DO_LINK) { avisar(t("Esse link é grande demais pra ser uma build."), true); return false; }
  try {
    const build = JSON.parse(await descomprimir(deBase64(m[1])));
    estado.classe = build.classe;
    estado.rascunhos[build.classe] = doBuild(build);
    guardar();
    avisar(t("Build aberta do link: {nome}. Pode mudar à vontade.", { nome: estado.rascunhos[build.classe].apelido || nomeDaClasse(build.classe) }));
    return true;
  } catch {
    avisar(t("Não consegui abrir a build desse link (ele pode ter sido cortado ao copiar)."), true);
    return false;
  }
}

// ------------------------------------------------------------ desenho

function avisar(texto, erro = false) {
  trocar($("avaliando"), el("span", { class: erro ? "t-falta" : "" }, texto));
}

function desenhar() {
  desenharClasses();
  desenharCabeca();
  desenharBoneco();
  desenharGemasECubo();
  desenharHabilidades();
  desenharParagon();
  desenharEditor();
}

function desenharClasses() {
  trocar($("classes-builds"), Object.keys(CLASSES).map(cl =>
    el("button", {
      class: "classe" + (cl === estado.classe ? " ativo" : ""), role: "tab",
      onclick: () => { estado.classe = cl; estado.alvo = { tipo: "espaco", lugar: "Head" }; estado.busca = ""; mudou(); },
    },
      icone(ICONE_HAB(ICONE_DA_CLASSE[cl]), "icone-classe"),
      el("span", { class: "classe-texto" },
        el("span", { class: "classe-nome" }, nomeDaClasse(cl)),
        el("span", { class: "classe-qtd" }, temConteudo(estado.rascunhos[cl]) ? t("em montagem") : t("nova"))))));
}

function desenharCabeca() {
  const b = atual();
  const nome = el("input", {
    class: "nome-da-build", value: b.apelido, maxlength: "40", autocomplete: "off", spellcheck: "false",
    placeholder: t("Nome da build (ex.: {classe} push)", { classe: nomeDaClasse(estado.classe) }), "aria-label": t("Nome da build"),
  });
  nome.addEventListener("input", () => { b.apelido = nome.value; guardar(); });

  // No app: grava em builds/. A 1ª vez cria; depois, altera a mesma build.
  const salvar = noApp() && el("button", { type: "button", class: "botao" }, b.id ? t("Salvar mudanças") : t("Salvar no app"));
  if (salvar) salvar.addEventListener("click", async () => {
    salvar.disabled = true;
    let r;
    try { r = await opcoes.salvar(paraBuild(), b.id || ""); } catch (e) { r = { erro: String(e) }; }
    salvar.disabled = false;
    if (!r || r.erro) { avisar((r && r.erro) || t("Não consegui salvar."), true); return; }
    const nova = !b.id;
    b.id = r.id;
    guardar();
    desenharCabeca();
    avisar(nova ? t("Salva no app: {nome}. Ela já está na aba Builds e o atalho passa a usar ela.", { nome: paraBuild().apelido })
                : t("Mudanças salvas em {nome}.", { nome: paraBuild().apelido }));
    if (opcoes.aoSalvar) opcoes.aoSalvar(r.id);
  });

  const copiar = el("button", { type: "button", class: noApp() ? "botao botao-leve" : "botao" }, t("Copiar link da build"));
  copiar.addEventListener("click", async () => {
    try {
      const link = await linkDaBuild();
      if (!noApp()) history.replaceState(null, "", link.slice(link.indexOf("#")));
      await navigator.clipboard.writeText(link);
      avisar(noApp() ? t("Link copiado: quem abrir vê a build no site e pode colar no app dele.")
                     : t("Link copiado. No app: aba Builds → \"+ Colar link\" e cole. A build fica salva lá e o atalho já usa ela."));
    } catch {
      avisar(noApp() ? t("Não deu pra copiar o link.") : t("Não deu pra copiar sozinho: o link está na barra de endereço, copie de lá."), true);
    }
  });
  // Folha de compartilhar do sistema (celular, Windows), quando o navegador tem.
  const partilhar = !noApp() && navigator.share && el("button", { type: "button", class: "botao botao-leve" }, t("Compartilhar"));
  if (partilhar) partilhar.addEventListener("click", async () => {
    try {
      const link = await linkDaBuild();
      history.replaceState(null, "", link.slice(link.indexOf("#")));
      await navigator.share({ title: `${paraBuild().apelido} — D3 Companion`, text: t("Minha build de Diablo III:"), url: link });
    } catch (erro) {
      if (!erro || erro.name !== "AbortError") avisar(t("Não deu pra compartilhar daqui: use \"Copiar link da build\"."), true);
    }
  });
  const baixar = !noApp() && el("button", { type: "button", class: "botao botao-leve" }, t("Baixar .json"));
  if (baixar) baixar.addEventListener("click", () => {
    const build = paraBuild();
    const arquivo = (build.apelido.normalize("NFKD").replace(/[^\w]+/g, "_").replace(/^_|_$/g, "").toLowerCase() || "build") + ".json";
    const a = el("a", { href: URL.createObjectURL(new Blob([JSON.stringify(build, null, 2)], { type: "application/json" })), download: arquivo });
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
    avisar(t("Baixado {arquivo}. Ele vai na pasta builds\\ do app (no .exe: %APPDATA%\\D3 Companion\\builds).", { arquivo }));
  });
  let confirmando = null;
  const limpar = el("button", { type: "button", class: "botao botao-leve botao-remover" }, t("Começar de novo"));
  limpar.addEventListener("click", () => {
    if (!confirmando) {
      limpar.textContent = t("Clique de novo pra apagar");
      limpar.classList.add("confirmar");
      confirmando = setTimeout(() => { confirmando = null; limpar.textContent = t("Começar de novo"); limpar.classList.remove("confirmar"); }, 4000);
      return;
    }
    clearTimeout(confirmando);
    delete estado.rascunhos[estado.classe];
    if (!noApp()) history.replaceState(null, "", location.pathname);
    avisar(noApp() ? t("Rascunho limpo. O que você já salvou continua na aba Builds.") : t("Build apagada. Comece escolhendo os itens."));
    mudou();
  });

  const onde = noApp() ? (b.id ? t("salva no app") : t("ainda não salva")) : b.nuvem ? t("salva na nuvem") : t("montada no site");
  trocar($("cabeca-build"),
    icone(ICONE_HAB(ICONE_DA_CLASSE[estado.classe]), "emblema"),
    el("div", { class: "cabeca-texto" },
      nome,
      el("p", { class: "build-meta" }, `${nomeDaClasse(estado.classe)} · ${onde} · ${t("atributo principal: {atributo}", { atributo: t(daClasse().atributo.rotulo) })}`)),
    el("div", { class: "cabeca-acoes" }, salvar, copiar, partilhar, baixar, limpar));
}

function botaoDoLugar(nome) {
  const l = atual().lugares[nome] || { item: null, afixos: [], ancient: false };
  const item = l.item && itemPorNome(l.item);
  const classe = l.item ? "com-item" : l.afixos.length ? "livre" : "geral";
  const selecionado = estado.alvo.tipo === "espaco" && estado.alvo.lugar === nome;
  return el("button", {
    class: `espaco ${classe}` + (selecionado ? " selecionado" : "") + (item && item.s ? " de-set" : ""),
    "data-dica": l.item,
    onclick: () => { estado.alvo = { tipo: "espaco", lugar: nome }; estado.busca = ""; desenhar(); },
  },
    el("span", { class: "espaco-icone" },
      icone(item && ICONE_ITEM(item.i), "icone-item"),
      l.ancient && el("span", { class: "selo-ancient", title: t("Precisa ser Ancient") }, "ANC")),
    el("span", { class: "espaco-texto" },
      el("span", { class: "espaco-item" }, l.item || (l.afixos.length ? t("Qualquer item") : t("Escolher…"))),
      el("span", { class: "espaco-nome" }, t(NOMES[nome])),
      l.afixos.length > 0 && el("span", { class: "espaco-afixos" }, (l.afixos.length > 1 ? t("{n} afixos", { n: l.afixos.length }) : t("1 afixo")))));
}

function desenharBoneco() {
  trocar($("equip-esq"), LUGARES_DO_BONECO.esq.map(botaoDoLugar));
  trocar($("equip-dir"), LUGARES_DO_BONECO.dir.map(botaoDoLugar));
}

function desenharGemasECubo() {
  const b = atual();
  const no = (i, pos) => {
    const g = b.gemas[i] && gemaPorNome(b.gemas[i]);
    const sel = estado.alvo.tipo === "gema" && estado.alvo.i === i;
    return el("button", {
      type: "button", class: `roda-no gema p${pos}` + (b.gemas[i] ? "" : " vazio") + (sel ? " selecionado" : ""),
      title: b.gemas[i] ? null : t("Escolher gema"), "data-dica": b.gemas[i], "aria-label": b.gemas[i] || t("Gema {n}: escolher", { n: i + 1 }),
      onclick: () => { estado.alvo = { tipo: "gema", i }; estado.busca = ""; desenhar(); },
    }, g && el("img", { src: ICONE_ITEM(g.i), alt: "", draggable: "false" }));
  };
  trocar($("roda"), el("span", { class: "roda-centro", "aria-hidden": "true" }), [0, 1, 2].map(i => no(i, [0, 2, 4][i])));
  const gemas = b.gemas.filter(Boolean);
  trocar($("gemas"), gemas.length
    ? gemas.map(g => el("div", { class: "mini-item", "data-dica": g }, el("span", { class: "t-lendario" }, g)))
    : el("p", { class: "nada" }, t("Clique nas casas da roda.")));

  trocar($("cubo"), Object.entries(PARTES_DO_CUBO).map(([parte, rotulo]) => {
    const nome = b.cubo[parte];
    const item = nome && itemPorNome(nome);
    const sel = estado.alvo.tipo === "cubo" && estado.alvo.parte === parte;
    return el("button", {
      type: "button", class: "cubo-carta" + (nome ? "" : " vazio") + (sel ? " selecionado" : ""), "data-dica": nome,
      onclick: () => { estado.alvo = { tipo: "cubo", parte }; estado.busca = ""; desenhar(); },
    },
      icone(item && ICONE_ITEM(item.i), "icone-cubo"),
      el("div", {},
        el("p", { class: "cubo-rotulo" }, t(rotulo)),
        el("p", { class: "cubo-nome" + (nome ? " t-lendario" : " mudo") }, nome || t("escolher…"))));
  }));
}

function desenharHabilidades() {
  const b = atual();
  const c = daClasse();
  const carta = i => {
    const a = b.ativas[i];
    const h = a && habPorSlug(c.ativas, a.s);
    const runa = h && h.r.find(r => r[0] === a.r);
    const [nomeLugar, tecla] = LUGARES_DAS_HABILIDADES[i];
    const sel = estado.alvo.tipo === "ativa" && estado.alvo.i === i;
    return el("button", {
      type: "button", class: "carta-hab" + (h ? "" : " a-escolher") + (sel ? " selecionado" : ""),
      onclick: () => { estado.alvo = { tipo: "ativa", i }; estado.busca = ""; desenhar(); },
    },
      el("span", { class: "carta-lugar" }, t(nomeLugar)),
      el("span", { class: "carta-corpo" },
        icone(h && ICONE_HAB(h.i), "icone-habilidade"),
        el("span", { class: "carta-texto" },
          el("span", { class: "carta-nome" }, h ? nomeDaHab(h) : t("Escolher…")),
          h && el("span", { class: "carta-runa" + (runa ? "" : " sem") }, runa ? nomeDaRuna(runa) : t("sem runa")))),
      el("span", { class: "carta-tecla" }, t(tecla)));
  };
  const passiva = i => {
    const h = b.passivas[i] && habPorSlug(c.passivas, b.passivas[i]);
    const sel = estado.alvo.tipo === "passiva" && estado.alvo.i === i;
    return el("button", {
      type: "button", class: "passiva-jogo" + (h ? "" : " a-escolher") + (sel ? " selecionado" : ""),
      onclick: () => { estado.alvo = { tipo: "passiva", i }; estado.busca = ""; desenhar(); },
    }, icone(h && ICONE_HAB(h.i), "icone-passiva icone-grande"), el("span", {}, h ? nomeDaHab(h) : t("Escolher…")));
  };
  trocar($("janela-habilidades"),
    el("section", { class: "secao-jogo" },
      el("h3", { class: "faixa-titulo" }, el("span", {}, t("Habilidades do mouse"))),
      el("div", { class: "grade-cartas" }, [0, 1].map(carta))),
    el("section", { class: "secao-jogo" },
      el("h3", { class: "faixa-titulo" }, el("span", {}, t("Barra de ação"))),
      el("div", { class: "grade-cartas" }, [2, 3, 4, 5].map(carta))),
    el("section", { class: "secao-jogo" },
      el("h3", { class: "faixa-titulo" }, el("span", {}, t("Passivas"))),
      el("div", { class: "fila-passivas" }, [0, 1, 2, 3].map(passiva))));
}

function desenharParagon() {
  const p = atual().paragon;
  const atributo = t(daClasse().atributo.rotulo);
  const numero = (valor, aoMudar, rotulo) => {
    const campo = el("input", { type: "number", min: "0", max: "99999", step: "1", value: String(valor), "aria-label": rotulo });
    campo.addEventListener("change", () => {
      const n = Math.max(0, Math.min(99999, Math.floor(Number(campo.value) || 0)));
      campo.value = String(n);
      aoMudar(n);
      guardar();
    });
    return campo;
  };
  trocar($("paragon"),
    el("div", { class: "paragon-explica" },
      el("p", {}, el("strong", {}, t("Pontos de cada atributo")), " ", t("no nível de paragon que você escolher."), " ",
        t("No jogo, cada grupo vai até 50 por atributo, menos o atributo principal e a Vitalidade, que não têm limite.")),
      el("p", {}, t("No app, a aba Paragon mostra isto em passos numerados, na ordem de encher."))),
    el("label", { class: "campo campo-nivel" }, el("span", { class: "campo-nome" }, t("Nível de paragon")),
      numero(p.nivel, n => { p.nivel = n; }, t("Nível de paragon"))),
    el("div", { class: "paragon-grupos" }, PARAGON.map(([grupo, nomes], g) =>
      el("div", { class: "paragon-grupo" },
        el("p", { class: "paragon-titulo" }, el("span", { class: "paragon-ordem" }, String(g + 1)), t(grupo)),
        el("div", { class: "paragon-campos" }, nomes.map((nome, i) =>
          el("label", { class: "paragon-campo" }, el("span", {}, nome ? t(nome) : atributo),
            numero(p.pontos[g][i], n => { p.pontos[g][i] = n; }, nome ? t(nome) : atributo))))))));
}

// ------------------------------------------------------------ editor (painel da direita)

function campoDeBusca(dica) {
  const campo = el("input", { type: "search", class: "busca-lista", value: estado.busca, placeholder: dica, autocomplete: "off", spellcheck: "false" });
  campo.addEventListener("input", () => {
    estado.busca = campo.value;
    const lista = raiz.querySelector(".lista-escolha");
    const b = normalizar(campo.value.trim());
    lista.querySelectorAll("[data-busca]").forEach(li => { li.hidden = b && !li.dataset.busca.includes(b); });
  });
  return campo;
}

function lista(opcoes, escolhido, escolher) {
  const b = normalizar(estado.busca.trim());
  return el("ul", { class: "lista-escolha" }, opcoes.map(o =>
    el("li", { "data-busca": normalizar(`${o.nome} ${o.sub || ""}`), hidden: b && !normalizar(`${o.nome} ${o.sub || ""}`).includes(b) ? "" : null },
      el("button", { type: "button", class: "opcao" + (o.nome === escolhido || o.valor === escolhido ? " ativo" : ""), "data-dica": o.dica, onclick: () => escolher(o) },
        icone(o.icone, o.redondo ? "icone-mini redondo" : "icone-mini"),
        el("span", {}, el("span", { class: "opcao-nome " + (o.cor || "") }, o.nome), o.sub && el("span", { class: "opcao-sub" }, o.sub))))));
}

function desenharEditor() {
  const caixa = $("detalhe");
  const a = estado.alvo;
  if (a.tipo === "espaco") return editorDoLugar(caixa, a.lugar);
  if (a.tipo === "gema") return editorDaGema(caixa, a.i);
  if (a.tipo === "cubo") return editorDoCubo(caixa, a.parte);
  if (a.tipo === "ativa") return editorDaAtiva(caixa, a.i);
  if (a.tipo === "passiva") return editorDaPassiva(caixa, a.i);
}

// Embaixo do nome: em português, o nome em inglês (o do jogo) e o nível; a busca acha os dois.
const subDaHab = h => (emIngles() ? t("nível {n}", { n: h.l }) : `${h.n} · nível ${h.l}`);
const opcaoDeItem = i => ({ nome: i.n, dica: i.n, icone: ICONE_ITEM(i.i), cor: i.s ? "t-set" : "t-lendario", sub: i.s ? "Set" : t("Lendário") });

function editorDoLugar(caixa, nome) {
  const l = lugar(nome);
  const afixos = afixosDaClasse();
  const marcar = (modelo, ligado) => {
    l.afixos = ligado ? [...new Set([...l.afixos, modelo])] : l.afixos.filter(m => m !== modelo);
    mudou();
  };
  const chip = a => {
    const ligado = l.afixos.includes(a.modelo);
    return el("button", { type: "button", class: "etiqueta chip-afixo" + (ligado ? " ligado" : ""), "aria-pressed": String(ligado),
      onclick: () => marcar(a.modelo, !ligado) }, t(a.rotulo));
  };
  const dasHabilidades = afixos.filter(x => x.habilidade);
  const escolhaDeHab = el("select", { "aria-label": t("Dano de uma habilidade") },
    el("option", { value: "" }, t("+ Dano de uma habilidade…")),
    dasHabilidades.filter(x => !l.afixos.includes(x.modelo)).map(x => el("option", { value: x.modelo }, x.rotulo)));
  escolhaDeHab.addEventListener("change", () => { if (escolhaDeHab.value) marcar(escolhaDeHab.value, true); });
  const ancient = el("input", { type: "checkbox", ...(l.ancient ? { checked: "" } : {}) });
  ancient.addEventListener("change", () => { l.ancient = ancient.checked; mudou(); });

  trocar(caixa,
    el("div", { class: "detalhe-slot" }, t(NOMES[nome])),
    el("p", { class: "detalhe-titulo " + (l.item ? "com-item" : "livre") }, l.item || t("Qualquer item")),
    el("h3", {}, t("Afixos que você quer")),
    el("div", { class: "chips" }, afixos.filter(x => !x.habilidade).map(chip),
      dasHabilidades.filter(x => l.afixos.includes(x.modelo)).map(chip)),
    escolhaDeHab,
    el("label", { class: "campo-chave campo-ancient" }, ancient,
      el("span", {}, el("span", { class: "campo-nome" }, t("Precisa ser Ancient")))),
    el("h3", {}, t("Item")),
    campoDeBusca(t("Buscar item pelo nome (em inglês, como no jogo)")),
    el("button", { type: "button", class: "opcao opcao-livre" + (l.item ? "" : " ativo"), onclick: () => { l.item = null; mudou(); } },
      icone(null, "icone-mini"), el("span", {}, el("span", { class: "opcao-nome" }, t("Qualquer item")), el("span", { class: "opcao-sub" }, t("vale o que tiver os afixos")))),
    lista(itensDoLugar(nome).map(opcaoDeItem), l.item, o => { l.item = o.nome; mudou(); }),
    el("p", { class: "nota" }, t("{classe}: só aparecem os itens que a classe usa. O atributo principal ({atributo}) já é exigido em todos os espaços.", { classe: nomeDaClasse(estado.classe), atributo: t(daClasse().atributo.rotulo) })));
}

function editorDaGema(caixa, i) {
  const b = atual();
  const outras = b.gemas.filter((g, j) => g && j !== i);
  trocar(caixa,
    el("div", { class: "detalhe-slot" }, t("Gema lendária {n}", { n: i + 1 })),
    el("p", { class: "detalhe-titulo livre" }, b.gemas[i] || t("Escolha uma gema")),
    b.gemas[i] && el("button", { type: "button", class: "botao botao-leve", onclick: () => { b.gemas[i] = null; mudou(); } }, t("Tirar a gema")),
    campoDeBusca(t("Buscar gema")),
    lista(estado.jogo.gemas.filter(g => !outras.includes(g.n)).map(g => ({ nome: g.n, dica: g.n, icone: ICONE_ITEM(g.i), cor: "t-lendario", redondo: true })),
      b.gemas[i], o => { b.gemas[i] = o.nome; mudou(); }));
}

function editorDoCubo(caixa, parte) {
  const b = atual();
  const itens = CUBO_ACEITA[parte].flatMap(e => (estado.jogo.espacos[e] || []))
    .filter(i => !i.s && (!i.c.length || i.c.includes(estado.classe)));  // poder de set não vai no cubo
  const unicos = [...new Map(itens.map(i => [i.n, i])).values()].sort((x, y) => x.n.localeCompare(y.n));
  trocar(caixa,
    el("div", { class: "detalhe-slot" }, `${t("Cubo de Kanai")} · ${t(PARTES_DO_CUBO[parte])}`),
    el("p", { class: "detalhe-titulo livre" }, b.cubo[parte] || t("Escolha o poder lendário")),
    b.cubo[parte] && el("button", { type: "button", class: "botao botao-leve", onclick: () => { b.cubo[parte] = null; mudou(); } }, t("Tirar do cubo")),
    campoDeBusca(t("Buscar item pelo nome")),
    lista(unicos.map(opcaoDeItem), b.cubo[parte], o => { b.cubo[parte] = o.nome; mudou(); }));
}

function editorDaAtiva(caixa, i) {
  const b = atual();
  const c = daClasse();
  const a = b.ativas[i];
  const h = a && habPorSlug(c.ativas, a.s);
  const usadas = b.ativas.filter((x, j) => x && j !== i).map(x => x.s);
  const [nomeLugar, tecla] = LUGARES_DAS_HABILIDADES[i];
  trocar(caixa,
    el("div", { class: "detalhe-slot" }, `${t(nomeLugar)} (${t(tecla)})`),
    el("p", { class: "detalhe-titulo livre" }, h ? nomeDaHab(h) : t("Escolha a habilidade")),
    h && !emIngles() && h.n !== h.p && el("p", { class: "mudo nome-ingles" }, `No jogo em inglês: ${h.n}`),
    h && [
      el("h3", {}, t("Runa")),
      el("div", { class: "runas" },
        el("button", { type: "button", class: "opcao" + (a.r ? "" : " ativo"), onclick: () => { a.r = ""; mudou(); } },
          el("span", {}, el("span", { class: "opcao-nome" }, t("Sem runa")))),
        h.r.map(r => el("button", {
          type: "button", class: "opcao" + (a.r === r[0] ? " ativo" : ""), onclick: () => { a.r = r[0]; mudou(); },
        }, el("span", {}, el("span", { class: "opcao-nome t-ouro" }, `◆ ${nomeDaRuna(r)}`), el("span", { class: "opcao-sub" }, t("libera no nível {n}", { n: r[2] })))))),
      el("button", { type: "button", class: "botao botao-leve", onclick: () => { b.ativas[i] = null; mudou(); } }, t("Tirar a habilidade")),
    ],
    el("h3", {}, t("Habilidade")),
    campoDeBusca(t("Buscar habilidade (português ou inglês)")),
    lista(c.ativas.filter(x => !usadas.includes(x.s)).map(x => ({ nome: nomeDaHab(x), valor: x.s, sub: subDaHab(x), icone: ICONE_HAB(x.i) })),
      a && a.s, o => { b.ativas[i] = { s: o.valor, r: "" }; mudou(); }));
}

function editorDaPassiva(caixa, i) {
  const b = atual();
  const c = daClasse();
  const h = b.passivas[i] && habPorSlug(c.passivas, b.passivas[i]);
  const usadas = b.passivas.filter((x, j) => x && j !== i);
  trocar(caixa,
    el("div", { class: "detalhe-slot" }, t("Passiva {n}", { n: i + 1 })),
    el("p", { class: "detalhe-titulo livre" }, h ? nomeDaHab(h) : t("Escolha a passiva")),
    h && el("button", { type: "button", class: "botao botao-leve", onclick: () => { b.passivas[i] = null; mudou(); } }, t("Tirar a passiva")),
    campoDeBusca(t("Buscar passiva")),
    lista(c.passivas.filter(x => !usadas.includes(x.s)).map(x => ({ nome: nomeDaHab(x), valor: x.s, sub: subDaHab(x), icone: ICONE_HAB(x.i), redondo: true })),
      b.passivas[i], o => { b.passivas[i] = o.valor; mudou(); }));
}

// ------------------------------------------------------------ início

function abrirSubAba(nome) {
  estado.sub = nome;
  raiz.querySelectorAll(".sub-aba").forEach(s => s.classList.toggle("ativa", s.dataset.sub === nome));
  raiz.querySelectorAll(".sub-painel").forEach(p => p.classList.toggle("ativo", p.dataset.m === `sub-${nome}`));
  raiz.querySelector(".builds-grade").classList.toggle("sem-detalhe", nome === "paragon");
  if (nome === "habilidades" && !["ativa", "passiva"].includes(estado.alvo.tipo)) estado.alvo = { tipo: "ativa", i: 0 };
  if (nome === "equipamento" && ["ativa", "passiva"].includes(estado.alvo.tipo)) estado.alvo = { tipo: "espaco", lugar: "Head" };
  estado.busca = "";
  desenharEditor();
  desenharHabilidades();
  desenharBoneco();
}

let pronto = null;  // a promessa do iniciar (o app pode pedir abrir() antes de terminar)

async function iniciar(elemento, escolhas) {
  raiz = elemento;
  opcoes = escolhas;
  raiz.querySelectorAll(".sub-aba").forEach(s => s.addEventListener("click", () => abrirSubAba(s.dataset.sub)));
  try {
    estado.jogo = await opcoes.carregar();
    if (!estado.jogo || !estado.jogo.classes) throw new Error("sem dados");
  } catch {
    trocar($("carregando"), el("span", { class: "t-falta" },
      noApp() ? t("Não consegui abrir os itens do jogo (falta o arquivo dados/jogo.json do app).") : t("Não consegui carregar os itens do jogo. Recarregue a página.")));
    return false;
  }
  const guardado = lerGuardado();
  if (guardado.rascunhos && typeof guardado.rascunhos === "object") {
    for (const [cl, b] of Object.entries(guardado.rascunhos)) if (CLASSES[cl] && b && b.lugares) estado.rascunhos[cl] = b;
  }
  if (CLASSES[guardado.classe]) estado.classe = guardado.classe;
  const doLink = !noApp() && await abrirLinkDoEndereco();
  $("carregando").hidden = true;
  $("builds-corpo").hidden = false;
  if (!doLink) {
    avisar(noApp() ? t("Escolha a classe, clique nos espaços e monte. No fim, \"Salvar no app\": a build vai pra aba Builds e o atalho passa a usar ela.")
                   : t("Escolha a classe, clique nos espaços e monte. No fim, \"Copiar link da build\" e cole no app."));
  }
  desenhar();
  return true;
}

// Uma build do app aberta pra mudar. id: a que "Salvar mudanças" altera ("" = salvar como nova).
async function abrir(build, id = "") {
  if (!(await pronto)) return;
  try {
    estado.classe = build.classe;
    estado.rascunhos[build.classe] = Object.assign(doBuild(build), { id });
  } catch {
    avisar(t("Não consegui abrir essa build no montador."), true);
    return;
  }
  estado.alvo = { tipo: "espaco", lugar: "Head" };
  estado.busca = "";
  guardar();
  avisar(id ? t("Mudando {nome}: \"Salvar mudanças\" grava em cima dela.", { nome: build.apelido })
            : t("Cópia de {nome}: ao salvar, vira uma build nova (a original fica como está).", { nome: build.apelido }));
  desenhar();
}

// Site com conta (nuvem.js): a build de agora e a id dela na nuvem ("" = ainda não está lá).
function paraNuvem() {
  return { build: paraBuild(), classe: estado.classe, nuvem: atual().nuvem || "" };
}
function marcarNuvem(classe, id) {
  const b = estado.rascunhos[classe];
  if (!b) return;
  b.nuvem = id;
  guardar();
  desenharCabeca();
}
// Esquece a id de uma build apagada na nuvem (sem id: de todas). O rascunho fica.
function esquecerNuvem(id) {
  for (const b of Object.values(estado.rascunhos)) if (b.nuvem && (!id || b.nuvem === id)) delete b.nuvem;
  guardar();
  desenharCabeca();
}
async function daNuvem(build, id) {
  if (!(await pronto)) return false;
  try {
    estado.rascunhos[build.classe] = Object.assign(doBuild(build), { nuvem: id });
    estado.classe = build.classe;
  } catch {
    avisar(t("Não consegui abrir essa build no montador."), true);
    return false;
  }
  estado.alvo = { tipo: "espaco", lugar: "Head" };
  estado.busca = "";
  if (!noApp()) history.replaceState(null, "", location.pathname);
  guardar();
  avisar(t("Build aberta da nuvem: {nome}. \"Salvar na nuvem\" grava em cima dela.", { nome: estado.rascunhos[build.classe].apelido || nomeDaClasse(build.classe) }));
  desenhar();
  return true;
}

window.Montador = {
  iniciar: (elemento, escolhas) => (pronto ||= iniciar(elemento, escolhas)),
  abrir,
  paraNuvem, marcarNuvem, esquecerNuvem, daNuvem, nomeDaClasse,
  noSite: Promise.resolve(false),  // no site: a promessa de "idioma + montador prontos"
};

// No site, liga sozinho (no app quem liga é o app.js, ao abrir a aba Montar).
const noSite = document.querySelector('[data-montador="site"]');
if (noSite && window.top !== window.self) {
  // Contra clickjacking (o GitHub Pages não deixa proibir iframe por cabeçalho):
  // dentro de outro site, a página some e tenta abrir por inteiro.
  document.documentElement.hidden = true;
  try { window.top.location.href = window.self.location.href; } catch { /* bloqueado: fica escondida */ }
} else if (noSite) {
  const json = async caminho => {
    const r = await fetch(caminho);
    if (!r.ok) throw new Error(String(r.status));
    return r.json();
  };
  window.Montador.noSite = (async () => {
    // Primeiro o idioma (o da escolha guardada ou o do navegador), depois o resto.
    if (window.Idioma) {
      window.Idioma.escolher();
      await window.Idioma.carregar(() => json("dados/en.json"));
      window.Idioma.aplicar();
    }
    const ok = window.Montador.iniciar(noSite, { modo: "site", carregar: () => json("dados/jogo.json") });
    if (window.Dicas) window.Dicas.ligar(() => json(emIngles() ? "dados/dicas.en.json" : "dados/dicas.json"));
    return ok;
  })();
}
})();
