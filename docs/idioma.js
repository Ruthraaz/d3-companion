// D3 Companion — idioma: inglês ou português. Igual no app e no site
// (docs/idioma.js é cópia).
//
// O texto no código continua em português; dados/en.json diz como fica em inglês:
//   Idioma.t("Salvar no app")          -> "Save to app" (inglês) ou o próprio texto (português)
//   Idioma.t("{n} afixos", { n: 3 })   -> "3 affixes"
// Frase que falta no en.json aparece em português (um teste avisa quando falta).
// No HTML, quem tem data-t ganha a tradução dos textos de dentro e dos atributos
// placeholder, title, aria-label, alt e content (Idioma.aplicar()).
//
// Qual idioma: o escolhido (no site fica no navegador; no app, nas Configurações)
// ou, sem escolha, o do navegador/Windows: português se for pt-*, senão inglês.

"use strict";

(() => {
  const GUARDADO = "d3c-idioma";
  const ATRIBUTOS = ["placeholder", "title", "aria-label", "alt", "content"];
  let idioma = "en";
  let en = {};

  function guardado() {
    try {
      const v = localStorage.getItem(GUARDADO);
      return v === "en" || v === "pt" ? v : null;
    } catch { return null; }
  }

  function doNavegador() {
    const lista = navigator.languages && navigator.languages.length ? navigator.languages : [navigator.language || ""];
    return lista.some(l => /^pt(-|$)/i.test(l)) ? "pt" : "en";
  }

  // fixo: "en"/"pt" (o app manda o das Configurações); sem ele, o guardado ou o do navegador.
  function escolher(fixo) {
    idioma = fixo === "en" || fixo === "pt" ? fixo : guardado() || doNavegador();
    document.documentElement.lang = idioma === "pt" ? "pt-BR" : "en";
    return idioma;
  }

  // trazer: função que devolve o en.json (fetch no site, Python no app).
  async function carregar(trazer) {
    if (idioma !== "en") return;
    try {
      const d = await trazer();
      if (d && typeof d === "object" && !Array.isArray(d) && !d.erro) en = d;
    } catch { /* sem o arquivo: fica em português */ }
  }

  function t(texto, vars) {
    let s = idioma === "en" && Object.prototype.hasOwnProperty.call(en, texto) ? en[texto] : texto;
    if (vars) s = s.replace(/\{(\w+)\}/g, (m, k) => (Object.prototype.hasOwnProperty.call(vars, k) ? String(vars[k]) : m));
    return s;
  }

  function aplicar(raiz = document) {
    raiz.querySelectorAll("[data-t]").forEach(no => {
      for (const filho of no.childNodes) {
        if (filho.nodeType !== Node.TEXT_NODE || !filho.textContent.trim()) continue;
        filho.ptOriginal ??= filho.textContent;
        const cru = filho.ptOriginal.trim();
        filho.textContent = filho.ptOriginal.replace(cru, t(cru.replace(/\s+/g, " ")));  // chave sem quebra de linha
      }
      for (const a of ATRIBUTOS) {
        if (!no.hasAttribute(a)) continue;
        const chave = `pt${a.replace(/-/g, "")}`;
        no.dataset[chave] ??= no.getAttribute(a);
        no.setAttribute(a, t(no.dataset[chave]));
      }
    });
    // Botão de trocar: mostra o outro idioma, no nome dele.
    raiz.querySelectorAll("[data-trocar-idioma]").forEach(botao => {
      const outro = idioma === "en" ? "pt" : "en";
      botao.textContent = outro === "pt" ? "Português" : "English";
      botao.lang = outro === "pt" ? "pt-BR" : "en";
      if (botao.dataset.ligado) return;
      botao.dataset.ligado = "1";
      botao.addEventListener("click", () => window.Idioma.trocar(idioma === "en" ? "pt" : "en"));
    });
  }

  // Site: guarda a escolha e recarrega (tudo já sai no idioma novo).
  // O app troca isto por uma função que grava nas Configurações.
  function trocar(novo) {
    try { localStorage.setItem(GUARDADO, novo); } catch { /* sem: vale só agora */ }
    location.reload();
  }

  window.Idioma = {
    escolher, carregar, t, aplicar, trocar,
    get atual() { return idioma; },
  };
})();
