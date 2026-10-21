# 📁 _BUSCA_/painel_busca_global.py
# coding: utf-8
"""
PainelBuscaGlobal — widget de resultados de busca no projeto.

Abre como aba dentro do TerminalTabWidget (igual PowerShell, Run, etc.).
A visibilidade é gerenciada pelo TerminalTabWidget — não use show()/hide() diretamente.
Agrupa resultados por arquivo (QTreeWidget expansível/recolhível).
Interface compacta: toda a barra de controle numa única linha.
Substitui globalmente ou por arquivo selecionado (checkbox).
Destaca o termo buscado com cor diferente em cada linha de resultado.

API pública:
  set_termo(termo)           — preenche campo "De:" (chamado por cb_grep_init)
  limpar()                   — limpa resultados E o campo De: (chame antes de nova busca)
  mostrar()                  — no-op (compatibilidade; quem abre a aba é o TerminalTabWidget)
  adicionar_resultado(r)     — callback de GrepThread / AnotacoesThread
  busca_concluida()          — callback de fim de busca
  contar_resultados() → int  — quantidade de ocorrências acumuladas
  focar_lista()              — move o foco pra árvore
"""
import os
import re
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTreeWidget, QTreeWidgetItem,
    QStyledItemDelegate, QStyle, QApplication,
)
from PySide6.QtCore import Qt, Signal, QRect
from PySide6.QtGui import QFont, QColor, QPainter
from _BUSCA_.modelo_resultado import TipoBusca
from _LOG_.log import log
_ARQ = "painel_busca_global.py"

_COR_ARQUIVO     = QColor("#d8a86e")   # laranja — arquivo (pai, ativo)
_COR_ARQUIVO_OFF = QColor("#554433")   # laranja escuro — arquivo (pai, desmarcado)
_COR_MATCH       = QColor("#9a9a9a")   # cinza — linha de resultado (ativa)
_COR_MATCH_OFF   = QColor("#444444")   # cinza escuro — resultado desmarcado
_COR_HL_BG       = QColor("#1a4a6e")   # azul escuro — fundo do termo destacado
_COR_HL_FG       = QColor("#e8d44d")   # amarelo — texto do termo destacado

# ─── Delegate de destaque ────────────────────────────────────────────────────

class _DelegateMatch(QStyledItemDelegate):
    """Pinta a substring buscada com fundo/cor de destaque nas linhas de resultado."""

    def __init__(self, termo_getter, parent=None):
        super().__init__(parent)
        self._get_termo = termo_getter

    def paint(self, painter: QPainter, option, index):
        if index.data(Qt.UserRole + 1) is not None:
            super().paint(painter, option, index)
            return

        resultado = index.data(Qt.UserRole)
        if not resultado:
            super().paint(painter, option, index)
            return

        termo = self._get_termo().strip()
        texto = index.data(Qt.DisplayRole) or ""

        if not termo:
            super().paint(painter, option, index)
            return

        t_low  = termo.lower()
        tx_low = texto.lower()
        pos    = tx_low.find(t_low)

        if pos < 0:
            super().paint(painter, option, index)
            return

        self.initStyleOption(option, index)
        widget = option.widget
        style  = widget.style() if widget else QApplication.style()
        style.drawPrimitive(QStyle.PE_PanelItemViewItem, option, painter, widget)

        t_len   = len(termo)
        parte_a = texto[:pos]
        parte_m = texto[pos : pos + t_len]
        parte_b = texto[pos + t_len :]

        fm   = option.fontMetrics
        rect = option.rect.adjusted(6, 0, -4, 0)
        x    = rect.left()
        y    = rect.top()
        h    = rect.height()

        if option.state & QStyle.State_Selected:
            cor_base = option.palette.highlightedText().color()
        else:
            cor_fg_item = index.data(Qt.ForegroundRole)
            cor_base = cor_fg_item.color() if cor_fg_item else _COR_MATCH

        painter.save()
        painter.setFont(option.font)

        def _draw(s, cor, bg=None):
            nonlocal x
            w = fm.horizontalAdvance(s)
            if bg:
                painter.fillRect(QRect(x, y + 2, w, h - 4), bg)
            painter.setPen(cor)
            painter.drawText(QRect(x, y, w, h),
                             Qt.AlignVCenter | Qt.TextSingleLine, s)
            x += w

        if parte_a:
            _draw(parte_a, cor_base)
        _draw(parte_m, _COR_HL_FG, bg=_COR_HL_BG)
        if parte_b:
            _draw(parte_b, cor_base)

        painter.restore()

# ─── Painel principal ────────────────────────────────────────────────────────

class PainelBuscaGlobal(QWidget):
    """
    Widget de busca no projeto — abre como aba no TerminalTabWidget.
    NÃO é um QDockWidget: não use addDockWidget, show(), hide() diretamente.
    O TerminalTabWidget gerencia a visibilidade via abrir_aba_busca_global().
    """

    abrir_resultado = Signal(str, int, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._total: int = 0
        self._itens_arq: dict[str, QTreeWidgetItem] = {}
        self._de_auto: bool = True
        self._ignore_next_click: bool = False
        self._construir_ui()

    # ── Construção ──────────────────────────────────────────────────────────

    def _construir_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(3)

        # ── LINHA ÚNICA: status | De → Para | Substituir | ⊞ | ⊟ ──────
        barra = QHBoxLayout()
        barra.setSpacing(5)

        self._label_status = QLabel("Aguardando busca…")
        self._label_status.setStyleSheet(
            "color:#777;font-size:11px;min-width:120px;"
        )
        barra.addWidget(self._label_status, stretch=3)

        _lbl = "color:#555;font-size:11px;"
        _inp = (
            "QLineEdit{background:#111;color:#ddd;"
            "border:1px solid #2a2a2a;border-radius:2px;"
            "padding:1px 5px;font-size:11px;max-height:20px;}"
            "QLineEdit:focus{border:1px solid #444;}"
        )
        _btn_plano = (
            "QPushButton{color:#555;background:transparent;border:none;"
            "font-size:12px;padding:1px 5px;}"
            "QPushButton:hover{color:#aaa;}"
        )

        lbl_de = QLabel("De:")
        lbl_de.setStyleSheet(_lbl)
        barra.addWidget(lbl_de)

        self._input_de = QLineEdit()
        self._input_de.setPlaceholderText("termo")
        self._input_de.setStyleSheet(_inp)
        self._input_de.setFixedHeight(22)
        self._input_de.textEdited.connect(self._ao_editar_de)
        barra.addWidget(self._input_de, stretch=2)

        seta = QLabel("→")
        seta.setStyleSheet("color:#444;font-size:12px;")
        barra.addWidget(seta)

        self._input_para = QLineEdit()
        self._input_para.setPlaceholderText("substituir por…")
        self._input_para.setStyleSheet(_inp)
        self._input_para.setFixedHeight(22)
        barra.addWidget(self._input_para, stretch=2)

        self._btn_sub = QPushButton("Substituir tudo")
        self._btn_sub.setStyleSheet(
            "QPushButton{background:#1e3a5f;color:#bbb;border:none;"
            "border-radius:2px;padding:2px 9px;font-size:11px;max-height:22px;}"
            "QPushButton:hover{background:#264f78;color:#e0e0e0;}"
        )
        self._btn_sub.clicked.connect(self._substituir_tudo)
        barra.addWidget(self._btn_sub)

        self._btn_expandir = QPushButton("⊞")
        self._btn_expandir.setToolTip("Expandir tudo")
        self._btn_expandir.setStyleSheet(_btn_plano)
        self._btn_expandir.setFixedWidth(22)
        self._btn_expandir.clicked.connect(lambda: self._arvore.expandAll())
        barra.addWidget(self._btn_expandir)

        self._btn_recolher = QPushButton("⊟")
        self._btn_recolher.setToolTip("Recolher tudo")
        self._btn_recolher.setStyleSheet(_btn_plano)
        self._btn_recolher.setFixedWidth(22)
        self._btn_recolher.clicked.connect(lambda: self._arvore.collapseAll())
        barra.addWidget(self._btn_recolher)

        layout.addLayout(barra)

        # ── Árvore de resultados ─────────────────────────────────────
        self._arvore = QTreeWidget()
        self._arvore.setHeaderHidden(True)
        self._arvore.setIndentation(14)
        self._arvore.setAnimated(True)
        self._arvore.setUniformRowHeights(False)
        self._arvore.setStyleSheet("""
            QTreeWidget {
                background-color: #070706;
                color: #e0e0e0;
                border: none;
                font-size: 12px;
            }
            QTreeWidget::item { padding: 2px 4px; }
            QTreeWidget::item:selected { background-color: #264f78; }
            QTreeWidget::item:hover    { background-color: #1a2a3a; }
            QTreeWidget::branch { background: #070706; }
        """)
        mono = QFont("hein_Codigo", 11)
        mono.setStyleHint(QFont.Monospace)
        self._arvore.setFont(mono)

        self._delegate = _DelegateMatch(
            termo_getter=lambda: self._input_de.text(),
            parent=self._arvore,
        )
        self._arvore.setItemDelegate(self._delegate)

        self._arvore.itemClicked.connect(self._ao_clicar)
        self._arvore.itemActivated.connect(self._ao_ativar)
        self._arvore.itemChanged.connect(self._ao_checkbox_mudou)
        self._arvore.itemExpanded.connect(self._ao_expandir)
        self._arvore.itemCollapsed.connect(self._ao_recolher)

        layout.addWidget(self._arvore)

    # ── API pública ──────────────────────────────────────────────────────────

    def set_termo(self, termo: str):
        """Preenche o campo 'De:' com o termo buscado."""
        self._input_de.setText(termo)
        self._de_auto = True

    def limpar(self):
        """Limpa resultados E o campo De:. Chame antes de iniciar nova busca."""
        self._arvore.clear()
        self._itens_arq.clear()
        self._total = 0
        self._de_auto = True
        self._input_de.clear()
        self._label_status.setText("Buscando…")

    def mostrar(self):
        """No-op — compatibilidade. Quem abre/foca a aba é o TerminalTabWidget."""
        pass

    def adicionar_resultado(self, resultado):
        """Callback: recebe cada ResultadoBusca emitido pelo GrepThread."""
        if self._de_auto and getattr(resultado, "termo", "") and not self._input_de.text():
            self._input_de.setText(resultado.termo)

        if resultado.tipo == TipoBusca.COMANDO:
            item = QTreeWidgetItem(self._arvore)
            item.setText(0, resultado.titulo)
            item.setData(0, Qt.UserRole, resultado)
            self._total += 1
            self._label_status.setText(f"{self._total} resultado(s)…")
            return

        caminho = resultado.caminho

        if caminho not in self._itens_arq:
            pai = self._criar_item_arquivo(caminho, resultado)
            self._itens_arq[caminho] = pai
        else:
            pai = self._itens_arq[caminho]

        filho = QTreeWidgetItem(pai)
        num_linha = resultado.linha + 1
        filho.setText(0, f"  {num_linha:>5}   {resultado.titulo.strip()}")
        filho.setData(0, Qt.UserRole, resultado)
        filho.setForeground(0, _COR_MATCH)

        self._atualizar_label_pai(pai)

        self._total += 1
        self._label_status.setText(f"{self._total} ocorrência(s)…")

    def contar_resultados(self) -> int:
        return self._total

    def focar_lista(self):
        self._arvore.setFocus()
        if self._arvore.topLevelItemCount() and not self._arvore.currentItem():
            self._arvore.setCurrentItem(self._arvore.topLevelItem(0))

    def busca_concluida(self):
        n_arq = len(self._itens_arq)
        if self._total:
            self._label_status.setText(
                f"{self._total} ocorrência(s) em {n_arq} arquivo(s)."
            )
        else:
            self._label_status.setText("Nenhum resultado encontrado.")

    # ── Helpers internos ─────────────────────────────────────────────────────

    def _criar_item_arquivo(self, caminho: str, resultado) -> QTreeWidgetItem:
        relpath = resultado.subtitulo.split("  linha")[0].strip()
        pai = QTreeWidgetItem(self._arvore)
        pai.setData(0, Qt.UserRole + 1, caminho)
        pai.setData(0, Qt.UserRole + 2, relpath)
        self._arvore.blockSignals(True)
        pai.setCheckState(0, Qt.Checked)
        self._arvore.blockSignals(False)
        self._atualizar_label_pai(pai)
        pai.setForeground(0, _COR_ARQUIVO)
        fonte_arq = QFont("hein_Codigo", 11)
        fonte_arq.setStyleHint(QFont.Monospace)
        pai.setFont(0, fonte_arq)
        pai.setExpanded(True)
        return pai

    def _atualizar_label_pai(self, pai: QTreeWidgetItem):
        relpath = pai.data(0, Qt.UserRole + 2) or ""
        count   = pai.childCount()
        icone   = "▼" if pai.isExpanded() else "▶"
        pai.setText(0, f"{icone}  {relpath}   [{count}]")

    def _ao_editar_de(self):
        self._de_auto = False

    # ── Expand / Collapse individual ─────────────────────────────────────────

    def _ao_clicar(self, item: QTreeWidgetItem, coluna: int):
        if self._ignore_next_click:
            self._ignore_next_click = False
            return
        if item.data(0, Qt.UserRole + 1) is not None:
            item.setExpanded(not item.isExpanded())

    def _ao_expandir(self, item: QTreeWidgetItem):
        if item.data(0, Qt.UserRole + 1) is not None:
            self._atualizar_label_pai(item)

    def _ao_recolher(self, item: QTreeWidgetItem):
        if item.data(0, Qt.UserRole + 1) is not None:
            self._atualizar_label_pai(item)

    # ── Checkbox individual ───────────────────────────────────────────────────

    def _ao_checkbox_mudou(self, item: QTreeWidgetItem, coluna: int):
        if item.data(0, Qt.UserRole + 1) is None:
            return
        self._ignore_next_click = True
        checked = item.checkState(0) == Qt.Checked
        cor_pai   = _COR_ARQUIVO if checked else _COR_ARQUIVO_OFF
        cor_filho = _COR_MATCH   if checked else _COR_MATCH_OFF
        item.setForeground(0, cor_pai)
        for i in range(item.childCount()):
            item.child(i).setForeground(0, cor_filho)

    # ── Substituição ──────────────────────────────────────────────────────────

    def _substituir_tudo(self):
        de   = self._input_de.text().strip()
        para = self._input_para.text()

        if not de:
            self._label_status.setText("Preencha o campo 'De:' antes de substituir.")
            return
        if not self._itens_arq:
            self._label_status.setText("Nenhum resultado para substituir.")
            return
        if de == para:
            self._label_status.setText("O termo de destino é idêntico ao original.")
            return

        padrao    = re.compile(re.escape(de), re.IGNORECASE)
        trocados  = 0
        ignorados = 0
        erros     = 0

        for caminho, pai in list(self._itens_arq.items()):
            if pai.checkState(0) != Qt.Checked:
                ignorados += 1
                continue
            try:
                with open(caminho, encoding="utf-8", errors="ignore") as f:
                    conteudo = f.read()
                novo = padrao.sub(para, conteudo)
                if novo != conteudo:
                    with open(caminho, "w", encoding="utf-8") as f:
                        f.write(novo)
                    trocados += 1
            except Exception as e:
                log.aviso(_ARQ, "_substituir_tudo", f"erro em {caminho}: {e}")
                erros += 1

        partes = [f"'{de}' → '{para}' em {trocados} arquivo(s)."]
        if ignorados:
            partes.append(f"{ignorados} desmarcado(s).")
        if erros:
            partes.append(f"{erros} erro(s) — veja o log.")
        else:
            partes.append("Reabra os arquivos para ver.")
        self._label_status.setText("  ".join(partes))

    # ── Interação ─────────────────────────────────────────────────────────────

    def _ao_ativar(self, item: QTreeWidgetItem, coluna: int = 0):
        resultado = item.data(0, Qt.UserRole)
        if not resultado:
            return
        if resultado.tipo == TipoBusca.COMANDO and callable(resultado.acao):
            log.debug(_ARQ, "_ao_ativar", f"executando comando: {resultado.titulo}")
            try:
                resultado.acao()
            except Exception as e:
                log.erro(_ARQ, "_ao_ativar", f"erro ao executar '{resultado.titulo}': {e}")
        else:
            self.abrir_resultado.emit(
                resultado.caminho,
                resultado.linha,
                resultado.coluna if resultado.coluna else 0,
            )
