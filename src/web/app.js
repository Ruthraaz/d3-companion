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
// Espaços nas duas colunas do equipamento: armadura à esquerda, joias e armas
// à direita. Os dois anéis usam o mesmo "Finger" (FingerL/FingerR = qual mão).
const BONECO = {
  esq: [["Head", "Head"], ["Shoulders", "Shoulders"], ["Torso", "Torso"], ["Hands", "Hands"],
        ["Wrists", "Wrists"], ["Legs", "Legs"], ["Feet", "Feet"]],
  dir: [["Neck", "Neck"], ["Waist", "Waist"], ["Finger", "FingerL"], ["Finger", "FingerR"],
        ["Weapon", "Weapon"], ["Off-Hand", "OffHand"]],
};
const NOME_DO_LUGAR = { FingerL: "Anel 1", FingerR: "Anel 2" };

// Classe nas builds -> nome no jogo em português.
const CLASSES = {
  Barbarian: "Bárbaro", Crusader: "Cruzado", "Demon Hunter": "Caçador de Demônios", Monk: "Monge",
  Necromancer: "Necromante", "Witch Doctor": "Feiticeiro", Wizard: "Arcanista",
};
// Ícone de cada classe: uma habilidade marcante dela, do servidor da Blizzard.
const ICONE_DA_CLASSE = {
  Barbarian: "barbarian_whirlwind", Crusader: "x1_crusader_blessedhammer", "Demon Hunter": "demonhunter_multishot",
  Monk: "monk_waveoflight", Necromancer: "p6_necro_bonespear", "Witch Doctor": "witchdoctor_zombiecharger",
  Wizard: "wizard_meteor",
};
const SITE_DO_APP = "https://ruthraaz.github.io/d3-companion/";
const URL_DE_ICONE = "https://blzmedia-a.akamaihd.net/d3/icons/skills/64/";

// Idioma (idioma.js): t() traduz a frase pelo dados/en.json. Em inglês, os nomes
// do jogo (classes, habilidades, runas, seguidor) e os textos vêm do jogo em inglês.
const t = (texto, vars) => (window.Idioma ? window.Idioma.t(texto, vars) : texto);
const emIngles = () => Boolean(window.Idioma) && window.Idioma.atual === "en";
const nomeDaClasse = cl => (emIngles() ? cl : CLASSES[cl] || cl);
const nomeDe = h => (emIngles() ? h.nome || h.nome_pt : h.nome_pt);
const descricaoDe = h => (emIngles() ? h.descricao || h.descricao_pt : h.descricao_pt) || "";
const LOCALE = () => (emIngles() ? "en-US" : "pt-BR");

const estado = {
  api: null,
  builds: [],
  build: 0,          // índice da build mostrada no boneco
  ativa: "",         // id da build que o atalho usa ("" = todas); fica no .env (BUILD_ATIVA)
  espaco: "Head",    // espaço aberto no painel de detalhe
  habilidade: null,  // {tipo: "ativas"|"passivas", i}: habilidade aberta no detalhe (no lugar do espaço)
  visual: {},        // id da build -> ícones e textos da Blizzard ("carregando" enquanto busca)
  historico: [],
  filtro: "todos",
  miniaturas: {},    // nome do arquivo -> data URI (pede ao Python uma vez só)
  ultimoVisto: null, // "quando" do registro mais novo já mostrado (ISO, compara como texto)
  guias: null,       // lista de guias do Maxroll (pede ao Python na 1ª vez que abre a aba)
  classe: null,      // classe do boneco: filtra as abas Guias e Builds (as duas usam a mesma)
  herois: [],        // heróis da BattleTag (aba Meu herói)
  regiaoHeroi: "us", // região do herói escolhido (us, eu, kr, tw)
  heroi: null,       // id do herói escolhido
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
  for (const f of filhos.flat(Infinity)) {
    if (f !== null && f !== undefined && f !== false) no.append(f);
  }
  return no;
}

function trocar(no, ...filhos) {
  no.replaceChildren(...filhos.flat(Infinity).filter(Boolean));
}

// Ícone carregado do servidor da Blizzard (nunca salvo no projeto). Sem
// endereço, ou se a imagem não abrir, fica um quadrado vazio do mesmo tamanho.
function icone(url, classe = "") {
  const caixa = el("span", { class: `icone ${classe}`, "aria-hidden": "true" });
  if (url) {
    const img = el("img", { src: url, alt: "", loading: "lazy", draggable: "false" });
    img.addEventListener("error", () => img.remove());
    caixa.append(img);
  }
  return caixa;
}

function iconeDaClasse(cl, classe = "icone-classe") {
  return icone(ICONE_DA_CLASSE[cl] ? `${URL_DE_ICONE}${ICONE_DA_CLASSE[cl]}.png` : null, classe);
}

// Botão de classe (ícone + nome + quantidade), usado nas abas Guias e Builds.
function botaoDeClasse(cl, qtd, extra, onclick) {
  return el("button", { class: `classe${cl === estado.classe ? " ativo" : ""}${extra}`, role: "tab", onclick },
    iconeDaClasse(cl),
    el("span", { class: "classe-texto" },
      el("span", { class: "classe-nome" }, nomeDaClasse(cl)),
      el("span", { class: "classe-qtd" }, qtd)));
}

function hora(iso) {
  const d = new Date(iso);
  const hoje = new Date().toDateString() === d.toDateString();
  const hh = d.toLocaleTimeString(LOCALE(), { hour: "2-digit", minute: "2-digit" });
  return hoje ? hh : `${d.toLocaleDateString(LOCALE())} ${hh}`;
}

// ------------------------------------------------------------ abas

// Prints guardados (Configurações): quanto ocupam e o botão de apagar.
const tamanho = bytes => bytes < 1024 * 1024 ? `${Math.max(1, Math.round(bytes / 1024))} KB`
  : `${(bytes / 1024 / 1024).toFixed(1).replace(".0", "")} MB`;

async function mostrarPrints(info) {
  info ||= await estado.api.capturas();
  const botao = document.getElementById("apagar-prints");
  document.getElementById("espaco-prints").textContent = info.imagens
    ? t("{n} prints, {tamanho} no total.", { n: info.imagens, tamanho: tamanho(info.bytes) })
    : t("Nenhum print guardado.");
  botao.disabled = !info.imagens;
  botao.textContent = t("Apagar prints");
  delete botao.dataset.confirmar;
}

async function apagarPrints() {
  const botao = document.getElementById("apagar-prints");
  const aviso = document.getElementById("aviso-prints");
  if (!botao.dataset.confirmar) {  // primeiro clique só pergunta
    botao.dataset.confirmar = "1";
    botao.textContent = t("Clique de novo pra apagar");
    aviso.textContent = t("O histórico fica, só sem as miniaturas.");
    return;
  }
  await mostrarPrints(await estado.api.apagar_capturas());
  aviso.textContent = t("Prints apagados.");
  estado.miniaturas = {};
  estado.ultimoVisto = null;  // redesenha o histórico sem as miniaturas
  atualizarHistorico();
}

function abrirAba(nome) {
  document.querySelectorAll(".aba").forEach(a => a.classList.toggle("ativa", a.dataset.aba === nome));
  document.querySelectorAll(".painel").forEach(p => p.classList.toggle("ativo", p.id === `painel-${nome}`));
  if (nome === "config") { carregarConfig(); mostrarPrints(); }
  if (nome === "guias") estado.guias ? desenharGuias() : carregarGuias();
  if (nome === "builds" && estado.api) desenharBuilds();  // a classe pode ter mudado na aba Guias
  if (nome === "montar" && estado.api) ligarMontador();
  if (nome === "heroi" && !estado.herois.length && document.getElementById("form-heroi").elements.battletag.value) buscarHerois();
}

// ------------------------------------------------------------ montar build

// O montador é o mesmo do site (montar.js). Aqui ele lê os dados do jogo e
// grava pelo Python, que confere a build antes (Api.salvar_montada).
function ligarMontador() {
  return window.Montador.iniciar(document.getElementById("painel-montar"), {
    modo: "app",
    carregar: async () => {
      const r = await estado.api.dados_do_jogo("jogo");
      if (r.erro) throw new Error(r.erro);
      return r;
    },
    salvar: (build, id) => estado.api.salvar_montada(build, id),
    aoSalvar: async id => {
      estado.builds = await estado.api.builds();
      const i = estado.builds.findIndex(b => b.id === id);
      if (i >= 0) { estado.build = i; estado.classe = estado.builds[i].classe; estado.habilidade = null; }
      delete estado.visual[id];  // ícones e textos da build mudaram
      if (estado.ativa !== id) await escolherBuild(id);
    },
  });
}

// "Mudar no montador": abre a build na aba Montar. As feitas lá são alteradas
// no lugar; as do Maxroll abrem como cópia (o original fica como está).
async function abrirNoMontador(b) {
  const r = await estado.api.build_para_montar(b.id);
  if (r.erro) { trocar(document.getElementById("avaliando"), el("span", { class: "t-falta" }, r.erro)); return; }
  abrirAba("montar");
  await window.Montador.abrir(r.build, r.pode_alterar ? b.id : "");
}

// ------------------------------------------------------------ guias do Maxroll

async function carregarGuias(atualizar = false) {
  const status = document.getElementById("guias-status");
  status.className = "importar-status";
  status.textContent = t("Buscando a lista de guias no Maxroll…");
  const r = await estado.api.guias(atualizar);
  if (r.erro) {
    status.className = "importar-status erro";
    status.textContent = r.erro;
    return;
  }
  status.textContent = "";
  estado.guias = r.guias;
  desenharGuias();
}

// Busca sem acento e sem maiúscula: "furia" acha "Fúria".
const normalizar = t => t.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();

function desenharGuias() {
  const porClasse = cl => estado.guias.filter(g => g.classe === cl);
  trocar(document.getElementById("classes"), Object.keys(CLASSES).map(cl =>
    botaoDeClasse(cl, t("{n} guias", { n: porClasse(cl).length }), "", () => { trocarClasse(cl); desenharGuias(); })));
  const busca = normalizar(document.getElementById("filtro-guias").value.trim());
  const daClasse = porClasse(estado.classe).filter(g => !busca || normalizar(g.titulo).includes(busca));

  // Guia já importado: a build guarda o link do guia de onde veio.
  const importadas = {};
  for (const b of estado.builds) {
    const guia = b.fonte && b.fonte.guia;
    if (guia) (importadas[guia] = importadas[guia] || []).push(b.apelido);
  }
  trocar(document.getElementById("lista-guias"), daClasse.length ? daClasse.map(g =>
    el("li", { class: "guia" + (importadas[g.link] ? " importado" : "") },
      iconeDaClasse(g.classe),
      el("div", {},
        el("p", { class: "guia-titulo" }, g.titulo),
        el("p", { class: "guia-sub" }, importadas[g.link]
          ? t("No app: {builds}", { builds: importadas[g.link].join(", ") })
          : nomeDaClasse(g.classe))),
      el("div", { class: "guia-acoes" },
        el("button", { type: "button", class: "botao", onclick: () => verBuildsDoGuia(g.link) }, t("Ver builds")),
        el("button", { type: "button", class: "botao botao-leve", onclick: () => estado.api.abrir_link(g.link) },
          t("Ler o guia")))))
    : el("li", { class: "vazio-lista" }, busca ? t("Nenhum guia com esse nome.") : t("Nenhum guia dessa classe.")));
}

// Abre o painel de importar (aba Builds) já buscando as builds do guia.
function verBuildsDoGuia(link) {
  abrirAba("builds");
  abrirImportar();
  document.getElementById("form-importar").elements.link.value = link;
  buscarTexto(link);
}

// ------------------------------------------------------------ builds

// Build com JSON errado fica de fora do app; aqui a pessoa vê o que corrigir.
function desenharProblemas(problemas) {
  const caixa = document.getElementById("problemas");
  const arquivos = Object.keys(problemas);
  caixa.hidden = !arquivos.length;
  trocar(caixa, arquivos.length && [
    el("p", { class: "problemas-titulo" },
      arquivos.length === 1 ? t("Uma build ficou de fora por erro no arquivo:")
        : t("{n} builds ficaram de fora por erro no arquivo:", { n: arquivos.length })),
    arquivos.map(arquivo => el("div", { class: "problema" },
      el("code", {}, `builds/${arquivo}`),
      el("ul", {}, problemas[arquivo].map(p => el("li", {}, p))))),
    el("p", { class: "mudo" }, t("Corrija o arquivo e abra o app de novo. Pra conferir antes:"), " ",
      el("code", {}, "python src/avaliador.py --conferir")),
  ]);
}

// Troca a classe do boneco. O boneco passa a mostrar uma build dessa classe
// (só pra ver: a build que o atalho usa não muda).
function trocarClasse(cl) {
  estado.classe = cl;
  const atual = estado.builds[estado.build];
  if (!atual || atual.classe !== cl) {
    const i = estado.builds.findIndex(b => b.classe === cl);
    if (i >= 0) { estado.build = i; estado.habilidade = null; }
  }
}

function desenharClassesDasBuilds() {
  trocar(document.getElementById("classes-builds"), Object.keys(CLASSES).map(cl => {
    const n = estado.builds.filter(b => b.classe === cl).length;
    return botaoDeClasse(cl, n ? (n > 1 ? t("{n} builds", { n }) : t("1 build")) : t("nenhuma build"), n ? "" : " sem-build",
      () => { trocarClasse(cl); desenharBuilds(); });
  }));
}

// Cabeçalho da build: emblema da classe, nome, de onde veio e os botões.
function desenharCabecaDaBuild(b) {
  const fonte = b && b.fonte;
  const noAtalho = b && b.id === estado.ativa;
  trocar(document.getElementById("cabeca-build"), b && [
    iconeDaClasse(b.classe, "emblema"),
    el("div", { class: "cabeca-texto" },
      el("h1", { class: "build-titulo" }, b.apelido),
      el("p", { class: "build-sub" }, b.nome),
      el("p", { class: "build-meta" }, [nomeDaClasse(b.classe),
        fonte && fonte.site && (fonte.site === "montar" ? t("Montada no site") : t("Fonte: {site}", { site: fonte.site === "maxroll" ? "Maxroll" : fonte.site })),
        fonte && fonte.perfil].filter(Boolean).join(" · "))),
    el("div", { class: "cabeca-acoes" },
      fonte && fonte.link && el("button", { type: "button", class: "botao botao-leve", onclick: () => estado.api.abrir_link(fonte.link) },
        t("Abrir no Maxroll")),
      el("button", {
        type: "button", class: "botao" + (noAtalho ? " no-atalho" : ""),
        title: noAtalho ? t("O atalho já avalia os itens com esta build") : t("O atalho passa a avaliar os itens só com esta build"),
        onclick: () => { if (!noAtalho) escolherBuild(b.id); },
      }, noAtalho ? t("✓ No atalho") : t("Usar no atalho")),
      el("button", {
        type: "button", class: "botao botao-leve",
        title: fonte && fonte.site === "montar" ? t("Abrir na aba Montar pra mudar") : t("Abrir uma cópia na aba Montar (a original fica como está)"),
        onclick: () => abrirNoMontador(b),
      }, fonte && fonte.site === "montar" ? t("Mudar no montador") : t("Copiar pro montador")),
      botaoDeRemover(b)),
  ]);
}

// Remover pede um segundo clique (o arquivo some de builds/ de verdade).
function botaoDeRemover(b) {
  let confirmando = null;
  const botao = el("button", { type: "button", class: "botao botao-leve botao-remover", title: t("Tirar esta build do app") }, t("Remover"));
  botao.addEventListener("click", async () => {
    if (!confirmando) {
      botao.textContent = t("Clique de novo pra remover");
      botao.classList.add("confirmar");
      confirmando = setTimeout(() => { confirmando = null; botao.textContent = t("Remover"); botao.classList.remove("confirmar"); }, 4000);
      return;
    }
    clearTimeout(confirmando);
    botao.disabled = true;
    const r = await estado.api.remover_build(b.id);
    if (r.erro) { trocar(document.getElementById("avaliando"), el("span", { class: "t-falta" }, r.erro)); }
    estado.builds = await estado.api.builds();
    if (estado.ativa === b.id) estado.ativa = "";
    estado.build = Math.max(0, estado.builds.findIndex(x => x.classe === estado.classe));
    estado.habilidade = null;
    if (estado.guias) desenharGuias();
    desenharBuilds();
    if (!r.erro) trocar(document.getElementById("avaliando"), t("Build removida: {nome}.", { nome: b.apelido }));
  });
  return botao;
}

function desenharBuilds() {
  desenharClassesDasBuilds();
  const caixa = document.getElementById("escolha-build");
  const daClasse = estado.builds.map((b, i) => [b, i]).filter(([b]) => b.classe === estado.classe);
  const corpo = document.getElementById("builds-corpo");
  corpo.hidden = !daClasse.length;
  if (!estado.builds.length) {
    // App novo: as builds são de cada um. Começa com o colar link aberto.
    desenharCabecaDaBuild(null);
    trocar(caixa, el("div", { class: "boas-vindas" },
      el("h2", {}, t("Monte a sua lista de builds")),
      el("p", {}, t("Cole abaixo o link de um guia ou do planejador do Maxroll. A build é importada e fica salva aqui no app, pronta pro atalho. Pode colar quantas quiser e tirar quando não usar mais.")),
      el("p", { class: "mudo" }, t("Não sabe qual?"), " ",
        el("button", { class: "link", type: "button", onclick: () => abrirAba("guias") }, t("Veja os guias por classe")), ".")));
    if (document.getElementById("importar").hidden) abrirImportar();
    document.getElementById("fechar-importar").hidden = true;
    trocar(document.getElementById("avaliando"));
    return;
  }
  document.getElementById("fechar-importar").hidden = false;
  if (!daClasse.length) {
    desenharCabecaDaBuild(null);
    trocar(caixa,
      el("p", { class: "mudo" }, t("Nenhuma build de {classe} ainda.", { classe: nomeDaClasse(estado.classe) }), " ",
        el("button", { class: "link", type: "button", onclick: () => abrirAba("guias") }, t("Ver os guias dessa classe"))),
      el("button", { class: "chip-build chip-importar", onclick: () => abrirImportar() },
        el("span", { class: "chip-apelido" }, t("+ Colar link")), el("span", { class: "chip-nome" }, t("de uma build do Maxroll"))));
    trocar(document.getElementById("avaliando"));
    return;
  }
  // Clicar numa build = o F8 passa a avaliar só com ela. "Todas" = com todas.
  // Com "Todas", o boneco continua mostrando a última build olhada (contorno fino).
  const todas = estado.ativa === "";
  trocar(caixa,
    el("button", {
      class: "chip-build chip-todas" + (todas ? " ativo" : ""),
      title: t("O atalho avalia o item com todas as builds"),
      onclick: () => escolherBuild(""),
    },
      el("span", { class: "chip-apelido", "data-marca": t("no atalho") }, t("Todas")),
      el("span", { class: "chip-nome" }, t("{n} builds, de todas as classes", { n: estado.builds.length })),
    ),
    daClasse.map(([b, i]) =>
      el("button", {
        class: "chip-build" + (b.id === estado.ativa ? " ativo" : "") + (i === estado.build && b.id !== estado.ativa ? " vendo" : ""),
        title: t("O atalho avalia o item só com {nome}", { nome: b.apelido }),
        onclick: () => { estado.build = i; escolherBuild(b.id); },
      },
        el("span", { class: "chip-apelido", "data-marca": t("no atalho") }, b.apelido),
        el("span", { class: "chip-nome" }, b.nome),
      )),
  );
  caixa.append(el("button", {
    class: "chip-build chip-importar",
    title: t("Trazer uma build pronta de um guia do Maxroll"),
    onclick: () => abrirImportar(),
  }, el("span", { class: "chip-apelido" }, t("+ Colar link")), el("span", { class: "chip-nome" }, t("de uma build do Maxroll"))));
  // A build do atalho pode ser de outra classe que a que está no boneco.
  const com = apelidoAtivo({ BUILD_ATIVA: estado.ativa });
  desenharCabecaDaBuild(estado.builds[estado.build]);
  trocar(document.getElementById("avaliando"), t("O atalho avalia o item com"), " ", el("strong", {}, com), ".");
  desenharVisual();
  carregarVisual(estado.builds[estado.build]);
}

function desenharVisual() {
  desenharBoneco();
  desenharExtras();
  desenharHabilidades();
  desenharDetalhe();
  const v = visualDa(estado.builds[estado.build]);
  const aviso = document.getElementById("aviso-visual");
  aviso.hidden = !v.erro;
  aviso.textContent = v.erro ? t("Sem ícones da Blizzard: {erro}", { erro: v.erro }) : "";
}

// Ícones e textos em português vêm da Blizzard pelo Python (com cache em
// dados/). Desenha primeiro sem ícone e redesenha quando chegam.
async function carregarVisual(build) {
  if (build.id in estado.visual) return;
  estado.visual[build.id] = "carregando";
  const v = await estado.api.visual(build.id);
  estado.visual[build.id] = v;
  if (estado.builds[estado.build].id === build.id) desenharVisual();
}

function visualDa(build) {
  const v = estado.visual[build.id];
  return v && v !== "carregando" ? v : { itens: {}, habilidades: { ativas: [], passivas: [] }, seguidor: null, carregando: v === "carregando" };
}

function iconeDoItem(nome) {
  const v = visualDa(estado.builds[estado.build]);
  return (v.itens && v.itens[nome] && v.itens[nome].icone) || null;
}

async function escolherBuild(id) {
  estado.ativa = id;
  desenharBuilds();
  const { erros } = await estado.api.escolher_build(id);
  if (erros && erros.BUILD_ATIVA) alert(erros.BUILD_ATIVA);
  atualizarEstado();
}

function apelidoAtivo(config) {
  const b = estado.builds.find(x => x.id === config.BUILD_ATIVA);
  return b ? b.apelido : t("todas as builds");
}

// Os itens que aparecem num lugar do boneco. Com dois anéis na build (ex.:
// Focus e Restraint), cada mão mostra um; senão, as duas mostram a lista.
function itensDoLugar(espaco, area) {
  if (area.startsWith("Finger") && espaco.itens.length === 2) {
    return [espaco.itens[area === "FingerL" ? 0 : 1]];
  }
  return espaco.itens;
}

// Um espaço do equipamento: ícone quadrado e, do lado, o item (na cor da
// raridade) com o nome do espaço embaixo.
function botaoDoEspaco(build, chave, area) {
  const espaco = build.espacos[chave];
  const itens = itensDoLugar(espaco, area);
  const classe = !espaco.definido ? "geral" : itens.length ? "com-item" : "livre";
  const item = itens.length ? itens.join(t(" ou ")) : t("Qualquer item");
  const n = espaco.obrigatorios.length + espaco.desejaveis.length;
  const selecionado = chave === estado.espaco && !estado.habilidade;
  return el("button", {
    class: `espaco ${classe}` + (selecionado ? " selecionado" : ""),
    ...(itens.length ? { "data-dica": itens[0] } : { title: espaco.definido ? item : t("A build não fala deste espaço: valem só as regras gerais") }),
    onclick: () => { estado.espaco = chave; estado.habilidade = null; desenharVisual(); },
  },
    el("span", { class: "espaco-icone" },
      icone(itens.length ? iconeDoItem(itens[0]) : null, "icone-item"),
      espaco.exige_ancient && el("span", { class: "selo-ancient", title: t("Precisa ser Ancient") }, "ANC")),
    el("span", { class: "espaco-texto" },
      el("span", { class: "espaco-item" }, item),
      el("span", { class: "espaco-nome" }, t(NOME_DO_LUGAR[area] || ESPACOS[chave] || chave)),
      n > 0 && el("span", { class: "espaco-afixos" }, n > 1 ? t("{n} afixos", { n }) : t("1 afixo")),
    ),
  );
}

function desenharBoneco() {
  const build = estado.builds[estado.build];
  trocar(document.getElementById("equip-esq"), BONECO.esq.map(([chave, area]) => botaoDoEspaco(build, chave, area)));
  trocar(document.getElementById("equip-dir"), BONECO.dir.map(([chave, area]) => botaoDoEspaco(build, chave, area)));
}

const PARTES_DO_CUBO = { arma: "Arma", armadura: "Armadura", joia: "Joia" };

function desenharExtras() {
  const build = estado.builds[estado.build];
  const cubo = build.cubo || {};
  // Cubo de Kanai: os 3 poderes, como as 3 casas do cubo no jogo.
  trocar(document.getElementById("cubo"), Object.entries(PARTES_DO_CUBO).map(([parte, rotulo]) =>
    el("div", { class: "cubo-carta" + (cubo[parte] ? "" : " vazio"), ...(cubo[parte] ? { "data-dica": cubo[parte] } : {}) },
      icone(cubo[parte] && iconeDoItem(cubo[parte]), "icone-cubo"),
      el("div", {},
        el("p", { class: "cubo-rotulo" }, t(rotulo)),
        el("p", { class: "cubo-nome" + (cubo[parte] ? " t-lendario" : " mudo") }, cubo[parte] || t("a build não diz"))))));
  trocar(document.getElementById("gemas"), build.gemas.length
    ? build.gemas.map(g => el("div", { class: "mini-item", "data-dica": g },
        icone(iconeDoItem(g), "icone-mini"), el("span", { class: "t-lendario" }, g)))
    : el("p", { class: "nada" }, t("A build não diz.")));

  // A roda é só das gemas lendárias (como as runas no d4builds): 3 casas em triângulo.
  const no = (nome, pos) => {
    const url = nome && iconeDoItem(nome);
    return el("span", { class: `roda-no gema p${pos}` + (nome ? "" : " vazio"), ...(nome ? { "data-dica": nome } : { title: t("Gema: a build não diz") }) },
      url && el("img", { src: url, alt: "", draggable: "false", onerror: e => e.target.remove() }));
  };
  trocar(document.getElementById("roda"),
    el("span", { class: "roda-centro", "aria-hidden": "true" }),
    [0, 1, 2].map(i => no(build.gemas[i] || null, [0, 2, 4][i])));
}

// Paragon na ordem do jogo: 4 grupos de 4 atributos (o 1º do Principal é o da classe).
const ATRIBUTO = {
  Barbarian: "Força", Crusader: "Força", "Demon Hunter": "Destreza", Monk: "Destreza",
  Necromancer: "Inteligência", "Witch Doctor": "Inteligência", Wizard: "Inteligência",
};
const PARAGON = [
  ["Principal", [null, "Vitalidade", "Velocidade de movimento", "Recurso máximo"]],
  ["Ataque", ["Vel. de ataque", "Redução de recarga", "Chance de crítico", "Dano crítico"]],
  ["Defesa", ["Vida %", "Armadura", "Resistência total", "Regeneração de vida"]],
  ["Utilidade", ["Dano em área", "Redução de custo", "Vida por acerto", "Achar ouro"]],
];
const MAXIMO_DO_PARAGON = 50;  // por atributo, fora o atributo principal e a Vitalidade

// Os 6 lugares da barra, na ordem do Maxroll: os dois do mouse e depois 1 a 4.
const LUGARES = [["Primária", "Botão esquerdo"], ["Secundária", "Botão direito"],
                 ["Tecla 1", "1"], ["Tecla 2", "2"], ["Tecla 3", "3"], ["Tecla 4", "4"]];

function desenharHabilidades() {
  const build = estado.builds[estado.build];
  const v = visualDa(build);
  const escolhidas = build.habilidades || { ativas: [], passivas: [] };
  const vazio = !escolhidas.ativas.length && !escolhidas.passivas.length;
  desenharParagon(build);
  desenharSeguidor(build);
  const janela = document.getElementById("janela-habilidades");
  if (vazio) {
    trocar(janela, el("p", { class: "nada" },
      t("Esta build ainda não tem habilidades. Elas vêm junto quando a build é importada do Maxroll.")));
    trocar(document.getElementById("ao-upar"), el("p", { class: "nada" }, t("Sem habilidades na build.")));
    return;
  }

  // Enquanto a Blizzard não respondeu, mostra o código da build (sem ícone).
  const daBuild = (tipo, i) => {
    if (v.habilidades[tipo][i]) return v.habilidades[tipo][i];
    const cru = escolhidas[tipo][i];
    if (!cru) return null;
    const slug = typeof cru === "string" ? cru : cru.habilidade;
    return { slug, nome: slug, nome_pt: slug, icone: null, descricao_pt: "", runa: null };
  };
  const escolhida = (tipo, i) => estado.habilidade && estado.habilidade.tipo === tipo && estado.habilidade.i === i;
  const escolher = (tipo, i) => { estado.habilidade = { tipo, i }; desenharHabilidades(); desenharDetalhe(); };

  const carta = i => {
    const h = daBuild("ativas", i);
    const [lugar, tecla] = LUGARES[i];
    return el("button", {
      type: "button", class: "carta-hab" + (h ? "" : " vazia") + (escolhida("ativas", i) ? " selecionado" : ""),
      ...(h ? {} : { disabled: "" }),
      onclick: () => escolher("ativas", i),
    },
      el("span", { class: "carta-lugar" }, t(lugar)),
      el("span", { class: "carta-corpo" },
        icone(h && h.icone, "icone-habilidade"),
        el("span", { class: "carta-texto" },
          el("span", { class: "carta-nome" }, h ? nomeDe(h) : t("vazio")),
          h && el("span", { class: "carta-runa" + (h.runa ? "" : " sem") }, h.runa ? nomeDe(h.runa) : t("sem runa")))),
      el("span", { class: "carta-tecla" }, t(tecla)),
      h && nivelDe(h) && el("span", { class: "carta-nivel" }, t("nível {n}", { n: nivelDe(h) })));
  };
  const passiva = i => {
    const h = daBuild("passivas", i);
    return el("button", {
      type: "button", class: "passiva-jogo" + (h ? "" : " vazia") + (escolhida("passivas", i) ? " selecionado" : ""),
      ...(h ? {} : { disabled: "" }),
      title: h ? nomeDe(h) + (nivelDe(h) ? ` · ${t("libera no nível {n}", { n: nivelDe(h) })}` : "") : "",
      onclick: () => escolher("passivas", i),
    }, icone(h && h.icone, "icone-passiva icone-grande"), el("span", {}, h ? nomeDe(h) : t("vazio")));
  };

  trocar(janela,
    el("section", { class: "secao-jogo" },
      el("h3", { class: "faixa-titulo" }, el("span", {}, t("Habilidades do mouse"))),
      el("div", { class: "grade-cartas" }, [0, 1].map(carta))),
    el("section", { class: "secao-jogo" },
      el("h3", { class: "faixa-titulo" }, el("span", {}, t("Barra de ação"))),
      el("div", { class: "grade-cartas" }, [2, 3, 4, 5].map(carta))),
    el("section", { class: "secao-jogo" },
      el("h3", { class: "faixa-titulo" }, el("span", {}, t("Passivas"))),
      el("div", { class: "fila-passivas" }, [0, 1, 2, 3].map(passiva))),
    el("p", { class: "nota" }, t("Clique numa habilidade pra ver o que ela e a runa fazem.")));
  desenharAoUpar(v);
}

// ------------------------------------------------------------ seguidor

const SEGUIDORES = { templar: "Templário", scoundrel: "Vigarista", enchantress: "Sibila" };
const ESPACOS_DO_SEGUIDOR = [
  ["Head", "Cabeça"], ["Shoulders", "Ombros"], ["Neck", "Amuleto"], ["Torso", "Peito"],
  ["Hands", "Mãos"], ["Wrists", "Braçadeiras"], ["Waist", "Cintura"], ["Legs", "Pernas"],
  ["Feet", "Pés"], ["FingerL", "Anel 1"], ["FingerR", "Anel 2"], ["Weapon", "Arma"],
  ["Off-Hand", "Mão secundária"], ["Relic", "Relíquia"],
];

function desenharSeguidor(build) {
  const caixa = document.getElementById("janela-seguidor");
  const s = build.seguidor;
  if (!s) {
    trocar(caixa, el("p", { class: "nada" }, t("Esta build não traz seguidor. As builds importadas do Maxroll trazem o seguidor do guia; se esta é de antes, cole o link de novo pra importar com ele.")));
    return;
  }
  const v = visualDa(build);
  const dele = v.seguidor;
  const habilidades = dele ? dele.habilidades
    : s.habilidades.map(slug => ({ slug, nome_pt: slug, nome: slug, nivel: null, icone: null, descricao_pt: "" }));
  const itens = ESPACOS_DO_SEGUIDOR.filter(([chave]) => s.itens[chave]);

  trocar(caixa,
    el("div", { class: "seguidor-cabeca" },
      el("p", { class: "seguidor-nome" }, (dele && nomeDe(dele)) || t(SEGUIDORES[s.quem] || s.quem)),
      el("p", { class: "mudo" }, t("O seguidor que o guia usa, com os itens e as 4 habilidades (uma a cada 5 níveis dele)."))),
    el("div", { class: "seguidor-grade" },
      el("section", { class: "secao-jogo" },
        el("h3", { class: "faixa-titulo" }, el("span", {}, t("Itens"))),
        itens.length
          ? el("ul", { class: "seguidor-itens" }, itens.map(([chave, rotulo]) =>
              el("li", { "data-dica": s.itens[chave] },
                icone(iconeDoItem(s.itens[chave]), "icone-mini"),
                el("span", {}, el("span", { class: "mini-rotulo" }, t(rotulo)), el("span", { class: "t-lendario" }, s.itens[chave])))))
          : el("p", { class: "nada" }, t("O guia não diz os itens."))),
      el("section", { class: "secao-jogo" },
        el("h3", { class: "faixa-titulo" }, el("span", {}, t("Habilidades"))),
        el("ol", { class: "seguidor-habilidades" }, habilidades.map(h =>
          el("li", {},
            icone(h.icone, "icone-habilidade"),
            el("div", {},
              el("p", { class: "seguidor-nivel" }, h.nivel ? t("Escolhida no nível {n}", { n: h.nivel }) : t("Habilidade")),
              el("p", { class: "seguidor-hab-nome" }, nomeDe(h)),
              descricaoDe(h) && el("p", { class: "descricao" }, descricaoDe(h)))))))),
    !dele && el("p", { class: "nota" }, v.carregando ? t("Buscando nomes e ícones na Blizzard…") : t("Sem nomes em português: falta a chave da Blizzard?")),
  );
}

// Nível em que a habilidade fica do jeito da build (ela e a runa liberadas).
function nivelDe(h) {
  return Math.max(h.nivel || 0, (h.runa && h.runa.nivel) || 0) || null;
}

// Linha do tempo pra upar: em que nível libera cada habilidade, runa e passiva da build.
function desenharAoUpar(v) {
  const marcos = [];
  for (const h of v.habilidades.ativas) {
    if (h.nivel) marcos.push({ nivel: h.nivel, texto: nomeDe(h), tipo: "ativa" });
    if (h.runa && h.runa.nivel) marcos.push({ nivel: h.runa.nivel, texto: t("runa {runa} ({hab})", { runa: nomeDe(h.runa), hab: nomeDe(h) }), tipo: "runa" });
  }
  for (const h of v.habilidades.passivas) {
    if (h.nivel) marcos.push({ nivel: h.nivel, texto: t("passiva {hab}", { hab: nomeDe(h) }), tipo: "passiva" });
  }
  const caixa = document.getElementById("ao-upar");
  if (!marcos.length) {
    trocar(caixa, el("p", { class: "nada" }, v.carregando ? t("Buscando na Blizzard…") : t("Sem dados de nível (falta a chave da Blizzard?).")));
    return;
  }
  const niveis = [...new Set(marcos.map(m => m.nivel))].sort((a, b) => a - b);
  trocar(caixa, el("ol", { class: "marcos" }, niveis.map(n =>
    el("li", { class: "marco" },
      el("span", { class: "marco-nivel" }, t("Nv {n}", { n })),
      el("span", {}, marcos.filter(m => m.nivel === n).map((m, i) => [
        i ? ", " : "", el("span", { class: `marco-${m.tipo}` }, m.texto)]))))));
}

// Ordem pra encher cada grupo (índices de PARAGON). O Maxroll só guarda os
// números, não a ordem: esta é a ordem comum dos guias de D3.
const ORDEM_DO_PARAGON = [
  [2, 3],        // Principal: Velocidade e Recurso primeiro; atributo e Vitalidade ficam com o resto
  [1, 2, 3, 0],  // Ataque: Recarga, Crítico, Dano crítico, Vel. de ataque
  [0, 2, 1, 3],  // Defesa: Vida %, Resistência, Armadura, Regeneração
  [0, 1, 2, 3],  // Utilidade: Área, Custo, Vida por acerto, Ouro
];

function desenharParagon(build) {
  const caixa = document.getElementById("paragon");
  const p = build.paragon;
  if (!p) {
    trocar(caixa, el("p", { class: "nada" }, t("A build não diz. Vem junto quando a build é importada do Maxroll.")));
    return;
  }
  const atributo = t(ATRIBUTO[build.classe] || "Atributo principal");
  const [principal, vit] = p.pontos[0];
  const passo = (numero, nome, n) => el("li", { class: "passo" + (n === 0 ? " zero" : "") },
    el("span", { class: "passo-num" }, numero),
    el("span", { class: "passo-nome" }, t(nome)),
    el("span", { class: "paragon-valor" }, n === 0 ? t("não pôr") : n >= MAXIMO_DO_PARAGON ? t("até 50") : t("{n} pontos", { n })));

  const grupos = PARAGON.map(([grupo, nomes], g) => {
    const ordem = ORDEM_DO_PARAGON[g];
    const comPonto = ordem.filter(i => p.pontos[g][i] > 0);
    const semPonto = ordem.filter(i => p.pontos[g][i] === 0);
    const linhas = [...comPonto, ...semPonto].map((i, k) =>
      passo(k < comPonto.length ? String(k + 1) : "–", nomes[i] || atributo, p.pontos[g][i]));
    if (g === 0) {
      // O número gigante do atributo principal é "o que sobra", não a prioridade.
      linhas.splice(comPonto.length, 0, el("li", { class: "passo passo-resto" },
        el("span", { class: "passo-num" }, String(comPonto.length + 1)),
        el("span", { class: "passo-nome" }, t("Todo o resto"),
          el("small", {}, [`${atributo} ${principal}`, vit && `${t("Vitalidade")} ${vit}`].filter(Boolean).join(" · "))),
        el("span", { class: "paragon-valor" }, t("sem limite"))));
    }
    return el("div", { class: "paragon-grupo" },
      el("p", { class: "paragon-titulo" }, el("span", { class: "paragon-ordem" }, String(g + 1)), t(grupo)),
      el("ol", { class: "passos" }, linhas));
  });

  trocar(caixa,
    el("div", { class: "paragon-explica" },
      el("p", {}, el("strong", {}, t("Como ler:")), " ",
        t("cada nível de paragon dá 1 ponto, e os grupos se revezam (Principal → Ataque → Defesa → Utilidade)."), " ",
        t("Dentro de cada grupo, encha na ordem dos números: o 1 primeiro, até o máximo, depois o 2…")),
      el("p", {}, el("strong", {}, t("{atributo} não é a prioridade:", { atributo })), " ",
        t("o número dela é grande só porque não tem limite. É onde caem os pontos do Principal depois que Velocidade e Recurso já encheram."))),
    el("div", { class: "paragon-grupos" }, grupos),
    p.nivel && el("p", { class: "nota" },
      t("Números da build no paragon {n}. \"Não pôr\" = a build deixa esse atributo em 0.", { n: p.nivel }), " ",
      t("A ordem dentro dos grupos é a comum dos guias; o Maxroll só guarda os números.")),
  );
}

function etiquetas(lista, classe) {
  if (!lista.length) return el("p", { class: "nada" }, t("Nenhum."));
  return el("ul", {}, lista.map(x => el("li", { class: `etiqueta ${classe}` }, t(x))));
}

function desenharDetalhe() {
  // Na aba Habilidades o detalhe é sempre de uma habilidade (trocar de build limpa a escolha).
  const sub = document.querySelector("#painel-builds .sub-aba.ativa");
  if (!estado.habilidade && sub && sub.dataset.sub === "habilidades") estado.habilidade = { tipo: "ativas", i: 0 };
  if (estado.habilidade) return desenharDetalheDaHabilidade();
  const build = estado.builds[estado.build];
  const espaco = build.espacos[estado.espaco];
  const nome = t(ESPACOS[estado.espaco] || estado.espaco);
  const caixa = document.getElementById("detalhe");

  trocar(caixa,
    el("div", { class: "detalhe-slot" }, nome + (espaco.exige_ancient ? " · Ancient" : "")),
    el("p", { class: "detalhe-titulo " + (espaco.itens.length ? "com-item" : "livre") },
      espaco.itens.length ? espaco.itens.join(t(" ou ")) : t("Qualquer item")),
    !espaco.definido && el("p", { class: "mudo" },
      t("A build {nome} não fala deste espaço: valem só as regras gerais, que ela pede em todos.", { nome: build.apelido })),
    el("h3", {}, t("Obrigatórios")),
    etiquetas(espaco.obrigatorios, "obrigatorio"),
    el("h3", {}, t("Desejáveis")),
    etiquetas(espaco.desejaveis, ""),
    blocoGemas(build),
    el("p", { class: "nota" },
      t("Obrigatório que falta = \"não serve\". Desejáveis só dão nota."), " ",
      t("Pra mudar, edite o arquivo da build em"), " ", el("code", {}, "builds/"), "."),
  );
}

function desenharDetalheDaHabilidade() {
  const { tipo, i } = estado.habilidade;
  const v = visualDa(estado.builds[estado.build]);
  const h = v.habilidades[tipo][i];
  const caixa = document.getElementById("detalhe");
  if (!h) {
    trocar(caixa, el("p", { class: "mudo" }, v.carregando ? t("Buscando na Blizzard…") : t("Sem dados desta habilidade.")));
    return;
  }
  trocar(caixa,
    el("div", { class: "detalhe-slot" },
      tipo === "passivas" ? t("Passiva") : `${t("Habilidade")} · ${t(LUGARES[i][0])} (${t(LUGARES[i][1])})`),
    el("div", { class: "detalhe-cabeca" },
      icone(h.icone, tipo === "passivas" ? "icone-passiva icone-grande" : "icone-habilidade icone-grande"),
      el("div", {},
        el("p", { class: "detalhe-titulo livre" }, nomeDe(h)),
        !emIngles() && h.nome !== h.nome_pt && el("p", { class: "mudo nome-ingles" }, `No jogo em inglês: ${h.nome}`))),
    h.nivel && el("p", { class: "mudo" }, h.runa && h.runa.nivel
      ? t("Libera no nível {n}; a runa {runa}, no nível {nr}.", { n: h.nivel, runa: nomeDe(h.runa), nr: h.runa.nivel })
      : t("Libera no nível {n}.", { n: h.nivel })),
    descricaoDe(h) && el("p", { class: "descricao" }, descricaoDe(h)),
    h.runa && [
      el("h3", {}, t("Runa")),
      el("p", { class: "runa-nome" }, nomeDe(h.runa),
        !emIngles() && h.runa.nome !== h.runa.nome_pt && el("span", { class: "mudo" }, ` (${h.runa.nome})`)),
      el("p", { class: "descricao" }, descricaoDe(h.runa)),
    ],
    tipo === "ativas" && !h.runa && el("p", { class: "mudo" }, t("A build não diz qual runa.")),
    el("p", { class: "nota" }, t("Textos e ícones da API oficial da Blizzard.")),
  );
}

function blocoGemas(build) {
  return [el("h3", {}, t("Gemas lendárias")), etiquetas(build.gemas, "gema")];
}

// ------------------------------------------------------------ meu herói

async function buscarHerois(evento) {
  if (evento) evento.preventDefault();
  const battletag = document.getElementById("form-heroi").elements.battletag.value.trim();
  const status = document.getElementById("heroi-status");
  if (!battletag) { status.className = "importar-status"; status.textContent = t("Escreva sua BattleTag primeiro."); return; }
  status.className = "importar-status";
  status.textContent = t("Buscando na Blizzard…");
  trocar(document.getElementById("lista-herois"));
  trocar(document.getElementById("comparar-com"));
  trocar(document.getElementById("resultado-heroi"));
  const r = await estado.api.herois(battletag);
  if (r.erro) { status.className = "importar-status erro"; status.textContent = r.erro; return; }
  estado.herois = r.herois;
  status.textContent = r.herois.length ? t("Escolha o herói.") : t("Essa conta não tem heróis.");
  desenharHerois();
}

function desenharHerois() {
  const variasRegioes = new Set(estado.herois.map(h => h.regiao)).size > 1;
  trocar(document.getElementById("lista-herois"), estado.herois.map(h =>
    el("button", {
      type: "button",
      class: "chip-build" + (h.id === estado.heroi && h.regiao === estado.regiaoHeroi ? " ativo-heroi" : ""),
      onclick: () => escolherHeroi(h.id, h.regiao),
    },
      iconeDaClasse(h.classe),
      el("span", {},
        el("span", { class: "chip-apelido" }, h.nome),
        el("span", { class: "chip-nome" }, [h.classe ? nomeDaClasse(h.classe) : "?", t("nível {n}", { n: h.nivel }),
          h.paragon ? `paragon ${h.paragon}` : "", h.temporada ? t("temporada") : "", h.hardcore ? "hardcore" : "",
          h.morto ? t("morto") : "", variasRegioes ? t(REGIOES[h.regiao] || h.regiao) : ""].filter(Boolean).join(" · "))))));
}

// Só aparece no chip quando a conta tem heróis em mais de uma região.
const REGIOES = { us: "Américas", eu: "Europa", kr: "Coreia", tw: "Taiwan" };  // passam por t()

function escolherHeroi(id, regiao) {
  estado.heroi = id;
  estado.regiaoHeroi = regiao;
  desenharHerois();
  const h = estado.herois.find(x => x.id === id && x.regiao === regiao);
  const daClasse = estado.builds.filter(b => b.classe === h.classe);
  const caixa = document.getElementById("comparar-com");
  if (!daClasse.length) {
    trocar(caixa, el("p", { class: "mudo" }, t("Você ainda não tem build de {classe}.", { classe: nomeDaClasse(h.classe) }), " ",
      el("button", { class: "link", type: "button", onclick: () => { trocarClasse(h.classe); abrirAba("guias"); } },
        t("Ver os guias dessa classe"))));
    trocar(document.getElementById("resultado-heroi"));
    return;
  }
  // Começa pela build do atalho, se for da classe do herói.
  const inicial = daClasse.find(b => b.id === estado.ativa) || daClasse[0];
  const escolha = el("select", { name: "build" }, daClasse.map(b =>
    el("option", { value: b.id, ...(b.id === inicial.id ? { selected: "" } : {}) }, `${b.apelido} — ${b.nome}`)));
  escolha.addEventListener("change", () => compararHeroi(escolha.value));
  trocar(caixa, el("label", { class: "campo" }, el("span", { class: "campo-nome" }, t("Comparar com a build")), escolha));
  compararHeroi(inicial.id);
}

const VEREDITO = { serve: "✅ Serve", parcial: "🟡 Por enquanto", nao: "❌ Não serve" };  // passam por t()
const MARCA_DA_HABILIDADE = { ok: "✓", runa: "≈", falta: "✗" };

async function compararHeroi(idBuild) {
  const caixa = document.getElementById("resultado-heroi");
  const battletag = document.getElementById("form-heroi").elements.battletag.value.trim();
  trocar(caixa, el("p", { class: "mudo" }, t("Comparando…")));
  const r = await estado.api.comparar_heroi(battletag, estado.heroi, idBuild, estado.regiaoHeroi || "us");
  if (r.erro) { trocar(caixa, el("p", { class: "importar-status erro" }, r.erro)); return; }
  const ordem = Object.keys(ESPACOS);
  const itens = [...r.itens].sort((a, b) => ordem.indexOf(a.espaco) - ordem.indexOf(b.espaco));
  const conta = v => itens.filter(i => i.veredito === v).length;
  const quando = r.heroi.atualizado ? new Date(r.heroi.atualizado * 1000).toLocaleString(LOCALE()) : null;
  const h = r.habilidades;

  trocar(caixa,
    el("p", { class: "resumo-heroi" },
      el("strong", {}, r.heroi.nome), " · ",
      t("{serve} peças servem, {parcial} por enquanto, {nao} não servem", { serve: conta("serve"), parcial: conta("parcial"), nao: conta("nao") }),
      quando && el("span", { class: "mudo" }, ` · ${t("dados da Blizzard de {quando}", { quando })}`)),
    !r.classe_igual && el("p", { class: "importar-status erro" }, t("Esse herói é de outra classe que a build.")),
    el("ul", { class: "itens-heroi" }, itens.map(i =>
      el("li", { class: `item-heroi ${i.veredito}` },
        icone(i.icone, "icone-item"),
        el("div", { class: "item-heroi-texto" },
          el("p", { class: "item-heroi-cabeca" },
            el("span", { class: "espaco-nome" }, t(ESPACOS[i.espaco] || i.espaco)), " ",
            el("span", { class: "item-heroi-nome" }, i.nome),
            el("span", { class: "veredito" }, t(VEREDITO[i.veredito]))),
          i.veredito !== "serve" && el("p", { class: "mudo" }, i.motivo),
          (i.tem.length > 0 || i.falta.length > 0) && el("p", { class: "item-heroi-afixos" },
            i.tem.map(x => el("span", { class: "t-ok" }, `${t(x)} ✓ `)),
            i.falta.map(x => el("span", { class: "t-falta" }, `${t(x)} ✗ `))),
          i.dica && el("p", { class: "dica" }, i.dica),
          i.encantado && !i.dica && i.falta.length > 0
            && el("p", { class: "mudo" }, t("Já trocado no Místico: \"{afixo}\" (só ele pode ser trocado de novo).", { afixo: i.encantado })))))),
    el("h3", {}, t("Habilidades")),
    h.ativas.length || h.passivas.length
      ? el("ul", { class: "habilidades-heroi" },
          h.ativas.map(a => el("li", { class: `hab-${a.estado}` },
            icone(a.icone, "icone-mini"),
            `${MARCA_DA_HABILIDADE[a.estado]} ${a.nome}`,
            a.runa_nome && el("span", { class: "mudo" }, ` · ${t("runa {runa}", { runa: a.runa_nome })}`),
            a.estado === "runa" && el("span", { class: "t-falta" }, ` (${t("você usa {runa}", { runa: a.runa_do_heroi_nome || t("outra") })})`),
            a.estado === "falta" && el("span", { class: "t-falta" }, ` (${t("falta na sua barra")})`))),
          h.passivas.map(p => el("li", { class: `hab-${p.estado}` },
            icone(p.icone, "icone-mini"),
            `${MARCA_DA_HABILIDADE[p.estado]} ${t("passiva {hab}", { hab: p.nome })}`,
            p.estado === "falta" && el("span", { class: "t-falta" }, ` (${t("falta")})`))))
      : el("p", { class: "nada" }, t("A build não tem habilidades (importe do Maxroll pra comparar).")),
    h.fora_da_build.length > 0 && el("p", { class: "mudo" }, t("No herói, mas fora da build: {lista}.", { lista: h.fora_da_build.join(", ") })),
    el("p", { class: "nota" }, t("Só os itens equipados. Mochila e baú: use o atalho no jogo.")),
  );
}

// ------------------------------------------------------------ importar do Maxroll

function abrirImportar() {
  const painel = document.getElementById("importar");
  painel.hidden = false;
  document.getElementById("importar-status").textContent = "";
  trocar(document.getElementById("importar-opcoes"));
  const campo = document.getElementById("form-importar").elements.link;
  campo.value = "";
  campo.focus();
}

function fecharImportar() {
  document.getElementById("importar").hidden = true;
}

async function buscarMaxroll(evento) {
  evento.preventDefault();
  buscarTexto(evento.target.elements.link.value.trim());
}

async function buscarTexto(texto) {
  const status = document.getElementById("importar-status");
  const opcoes = document.getElementById("importar-opcoes");
  if (!texto) { status.textContent = t("Cole um link primeiro."); return; }
  trocar(opcoes);
  status.className = "importar-status";
  status.textContent = t("Buscando no Maxroll…");
  const r = await estado.api.buscar_maxroll(texto);
  if (r.erro) {
    status.className = "importar-status erro";
    status.textContent = r.erro;
    return;
  }
  if (r.site) {
    status.textContent = t("Build montada no site: {nome} ({classe}).", { nome: r.site.nome, classe: nomeDaClasse(r.site.classe) });
    desenharImportarDoSite(texto, r.site);
    return;
  }
  status.textContent = r.builds.length > 1
    ? t("Esse link tem {n} builds. Escolha uma e o perfil (cada perfil é uma variação da build).", { n: r.builds.length })
    : t("Escolha o perfil (cada perfil é uma variação da build).");
  desenharOpcoesDeImportar(r.builds, 0);
}

function desenharOpcoesDeImportar(builds, escolhida) {
  const b = builds[escolhida];
  const perfil = el("select", { name: "perfil" },
    b.perfis.map((nome, i) => el("option", { value: String(i), ...(i === b.perfil ? { selected: "" } : {}) },
      `${i + 1}. ${nome}`)));
  const apelido = el("input", { name: "apelido", value: b.nome, autocomplete: "off", maxlength: "40" });
  const botao = el("button", { type: "button", class: "botao" }, t("Importar"));
  botao.addEventListener("click", () => importarMaxroll(b, Number(perfil.value), apelido.value, botao));

  trocar(document.getElementById("importar-opcoes"),
    builds.length > 1 && el("div", { class: "opcoes-builds" }, builds.map((x, i) =>
      el("button", {
        type: "button",
        class: "opcao-build" + (i === escolhida ? " ativo" : ""),
        onclick: () => desenharOpcoesDeImportar(builds, i),
      },
        el("span", { class: "chip-apelido" }, x.nome),
        el("span", { class: "chip-nome" }, `${nomeDaClasse(x.classe)} · ${t("{n} perfis", { n: x.perfis.length })}`)))),
    el("div", { class: "importar-campos" },
      el("label", { class: "campo" }, el("span", { class: "campo-nome" }, t("Perfil")), perfil),
      el("label", { class: "campo" }, el("span", { class: "campo-nome" }, t("Nome curto na janela e no selo")), apelido),
      botao),
  );
}

// Link do "Montar build" do site: a build já vem pronta, só falta o nome curto.
function desenharImportarDoSite(texto, site) {
  const apelido = el("input", { name: "apelido", value: site.apelido, autocomplete: "off", maxlength: "40" });
  const botao = el("button", { type: "button", class: "botao" }, t("Importar"));
  botao.addEventListener("click", () => importarMaxroll(null, 0, apelido.value, botao, texto));
  trocar(document.getElementById("importar-opcoes"),
    el("div", { class: "importar-campos" },
      el("label", { class: "campo" }, el("span", { class: "campo-nome" }, t("Nome curto na janela e no selo")), apelido),
      botao));
}

async function importarMaxroll(b, perfil, apelido, botao, linkDoSite = null) {
  const status = document.getElementById("importar-status");
  botao.disabled = true;
  status.className = "importar-status";
  status.textContent = t("Importando…");
  const r = linkDoSite
    ? await estado.api.importar_do_site(linkDoSite, apelido)
    : await estado.api.importar_maxroll(b.numero, perfil, apelido);
  botao.disabled = false;
  if (r.erro) {
    status.className = "importar-status erro";
    status.textContent = r.erro;
    return;
  }
  // A build nova entra na lista; o overlay só lê builds/ ao abrir, então reinicia.
  estado.builds = await estado.api.builds();
  estado.build = Math.max(0, estado.builds.findIndex(x => x.id === r.id));
  estado.classe = estado.builds[estado.build].classe;
  if (estado.guias) desenharGuias();
  estado.habilidade = null;
  fecharImportar();
  // Colou o link, já vale: o atalho passa a avaliar com a build nova.
  estado.ativa = r.id;
  await estado.api.escolher_build(r.id);
  desenharBuilds();
  estado.api.reiniciar_overlay();
  setTimeout(atualizarEstado, 1500);
  trocar(document.getElementById("avaliando"),
    el("strong", { class: "t-ok" }, t("Build importada: {nome}.", { nome: estado.builds[estado.build].apelido })), " ",
    t("O atalho já avalia com ela: no jogo, passe o mouse num item e aperte o atalho. O arquivo ficou em"), " ",
    el("code", {}, `builds/${r.id}.json`), ".");
}

// ------------------------------------------------------------ histórico

function desenharHistorico(anterior = null) {
  const lista = document.getElementById("lista-historico");
  // "Serve" junta o que serve e o que serve por enquanto (pra upar).
  const itens = estado.historico.filter(h =>
    estado.filtro === "todos" || (estado.filtro === "serve") === Boolean(h.serve || h.parcial));
  if (!itens.length) {
    trocar(lista, el("li", { class: "vazio-lista" },
      estado.historico.length
        ? t("Nenhum item neste filtro.")
        : t("Nada avaliado ainda. No jogo, passe o mouse num item e aperte o atalho.")));
    return;
  }
  trocar(lista, itens.map(h => registro(h, anterior)));
}

function registro(h, anterior) {
  const tipo = [h.qualidade, h.tipo].filter(Boolean).join(" ");
  const mini = el("div", { class: "miniatura", title: h.imagem || "" });
  if (h.imagem) pedirMiniatura(h.imagem, mini);
  const novo = anterior && h.quando > anterior;
  return el("li", { class: "registro" + (h.serve ? " serve" : h.parcial ? " parcial" : "") + (novo ? " novo" : "") },
    mini,
    el("div", {},
      el("p", { class: "registro-titulo" }, h.titulo),
      el("p", { class: "registro-tipo" },
        [tipo, h.com && t("avaliado com {build}", { build: h.com === "Todas" ? t("todas as builds") : h.com })]
          .filter(Boolean).join(" · ")),
      h.linhas.map(linha => el("p", { class: "registro-linha" },
        linha.map(([texto, estilo]) => el("span", { class: `t-${estilo}` }, texto)))),
    ),
    el("div", { class: "registro-hora" },
      hora(h.quando),
      el("br"),
      el("span", { class: "veredito" }, h.serve ? t("Serve") : h.parcial ? t("Por enquanto") : t("Não serve")),
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
    ? `${t("Overlay ativo")} · ${e.config.AUTOMATICO === "sim" ? t("automático + ") : ""}${e.config.ATALHO} · ${apelidoAtivo(e.config)}`
    : t("Overlay parado — veja Configurações");
  document.getElementById("log").textContent = e.log.join("\n") || t("(sem mensagens)");
}

async function carregarConfig() {
  const valores = await estado.api.config();
  const form = document.getElementById("form-config");
  for (const [chave, valor] of Object.entries(valores)) {
    const campo = form.elements[chave];
    if (!campo) continue;
    if (campo.type === "checkbox") campo.checked = valor === "sim";
    else campo.value = valor;
  }
  if (!form.elements.IDIOMA.value) form.elements.IDIOMA.value = window.Idioma.atual;
}

async function salvarConfig(evento) {
  evento.preventDefault();
  const form = evento.target;
  const mudancas = {
    ATALHO: form.elements.ATALHO.value,
    SELO_SEGUNDOS: form.elements.SELO_SEGUNDOS.value,
    AUTOMATICO: form.elements.AUTOMATICO.checked ? "sim" : "nao",
    IDIOMA: form.elements.IDIOMA.value,
  };
  const aviso = document.getElementById("aviso-config");
  aviso.textContent = "";
  const { erros } = await estado.api.salvar_config(mudancas);
  for (const chave of Object.keys(mudancas)) {
    form.elements[chave].classList.toggle("invalido", Boolean(erros[chave]));
    const aviso = form.querySelector(`[data-erro="${chave}"]`);
    if (aviso) aviso.textContent = erros[chave] || "";
  }
  if (!Object.keys(erros).length) {
    // Idioma novo: a janela recarrega pra sair toda no idioma escolhido.
    if (mudancas.IDIOMA !== window.Idioma.atual) { recarregarNoIdioma(mudancas.IDIOMA); return; }
    aviso.textContent = t("Salvo. Overlay reiniciado.");
    setTimeout(atualizarEstado, 1500);
  }
}

// ------------------------------------------------------------ início

async function iniciar(api) {
  estado.api = api;
  // Primeiro o idioma (das Configurações; sem escolha, o do Windows), depois o resto.
  const { IDIOMA } = await api.config();
  window.Idioma.escolher(IDIOMA);
  await window.Idioma.carregar(() => api.dados_do_jogo("en"));
  window.Idioma.trocar = async novo => {
    await api.salvar_config({ IDIOMA: novo });
    recarregarNoIdioma(novo);
  };
  window.Idioma.aplicar();
  window.Dicas.ligar(() => api.dados_do_jogo(emIngles() ? "dicas.en" : "dicas"));
  document.querySelectorAll(".aba").forEach(a => a.addEventListener("click", () => abrirAba(a.dataset.aba)));
  document.querySelectorAll(".filtro").forEach(f => f.addEventListener("click", () => {
    estado.filtro = f.dataset.filtro;
    document.querySelectorAll(".filtro").forEach(x => x.classList.toggle("ativo", x === f));
    desenharHistorico();  // trocar o filtro não faz nada "brilhar"
  }));
  document.getElementById("form-config").addEventListener("submit", salvarConfig);
  document.getElementById("form-importar").addEventListener("submit", buscarMaxroll);
  document.getElementById("fechar-importar").addEventListener("click", fecharImportar);
  document.getElementById("atualizar-guias").addEventListener("click", () => carregarGuias(true));
  document.getElementById("form-heroi").addEventListener("submit", buscarHerois);
  document.getElementById("reiniciar").addEventListener("click", async () => {
    await estado.api.reiniciar_overlay();
    setTimeout(atualizarEstado, 1500);
  });
  document.getElementById("apagar-prints").addEventListener("click", apagarPrints);
  document.getElementById("abrir-site").addEventListener("click", () => estado.api.abrir_site());
  document.getElementById("copiar-site").addEventListener("click", async () => {
    const aviso = document.getElementById("aviso-indicar");
    try { await navigator.clipboard.writeText(SITE_DO_APP); aviso.textContent = t("Link copiado!"); }
    catch { aviso.textContent = SITE_DO_APP; }
  });
  document.getElementById("filtro-guias").addEventListener("input", () => { if (estado.guias) desenharGuias(); });
  document.querySelectorAll("#painel-builds .sub-aba").forEach(s => s.addEventListener("click", () => abrirSubAba(s.dataset.sub)));

  try {
    abertura(15, t("Lendo as builds…"));
    estado.builds = await api.builds();
    desenharProblemas(await api.problemas_das_builds());
    abertura(45, t("Lendo as configurações…"));
    const { BUILD_ATIVA, BATTLETAG } = await api.config();
    document.getElementById("form-heroi").elements.battletag.value = BATTLETAG || "";
    const i = estado.builds.findIndex(b => b.id === BUILD_ATIVA);
    if (i >= 0) { estado.ativa = BUILD_ATIVA; estado.build = i; }
    estado.classe = (estado.builds[estado.build] && estado.builds[estado.build].classe) || "Demon Hunter";
    desenharBuilds();
    abertura(75, t("Ligando o overlay do jogo…"));
    await Promise.all([atualizarHistorico(), atualizarEstado()]);
    abertura(100, t("Pronto."));
    const tela = document.getElementById("abertura");
    setTimeout(() => tela.classList.add("saindo"), 250);
    setTimeout(() => { tela.hidden = true; }, 700);
  } catch (erro) {
    // Sem esconder a tela: diz o que houve pra pessoa poder mandar o erro.
    abertura(100, t("Não deu pra abrir: {erro}", { erro: erro && erro.message ? erro.message : erro }), true);
    return;
  }
  conferirAtualizacao();  // sem await: o GitHub pode demorar, o app já está pronto
  // O overlay é outro processo: de tempos em tempos, vê se chegou item novo.
  setInterval(atualizarHistorico, 1500);
  setInterval(atualizarEstado, 3000);
}

// Versão nova no GitHub: mostra a faixa. "Atualizar agora" baixa e instala (o app
// fecha e abre de novo); no zip ou do código, abre a página da versão.
async function conferirAtualizacao() {
  const nova = await estado.api.atualizacao();
  if (!nova || !nova.versao) return;
  const faixa = document.getElementById("atualizacao");
  const texto = document.getElementById("atualizacao-texto");
  const botao = document.getElementById("atualizar-agora");
  texto.textContent = t("Versão {nova} disponível (você tem a {atual}).", { nova: nova.versao, atual: nova.atual });
  if (!nova.sozinho) botao.textContent = t("Baixar");
  document.getElementById("ver-novidades").onclick = () => estado.api.ver_novidades();
  botao.onclick = async () => {
    botao.disabled = true;
    const vigia = nova.sozinho && setInterval(async () => {
      const p = await estado.api.progresso_da_atualizacao();
      texto.textContent = t("Baixando a versão {nova}… {pct}%", { nova: nova.versao, pct: Math.floor(p * 100) });
    }, 500);
    const r = await estado.api.atualizar();
    clearInterval(vigia);
    if (r.erro) { texto.textContent = r.erro; botao.disabled = false; return; }
    if (r.instalando) texto.textContent = t("Instalando… o app fecha e abre de novo sozinho.");
    else botao.disabled = false;
  };
  faixa.hidden = false;
}

// No app o idioma fica no .env; o navegador guarda também, só pro modo de exemplo.
function recarregarNoIdioma(novo) {
  try { localStorage.setItem("d3c-idioma", novo); } catch { /* sem: o .env basta */ }
  location.reload();
}

// Barra da tela de abertura (0 a 100).
function abertura(pct, texto, erro = false) {
  document.getElementById("abertura-progresso").style.width = `${pct}%`;
  const caixa = document.getElementById("abertura-texto");
  caixa.textContent = texto;
  caixa.classList.toggle("erro", erro);
}

function abrirSubAba(nome) {
  document.querySelectorAll("#painel-builds .sub-aba").forEach(s => s.classList.toggle("ativa", s.dataset.sub === nome));
  document.querySelectorAll("#painel-builds .sub-painel").forEach(p => p.classList.toggle("ativo", p.id === `sub-${nome}`));
  // O detalhe do lado é do equipamento e das habilidades: no resto só atrapalha.
  document.querySelector("#painel-builds .builds-grade").classList.toggle("sem-detalhe", !["equipamento", "habilidades"].includes(nome));
  // Nas habilidades o detalhe mostra uma habilidade (a 1ª, se nenhuma foi clicada); no equipamento, o espaço.
  const build = estado.builds[estado.build];
  if (!build) return;
  if (nome === "habilidades" && !estado.habilidade) estado.habilidade = { tipo: "ativas", i: 0 };
  if (nome === "equipamento") estado.habilidade = null;
  desenharHabilidades();
  desenharDetalhe();
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
    return { id: apelido.toLowerCase(), nome, apelido, classe: "Demon Hunter", exige_ancient: ancient,
             gerais: { obrigatorios: ["Destreza"], desejaveis: ["Vitalidade"] }, espacos, gemas };
  };
  const critico = afixo("Encaixe", "Crítico", "Dano crítico");
  // ?vazio na URL: app recém-instalado, sem nenhuma build.
  const builds = location.search.includes("vazio") ? [] : [
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
    Object.assign(build("Unhallowed Essence — Multidisparo", "Unhallowed", {
      Head: esp(["Accursed Visage"], ["Encaixe", "Crítico"]),
      Torso: esp(["Cage of the Hellborn"], ["Encaixe"]),
      Hands: esp(["Fiendish Grips"], ["Crítico", "Dano crítico"]),
      Finger: esp(["Focus", "Restraint"], critico),
      Weapon: esp(["Yang's Recurve"], ["Dano da arma", "Encaixe"]),
    }, ["Bane of the Trapped", "Zei's Stone of Vengeance"]), {
      fonte: { site: "maxroll", perfil: "Sanc: Solo Push Odyssey", link: "https://maxroll.gg/d3/planner/345357607",
               guia: "https://maxroll.gg/d3/guides/ue-multishot-demon-hunter-guide" },
      cubo: { arma: "Odyssey's End", armadura: "Mantle of Channeling", joia: "Ring of Royal Grandeur" },
      paragon: { nivel: 5000, pontos: [[3950, 400, 50, 0], [50, 50, 50, 50], [50, 50, 50, 50], [50, 50, 50, 50]] },
      seguidor: { quem: "templar", habilidades: ["heal", "loyalty", "onslaught", "guardian"],
                  itens: { Head: "Leoric's Crown", FingerL: "Unity", Weapon: "Thunderfury, Blessed Blade of the Windseeker",
                           Relic: "Enchanting Favor" } },
      habilidades: {
        ativas: ["entangling-shot", "multishot", "strafe", "preparation", "smoke-screen", "vengeance"]
          .map(habilidade => ({ habilidade, runa: "a" })),
        passivas: ["cull-the-weak", "ambush", "tactical-advantage", "steady-aim"],
      },
    }),
    build("Legacy of Nightmares", "LoN", {
      Head: esp([], ["Encaixe", "Crítico"], true),
      Finger: esp(["Litany of the Undaunted", "The Wailing Host"], critico, false),
    }, ["Bane of the Trapped"], true),
  ];
  const agora = Date.now();
  const quando = min => new Date(agora - min * 60000).toISOString().slice(0, 19);
  // O app grava o selo já no idioma da hora; o exemplo monta na hora de mostrar.
  const historico = () => {
    const pede = t("A build pede: {itens}", { itens: "Gas Powered Automail Forearm" });
    const gema = [" · " + t("Gema da build"), "normal"];
    return [
      { quando: quando(1), com: "Dreadlands", titulo: "Antique Vintage Boots", qualidade: "Set", tipo: "Boots", serve: true,
        linhas: [[["✅ ", "normal"], ["Dreadlands", "build"], [" · ", "normal"], [t("Destreza") + " ✓", "ok"], ["  ", "normal"],
                  [t("Vitalidade") + " ✓", "ok"]]] },
      { quando: quando(2), com: "Dreadlands", titulo: "Rare Gloves", qualidade: "Rare", tipo: "Gloves", serve: false, parcial: true,
        linhas: [[[t("🟡 Por enquanto") + " · ", "normal"], ["Dreadlands", "build"], [" · ", "normal"], [t("Destreza") + " ✓", "ok"],
                  ["  ", "normal"], [t("Vitalidade") + " ✓", "ok"], ["  ", "normal"], [t("Crítico") + " ✓", "ok"], ["  ", "normal"],
                  [t("Dano crítico") + " ✗", "falta"]],
                 [[pede, "motivo"]]] },
      { quando: quando(3), titulo: "Cain's Scrivener", qualidade: "Set", tipo: "Gloves", serve: false,
        linhas: [[[t("❌ Não serve"), "build"]], [["Dreadlands: " + pede, "motivo"]]] },
      { quando: quando(6), titulo: "Zei's Stone of Vengeance", qualidade: "Legendary", tipo: "Gem", serve: true,
        linhas: [[["✅ ", "normal"], ["Dreadlands", "build"], gema], [["✅ ", "normal"], ["LoN", "build"], gema]] },
    ];
  };
  let config = { ATALHO: "F8", SELO_SEGUNDOS: "6", BUILD_ATIVA: "", AUTOMATICO: "sim", BATTLETAG: "", IDIOMA: "" };
  const fichaDe = (build, id) => ({
    ...build, id,
    gerais: { obrigatorios: ["Destreza"], desejaveis: [] },
    espacos: Object.fromEntries(Object.keys(ESPACOS).map(k => {
      const e = (build.espacos || {})[k] || {};
      return [k, { definido: k in (build.espacos || {}), itens: e.itens || [], obrigatorios: ["Destreza"],
                   desejaveis: (e.desejaveis || []).map(r => r.rotulo), exige_ancient: !!e.exige_ancient }];
    })),
  });
  const montadas = {};
  return {
    dados_do_jogo: async qual => (await fetch(`dados/${qual}.json`)).json(),
    salvar_montada: async (build, id) => {
      id ||= `montada_${Object.keys(montadas).length + 1}`;
      montadas[id] = build;
      const i = builds.findIndex(b => b.id === id);
      if (i >= 0) builds[i] = fichaDe(build, id); else builds.push(fichaDe(build, id));
      return { id };
    },
    build_para_montar: async id => {
      const b = builds.find(x => x.id === id);
      return { build: montadas[id] || { ...b, espacos: Object.fromEntries(Object.entries(b.espacos).filter(([, e]) => e.definido)
        .map(([k, e]) => [k, { itens: e.itens }])) }, pode_alterar: id in montadas };
    },
    abrir_site: async () => window.open(SITE_DO_APP, "_blank", "noopener"),
    builds: async () => builds,
    // ?problema na URL simula uma build com erro, pra ver o aviso.
    problemas_das_builds: async () => location.search.includes("problema")
      ? { "minha_build.json": ["Espaço 'Hand' não existe. Quis dizer 'Hands'? Opções: Head, Shoulders, …"] }
      : {},
    historico: async () => historico(),
    miniatura: async () => null,
    config: async () => config,
    salvar_config: async m => {
      const erros = {};
      if (m.ATALHO !== undefined && !/^((ctrl|alt|shift|win)\+)*(f([1-9]|1[0-9]|2[0-4])|[a-z0-9]|insert|pause)$/i.test(m.ATALHO.replace(/\s/g, "")))
        erros.ATALHO = `Atalho inválido: '${m.ATALHO}'. Exemplos: F8, Ctrl+F8, Alt+Q.`;
      const s = parseFloat(String(m.SELO_SEGUNDOS || "6").replace(",", "."));
      if (!(s >= 1 && s <= 60)) erros.SELO_SEGUNDOS = "Tempo do selo precisa ficar entre 1 e 60 segundos.";
      if (m.IDIOMA !== undefined && !["en", "pt"].includes(m.IDIOMA)) erros.IDIOMA = "Idioma precisa ser \"en\" ou \"pt\".";
      if (!Object.keys(erros).length) config = { ...config, ...m };
      return { erros };
    },
    estado: async () => ({ rodando: true, config, log: ["(modo de exemplo: aberto fora do app)"] }),
    reiniciar_overlay: async () => ({}),
    atualizacao: async () => ({}),  // o site de exemplo não se atualiza
    capturas: async () => ({ imagens: 36, bytes: 5.4 * 1024 * 1024 }),
    apagar_capturas: async () => ({ imagens: 0, bytes: 0 }),
    remover_build: async id => {
      const i = builds.findIndex(b => b.id === id);
      if (i < 0) return { erro: "Essa build não está mais na pasta." };
      builds.splice(i, 1);
      if (config.BUILD_ATIVA === id) config = { ...config, BUILD_ATIVA: "" };
      return { ok: true };
    },
    escolher_build: async id => { config = { ...config, BUILD_ATIVA: id }; return { erros: {} }; },
    visual: async id => visualDeExemplo(builds.find(b => b.id === id)),
    abrir_link: async url => { window.open(url, "_blank"); },
    herois: async tag => /#\d{3,6}$/.test(tag)
      ? { herois: [{ id: 1, regiao: "us", nome: "Caçadora", classe: "Demon Hunter", nivel: 70, paragon: 1520, temporada: true },
                   { id: 2, regiao: "us", nome: "Bruxo", classe: "Witch Doctor", nivel: 43, paragon: 1520, temporada: true }] }
      : { erro: "Escreva a BattleTag com o número, ex.: Jogador#1234 (aparece no canto do app da Battle.net)." },
    comparar_heroi: async () => {
      const I = "https://blzmedia-a.akamaihd.net/d3/icons/items/large/";
      return {
        heroi: { nome: "Caçadora", classe: "Demon Hunter", nivel: 70, paragon: 1520, atualizado: Date.now() / 1000 - 3600 },
        classe_igual: true,
        itens: [
          { espaco: "Head", nome: "Accursed Visage", icone: I + "unique_helm_set_03_p2_demonhunter_male.png", veredito: "serve",
            motivo: "Item da build", tem: ["Destreza", "Vitalidade", "Encaixe"], falta: ["Crítico"],
            dica: 'Dica: no Místico, troque "+12% Life" por Crítico.' },
          { espaco: "Hands", nome: "Cain's Scrivener", icone: null, veredito: "parcial", motivo: "A build pede: Fiendish Grips",
            tem: ["Destreza", "Vitalidade", "Crítico"], falta: ["Dano crítico"], dica: null, encantado: "+700 Vitality" },
          { espaco: "Weapon", nome: "Dead Man's Legacy", icone: null, veredito: "nao", motivo: "A build pede: Yang's Recurve", tem: [], falta: [] },
        ],
        habilidades: {
          ativas: [{ nome: "Tiro Múltiplo", runa_nome: "Bombardeio", estado: "ok" },
                   { nome: "Metralhar", runa_nome: "Drifting Shadow", estado: "runa", runa_do_heroi_nome: "Emaranhado" },
                   { nome: "Vingança", runa_nome: "Coração Negro", estado: "falta" }],
          passivas: [{ nome: "Emboscada", estado: "ok" }, { nome: "Mira Firme", estado: "falta" }],
          fora_da_build: ["Companheiro"],
        },
      };
    },
    guias: async () => ({ guias: [
      ["shadow-impale-demon-hunter", "Shadow Impale", "Demon Hunter"],
      ["ue-multishot-demon-hunter", "UE Multishot", "Demon Hunter"],
      ["god-ha-demon-hunter", "GoD HA", "Demon Hunter"],
      ["lod-meteor-wizard", "LoD Meteor", "Wizard"],
      ["ik-hota-barbarian", "IK HotA", "Barbarian"],
    ].map(([s, titulo, classe]) => ({ link: `https://maxroll.gg/d3/guides/${s}-guide`, titulo, classe })) }),
    buscar_maxroll: async texto => /maxroll\.gg\/d3\/(guides|planner)\//.test(texto)
      ? { builds: [
          { numero: 236100095, nome: "Sanc Shadow Impale", classe: "Demon Hunter", perfil: 0,
            perfis: ["Sanc: Solo Push", "Sanc: Speeds Lightning", "Sanc: Group Speeds", "Sanc: RGK"] },
          { numero: 112481789, nome: "Impale Core (mXr)", classe: "Demon Hunter", perfil: 0,
            perfis: ["Core Setup", "4th Cube"] },
        ] }
      : { erro: "Não achei a build no link. Cole o link de um guia de D3 do Maxroll (maxroll.gg/d3/guides/...) ou do planejador (maxroll.gg/d3/planner/...)." },
    importar_maxroll: async (numero, perfil, apelido) => {
      const nova = { ...builds[1], id: `importada_${numero}`, apelido: apelido || "Importada",
                     nome: `Importada — perfil ${perfil + 1}` };
      builds.push(nova);
      return { id: nova.id };
    },
  };
}

// Ícones de verdade (endereços da Blizzard) pra ver o visual fora do app.
function visualDeExemplo(build) {
  const ICONES = "https://blzmedia-a.akamaihd.net/d3/icons";
  const itemIcone = {
    "Accursed Visage": "unique_helm_set_03_p2_demonhunter_male", "Cage of the Hellborn": "unique_chest_set_03_p2_demonhunter_male",
    "Fiendish Grips": "unique_gloves_set_03_p2_demonhunter_male", "Focus": "unique_ring_set_001_x1_demonhunter_male",
    "Restraint": "unique_ring_set_002_x1_demonhunter_male", "Yang's Recurve": "p61_unique_bow_104_x1_demonhunter_male",
    "Zei's Stone of Vengeance": "unique_gem_012_x1_demonhunter_male",
    "Bane of the Trapped": "unique_gem_002_x1_demonhunter_male",
    "Odyssey's End": "p69_unique_bow_102_demonhunter_male",
    "Mantle of Channeling": "p4_unique_shoulder_103_demonhunter_male",
    "Ring of Royal Grandeur": "unique_ring_107_x1_demonhunter_male",
  };
  const itens = Object.fromEntries(Object.entries(itemIcone).map(([nome, i]) =>
    [nome, { nome, icone: `${ICONES}/items/large/${i}.png` }]));
  const pt = {
    "entangling-shot": "Tiro Enredante", multishot: "Tiro Múltiplo", strafe: "Metralhar", preparation: "Preparação",
    "smoke-screen": "Cortina de Fumaça", vengeance: "Vingança", "cull-the-weak": "Abater os Fracos",
    ambush: "Emboscada", "tactical-advantage": "Vantagem Tática", "steady-aim": "Mira Firme",
  };
  const comX1 = ["entangling-shot", "vengeance", "ambush"];  // ícones da expansão têm "x1_"
  const niveis = { "entangling-shot": 1, multishot: 26, strafe: 14, preparation: 17, "smoke-screen": 21, vengeance: 61,
                   "cull-the-weak": 10, ambush: 64, "tactical-advantage": 16, "steady-aim": 10 };
  const habilidade = (slug, passiva) => ({
    slug, nome: slug, nome_pt: pt[slug] || slug, nivel: niveis[slug] || 1,
    icone: `${ICONES}/skills/64/${comX1.includes(slug) ? "x1_" : ""}demonhunter_${passiva ? "passive_" : ""}${slug.replace(/-/g, "")}.png`,
    descricao_pt: "Descrição de exemplo (no app vem da Blizzard, em português).",
  });
  const h = build.habilidades || { ativas: [], passivas: [] };
  return {
    itens,
    habilidades: {
      ativas: h.ativas.map(a => ({ ...habilidade(a.habilidade), runa: { letra: "a", nome: "Rune", nome_pt: "Runa de exemplo", descricao_pt: "O que a runa muda.", nivel: 30 } })),
      passivas: h.passivas.map(p => habilidade(p, true)),
    },
    seguidor: build.seguidor ? { nome: "Templar", nome_pt: "Templário", habilidades: [
      ["Cura", 5, "templar_heal_110"], ["Lealdade", 10, "templar_loyalty"],
      ["Investida", 15, "templar_onslaught_v2"], ["Guardião", 20, "templar_cheatdeath_passive"],
    ].map(([nome_pt, nivel, i]) => ({ nome_pt, nome: nome_pt, nivel, icone: `${ICONES}/skills/64/${i}.png`,
                                     descricao_pt: "Descrição de exemplo (no app vem da Blizzard, em português)." })) } : null,
  };
}
