# 📁 _APP_/outdoor.py
from PySide6.QtWidgets import QWidget, QVBoxLayout, QStackedWidget
from PySide6.QtCore import Signal
from _APP_.dialogo_novo_projeto import PainelNovoProjeto
from _APP_.painel_boas_vindas import PainelBoasVindas
from _CONFIGURA_ import TITULO_APP

class Outdoor(QWidget):
    _TITULO_BOAS_VINDAS  = TITULO_APP
    _TITULO_NOVO_PROJETO = "Novo Projeto"

    novo_projeto_signal          = Signal()
    abrir_projeto_path_signal    = Signal(str)
    abrir_projeto_dialogo_signal = Signal()
    abrir_arquivo_signal         = Signal()
    titulo_mudou                 = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        # sem setStyleSheet aqui — o PainelBoasVindas já cuida do próprio fundo

        self._stack = QStackedWidget()
        layout.addWidget(self._stack)

        self._boas_vindas = PainelBoasVindas()
        self._boas_vindas.novo_projeto.connect(self._ir_para_novo_projeto)
        self._boas_vindas.abrir_projeto_path.connect(self.abrir_projeto_path_signal)
        self._boas_vindas.abrir_projeto_dialogo.connect(self.abrir_projeto_dialogo_signal)
        self._boas_vindas.abrir_arquivo.connect(self.abrir_arquivo_signal)
        self._stack.addWidget(self._boas_vindas)

        self._painel_novo_projeto = PainelNovoProjeto()
        self._painel_novo_projeto.criar_projeto.connect(self._repassar_criar_projeto)
        self._painel_novo_projeto.voltar.connect(self.mostrar_boas_vindas)
        self._stack.addWidget(self._painel_novo_projeto)

        self._stack.setCurrentWidget(self._boas_vindas)

    def _ir_para_novo_projeto(self):
        self._stack.setCurrentWidget(self._painel_novo_projeto)
        self.titulo_mudou.emit(self._TITULO_NOVO_PROJETO)

    def mostrar_boas_vindas(self):
        self._boas_vindas.atualizar_recentes()
        self._stack.setCurrentWidget(self._boas_vindas)
        self.titulo_mudou.emit(self._TITULO_BOAS_VINDAS)

    def mostrar_novo_projeto(self):
        self._ir_para_novo_projeto()

    def _repassar_criar_projeto(self, nome: str, destino: str):
        pass  # MainWindow conecta diretamente ao _painel_novo_projeto.criar_projeto

    def titulo_aba(self) -> str:
        return self._TITULO_BOAS_VINDAS
