"""
Configurações que a janela deixa mudar: ficam no .env, junto do TESSERACT_CMD.

Só mexemos nas chaves de CHAVES. O resto do .env (e os comentários) fica como
estava, porque o Arthur também edita esse arquivo à mão.
"""

import re
from pathlib import Path

from dotenv import dotenv_values

from atalho import ler_atalho

ARQUIVO_ENV = Path(__file__).resolve().parent.parent / ".env"

# chave -> valor padrão (o mesmo que o app usa quando a chave não existe)
# BUILD_ATIVA = id da build escolhida na janela (nome do arquivo em builds/); vazio = todas.
# AUTOMATICO = "sim": avalia sozinho ao passar o mouse num item; "nao": só pelo atalho.
# BATTLETAG = a da aba "Meu herói" (ex.: Arthur#1234), pra não digitar toda vez.
CHAVES = {"ATALHO": "F8", "SELO_SEGUNDOS": "6", "BUILD_ATIVA": "", "AUTOMATICO": "sim", "BATTLETAG": ""}


def ler_config(arquivo: Path = ARQUIVO_ENV) -> dict[str, str]:
    valores = dotenv_values(arquivo) if arquivo.exists() else {}
    return {chave: (valores.get(chave) or padrao) for chave, padrao in CHAVES.items()}


def validar(chave: str, valor: str) -> str | None:
    """Mensagem de erro em português, ou None se o valor está ok."""
    if chave == "ATALHO":
        try:
            ler_atalho(valor)
        except ValueError:
            return f"Atalho inválido: {valor!r}. Exemplos: F8, Ctrl+F8, Alt+Q."
    elif chave == "SELO_SEGUNDOS":
        try:
            segundos = float(valor.replace(",", "."))
        except ValueError:
            return "Tempo do selo precisa ser um número (ex.: 6)."
        if not 1 <= segundos <= 60:
            return "Tempo do selo precisa ficar entre 1 e 60 segundos."
    elif chave == "AUTOMATICO":
        if valor not in ("sim", "nao"):
            return 'Avaliação automática precisa ser "sim" ou "nao".'
    elif chave == "BATTLETAG":
        from heroi import conta_da_battletag  # aqui: só a aba do herói precisa
        from blizzard import ErroBlizzard
        if valor:
            try:
                conta_da_battletag(valor)
            except ErroBlizzard as e:
                return str(e)
    elif chave == "BUILD_ATIVA":
        from avaliador import carregar_builds  # aqui: config não precisa das builds pro resto
        if valor and valor not in {b["id"] for b in carregar_builds()}:
            return f"Não existe build {valor!r} em builds/."
    else:
        return f"Configuração desconhecida: {chave}."
    return None


def salvar_config(mudancas: dict[str, str], arquivo: Path = ARQUIVO_ENV) -> dict[str, str]:
    """Grava as mudanças no .env. Devolve {chave: erro}; vazio = tudo salvo.

    Se qualquer valor for inválido, nada é gravado.
    """
    mudancas = {k: str(v).strip() for k, v in mudancas.items()}
    if "SELO_SEGUNDOS" in mudancas:
        mudancas["SELO_SEGUNDOS"] = mudancas["SELO_SEGUNDOS"].replace(",", ".")
    erros = {k: e for k, v in mudancas.items() if (e := validar(k, v))}
    if erros:
        return erros

    linhas = arquivo.read_text(encoding="utf-8").splitlines() if arquivo.exists() else []
    faltando = dict(mudancas)
    for i, linha in enumerate(linhas):
        m = re.match(r"\s*([A-Z_]+)\s*=", linha)
        if m and m.group(1) in faltando:
            linhas[i] = f"{m.group(1)}={faltando.pop(m.group(1))}"
    linhas += [f"{k}={v}" for k, v in faltando.items()]
    arquivo.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    return {}
