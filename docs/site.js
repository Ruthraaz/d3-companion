// Site do D3 Companion: pega no GitHub a última versão publicada e aponta os
// botões de download direto pro instalador dela. Sem internet ou sem versão ainda,
// os botões continuam levando pra página de versões do GitHub.

"use strict";

// Contra clickjacking: o GitHub Pages não deixa mandar o cabeçalho que proíbe
// abrir o site dentro de outro (iframe). Então, se estiver dentro de outro site,
// a página some e tenta abrir sozinha, por inteiro.
if (window.top !== window.self) {
  document.documentElement.hidden = true;
  try { window.top.location.href = window.self.location.href; } catch { /* o outro site bloqueou: fica escondida */ }
}

// Idioma: a página em inglês é a raiz e a em português fica em pt/. A escolha
// (link "English"/"Português" daqui ou o botão do montador) fica guardada no
// navegador; sem escolha, quem tem o navegador em português vai pra pt/.
const EM_PT = document.documentElement.lang.startsWith("pt");
const GUARDADO = "d3c-idioma";
const guardado = () => { try { return localStorage.getItem(GUARDADO); } catch { return null; } };
const quer = guardado() || ((navigator.languages || [navigator.language || ""]).some(l => /^pt(-|$)/i.test(l)) ? "pt" : "en");
if (quer === "pt" && !EM_PT) location.replace(`pt/${location.hash}`);
else if (quer === "en" && EM_PT && guardado()) location.replace(`../${location.hash}`);
document.querySelectorAll(".js-idioma").forEach(a => a.addEventListener("click", () => {
  try { localStorage.setItem(GUARDADO, a.dataset.idioma === "pt" ? "pt" : "en"); } catch { /* sem: vale o link */ }
}));

const TEXTOS = EM_PT ? {
  baixar: v => `Baixar para Windows · v${v}`, detalhe: (v, t) => `Versão ${v} · ${t} · instalador, sem administrador`,
  semVersao: "Windows 10 e 11 · instalador", baixando: "Baixando… veja a barra do navegador",
  partilhar: "Ajudante grátis pra Diablo III: diz se o item serve na sua build.", copiado: "Link copiado!", data: "pt-BR",
} : {
  baixar: v => `Download for Windows · v${v}`, detalhe: (v, t) => `Version ${v} · ${t} · installer, no admin needed`,
  semVersao: "Windows 10 and 11 · installer", baixando: "Downloading… check your browser's bar",
  partilhar: "Free Diablo III helper: tells you if an item fits your build.", copiado: "Link copied!", data: "en-US",
};

const API = "https://api.github.com/repos/Ruthraaz/d3-companion/releases/latest";
const DOWNLOAD_OK = /^https:\/\/github\.com\/Ruthraaz\/d3-companion\/releases\/download\//;

const mb = bytes => `${Math.round(bytes / 1024 / 1024)} MB`;
const dia = iso => new Date(iso).toLocaleDateString(TEXTOS.data, { day: "numeric", month: "long", year: "numeric" });

function escrever(seletor, texto) {
  document.querySelectorAll(seletor).forEach(el => { el.textContent = texto; });
}

async function carregarVersao() {
  try {
    const r = await fetch(API, { headers: { Accept: "application/vnd.github+json" } });
    if (!r.ok) throw new Error(`GitHub respondeu ${r.status}`);
    const versao = await r.json();
    // O instalador; versão antiga, sem ele, ainda baixa o zip.
    const assets = versao.assets || [];
    const zip = assets.find(a => /-Setup-[\d.]+\.exe$/i.test(a.name)) || assets.find(a => /windows\.zip$/i.test(a.name));
    // Só aceita link de download deste repositório (nada de endereço de fora).
    if (!zip || !DOWNLOAD_OK.test(zip.browser_download_url)) throw new Error("sem zip na versão");

    const nome = versao.tag_name.replace(/^v/, "");
    document.querySelectorAll(".js-baixar").forEach(a => { a.href = zip.browser_download_url; });
    escrever(".js-rotulo", TEXTOS.baixar(nome));
    escrever(".js-detalhe", TEXTOS.detalhe(nome, mb(zip.size)));
    escrever(".js-versao", nome);
    escrever(".js-tamanho", mb(zip.size));
    escrever(".js-data", dia(versao.published_at));
  } catch {
    escrever(".js-detalhe", TEXTOS.semVersao);
  }
}

// Ao clicar, avisa que o download começou (o navegador mostra o progresso).
document.querySelectorAll(".js-baixar").forEach(a => a.addEventListener("click", () => {
  if (!DOWNLOAD_OK.test(a.href)) return;  // ainda é a página de versões: o GitHub abre
  a.classList.add("baixando");
  const rotulo = a.querySelector(".js-rotulo");
  const antes = rotulo.textContent;
  rotulo.textContent = TEXTOS.baixando;
  setTimeout(() => { a.classList.remove("baixando"); rotulo.textContent = antes; }, 6000);
}));

// "Mandar o site pra um amigo": a folha de compartilhar do celular/Windows ou,
// sem ela, copia o endereço. O endereço é fixo (nada do que está na página).
const ENDERECO = EM_PT ? "https://ruthraaz.github.io/d3-companion/pt/" : "https://ruthraaz.github.io/d3-companion/";
document.querySelectorAll(".js-compartilhar").forEach(botao => botao.addEventListener("click", async () => {
  const antes = botao.textContent;
  try {
    if (navigator.share) {
      await navigator.share({ title: "D3 Companion", text: TEXTOS.partilhar, url: ENDERECO });
      return;
    }
    await navigator.clipboard.writeText(ENDERECO);
    botao.textContent = TEXTOS.copiado;
  } catch (erro) {
    if (erro && erro.name === "AbortError") return;  // fechou a folha de compartilhar
    botao.textContent = ENDERECO;
  }
  setTimeout(() => { botao.textContent = antes; }, 3000);
}));

carregarVersao();
