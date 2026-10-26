// D3 Companion — dica do item: o quadro que aparece ao passar o mouse (ou focar
// com o Tab) num item ou gema. Igual no app e no site (docs/dica.js é cópia).
//
// Qualquer elemento com data-dica="<nome do item em inglês>" ganha a dica. Os
// textos vêm de dados/dicas.json (gerado da API da Blizzard por
// ferramentas/dados_do_site.py) e entram só como texto (textContent), nunca HTML.
//
// Uso: Dicas.ligar(async () => <o dicas.json>). Ele só é pedido no 1º mouse em cima.

"use strict";

(() => {
  const VAZIO = { itens: {}, sets: {} };
  let carregar = null;
  let pedido = null;
  let quadro = null;
  let alvo = null;

  function criar(tag, classe, texto) {
    const no = document.createElement(tag);
    if (classe) no.className = classe;
    if (texto) no.textContent = texto;
    return no;
  }

  function dados() {
    pedido ||= Promise.resolve()
      .then(() => carregar())
      .then(d => (d && typeof d.itens === "object" ? d : VAZIO))
      .catch(() => VAZIO);
    return pedido;
  }

  function preencher(nome, d, sets) {
    const filhos = [criar("p", "dica-nome " + (d.s ? "t-set" : "t-lendario"), d.n || nome)];
    if (d.n && d.n !== nome) filhos.push(criar("p", "dica-ingles", nome));
    if (d.t) filhos.push(criar("p", "dica-tipo", d.t));
    for (const p of d.p || []) filhos.push(criar("p", "dica-poder", p));
    if (d.s) {
      filhos.push(criar("p", "dica-set-nome", d.s));
      for (const linha of sets[d.s] || []) filhos.push(criar("p", "dica-set", linha));
    }
    if (d.f) filhos.push(criar("p", "dica-sabor", d.f));
    quadro.replaceChildren(...filhos);
  }

  // Ao lado do elemento (à direita se couber, senão à esquerda), sem sair da janela.
  function posicionar(no) {
    const r = no.getBoundingClientRect();
    const q = quadro.getBoundingClientRect();
    const margem = 10;
    let x = r.right + margem;
    if (x + q.width > innerWidth - margem) x = Math.max(margem, r.left - q.width - margem);
    const y = Math.min(Math.max(margem, r.top), Math.max(margem, innerHeight - q.height - margem));
    quadro.style.left = `${Math.round(x)}px`;
    quadro.style.top = `${Math.round(y)}px`;
  }

  async function mostrar(no) {
    alvo = no;
    const nome = no.dataset.dica;
    const todos = await dados();
    if (alvo !== no || !no.isConnected) return;  // o mouse já saiu
    const d = Object.prototype.hasOwnProperty.call(todos.itens, nome) ? todos.itens[nome] : null;
    if (!d) { quadro.hidden = true; return; }
    preencher(nome, d, todos.sets || {});
    quadro.hidden = false;
    posicionar(no);
  }

  function esconder() {
    alvo = null;
    if (quadro) quadro.hidden = true;
  }

  function aoEntrar(e) {
    const no = e.target.closest && e.target.closest("[data-dica]");
    if (no === alvo) return;
    if (no && no.dataset.dica) mostrar(no);
    else esconder();
  }

  window.Dicas = {
    ligar(funcao) {
      carregar = funcao;
      if (quadro) return;
      quadro = criar("div", "dica-item");
      quadro.setAttribute("role", "tooltip");
      quadro.hidden = true;
      document.body.append(quadro);
      document.addEventListener("mouseover", aoEntrar);
      document.addEventListener("focusin", aoEntrar);
      document.addEventListener("focusout", esconder);
      document.addEventListener("mousedown", esconder);
      document.addEventListener("keydown", e => { if (e.key === "Escape") esconder(); });
      addEventListener("scroll", esconder, true);
      addEventListener("blur", esconder);
    },
  };
})();
