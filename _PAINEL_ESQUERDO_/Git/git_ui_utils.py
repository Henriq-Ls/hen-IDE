# 📁 _PAINEL_ESQUERDO_/Git/git_ui_utils.py

import threading
from PySide6.QtCore import Qt, Signal, QObject
from PySide6.QtWidgets import QPushButton, QFrame
from _CONFIGURA_.gerenciador_tema import tema_global   # lê cores do tema no momento da chamada
from _LOG_.log import log
_ARQ = "git_ui_utils.py"

# ══════════════════════════════════════════════════════════════════════
# Ponte thread-safe
# ══════════════════════════════════════════════════════════════════════

class _Ponte(QObject):
    _concluido = Signal(object)

    def __init__(self, tarefa, callback, parent=None):
        super().__init__(parent)
        self._tarefa = tarefa
        self._concluido.connect(callback)

    def iniciar(self):
        def _rodar():
            try:
                resultado = self._tarefa()
            except Exception:
                log.excecao(_ARQ, "_Ponte._rodar", "exceção na thread")
                resultado = None
            self._concluido.emit(resultado)

        threading.Thread(target=_rodar, daemon=True).start()

def _em_thread(tarefa, callback, parent: QObject):
    ponte = _Ponte(tarefa, callback, parent)
    ponte.iniciar()

    return ponte

# ══════════════════════════════════════════════════════════════════════
# Utilitários de UI
# ══════════════════════════════════════════════════════════════════════

def _botao(texto, cor_fundo=None, cor_texto=None): # lê do tema ao criar o botão — se o chamador não passar cor, usa o padrão do JSON
    t = tema_global()
    if cor_fundo is None:
        cor_fundo = t.cor("interface.botao_padrao_fundo", "#1a3a1a")
    if cor_texto is None:
        cor_texto = t.cor("interface.botao_padrao_texto", "#4ec994")
    hover   = t.cor("interface.fundo_item_selecionado", "#1f3d1f")
    pressed = t.cor("interface.fundo_item_hover",       "#1a2e1a")

    btn = QPushButton(texto)
    btn.setCursor(Qt.PointingHandCursor)
    btn.setStyleSheet(f"""
        QPushButton {{
            background-color: {cor_fundo};
            color: {cor_texto};
            border: none;
            border-radius: 4px;
            padding: 6px 10px;
            font-size: 11px;
            text-align: left;
        }}
        QPushButton:hover {{
            background-color: {hover};
        }}
        QPushButton:pressed {{
            background-color: {pressed};
        }}
        QPushButton:focus {{
            outline: none;
        }}
        QPushButton:disabled {{
            background-color: #1a1a1a;
            color: #444;
        }}
    """)

    return btn

def _sep():
    linha = QFrame()
    linha.setFrameShape(QFrame.HLine)
    linha.setStyleSheet("color:#222; margin:2px 0;")

    return linha
