"""As builds de builds/ que os testes usam pra comparar resultados.

Builds importadas depois (do Maxroll) não entram: senão cada importação mudaria
o que os testes esperam. A conferência (test_builds) continua olhando todas.
"""

BUILDS_DOS_TESTES = {"dreadlands_metralhar", "legacy_of_nightmares", "unhallowed_multidisparo"}
