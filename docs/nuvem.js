// D3 Companion — builds na nuvem (só no site, montar.html). Opcional: sem o
// config-nuvem.js preenchido, nada disto aparece e o montador segue sem conta.
//
// A conta é do Supabase, entrando com Discord ou Google (sem senha nossa). A
// biblioteca supabase-js vem do jsDelivr numa versão fixa, com SRI (o navegador
// confere o hash e recusa o arquivo se ele mudar), e só é baixada quando a
// pessoa clica em "Entrar" ou já está conectada: quem só monta não fala com ninguém.
//
// Na tabela vão só o id da conta e as builds (ferramentas/supabase.sql); o RLS
// de lá garante que cada um só vê, muda e apaga as próprias.

"use strict";

(() => {

const SUPABASE_JS = "https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2.117.3/dist/umd/supabase.js";
const SUPABASE_SRI = "sha384-BWcjm9OdFth9TbhCxZPdm+gAOUMAzQy9nmTs12ioXdCcbVnJaPMn+fMUoQCLt60R";
const MAXIMO_DE_BUILDS = 50;      // os dois iguais aos do supabase.sql
const MAXIMO_DA_BUILD = 50000;    // bytes do JSON da build
const PROVEDORES = { discord: "Discord", google: "Google" };
const ID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;

const t = (texto, vars) => (window.Idioma ? window.Idioma.t(texto, vars) : texto);
const emIngles = () => Boolean(window.Idioma) && window.Idioma.atual === "en";

// O endereço tem que ser de um projeto do Supabase e a chave, a pública
// ("publishable" ou o JWT "anon"). Qualquer outra coisa desliga a nuvem.
function configDaNuvem(c) {
  if (!c || typeof c.url !== "string" || typeof c.chave !== "string") return null;
  const url = c.url.trim().replace(/\/+$/, "");
  const chave = c.chave.trim();
  if (!/^https:\/\/[a-z0-9-]+\.supabase\.co$/.test(url) || !chave) return null;
  if (/^sb_publishable_[\w-]+$/.test(chave)) return { url, chave };
  const partes = chave.split(".");
  if (partes.length !== 3) return null;
  try {
    const dados = JSON.parse(atob(partes[1].replace(/-/g, "+").replace(/_/g, "/")));
    return dados && dados.role === "anon" ? { url, chave } : null;
  } catch { return null; }
}

const config = configDaNuvem(window.D3C_NUVEM);
// Onde o supabase-js guarda a sessão neste navegador (o padrão dele).
const GUARDADO = config && `sb-${new URL(config.url).hostname.split(".")[0]}-auth-token`;

let raiz = null;
let cliente = null;
let carregando = null;
let sessao = null;
let minhas = null;        // null = "Minhas builds" fechada; senão a lista
let ocupado = false;
let aviso = { texto: "", erro: false };

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

function temSessaoGuardada() {
  try { return Boolean(localStorage.getItem(GUARDADO) || localStorage.getItem(`${GUARDADO}-code-verifier`)); } catch { return false; }
}
const voltouDoLogin = () => /[?&](code|error)=/.test(location.search);

function avisar(texto, erro = false) {
  aviso = { texto, erro };
  desenhar();
}

function mensagemDeErro(e) {
  const texto = String((e && e.message) || "");
  if (/Limite de 50/.test(texto)) return t("Você chegou ao limite de {n} builds na nuvem. Apague alguma em \"Minhas builds\".", { n: MAXIMO_DE_BUILDS });
  if (/JWT|session|token/i.test(texto)) return t("Sua sessão acabou. Entre de novo.");
  return t("A nuvem não respondeu. Tente de novo daqui a pouco.");
}

// Faz a tarefa com os botões travados; erro vira aviso.
async function fazer(tarefa) {
  if (ocupado) return;
  ocupado = true;
  desenhar();
  try { await tarefa(); } catch (e) { aviso = { texto: mensagemDeErro(e), erro: true }; }
  ocupado = false;
  desenhar();
}

// ------------------------------------------------------------ supabase-js (só quando precisa)

function carregarBiblioteca() {
  return (carregando ||= new Promise((pronto, falha) => {
    const s = document.createElement("script");
    s.src = SUPABASE_JS;
    s.integrity = SUPABASE_SRI;
    s.crossOrigin = "anonymous";
    s.referrerPolicy = "no-referrer";
    s.addEventListener("load", pronto);
    s.addEventListener("error", () => { carregando = null; falha(new Error("supabase-js")); });
    document.head.append(s);
  }).then(() => {
    cliente = window.supabase.createClient(config.url, config.chave, {
      auth: { flowType: "pkce", persistSession: true, autoRefreshToken: true, detectSessionInUrl: true },
    });
    cliente.auth.onAuthStateChange((evento, nova) => {
      sessao = nova;
      if (!nova) minhas = null;
      desenhar();
    });
    return cliente;
  }));
}

async function lerSessao() {
  const c = await carregarBiblioteca();
  const { data } = await c.auth.getSession();   // na volta do login, troca o ?code= pela sessão
  sessao = data.session;
}

// ------------------------------------------------------------ ações

async function entrar(provedor) {
  avisar(t("Abrindo o {provedor}…", { provedor: PROVEDORES[provedor] }));
  try {
    const c = await carregarBiblioteca();
    const { error } = await c.auth.signInWithOAuth({ provider: provedor, options: { redirectTo: location.origin + location.pathname } });
    if (error) throw error;
  } catch {
    avisar(t("Não consegui abrir o login. Tente de novo daqui a pouco."), true);
  }
}

const sair = () => fazer(async () => {
  await cliente.auth.signOut({ scope: "local" });   // só este navegador
  sessao = null;
  minhas = null;
  aviso = { texto: t("Você saiu. Suas builds continuam na nuvem."), erro: false };
});

const salvar = () => fazer(async () => {
  const { build, classe, nuvem } = window.Montador.paraNuvem();
  if (new Blob([JSON.stringify(build)]).size > MAXIMO_DA_BUILD) {
    aviso = { texto: t("Essa build é grande demais pra nuvem."), erro: true };
    return;
  }
  const linha = { nome: build.apelido.slice(0, 60), classe, dados: build };
  let id = "";
  if (ID.test(nuvem)) {   // já está na nuvem: grava em cima (se ainda existir)
    const { data, error } = await cliente.from("builds").update(linha).eq("id", nuvem).select("id");
    if (error) throw error;
    id = data.length ? data[0].id : "";
  }
  const nova = !id;
  if (nova) {
    const { data, error } = await cliente.from("builds").insert(linha).select("id").single();
    if (error) throw error;
    id = data.id;
  }
  window.Montador.marcarNuvem(classe, id);
  aviso = { texto: nova ? t("Salva na nuvem: {nome}. Em outro PC, entre com a mesma conta e abra em \"Minhas builds\".", { nome: linha.nome })
                        : t("Mudanças salvas na nuvem: {nome}.", { nome: linha.nome }), erro: false };
  if (minhas) await lerMinhas();
});

async function lerMinhas() {
  const { data, error } = await cliente.from("builds").select("id, nome, classe, alterado")
    .order("alterado", { ascending: false }).limit(MAXIMO_DE_BUILDS);
  if (error) throw error;
  minhas = data;
}

const abrirMinhas = () => {
  if (minhas) { minhas = null; desenhar(); return; }
  fazer(lerMinhas);
};

const abrir = id => fazer(async () => {
  const { data, error } = await cliente.from("builds").select("dados").eq("id", id).single();
  if (error) throw error;
  if (await window.Montador.daNuvem(data.dados, id)) aviso = { texto: "", erro: false };
  window.scrollTo({ top: 0 });
});

const apagar = id => fazer(async () => {
  const { error } = await cliente.from("builds").delete().eq("id", id);
  if (error) throw error;
  window.Montador.esquecerNuvem(id);
  minhas = minhas.filter(b => b.id !== id);
  aviso = { texto: t("Build apagada da nuvem."), erro: false };
});

const apagarTodas = () => fazer(async () => {
  const { error } = await cliente.from("builds").delete().eq("user_id", sessao.user.id);
  if (error) throw error;
  window.Montador.esquecerNuvem();
  minhas = [];
  aviso = { texto: t("Todas as suas builds foram apagadas da nuvem. O que está no montador continua aqui."), erro: false };
});

// Apaga a conta no Supabase (e, junto, todas as builds dela).
const apagarConta = () => fazer(async () => {
  const { error } = await cliente.rpc("apagar_minha_conta");
  if (error) throw error;
  await cliente.auth.signOut({ scope: "local" });
  window.Montador.esquecerNuvem();
  sessao = null;
  minhas = null;
  aviso = { texto: t("Conta apagada, com todas as builds dela. Pra usar a nuvem de novo, é só entrar."), erro: false };
});

// ------------------------------------------------------------ desenho

// Botão que pede um 2º clique antes de apagar.
function botaoDeApagar(texto, aoConfirmar, classe = "botao botao-leve botao-remover") {
  const b = el("button", { type: "button", class: classe, ...(ocupado ? { disabled: "" } : {}) }, texto);
  let espera = null;
  b.addEventListener("click", () => {
    if (espera) { clearTimeout(espera); espera = null; aoConfirmar(); return; }
    b.textContent = t("Clique de novo pra apagar");
    b.classList.add("confirmar");
    espera = setTimeout(() => { espera = null; b.textContent = texto; b.classList.remove("confirmar"); }, 4000);
  });
  return b;
}

function botao(texto, aoClicar, classe = "botao botao-leve") {
  return el("button", { type: "button", class: classe, onclick: aoClicar, ...(ocupado ? { disabled: "" } : {}) }, texto);
}

function desenharMinhas() {
  const data = d => new Date(d).toLocaleDateString(emIngles() ? "en" : "pt-BR", { day: "numeric", month: "short", year: "numeric" });
  const nomeDaClasse = cl => (window.Montador.nomeDaClasse(cl) || cl);
  return el("div", { class: "nuvem-minhas" },
    el("h3", {}, t("Minhas builds na nuvem"), " ", el("span", { class: "mudo" }, `${minhas.length}/${MAXIMO_DE_BUILDS}`)),
    minhas.length
      ? el("ul", { class: "nuvem-lista" }, minhas.map(b => el("li", {},
          el("span", { class: "nuvem-build" },
            el("span", { class: "nuvem-nome" }, b.nome),
            el("span", { class: "mudo" }, `${nomeDaClasse(b.classe)} · ${data(b.alterado)}`)),
          botao(t("Abrir"), () => abrir(b.id)),
          botaoDeApagar(t("Apagar"), () => apagar(b.id)))))
      : el("p", { class: "mudo" }, t("Nenhuma build na nuvem ainda. Monte uma e clique em \"Salvar na nuvem\".")),
    el("div", { class: "nuvem-perigo" },
      minhas.length > 0 && botaoDeApagar(t("Apagar minhas builds"), apagarTodas),
      botaoDeApagar(t("Apagar minha conta"), apagarConta),
      el("a", { href: emIngles() ? "./#nuvem" : "pt/#nuvem" }, t("O que fica guardado?"))));
}

function desenhar() {
  if (!raiz) return;
  const provedor = sessao && PROVEDORES[(sessao.user.app_metadata || {}).provider];
  const corpo = sessao
    ? [el("p", { class: "nuvem-texto" }, el("strong", {}, t("Nuvem")), " · ",
         provedor ? t("conectado com {provedor}", { provedor }) : t("conectado")),
       el("div", { class: "nuvem-acoes" },
         botao(t("Salvar na nuvem"), salvar, "botao"),
         botao(minhas ? t("Fechar minhas builds") : t("Minhas builds"), abrirMinhas),
         botao(t("Sair"), sair))]
    : [el("p", { class: "nuvem-texto" }, el("strong", {}, t("Nuvem")), " · ",
         t("Opcional: entre pra salvar suas builds e abrir em qualquer PC."), " ",
         el("a", { href: emIngles() ? "./#nuvem" : "pt/#nuvem" }, t("O que fica guardado?"))),
       el("div", { class: "nuvem-acoes" },
         Object.entries(PROVEDORES).map(([id, nome]) =>
           botao(t("Entrar com {provedor}", { provedor: nome }), () => entrar(id))))];
  raiz.replaceChildren(...[
    el("div", { class: "nuvem-barra" }, corpo),
    aviso.texto && el("p", { class: "nuvem-aviso" + (aviso.erro ? " t-falta" : ""), role: "status" }, aviso.texto),
    sessao && minhas && desenharMinhas(),
  ].filter(Boolean));
}

// ------------------------------------------------------------ início

async function ligar() {
  const caixa = document.querySelector("[data-nuvem]");
  if (!caixa || !window.Montador) return;
  if (!config) {
    const c = window.D3C_NUVEM;
    if (c && (c.url || c.chave)) console.warn("config-nuvem.js: endereço ou chave inválidos (só vale a chave pública). A nuvem fica desligada.");
    return;
  }
  if (!(await window.Montador.noSite)) return;   // o montador não abriu: sem nuvem também
  raiz = caixa;
  raiz.setAttribute("aria-label", t("Builds na nuvem"));
  raiz.hidden = false;
  desenhar();
  const voltou = voltouDoLogin();
  if (!temSessaoGuardada() && !voltou) return;
  const deuErro = new URLSearchParams(location.search).has("error");
  try {
    await lerSessao();
    if (deuErro) avisar(t("O login não terminou (cancelado ou recusado). Tente de novo."), true);
    else if (sessao && voltou) avisar(t("Conectado. Agora \"Salvar na nuvem\" guarda a build de agora na sua conta."));
  } catch {
    avisar(t("Não consegui falar com a nuvem agora. O montador segue funcionando sem ela."), true);
  }
  // Tira o ?code= (ou o erro) do endereço, mantendo a build do #b=, se houver.
  if (voltou) history.replaceState(null, "", location.pathname + location.hash);
  desenhar();
}

ligar();
})();
