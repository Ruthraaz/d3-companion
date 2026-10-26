// Site do D3 Companion: pega no GitHub a última versão publicada e aponta os
// botões de download direto pro zip dela. Sem internet ou sem versão ainda,
// os botões continuam levando pra página de versões do GitHub.

"use strict";

const API = "https://api.github.com/repos/Ruthraaz/d3-companion/releases/latest";
const DOWNLOAD_OK = /^https:\/\/github\.com\/Ruthraaz\/d3-companion\/releases\/download\//;

const mb = bytes => `${Math.round(bytes / 1024 / 1024)} MB`;
const dia = iso => new Date(iso).toLocaleDateString("pt-BR", { day: "numeric", month: "long", year: "numeric" });

function escrever(seletor, texto) {
  document.querySelectorAll(seletor).forEach(el => { el.textContent = texto; });
}

async function carregarVersao() {
  try {
    const r = await fetch(API, { headers: { Accept: "application/vnd.github+json" } });
    if (!r.ok) throw new Error(`GitHub respondeu ${r.status}`);
    const versao = await r.json();
    const zip = (versao.assets || []).find(a => /windows\.zip$/i.test(a.name));
    // Só aceita link de download deste repositório (nada de endereço de fora).
    if (!zip || !DOWNLOAD_OK.test(zip.browser_download_url)) throw new Error("sem zip na versão");

    const nome = versao.tag_name.replace(/^v/, "");
    document.querySelectorAll(".js-baixar").forEach(a => { a.href = zip.browser_download_url; });
    escrever(".js-rotulo", `Baixar para Windows · v${nome}`);
    escrever(".js-detalhe", `Versão ${nome} · ${mb(zip.size)} · zip, sem instalação`);
    escrever(".js-versao", nome);
    escrever(".js-tamanho", mb(zip.size));
    escrever(".js-data", dia(versao.published_at));
  } catch {
    escrever(".js-detalhe", "Windows 10 e 11 · zip, sem instalação");
  }
}

// Ao clicar, avisa que o download começou (o navegador mostra o progresso).
document.querySelectorAll(".js-baixar").forEach(a => a.addEventListener("click", () => {
  if (!DOWNLOAD_OK.test(a.href)) return;  // ainda é a página de versões: o GitHub abre
  a.classList.add("baixando");
  const rotulo = a.querySelector(".js-rotulo");
  const antes = rotulo.textContent;
  rotulo.textContent = "Baixando… veja a barra do navegador";
  setTimeout(() => { a.classList.remove("baixando"); rotulo.textContent = antes; }, 6000);
}));

carregarVersao();
