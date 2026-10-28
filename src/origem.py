"""
De onde vem cada item: o "Como conseguir" da tela da build.

O que dá pra saber pela API da Blizzard (detalhes do item):
  - forjado: o tooltipParams aponta pro artesão ("/artisan/blacksmith/recipe/...");
  - só na temporada: isSeasonRequiredToDrop;
  - gema lendária: typeName "Legendary Gem".
O que a API não diz fica aqui, escrito à mão: os itens que só saem do Cache
Horádrico de um ato (recompensa das missões do Modo Aventura). O Cache do Ato IV
não tem itens próprios: sorteia entre os dos outros atos.

O resto (lendários e conjuntos comuns) segue a regra geral do jogo: cai de
monstros em qualquer lugar, sai na aposta da Kadala e na receita do cubo de
Kanai que transforma um item raro em lendário do mesmo tipo.

Cada origem é {"texto": frase em português, "vars": {...}}; a janela traduz
com o en.json, como as outras frases.
"""

from blizzard import ErroBlizzard, chave_do_nome

ITENS_DO_CACHE = {
    "I": ("Golden Gorget of Leoric", "Mad Monarch's Scepter", "Pauldrons of the Skeleton King",
          "Ring of Royal Grandeur", "Sanguinary Vambraces"),
    "II": ("Cloak of Deception", "Coven's Criterion", "Gloves of Worship", "Illusory Boots"),
    "III": ("Avarice Band", "Boots of Disregard", "Burst of Wrath", "Envious Blade",
            "Insatiable Belt", "Overwhelming Desire", "Pride's Fall"),
    "V": ("Death's Bargain", "Helltrapper", "Pandemonium Loop", "Salvation", "Soulsmasher"),
}
ATO_DO_CACHE = {chave_do_nome(nome): ato for ato, nomes in ITENS_DO_CACHE.items() for nome in nomes}

ARTESAOS = {
    "blacksmith": "Forjado pelo Ferreiro (precisa do plano).",
    "jeweler": "Feito pelo Joalheiro (precisa do plano).",
    "mystic": "Feito pela Mística.",
}


def _frase(texto: str, **vars) -> dict:
    return {"texto": texto, "vars": vars}


def origem(nome: str, detalhes: dict | None) -> list[dict]:
    """Os jeitos de conseguir o item. `detalhes` é o que a Blizzard devolve
    (detalhes_do_item); sem ele (sem internet ou item que a Blizzard não conhece),
    só sabe dos itens do Cache e devolve [] pros outros (melhor nada que errado)."""
    ato = ATO_DO_CACHE.get(chave_do_nome(nome))
    if ato:
        return [_frase("Só sai do Cache Horádrico do Ato {ato} (missões do Modo Aventura).", ato=ato),
                _frase("O Cache do Ato IV também pode trazer."),
                _frase("Não cai de monstros nem sai na Kadala ou no cubo.")]
    if not detalhes:
        return []
    caminho = str(detalhes.get("tooltipParams") or "")
    if caminho.startswith("/artisan/"):
        artesao = caminho.split("/")[2]
        return [_frase(ARTESAOS.get(artesao, "Feito por um artesão (precisa do plano)."))]
    if detalhes.get("typeName") == "Legendary Gem":
        return [_frase("Cai dos Guardiões da Grande Fenda.")]
    jeitos = [_frase("Cai de monstros em qualquer lugar (mais em Tormento alto e nas Fendas)."),
              _frase("Aposta na Kadala, com Fragmentos de Sangue."),
              _frase("Cubo de Kanai: receita que transforma um item raro do mesmo tipo em lendário.")]
    if detalhes.get("isSeasonRequiredToDrop"):
        jeitos.append(_frase("Só cai com personagem de temporada."))
    return jeitos


def origens_dos_itens(nomes: list[str], api) -> dict[str, list[dict]]:
    """origem() de vários itens. Os detalhes vêm da Blizzard (com cache em disco);
    item desconhecido ou sem internet fica sem origem."""
    from concurrent.futures import ThreadPoolExecutor

    def um(nome):
        if chave_do_nome(nome) in ATO_DO_CACHE:
            return nome, origem(nome, None)  # não precisa perguntar à Blizzard
        try:
            return nome, origem(nome, api.detalhes_do_item(nome))
        except ErroBlizzard:
            return nome, origem(nome, None)
    with ThreadPoolExecutor(max_workers=6) as grupo:
        return dict(grupo.map(um, list(dict.fromkeys(nomes))))
