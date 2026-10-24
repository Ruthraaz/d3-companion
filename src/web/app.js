// D3 Companion — janela principal.
// Os dados vêm do Python (src/janela.py, classe Api) por window.pywebview.api.
// Aberta direto no navegador (sem pywebview), a página usa dados de exemplo:
// serve pra mexer no visual sem abrir o jogo nem o app.

"use strict";

// Nomes dos espaços em português; a chave é a mesma do JSON da build.
const ESPACOS = {
  Head: "Cabeça", Shoulders: "Ombros", Neck: "Amuleto", Torso: "Peito",
  Hands: "Mãos", Wrists: "Braçadeiras", Waist: "Cintura", Legs: "Pernas",
  Feet: "Pés", Finger: "Anéis", Weapon: "Arma", "Off-Hand": "Mão secundária",
};
// Lugar de cada espaço no boneco (grid-area do CSS). Os dois anéis usam o mesmo "Finger".
const BONECO = [
  ["Shoulders", "Shoulders"], ["Head", "Head"], ["Neck", "Neck"],
  ["Hands", "Hands"], ["Torso", "Torso"], ["Wrists", "Wrists"],
  ["Finger", "FingerL"], ["Waist", "Waist"], ["Finger", "FingerR"],
  ["Weapon", "Weapon"], ["Legs", "Legs"], ["Off-Hand", "OffHand"],
  ["Feet", "Feet"],
];

const estado = {
  api: null,
  builds: [],
  build: 0,          // índice da build escolhida
  espaco: "Head",    // espaço aberto no painel de detalhe
  historico: [],
  filtro: "todos",
  miniaturas: {},    // nome do arquivo -> data URI (pede ao Python uma vez só)
  ultimoVisto: null, // "quando" do registro mais novo já mostrado (ISO, compara como texto)
};

// ------------------------------------------------------------ utilidades

// Cria elementos sem innerHTML: nomes de item vêm do OCR e não são confiáveis.
function el(tag, props = {}, ...filhos) {
  const no = document.createElement(tag);
  for (const [k, v] of Object.entries(props)) {
    if (k === "class") no.className = v;
    else if (k === "dataset") Object.assign(no.dataset, v);
    else if (k.startsWith("on")) no.addEventListener(k.slice(2), v);
    else no.setAttribute(k, v);
  }
  for (const f of filhos.flat()) {
    if (f !== null && f !== undefined && f !== false) no.append(f);
  }
  return no;
}

function trocar(no, ...filhos) {
  no.replaceChildren(...filhos.flat().filter(Boolean));
}

function hora(iso) {
  const d = new Date(iso);
  const hoje = new Date().toDateString() === d.toDateString();
  const hh = d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
  return hoje ? hh : `${d.toLocaleDateString("pt-BR")} ${hh}`;
}

// ------------------------------------------------------------ abas

function abrirAba(nome) {
  document.querySelectorAll(".aba").forEach(a => a.classList.toggle("ativa", a.dataset.aba === nome));
  document.querySelectorAll(".painel").forEach(p => p.classList.toggle("ativo", p.id === `painel-${nome}`));
  if (nome === "config") carregarConfig();
}

// ------------------------------------------------------------ builds

function desenharBuilds() {
  const caixa = document.getElementById("escolha-build");
  if (!estado.builds.length) {
    trocar(caixa, el("p", { class: "mudo" }, "Nenhuma build em builds/. Crie um arquivo JSON lá (veja o README)."));
    return;
  }
  trocar(caixa, estado.builds.map((b, i) =>
    el("button", {
      class: "chip-build" + (i === estado.build ? " ativo" : ""),
      onclick: () => { estado.build = i; desenharBuilds(); },
    },
      el("span", { class: "chip-apelido" }, b.apelido),
      el("span", { class: "chip-nome" }, b.nome),
    )));
  desenharBoneco();
  desenharDetalhe();
}

function desenharBoneco() {
  const build = estado.builds[estado.build];
  trocar(document.getElementById("boneco"), BONECO.map(([chave, area]) => {
    const espaco = build.espacos[chave];
    const classe = !espaco.definido ? "geral" : espaco.itens.length ? "com-item" : "livre";
    const item = espaco.itens.length ? espaco.itens.join(" ou ") : "Qualquer item";
    const n = espaco.obrigatorios.length + espaco.desejaveis.length;
    const afixos = n ? `${n} afixo${n > 1 ? "s" : ""}` : "";
    return el("button", {
      class: `espaco ${classe}` + (chave === estado.espaco ? " selecionado" : ""),
      style: `grid-area: ${area}`,
      title: espaco.definido ? item : "A build não fala deste espaço: valem só as regras gerais",
      onclick: () => { estado.espaco = chave; desenharBoneco(); desenharDetalhe(); },
    },
      el("span", { class: "espaco-nome" }, ESPACOS[chave] || chave),
      el("span", { class: "espaco-item" }, item),
      afixos && el("span", { class: "espaco-afixos" }, afixos),
      espaco.exige_ancient && el("span", { class: "selo-ancient", title: "Precisa ser Ancient" }, "ANC"),
    );
  }));
}

function etiquetas(lista, classe) {
  if (!lista.length) return el("p", { class: "nada" }, "Nenhum.");
  return el("ul", {}, lista.map(t => el("li", { class: `etiqueta ${classe}` }, t)));
}

function desenharDetalhe() {
  const build = estado.builds[estado.build];
  const espaco = build.espacos[estado.espaco];
  const nome = ESPACOS[estado.espaco] || estado.espaco;
  const caixa = document.getElementById("detalhe");

  trocar(caixa,
    el("div", { class: "detalhe-slot" }, nome + (espaco.exige_ancient ? " · Ancient" : "")),
    el("p", { class: "detalhe-titulo " + (espaco.itens.length ? "com-item" : "livre") },
      espaco.itens.length ? espaco.itens.join(" ou ") : "Qualquer item"),
    !espaco.definido && el("p", { class: "mudo" },
      `A build ${build.apelido} não fala deste espaço: valem só as regras gerais, que ela pede em todos.`),
    el("h3", {}, "Obrigatórios"),
    etiquetas(espaco.obrigatorios, "obrigatorio"),
    el("h3", {}, "Desejáveis"),
    etiquetas(espaco.desejaveis, ""),
    blocoGemas(build),
    el("p", { class: "nota" },
      "Obrigatório que falta = \"não serve\". Desejáveis só dão nota. ",
      "Pra mudar, edite o arquivo da build em ", el("code", {}, "builds/"), "."),
  );
}

function blocoGemas(build) {
  return [el("h3", {}, "Gemas lendárias"), etiquetas(build.gemas, "gema")];
}

// ------------------------------------------------------------ histórico

function desenharHistorico(anterior = null) {
  const lista = document.getElementById("lista-historico");
  const itens = estado.historico.filter(h =>
    estado.filtro === "todos" || (estado.filtro === "serve") === h.serve);
  if (!itens.length) {
    trocar(lista, el("li", { class: "vazio-lista" },
      estado.historico.length
        ? "Nenhum item neste filtro."
        : "Nada avaliado ainda. No jogo, passe o mouse num item e aperte o atalho."));
    return;
  }
  trocar(lista, itens.map(h => registro(h, anterior)));
}

function registro(h, anterior) {
  const tipo = [h.qualidade, h.tipo].filter(Boolean).join(" ");
  const mini = el("div", { class: "miniatura", title: h.imagem || "" });
  if (h.imagem) pedirMiniatura(h.imagem, mini);
  const novo = anterior && h.quando > anterior;
  return el("li", { class: "registro" + (h.serve ? " serve" : "") + (novo ? " novo" : "") },
    mini,
    el("div", {},
      el("p", { class: "registro-titulo" }, h.titulo),
      tipo && el("p", { class: "registro-tipo" }, tipo),
      h.linhas.map(linha => el("p", { class: "registro-linha" },
        linha.map(([texto, estilo]) => el("span", { class: `t-${estilo}` }, texto)))),
    ),
    el("div", { class: "registro-hora" },
      hora(h.quando),
      el("br"),
      el("span", { class: "veredito" }, h.serve ? "Serve" : "Não serve"),
    ),
  );
}

async function pedirMiniatura(nome, alvo) {
  if (!(nome in estado.miniaturas)) {
    estado.miniaturas[nome] = await estado.api.miniatura(nome);
  }
  const url = estado.miniaturas[nome];
  if (url) alvo.style.backgroundImage = `url("${url}")`;
}

async function atualizarHistorico() {
  const novos = await estado.api.historico(100);
  const maisNovo = novos[0] ? novos[0].quando : null;
  if (maisNovo === estado.ultimoVisto && novos.length === estado.historico.length) return;
  const anterior = estado.ultimoVisto;  // o que chegou depois disso brilha
  estado.ultimoVisto = maisNovo;
  estado.historico = novos;
  desenharHistorico(anterior);
}

// ------------------------------------------------------------ estado e config

async function atualizarEstado() {
  const e = await estado.api.estado();
  const caixa = document.getElementById("estado");
  caixa.classList.toggle("ligado", e.rodando);
  caixa.classList.toggle("parado", !e.rodando);
  caixa.querySelector(".estado-texto").textContent = e.rodando
    ? `Overlay ativo · ${e.config.ATALHO}`
    : "Overlay parado — veja Configurações";
  document.getElementById("log").textContent = e.log.join("\n") || "(sem mensagens)";
}

async function carregarConfig() {
  const valores = await estado.api.config();
  const form = document.getElementById("form-config");
  for (const [chave, valor] of Object.entries(valores)) {
    if (form.elements[chave]) form.elements[chave].value = valor;
  }
}

async function salvarConfig(evento) {
  evento.preventDefault();
  const form = evento.target;
  const mudancas = {
    ATALHO: form.elements.ATALHO.value,
    SELO_SEGUNDOS: form.elements.SELO_SEGUNDOS.value,
  };
  const aviso = document.getElementById("aviso-config");
  aviso.textContent = "";
  const { erros } = await estado.api.salvar_config(mudancas);
  for (const chave of Object.keys(mudancas)) {
    form.elements[chave].classList.toggle("invalido", Boolean(erros[chave]));
    form.querySelector(`[data-erro="${chave}"]`).textContent = erros[chave] || "";
  }
  if (!Object.keys(erros).length) {
    aviso.textContent = "Salvo. Overlay reiniciado.";
    setTimeout(atualizarEstado, 1500);
  }
}

// ------------------------------------------------------------ início

async function iniciar(api) {
  estado.api = api;
  document.querySelectorAll(".aba").forEach(a => a.addEventListener("click", () => abrirAba(a.dataset.aba)));
  document.querySelectorAll(".filtro").forEach(f => f.addEventListener("click", () => {
    estado.filtro = f.dataset.filtro;
    document.querySelectorAll(".filtro").forEach(x => x.classList.toggle("ativo", x === f));
    desenharHistorico();  // trocar o filtro não faz nada "brilhar"
  }));
  document.getElementById("form-config").addEventListener("submit", salvarConfig);
  document.getElementById("reiniciar").addEventListener("click", async () => {
    await estado.api.reiniciar_overlay();
    setTimeout(atualizarEstado, 1500);
  });

  estado.builds = await api.builds();
  desenharBuilds();
  await Promise.all([atualizarHistorico(), atualizarEstado()]);
  // O overlay é outro processo: de tempos em tempos, vê se chegou item novo.
  setInterval(atualizarHistorico, 1500);
  setInterval(atualizarEstado, 3000);
}

if (window.pywebview && window.pywebview.api) {
  iniciar(window.pywebview.api);
} else {
  let pronto = false;
  window.addEventListener("pywebviewready", () => { pronto = true; iniciar(window.pywebview.api); });
  // Sem pywebview em 600 ms: é um navegador comum, usa os dados de exemplo.
  setTimeout(() => { if (!pronto) iniciar(apiDeExemplo()); }, 600);
}

// ------------------------------------------------------------ dados de exemplo

function apiDeExemplo() {
  const afixo = (...r) => r;

  const esp = (itens, deseja = [], ancient = false) => ({
    definido: true, itens, obrigatorios: ["Destreza"], desejaveis: ["Vitalidade", ...deseja], exige_ancient: ancient,
  });
  // Como a ficha_da_build do Python: os espaços que faltam viram "só regras gerais".
  const build = (nome, apelido, espacos, gemas, ancient = false) => {
    for (const chave of Object.keys(ESPACOS)) {
      espacos[chave] = espacos[chave] || { ...esp([], [], ancient), definido: false };
    }
    return { nome, apelido, classe: "Demon Hunter", exige_ancient: ancient,
             gerais: { obrigatorios: ["Destreza"], desejaveis: ["Vitalidade"] }, espacos, gemas };
  };
  const critico = afixo("Encaixe", "Crítico", "Dano crítico");
  const builds = [
    build("Gears of Dreadlands — Metralhar", "Dreadlands", {
      Head: esp(["Dystopian Goggles"], ["Encaixe", "Crítico"]),
      Shoulders: esp(["Mechanical Pauldrons"]),
      Torso: esp(["Galvanized Vest"], ["Encaixe"]),
      Hands: esp(["Gas Powered Automail Forearm"], ["Crítico", "Dano crítico"]),
      Legs: esp(["Cold Cathode Trousers"], ["Encaixe"]),
      Feet: esp(["Antique Vintage Boots"]),
      Neck: esp([], critico), Finger: esp([], critico),
      Weapon: esp([], ["Dano da arma", "Encaixe"]),
    }, ["Bane of the Trapped", "Zei's Stone of Vengeance", "Bane of the Powerful"]),
    build("Unhallowed Essence — Multidisparo", "Unhallowed", {
      Head: esp(["Accursed Visage"], ["Encaixe", "Crítico"]),
      Torso: esp(["Cage of the Hellborn"], ["Encaixe"]),
      Hands: esp(["Fiendish Grips"], ["Crítico", "Dano crítico"]),
      Finger: esp([], critico),
    }, ["Bane of the Trapped", "Zei's Stone of Vengeance"]),
    build("Legacy of Nightmares", "LoN", {
      Head: esp([], ["Encaixe", "Crítico"], true),
      Finger: esp(["Litany of the Undaunted", "The Wailing Host"], critico, false),
    }, ["Bane of the Trapped"], true),
  ];
  const agora = Date.now();
  const quando = min => new Date(agora - min * 60000).toISOString().slice(0, 19);
  const historico = [
    { quando: quando(1), titulo: "Antique Vintage Boots", qualidade: "Set", tipo: "Boots", serve: true,
      linhas: [[["✅ ", "normal"], ["Dreadlands", "build"], [" · ", "normal"], ["Destreza ✓", "ok"], ["  ", "normal"], ["Vitalidade ✓", "ok"]]] },
    { quando: quando(3), titulo: "Cain's Scrivener", qualidade: "Set", tipo: "Gloves", serve: false,
      linhas: [[["❌ Não serve", "build"]], [["Dreadlands: A build pede: Gas Powered Automail Forearm", "motivo"]]] },
    { quando: quando(6), titulo: "Zei's Stone of Vengeance", qualidade: "Legendary", tipo: "Gem", serve: true,
      linhas: [[["✅ ", "normal"], ["Dreadlands", "build"], [" · Gema da build", "normal"]],
               [["✅ ", "normal"], ["LoN", "build"], [" · Gema da build", "normal"]]] },
  ];
  let config = { ATALHO: "F8", SELO_SEGUNDOS: "6" };
  return {
    builds: async () => builds,
    historico: async () => historico,
    miniatura: async () => null,
    config: async () => config,
    salvar_config: async m => {
      const erros = {};
      if (!/^((ctrl|alt|shift|win)\+)*(f([1-9]|1[0-9]|2[0-4])|[a-z0-9]|insert|pause)$/i.test(m.ATALHO.replace(/\s/g, "")))
        erros.ATALHO = `Atalho inválido: '${m.ATALHO}'. Exemplos: F8, Ctrl+F8, Alt+Q.`;
      const s = parseFloat(String(m.SELO_SEGUNDOS).replace(",", "."));
      if (!(s >= 1 && s <= 60)) erros.SELO_SEGUNDOS = "Tempo do selo precisa ficar entre 1 e 60 segundos.";
      if (!Object.keys(erros).length) config = m;
      return { erros };
    },
    estado: async () => ({ rodando: true, config, log: ["(modo de exemplo: aberto fora do app)"] }),
    reiniciar_overlay: async () => ({}),
  };
}
