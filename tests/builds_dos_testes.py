"""As builds que os testes usam pra comparar resultados.

Ficam em tests/builds/, fora da pasta de builds do usuário: builds/ é de quem
usa o app (cada um importa as suas), e mudar ela não pode mudar os testes.
"""

from pathlib import Path

PASTA_DOS_TESTES = Path(__file__).resolve().parent / "builds"

BUILDS_DOS_TESTES = {"dreadlands_metralhar", "legacy_of_nightmares", "unhallowed_multidisparo"}
