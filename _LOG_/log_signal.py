# 📁 _LOG_/log_signal.py
"""
Sinal Qt global que conecta o sistema de log à interface visual.

O log.py emite aqui.
O PainelLogs escuta aqui.

Nenhum outro arquivo precisa mudar.
"""

from PySide6.QtCore import QObject, Signal

class _LogSignal(QObject):
    """
    nova_entrada(nivel, texto)
        nivel → "OK" | "INFO" | "AVISO" | "ERRO"
        texto → linha formatada completa
    """
    nova_entrada = Signal(str, str)

# instância global — importar sempre desta forma:
#   from _LOG_.log_signal import log_signal
log_signal = _LogSignal()
