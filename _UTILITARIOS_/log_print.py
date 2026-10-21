# 📁 _UTILITARIOS_/log_print.py
"""
Output voltado ao usuário — aparece no painel Saída da IDE e na status bar.

Não salva em arquivo. Não tem arquivo/método — só a mensagem.
Use para tudo que o usuário precisa saber: progresso, resultados, avisos de ação.

Uso:
    from _UTILITARIOS_.log_print import log_print
    log_print.info("Formatando 24 arquivos...")
    log_print.ok("Formatação concluída!")
    log_print.aviso("2 funções muito longas detectadas")
    log_print.erro("Arquivo não encontrado: main.py")
"""
from datetime import datetime
from PySide6.QtCore import QObject, Signal

class _LogPrint(QObject):
    """Emissor singleton de output voltado ao usuário."""

    # (nivel, hora, mensagem) → PainelSaida
    nova_saida = Signal(str, str, str)

    # (mensagem, duracao_ms) → StatusBar da MainWindow
    status_msg = Signal(str, int)

    # () → abre/foca a aba Saída no terminal (emitido em toda mensagem)
    pedido_foco = Signal()

    def _emitir(self, nivel: str, mensagem: str, duracao_ms: int) -> None:
        hora = datetime.now().strftime("%H:%M:%S")
        self.nova_saida.emit(nivel, hora, mensagem)
        self.status_msg.emit(mensagem, duracao_ms)
        self.pedido_foco.emit()

    def info(self, mensagem: str, duracao_ms: int = 5000) -> None:
        """Informação de progresso — o que está acontecendo agora."""
        self._emitir("INFO", mensagem, duracao_ms)

    def ok(self, mensagem: str, duracao_ms: int = 5000) -> None:
        """Conclusão com sucesso."""
        self._emitir("OK", mensagem, duracao_ms)

    def aviso(self, mensagem: str, duracao_ms: int = 6000) -> None:
        """Atenção — algo que o usuário deve notar."""
        self._emitir("AVISO", mensagem, duracao_ms)

    def erro(self, mensagem: str, duracao_ms: int = 8000) -> None:
        """Erro que afeta o usuário."""
        self._emitir("ERRO", mensagem, duracao_ms)

# instância global — importar sempre assim:
#   from _UTILITARIOS_.log_print import log_print
log_print = _LogPrint()
