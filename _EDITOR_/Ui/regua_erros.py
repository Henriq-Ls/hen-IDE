# 📁 _EDITOR_/Ui/regua_erros.py
# -*- coding: utf-8 -*-

import math
from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter, QColor, QPen, QBrush
from PySide6.QtWidgets import QWidget, QToolTip
from _CONFIGURA_ import LARGURA_ERRO
from _LOG_.log import log

def _largura_erro_config() -> int:
    """Lê largura_erro do configurar.json; fallback = LARGURA_ERRO do init."""
    try:
        from _CONFIGURA_.gerenciador_configurar import config_global

        return int(config_global().obter("gutter", "largura_erro", LARGURA_ERRO))

    except Exception:

        return LARGURA_ERRO

class ReguaErros(QWidget):
    """
    Régua de diagnósticos lateral — mostra erros, git, busca, cursor e breakpoints.
    """
    LARGURA = LARGURA_ERRO   # atualizado em __init__ via config

    def __init__(self, editor):
        super().__init__(editor)
        self._editor       = editor
        self._erros:       dict[int, str] = {}
        self._git:         dict[int, str] = {}
        self._busca:       list[int]      = []
        self._breakpoints: set[int]       = set()

        self.__class__.LARGURA = _largura_erro_config()
        self.setFixedWidth(self.LARGURA)
        self.setCursor(Qt.PointingHandCursor)
        self.setMouseTracking(True)

        try:
            from _CONFIGURA_.gerenciador_tema import tema_global
            _t = tema_global()

            self.cor_fundo = _t.qcolor("editor.fundo_calha", "#020202")

            self._COR_GIT = {
                "added": _t.qcolor("editor.git_adicionado", "#4ec994"),
                "modified": _t.qcolor("editor.git_modificado", "#e5c07b"),
                "deleted": _t.qcolor("editor.git_deletado", "#e06c75"),
            }
            self._cor_erro  = _t.qcolor("editor.erro",  "#e06c75")
            self._cor_aviso = _t.qcolor("editor.aviso", "#e5c07b")

        except Exception:
            self.cor_fundo = QColor("#020202")

            self._COR_GIT = {
                "added": QColor("#4ec994"),
                "modified": QColor("#e5c07b"),
                "deleted": QColor("#e06c75"),
            }
            self._cor_erro  = QColor("#e06c75")
            self._cor_aviso = QColor("#e5c07b")

    def set_erros(self, erros: dict[int, str]):
        if erros != self._erros:
            log.info(
                "regua_erros.py",
                "set_erros",
                f"regua recebeu {len(erros)}"
            )

        self._erros = erros
        self.update()
    def set_git_changes(self, mudancas: dict[int, str]):
        self._git = mudancas
        self.update()

    def set_busca(self, ocorrencias: list[int]):
        self._busca = list(ocorrencias)
        self.update()

    def set_breakpoints(self, bp: set[int]):
        self._breakpoints = set(bp)
        self.update()

    def _linha_em_y(self, y: float) -> int:
        """
        Converte posição Y (pixels) em número de linha 1-based.

        Usa math.ceil — inversa correta do int/floor usado em paintEvent:
          paint:  _y(L) = int((L-1)*h/total)   ← floor
          click:  L = ceil(y*total/h) + 1        ← ceil = inversa de floor

        Snap: se houver marcadores (erros ou ocorrências de busca) dentro
        de ±5 linhas, salta para o mais próximo — útil para clicar em
        marcadores pequenos (4px) em arquivos grandes.
        """
        total = max(1, self._editor.document().blockCount())
        h     = max(1, self.height())
        linha = int(math.ceil(y * total / h)) + 1
        linha = max(1, min(linha, total))

        # Snap para o marcador mais próximo dentro de ±5 linhas
        candidatos = list(self._erros.keys()) + list(self._busca)
        if candidatos:
            def _dist(l):
                return abs(int((l - 1) / total * h) - y)

            mais_proximo = min(candidatos, key=_dist)
            tolerancia   = max(4, int(h / total * 5))
            if _dist(mais_proximo) <= tolerancia:

                return mais_proximo

        return linha

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            linha = self._linha_em_y(event.position().y())
            self._editor.ir_para_linha(linha)

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        linha = self._linha_em_y(event.position().y())
        if linha in self._erros:
            msgs = getattr(self._editor, '_mensagens_erros', {})
            tipo = self._erros[linha]
            raw  = msgs.get(linha) or ("⚠  Aviso" if tipo == "warning" else "Erro")
            try:
                from _TRADUTION_.tradutor_erros import traduzir
                msg = traduzir(raw)
            except Exception:
                msg = raw
            QToolTip.showText(event.globalPosition().toPoint(), msg, self)
        else:
            QToolTip.hideText()

        super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        QToolTip.hideText()

        super().leaveEvent(event)

    # ⚠️  função grande (57 linhas)
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), self.cor_fundo)

        total = max(1, self._editor.document().blockCount())
        h = self.height()
        w = self.LARGURA

        def _y(linha: int) -> int:
            return int((linha - 1) / total * h)

        def _alt(linha: int) -> int:
            return max(3, int(h / total))

        for linha, tipo in self._git.items():
            cor = self._COR_GIT.get(tipo)
            if not cor:
                continue

            y = _y(linha)
            alt = 4 if tipo == "deleted" else _alt(linha)

            painter.fillRect(0, y, 5, alt, cor)

        painter.setPen(QPen(QColor("#FFB86C"), 1))
        painter.setBrush(Qt.NoBrush)

        for linha in self._busca:
            y = _y(linha)
            painter.drawRect(5, y, w - 6, 3)

        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setBrush(QBrush(QColor("#FF5555")))
        painter.setPen(Qt.NoPen)

        for linha in self._breakpoints:
            y = _y(linha)
            cx = w // 2
            painter.drawEllipse(cx - 3, y + 1, 6, 6)

        painter.setRenderHint(QPainter.Antialiasing, False)

        for linha, tipo in self._erros.items():
            cor = self._cor_erro if tipo == "error" else self._cor_aviso
            y = _y(linha)

            painter.fillRect(5, y, w - 5, 4, cor)

        linha_cursor = self._editor.textCursor().blockNumber() + 1
        y_cur = _y(linha_cursor)

        painter.setPen(QPen(QColor(255, 255, 255, 80), 1))
        painter.drawLine(0, y_cur, w, y_cur)

        painter.end()
