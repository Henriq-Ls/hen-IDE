# 📁 _PAINEL_ESQUERDO_/painel_abas_inferior.py
"""Painel inferior esquerdo com abas Git e Executável."""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QStackedWidget, QLabel,
)
from _UTILITARIOS_.icones import icone_tema
from PySide6.QtGui import QPainter, QColor, QPainterPath
from PySide6.QtCore import Qt, Signal
from _PAINEL_ESQUERDO_.Git.git_ui import PainelGitHub
from _PAINEL_ESQUERDO_.painel_executavel import PainelExecutavel
from _CONFIGURA_.gerenciador_tema import tema_global
from _CONFIGURA_ import BordaCompleta
from _LOG_.log import log

_ARQ = "painel_abas_inferior.py"


def _padding_h_inferior() -> int:
    """Lê padding_aba_h do JSON de configuração (fallback: 10)."""
    try:
        from _CONFIGURA_.gerenciador_configurar import config_global
        return int(config_global().obter("ui", "padding_aba_h", 10))
    except Exception:
        return 10


class _BarraAbas(QWidget):
    """Barra de abas inferior."""

    def __init__(self, parent=None):
        super().__init__(parent)


class AbaInferiorBotao(QPushButton):
    """Botão de aba inferior com cantos arredondados + pés em S."""

    def __init__(self, icone, texto, parent=None):
        super().__init__(parent)
        self.setProperty("ativa", "false")
        self.setCursor(Qt.PointingHandCursor)
        self._borda_cor    = "#888888"
        self._borda_larg   = 2
        self._borda_estilo = "solid"

        layout = QHBoxLayout(self)
        _ph = _padding_h_inferior()
        layout.setContentsMargins(_ph, 2, _ph, 2)
        layout.setSpacing(4)

        self._label_icone = QLabel()
        self._label_icone.setPixmap(icone.pixmap(16, 16))
        self._label_icone.setObjectName("aba_inferior_icone")
        self._label_icone.setAttribute(Qt.WA_TransparentForMouseEvents)

        self._label_texto = QLabel(texto)
        self._label_texto.setObjectName("aba_inferior_texto")
        self._label_texto.setAttribute(Qt.WA_TransparentForMouseEvents)

        layout.addWidget(self._label_icone)
        layout.addWidget(self._label_texto)

        from PySide6.QtGui import QFontMetrics
        fm    = QFontMetrics(self._label_texto.font())
        min_w = (_ph * 2) + 16 + 4 + fm.horizontalAdvance(texto) + 8
        self.setMinimumWidth(min_w)

    def atualizar_icone(self, icone):
        self._label_icone.setPixmap(icone.pixmap(16, 16))

    def atualizar_borda_aba(self, cor: str, larg: int, estilo: str):
        self._borda_cor    = cor
        self._borda_larg   = larg
        self._borda_estilo = estilo
        self.update()

    def _caminho_borda(self):
        """Contorno superior + laterais sem fechar o fundo (open path)."""
        w, h = self.width(), self.height()
        r = 4
        f = 8
        path = QPainterPath()
        path.moveTo(0, h)
        path.cubicTo(f * 0.5, h, f, h - f * 0.5, f, h - f)
        path.lineTo(f, r)
        path.quadTo(f, 0, f + r, 0)
        path.lineTo(w - f - r, 0)
        path.quadTo(w - f, 0, w - f, r)
        path.lineTo(w - f, h - f)
        path.cubicTo(w - f, h - f * 0.5, w - f * 0.5, h, w, h)
        return path

    def _caminho(self):
        """Retângulo com cantos superiores arredondados e pés em S."""
        w, h = self.width(), self.height()
        r = 4
        f = 8
        path = QPainterPath()
        path.moveTo(0, h)
        path.cubicTo(f * 0.5, h, f, h - f * 0.5, f, h - f)
        path.lineTo(f, r)
        path.quadTo(f, 0, f + r, 0)
        path.lineTo(w - f - r, 0)
        path.quadTo(w - f, 0, w - f, r)
        path.lineTo(w - f, h - f)
        path.cubicTo(w - f, h - f * 0.5, w - f * 0.5, h, w, h)
        path.closeSubpath()
        return path

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        t = tema_global()
        if self.property("ativa") == "true":
            cor = t.cor("interface.fundo_aba_ativa",   "#1a1f2e")
        else:
            cor = t.cor("interface.fundo_aba_inativa", "#1b242d")
        painter.fillPath(self._caminho(), QColor(cor))
        painter.end()
        super().paintEvent(event)


class PainelAbasInferior(QWidget):
    push_realizado   = Signal()
    commit_realizado = Signal()
    abrir_executavel_config = Signal(str)

    def __init__(self, tema: dict = None, parent=None):
        super().__init__(parent)
        self._tema = tema or tema_global().dados()
        self._construir()
        log.ok(_ARQ, "_construir", "PainelAbasInferior pronto")

    def _construir(self):
        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(0)

        barra = _BarraAbas()
        self._barra_abas = barra
        barra.setObjectName("barra_abas")
        barra.setStyleSheet("QPushButton { background: transparent; border: none; }")

        bl = QHBoxLayout(barra)
        bl.setContentsMargins(0, 4, 0, 0)
        bl.setSpacing(2)

        self._btn_git = self._criar_btn(icone_tema("fa5b.git-alt"), "Git")
        self._btn_exe = self._criar_btn(icone_tema("mdi.package-variant-closed"), "Exe")
        self._aplicar_cor_texto(0)

        bl.addWidget(self._btn_git)
        bl.addWidget(self._btn_exe)
        bl.addStretch()

        raiz.addWidget(barra)

        self._pilha = QStackedWidget()
        self._git   = PainelGitHub(tema=self._tema)
        self._executavel = PainelExecutavel()

        self._git.commit_realizado.connect(self.commit_realizado)
        self._git.push_realizado.connect(self.push_realizado)
        self._executavel.abrir_executavel_config.connect(self.abrir_executavel_config)

        self._pilha.addWidget(self._git)  # índice 0
        self._pilha.addWidget(self._executavel)  # índice 1

        raiz.addWidget(self._pilha, 1)

        def _obter_tab_git():
            from PySide6.QtCore import QRect, QPoint
            for child in self._barra_abas.children():
                if (hasattr(child, 'property') and child.property("ativa") == "true"
                        and hasattr(child, 'width') and hasattr(child, 'height')):
                    pos = child.mapTo(self, QPoint(0, 0))
                    return QRect(pos.x(), pos.y(), child.width(), child.height())
            return None

        self._borda_completa = BordaCompleta.criar(self, _obter_tab_git)

        self._btn_git.clicked.connect(lambda: self._trocar(0))
        self._btn_exe.clicked.connect(lambda: self._trocar(1))
        self._trocar(0)

    def atualizar_borda(self, cor: str, larg: int, estilo: str, raio: int = 8, sem_topo: bool = True):
        if hasattr(self, "_borda_completa"):
            self._borda_completa.atualizar(cor, larg, estilo)
        if hasattr(self._btn_git, "atualizar_borda_aba"):
            self._btn_git.atualizar_borda_aba(cor, larg, estilo)
        if hasattr(self._btn_exe, "atualizar_borda_aba"):
            self._btn_exe.atualizar_borda_aba(cor, larg, estilo)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "_borda_completa"):
            self._borda_completa.setGeometry(self.rect())
            self._borda_completa.raise_()

    def _criar_btn(self, icone, texto):
        return AbaInferiorBotao(icone, texto)

    def set_projeto(self, caminho: str):
        self._git.set_projeto(caminho)
        self._executavel.set_projeto(caminho)

    def set_arquivo_ativo(self, caminho_arquivo: str):
        """Pass-through: notifica o painel Git sobre o arquivo em foco no editor."""
        if hasattr(self._git, "set_arquivo_ativo"):
            self._git.set_arquivo_ativo(caminho_arquivo)

    @property
    def _tela_projeto(self):
        return self._git._tela_projeto

    def _aplicar_cor_texto(self, indice_ativo):
        cor_inativa = tema_global().cor("interface.texto_fraco", "#7094A1")
        cor_ativa   = tema_global().cor("interface.texto", "#FF4D9D")
        for indice, botao in ((0, self._btn_git), (1, self._btn_exe)):
            cor = cor_ativa if indice_ativo == indice else cor_inativa
            botao._label_texto.setStyleSheet(
                f"QLabel#aba_inferior_texto {{ color: {cor}; }}"
            )

    def conectar_painel_arquivos(self, painel) -> None:
        """Liga o PainelArquivos para ativar/desativar checkboxes de staging
        ao entrar/sair da aba Git. Chamar uma vez após criar os dois widgets."""
        self._painel_arquivos_ref = painel

    def _trocar(self, indice):
        indice = max(0, min(indice, self._pilha.count() - 1))
        if indice != 0 and hasattr(self, "_painel_arquivos_ref"):
            try:
                self._painel_arquivos_ref.sair_modo_staging()
            except Exception as exc:
                log.aviso(_ARQ, "_trocar", f"Não foi possível sair do staging: {exc}")
        self._pilha.setCurrentIndex(indice)
        for i, botao in ((0, self._btn_git), (1, self._btn_exe)):
            ativa = "true" if indice == i else "false"
            botao.setProperty("ativa", ativa)
            botao.style().unpolish(botao)
            botao.style().polish(botao)
            botao.update()
        self._aplicar_cor_texto(indice)
        if hasattr(self, "_barra_abas"):
            self._barra_abas.update()

    @property
    def executavel(self):
        return self._executavel

    def mostrar_executavel(self):
        self._trocar(1)

    def atualizar_tema(self, tema: dict = None):
        self._btn_git.atualizar_icone(icone_tema("fa5b.git-alt"))
        self._btn_exe.atualizar_icone(icone_tema("mdi.package-variant-closed"))
        self._aplicar_cor_texto(self._pilha.currentIndex())
        if hasattr(self._git, "atualizar_tema"):
            self._git.atualizar_tema(tema)
        if hasattr(self._executavel, "atualizar_tema"):
            self._executavel.atualizar_tema(tema)
