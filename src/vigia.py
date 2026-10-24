"""
Avaliação automática: passou o mouse num item, o selo aparece sozinho.

O overlay olha a tela de tempos em tempos (captura.olhada_rapida, barata) e
este módulo decide o que fazer com cada olhada. Ele não sabe de tela, OCR nem
Qt — só de "assinaturas" — e por isso dá pra testar sem jogo.

  - dica nova aparecendo: espera a assinatura se repetir (a dica terminou de
    aparecer e a tela parou) e só então manda AVALIAR, uma vez;
  - mesma dica de antes (voltou no mesmo item): mostra o resultado guardado,
    sem OCR de novo;
  - a dica sumiu (2 olhadas seguidas sem dica): manda ESCONDER o selo.
"""

from collections import OrderedDict

NADA, AVALIAR, GUARDADO, ESCONDER = "nada", "avaliar", "guardado", "esconder"
OLHADAS_PRA_SUMIR = 2
GUARDAR_NO_MAXIMO = 40


class Vigia:
    def __init__(self):
        self._anterior = None   # assinatura da olhada passada
        self._mostrando = None  # assinatura da dica cujo selo está na tela
        self._sem_dica = 0
        self._guardados: OrderedDict = OrderedDict()

    def olhar(self, assinatura) -> tuple[str, object]:
        """Recebe a assinatura da olhada (ou None) e devolve (ação, valor).
        Em GUARDADO, o valor é o que foi guardado com `guardar`."""
        if assinatura is None:
            self._anterior = None
            self._sem_dica += 1
            if self._sem_dica == OLHADAS_PRA_SUMIR and self._mostrando is not None:
                self._mostrando = None
                return ESCONDER, None
            return NADA, None

        self._sem_dica = 0
        if assinatura != self._anterior:  # ainda mudando: espera estabilizar
            self._anterior = assinatura
            return NADA, None
        if assinatura == self._mostrando:  # já é o selo que está na tela
            return NADA, None

        self._mostrando = assinatura
        if assinatura in self._guardados:
            self._guardados.move_to_end(assinatura)
            valor = self._guardados[assinatura]
            # Guardado como None = já vimos que não é dica de item: fica quieto.
            return (GUARDADO, valor) if valor is not None else (NADA, None)
        return AVALIAR, None

    def esquecer_tela(self) -> bool:
        """O jogo saiu da frente (ou o modo automático foi desligado): esquece o
        que estava na tela, mas mantém os resultados guardados. Devolve True se
        havia um selo na tela, que então precisa ser escondido."""
        havia = self._mostrando is not None
        self._anterior = self._mostrando = None
        self._sem_dica = 0
        return havia

    def guardar(self, assinatura, resultado) -> None:
        """Guarda o resultado da avaliação (None = "não era um item")."""
        self._guardados[assinatura] = resultado
        self._guardados.move_to_end(assinatura)
        while len(self._guardados) > GUARDAR_NO_MAXIMO:
            self._guardados.popitem(last=False)
