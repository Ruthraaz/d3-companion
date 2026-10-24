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
  build: 0,          // índice da build mostrada no boneco
  ativa: "",         // id da build que o atalho usa ("" = todas); fica no .env (BUILD_ATIVA)
  espaco: "Head",    // espaço aberto no painel de detalhe
  habilidade: null,  // {tipo: "ativas"|"passivas", i}: habilidade aberta no detalhe (no lugar do espaço)
  visual: {},        // id da build -> ícones e textos da Blizzard ("carregando" enquanto busca)
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

// Build com JSON errado fica de fora do app; aqui a pessoa vê o que corrigir.
function desenharProblemas(problemas) {
  const caixa = document.getElementById("problemas");
  const arquivos = Object.keys(problemas);
  caixa.hidden = !arquivos.length;
  trocar(caixa, arquivos.length && [
    el("p", { class: "problemas-titulo" },
      `${arquivos.length === 1 ? "Uma build ficou" : `${arquivos.length} builds ficaram`} de fora por erro no arquivo:`),
    arquivos.map(arquivo => el("div", { class: "problema" },
      el("code", {}, `builds/${arquivo}`),
      el("ul", {}, problemas[arquivo].map(p => el("li", {}, p))))),
    el("p", { class: "mudo" }, "Corrija o arquivo e abra o app de novo. Pra conferir antes: ",
      el("code", {}, "python src/avaliador.py --conferir")),
  ]);
}

function desenharBuilds() {
  const caixa = document.getElementById("escolha-build");
  if (!estado.builds.length) {
    trocar(caixa,
      el("p", { class: "mudo" }, "Nenhuma build ainda."),
      el("button", { class: "chip-build chip-importar", onclick: () => abrirImportar() },
        el("span", { class: "chip-apelido" }, "+ Importar"), el("span", { class: "chip-nome" }, "do Maxroll")));
    return;
  }
  // Clicar numa build = o F8 passa a avaliar só com ela. "Todas" = com todas.
  // Com "Todas", o boneco continua mostrando a última build olhada (contorno fino).
  const todas = estado.ativa === "";
  trocar(caixa,
    el("button", {
      class: "chip-build chip-todas" + (todas ? " ativo" : ""),
      title: "O atalho avalia o item com todas as builds",
      onclick: () => escolherBuild(""),
    },
      el("span", { class: "chip-apelido" }, "Todas"),
      el("span", { class: "chip-nome" }, `${estado.builds.length} builds`),
    ),
    estado.builds.map((b, i) =>
      el("button", {
        class: "chip-build" + (b.id === estado.ativa ? " ativo" : "") + (todas && i === estado.build ? " vendo" : ""),
        title: `O atalho avalia o item só com ${b.apelido}`,
        onclick: () => { estado.build = i; escolherBuild(b.id); },
      },
        el("span", { class: "chip-apelido" }, b.apelido),
        el("span", { class: "chip-nome" }, b.nome),
      )),
  );
  caixa.append(el("button", {
    class: "chip-build chip-importar",
    title: "Trazer uma build pronta de um guia do Maxroll",
    onclick: () => abrirImportar(),
  }, el("span", { class: "chip-apelido" }, "+ Importar"), el("span", { class: "chip-nome" }, "do Maxroll")));
  const com = todas ? "todas as builds" : estado.builds[estado.build].apelido;
  const fonte = estado.builds[estado.build].fonte;
  trocar(document.getElementById("avaliando"),
    "O atalho avalia o item com ", el("strong", {}, com), ".",
    fonte && fonte.link && el("span", { class: "fonte" },
      ` Fonte: ${fonte.site === "maxroll" ? "Maxroll" : fonte.site}`,
      fonte.perfil && ` · ${fonte.perfil}`, " ",
      el("button", { class: "link", type: "button", onclick: () => estado.api.abrir_link(fonte.link) },
        "abrir no navegador")));
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
  aviso.textContent = v.erro ? `Sem ícones da Blizzard: ${v.erro}` : "";
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
  return v && v !== "carregando" ? v : { itens: {}, habilidades: { ativas: [], passivas: [] }, carregando: v === "carregando" };
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
  return b ? b.apelido : "todas as builds";
}

// Os itens que aparecem num lugar do boneco. Com dois anéis na build (ex.:
// Focus e Restraint), cada mão mostra um; senão, as duas mostram a lista.
function itensDoLugar(espaco, area) {
  if (area.startsWith("Finger") && espaco.itens.length === 2) {
    return [espaco.itens[area === "FingerL" ? 0 : 1]];
  }
  return espaco.itens;
}

function desenharBoneco() {
  const build = estado.builds[estado.build];
  trocar(document.getElementById("boneco"), BONECO.map(([chave, area]) => {
    const espaco = build.espacos[chave];
    const itens = itensDoLugar(espaco, area);
    const classe = !espaco.definido ? "geral" : itens.length ? "com-item" : "livre";
    const item = itens.length ? itens.join(" ou ") : "Qualquer item";
    const n = espaco.obrigatorios.length + espaco.desejaveis.length;
    const afixos = n ? `${n} afixo${n > 1 ? "s" : ""}` : "";
    const selecionado = chave === estado.espaco && !estado.habilidade;
    return el("button", {
      class: `espaco ${classe}` + (selecionado ? " selecionado" : ""),
      style: `grid-area: ${area}`,
      title: espaco.definido ? item : "A build não fala deste espaço: valem só as regras gerais",
      onclick: () => { estado.espaco = chave; estado.habilidade = null; desenharVisual(); },
    },
      icone(itens.length ? iconeDoItem(itens[0]) : null, "icone-item"),
      el("span", { class: "espaco-texto" },
        el("span", { class: "espaco-nome" }, ESPACOS[chave] || chave),
        el("span", { class: "espaco-item" }, item),
        afixos && el("span", { class: "espaco-afixos" }, afixos),
      ),
      espaco.exige_ancient && el("span", { class: "selo-ancient", title: "Precisa ser Ancient" }, "ANC"),
    );
  }));
}

const PARTES_DO_CUBO = { arma: "Arma", armadura: "Armadura", joia: "Joia" };

function desenharExtras() {
  const build = estado.builds[estado.build];
  const cubo = build.cubo || {};
  trocar(document.getElementById("cubo"), Object.keys(cubo).length
    ? Object.entries(PARTES_DO_CUBO).filter(([parte]) => cubo[parte]).map(([parte, rotulo]) =>
        el("div", { class: "mini-item", title: `${rotulo}: ${cubo[parte]}` },
          icone(iconeDoItem(cubo[parte]), "icone-mini"),
          el("span", {}, el("span", { class: "mini-rotulo" }, rotulo), cubo[parte])))
    : el("p", { class: "nada" }, "A build não diz."));
  trocar(document.getElementById("gemas"), build.gemas.length
    ? build.gemas.map(g => el("div", { class: "mini-item", title: g },
        icone(iconeDoItem(g), "icone-mini"), el("span", { class: "t-lendario" }, g)))
    : el("p", { class: "nada" }, "A build não diz."));
}

// Tecla de cada lugar da barra, na ordem em que o Maxroll guarda as habilidades
// (botão esquerdo e direito do mouse, depois 1 a 4).
const TECLAS = ["Esq.", "Dir.", "1", "2", "3", "4"];

function desenharHabilidades() {
  const build = estado.builds[estado.build];
  const v = visualDa(build);
  const escolhidas = build.habilidades || { ativas: [], passivas: [] };
  const vazio = !escolhidas.ativas.length && !escolhidas.passivas.length;
  const botao = (tipo, i, h, rotulo) => el("button", {
    class: "habilidade" + (h ? "" : " vazia")
      + (estado.habilidade && estado.habilidade.tipo === tipo && estado.habilidade.i === i ? " selecionado" : ""),
    ...(h ? {} : { disabled: "" }),  // el() grava qualquer valor; só põe quando vazio
    title: h ? h.nome_pt : "",
    onclick: () => { estado.habilidade = { tipo, i }; desenharVisual(); },
  },
    icone(h && h.icone, tipo === "passivas" ? "icone-passiva" : "icone-habilidade"),
    rotulo && el("span", { class: "tecla" }, rotulo),
    el("span", { class: "habilidade-nome" }, h ? h.nome_pt : ""),
    h && h.runa && el("span", { class: "habilidade-runa" }, h.runa.nome_pt),
  );

  // Enquanto a Blizzard não respondeu, mostra o código da build (sem ícone).
  const daBuild = (tipo, i) => {
    if (v.habilidades[tipo][i]) return v.habilidades[tipo][i];
    const cru = escolhidas[tipo][i];
    if (!cru) return null;
    const slug = typeof cru === "string" ? cru : cru.habilidade;
    return { slug, nome: slug, nome_pt: slug, icone: null, descricao_pt: "", runa: null };
  };
  const ativas = document.getElementById("barra-ativas");
  const passivas = document.getElementById("barra-passivas");
  if (vazio) {
    trocar(ativas, el("p", { class: "nada" },
      "Esta build ainda não tem habilidades. Elas vêm junto quando a build é importada do Maxroll."));
    trocar(passivas);
    return;
  }
  trocar(ativas, TECLAS.map((tecla, i) => botao("ativas", i, daBuild("ativas", i), tecla)));
  trocar(passivas, [0, 1, 2, 3].map(i => botao("passivas", i, daBuild("passivas", i), null)));
}

function etiquetas(lista, classe) {
  if (!lista.length) return el("p", { class: "nada" }, "Nenhum.");
  return el("ul", {}, lista.map(t => el("li", { class: `etiqueta ${classe}` }, t)));
}

function desenharDetalhe() {
  if (estado.habilidade) return desenharDetalheDaHabilidade();
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

function desenharDetalheDaHabilidade() {
  const { tipo, i } = estado.habilidade;
  const v = visualDa(estado.builds[estado.build]);
  const h = v.habilidades[tipo][i];
  const caixa = document.getElementById("detalhe");
  if (!h) {
    trocar(caixa, el("p", { class: "mudo" }, v.carregando ? "Buscando na Blizzard…" : "Sem dados desta habilidade."));
    return;
  }
  trocar(caixa,
    el("div", { class: "detalhe-slot" },
      tipo === "passivas" ? "Passiva" : `Habilidade · tecla ${TECLAS[i]}`),
    el("div", { class: "detalhe-cabeca" },
      icone(h.icone, tipo === "passivas" ? "icone-passiva icone-grande" : "icone-habilidade icone-grande"),
      el("div", {},
        el("p", { class: "detalhe-titulo livre" }, h.nome_pt),
        h.nome !== h.nome_pt && el("p", { class: "mudo nome-ingles" }, `No jogo em inglês: ${h.nome}`))),
    h.descricao_pt && el("p", { class: "descricao" }, h.descricao_pt),
    h.runa && [
      el("h3", {}, "Runa"),
      el("p", { class: "runa-nome" }, h.runa.nome_pt,
        h.runa.nome !== h.runa.nome_pt && el("span", { class: "mudo" }, ` (${h.runa.nome})`)),
      el("p", { class: "descricao" }, h.runa.descricao_pt),
    ],
    tipo === "ativas" && !h.runa && el("p", { class: "mudo" }, "A build não diz qual runa."),
    el("p", { class: "nota" }, "Textos e ícones da API oficial da Blizzard."),
  );
}

function blocoGemas(build) {
  return [el("h3", {}, "Gemas lendárias"), etiquetas(build.gemas, "gema")];
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
  const texto = evento.target.elements.link.value.trim();
  const status = document.getElementById("importar-status");
  const opcoes = document.getElementById("importar-opcoes");
  if (!texto) { status.textContent = "Cole um link primeiro."; return; }
  trocar(opcoes);
  status.className = "importar-status";
  status.textContent = "Buscando no Maxroll…";
  const r = await estado.api.buscar_maxroll(texto);
  if (r.erro) {
    status.className = "importar-status erro";
    status.textContent = r.erro;
    return;
  }
  status.textContent = r.builds.length > 1
    ? `Esse link tem ${r.builds.length} builds. Escolha uma e o perfil (cada perfil é uma variação da build).`
    : "Escolha o perfil (cada perfil é uma variação da build).";
  desenharOpcoesDeImportar(r.builds, 0);
}

function desenharOpcoesDeImportar(builds, escolhida) {
  const b = builds[escolhida];
  const perfil = el("select", { name: "perfil" },
    b.perfis.map((nome, i) => el("option", { value: String(i), ...(i === b.perfil ? { selected: "" } : {}) },
      `${i + 1}. ${nome}`)));
  const apelido = el("input", { name: "apelido", value: b.nome, autocomplete: "off", maxlength: "40" });
  const botao = el("button", { type: "button", class: "botao" }, "Importar");
  botao.addEventListener("click", () => importarMaxroll(b, Number(perfil.value), apelido.value, botao));

  trocar(document.getElementById("importar-opcoes"),
    builds.length > 1 && el("div", { class: "opcoes-builds" }, builds.map((x, i) =>
      el("button", {
        type: "button",
        class: "opcao-build" + (i === escolhida ? " ativo" : ""),
        onclick: () => desenharOpcoesDeImportar(builds, i),
      },
        el("span", { class: "chip-apelido" }, x.nome),
        el("span", { class: "chip-nome" }, `${x.classe} · ${x.perfis.length} perfis`)))),
    el("div", { class: "importar-campos" },
      el("label", { class: "campo" }, el("span", { class: "campo-nome" }, "Perfil"), perfil),
      el("label", { class: "campo" }, el("span", { class: "campo-nome" }, "Nome curto na janela e no selo"), apelido),
      botao),
  );
}

async function importarMaxroll(b, perfil, apelido, botao) {
  const status = document.getElementById("importar-status");
  botao.disabled = true;
  status.className = "importar-status";
  status.textContent = "Importando…";
  const r = await estado.api.importar_maxroll(b.numero, perfil, apelido);
  botao.disabled = false;
  if (r.erro) {
    status.className = "importar-status erro";
    status.textContent = r.erro;
    return;
  }
  // A build nova entra na lista; o overlay só lê builds/ ao abrir, então reinicia.
  estado.builds = await estado.api.builds();
  estado.build = Math.max(0, estado.builds.findIndex(x => x.id === r.id));
  estado.habilidade = null;
  fecharImportar();
  desenharBuilds();
  estado.api.reiniciar_overlay();
  setTimeout(atualizarEstado, 1500);
  trocar(document.getElementById("avaliando"),
    el("strong", { class: "t-ok" }, `Build importada: ${estado.builds[estado.build].apelido}. `),
    "Clique nela pro atalho avaliar só com ela. O arquivo ficou em ",
    el("code", {}, `builds/${r.id}.json`), ".");
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
      el("p", { class: "registro-tipo" },
        [tipo, h.com && `avaliado com ${h.com === "Todas" ? "todas as builds" : h.com}`]
          .filter(Boolean).join(" · ")),
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
    ? `Overlay ativo · ${e.config.AUTOMATICO === "sim" ? "automático + " : ""}${e.config.ATALHO} · ${apelidoAtivo(e.config)}`
    : "Overlay parado — veja Configurações";
  document.getElementById("log").textContent = e.log.join("\n") || "(sem mensagens)";
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
}

async function salvarConfig(evento) {
  evento.preventDefault();
  const form = evento.target;
  const mudancas = {
    ATALHO: form.elements.ATALHO.value,
    SELO_SEGUNDOS: form.elements.SELO_SEGUNDOS.value,
    AUTOMATICO: form.elements.AUTOMATICO.checked ? "sim" : "nao",
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
  document.getElementById("form-importar").addEventListener("submit", buscarMaxroll);
  document.getElementById("fechar-importar").addEventListener("click", fecharImportar);
  document.getElementById("reiniciar").addEventListener("click", async () => {
    await estado.api.reiniciar_overlay();
    setTimeout(atualizarEstado, 1500);
  });

  estado.builds = await api.builds();
  desenharProblemas(await api.problemas_das_builds());
  const { BUILD_ATIVA } = await api.config();
  const i = estado.builds.findIndex(b => b.id === BUILD_ATIVA);
  if (i >= 0) { estado.ativa = BUILD_ATIVA; estado.build = i; }
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
    return { id: apelido.toLowerCase(), nome, apelido, classe: "Demon Hunter", exige_ancient: ancient,
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
    Object.assign(build("Unhallowed Essence — Multidisparo", "Unhallowed", {
      Head: esp(["Accursed Visage"], ["Encaixe", "Crítico"]),
      Torso: esp(["Cage of the Hellborn"], ["Encaixe"]),
      Hands: esp(["Fiendish Grips"], ["Crítico", "Dano crítico"]),
      Finger: esp(["Focus", "Restraint"], critico),
      Weapon: esp(["Yang's Recurve"], ["Dano da arma", "Encaixe"]),
    }, ["Bane of the Trapped", "Zei's Stone of Vengeance"]), {
      fonte: { site: "maxroll", perfil: "Sanc: Solo Push Odyssey", link: "https://maxroll.gg/d3/planner/345357607" },
      cubo: { arma: "Odyssey's End", armadura: "Mantle of Channeling", joia: "Ring of Royal Grandeur" },
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
  const historico = [
    { quando: quando(1), com: "Dreadlands", titulo: "Antique Vintage Boots", qualidade: "Set", tipo: "Boots", serve: true,
      linhas: [[["✅ ", "normal"], ["Dreadlands", "build"], [" · ", "normal"], ["Destreza ✓", "ok"], ["  ", "normal"], ["Vitalidade ✓", "ok"]]] },
    { quando: quando(3), titulo: "Cain's Scrivener", qualidade: "Set", tipo: "Gloves", serve: false,
      linhas: [[["❌ Não serve", "build"]], [["Dreadlands: A build pede: Gas Powered Automail Forearm", "motivo"]]] },
    { quando: quando(6), titulo: "Zei's Stone of Vengeance", qualidade: "Legendary", tipo: "Gem", serve: true,
      linhas: [[["✅ ", "normal"], ["Dreadlands", "build"], [" · Gema da build", "normal"]],
               [["✅ ", "normal"], ["LoN", "build"], [" · Gema da build", "normal"]]] },
  ];
  let config = { ATALHO: "F8", SELO_SEGUNDOS: "6", BUILD_ATIVA: "", AUTOMATICO: "sim" };
  return {
    builds: async () => builds,
    // ?problema na URL simula uma build com erro, pra ver o aviso.
    problemas_das_builds: async () => location.search.includes("problema")
      ? { "minha_build.json": ["Espaço 'Hand' não existe. Quis dizer 'Hands'? Opções: Head, Shoulders, …"] }
      : {},
    historico: async () => historico,
    miniatura: async () => null,
    config: async () => config,
    salvar_config: async m => {
      const erros = {};
      if (!/^((ctrl|alt|shift|win)\+)*(f([1-9]|1[0-9]|2[0-4])|[a-z0-9]|insert|pause)$/i.test(m.ATALHO.replace(/\s/g, "")))
        erros.ATALHO = `Atalho inválido: '${m.ATALHO}'. Exemplos: F8, Ctrl+F8, Alt+Q.`;
      const s = parseFloat(String(m.SELO_SEGUNDOS).replace(",", "."));
      if (!(s >= 1 && s <= 60)) erros.SELO_SEGUNDOS = "Tempo do selo precisa ficar entre 1 e 60 segundos.";
      if (!Object.keys(erros).length) config = { ...config, ...m };
      return { erros };
    },
    estado: async () => ({ rodando: true, config, log: ["(modo de exemplo: aberto fora do app)"] }),
    reiniciar_overlay: async () => ({}),
    escolher_build: async id => { config = { ...config, BUILD_ATIVA: id }; return { erros: {} }; },
    visual: async id => visualDeExemplo(builds.find(b => b.id === id)),
    abrir_link: async url => { window.open(url, "_blank"); },
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
  const habilidade = (slug, passiva) => ({
    slug, nome: slug, nome_pt: pt[slug] || slug,
    icone: `${ICONES}/skills/64/${comX1.includes(slug) ? "x1_" : ""}demonhunter_${passiva ? "passive_" : ""}${slug.replace(/-/g, "")}.png`,
    descricao_pt: "Descrição de exemplo (no app vem da Blizzard, em português).",
  });
  const h = build.habilidades || { ativas: [], passivas: [] };
  return {
    itens,
    habilidades: {
      ativas: h.ativas.map(a => ({ ...habilidade(a.habilidade), runa: { letra: "a", nome: "Rune", nome_pt: "Runa de exemplo", descricao_pt: "O que a runa muda." } })),
      passivas: h.passivas.map(p => habilidade(p, true)),
    },
  };
}
