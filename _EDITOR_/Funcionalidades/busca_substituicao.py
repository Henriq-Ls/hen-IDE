# 📁 _EDITOR_/Funcionalidades/busca_substituicao.py
"""
Painel de busca e substituição integrado ao CodeEditor.
O campo de busca é auto-expansível: fica como uma linha quando vazio,
expande até MAX_LINHAS quando recebe um bloco colado.
"""
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout,
    QPlainTextEdit, QLineEdit, QPushButton, QLabel, QCheckBox, QTextEdit,
    QSizePolicy
)
from PySide6.QtCore import Qt, QRegularExpression, QSize, QTimer
from PySide6.QtGui import (
    QTextCursor, QTextDocument,
    QTextCharFormat, QColor, QKeyEvent
)

# ──────────────────────────────────────────────────────────────────────────────
# Campo de busca auto-expansível
# ──────────────────────────────────────────────────────────────────────────────

class _CampoBuscaExpandivel(QPlainTextEdit):
    """
    QPlainTextEdit que:
    - Começa com a altura de uma linha (igual a um QLineEdit).
    - Expande automaticamente até MAX_LINHAS quando o conteúdo aumenta.
    - Enter       → dispara busca (sem inserir nova linha).
    - Shift+Enter → insere nova linha (busca literal de bloco).
    """

    MAX_LINHAS = 6

    def __init__(self, placeholder: str = "", parent=None):
        super().__init__(parent)
        self.setPlaceholderText(placeholder)
        self.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setTabChangesFocus(False)

        # Conecta ao sinal de mudança de conteúdo — com defer para layout estar pronto
        self.document().contentsChanged.connect(self._agendar_ajuste)

    # ── cálculo de altura ──────────────────────────────────────────────

    def _linha_altura(self) -> int:
        """Altura em px de uma única linha de texto."""
        fm = self.fontMetrics()
        m  = self.contentsMargins()

        return fm.lineSpacing() + m.top() + m.bottom() + int(self.document().documentMargin()) * 2 + 6

    def _agendar_ajuste(self):
        """Adia o ajuste para o próximo ciclo do event loop (layout já atualizado)."""
        QTimer.singleShot(0, self._ajustar_altura)

    def _ajustar_altura(self):
        doc    = self.document()
        layout = doc.documentLayout()
        # Altura real do documento (inclui wrapping visual)
        doc_h  = int(layout.documentSize().height())
        lh     = self.fontMetrics().lineSpacing()
        if lh <= 0:

            return

        linhas_visuais = max(1, (doc_h + lh - 1) // lh)
        linhas = min(linhas_visuais, self.MAX_LINHAS)

        m = self.contentsMargins()
        overhead = m.top() + m.bottom() + int(doc.documentMargin()) * 2 + 6
        nova_h = lh * linhas + overhead

        if nova_h != self.height():
            self.setFixedHeight(nova_h)
            self.updateGeometry()
            pai = self.parentWidget()
            if pai:
                pai.adjustSize()
                pai._reposicionar() if hasattr(pai, "_reposicionar") else None

        # Scrollbar só se excedeu o limite
        if linhas_visuais > self.MAX_LINHAS:
            self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        else:
            self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

    # ── tamanho inicial ────────────────────────────────────────────────

    def sizeHint(self) -> QSize:
        return QSize(200, self._linha_altura())

    def minimumSizeHint(self) -> QSize:
        return QSize(100, self._linha_altura())

    # ── teclado ───────────────────────────────────────────────────────

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key_Escape:
            pai = self.parentWidget()
            if pai and hasattr(pai, "fechar"):
                pai.fechar()

            return

        # Enter sem Shift → próximo resultado
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            if event.modifiers() & Qt.ShiftModifier:
                super().keyPressEvent(event)
            else:
                pai = self.parentWidget()
                if pai and hasattr(pai, "_proximo"):
                    pai._proximo()

            return

        super().keyPressEvent(event)

    # ── compat QLineEdit ──────────────────────────────────────────────

    def text(self) -> str:
        return self.toPlainText()

    def setText(self, t: str):
        self.setPlainText(t)

# ──────────────────────────────────────────────────────────────────────────────
# Painel principal
# ──────────────────────────────────────────────────────────────────────────────

class PainelBuscaSubstituicao(QWidget):
    """
    Barra flutuante de busca/substituição.
    Deve ser filho do CodeEditor para ficar sobreposta a ele.

    Atalhos:
        Ctrl+F  → abre busca
        Ctrl+H  → abre busca + substituição
        Esc     → fecha
        Enter / F3 → próximo resultado
        Shift+F3   → resultado anterior
    """

    def __init__(self, editor):
        super().__init__(editor)
        self._editor = editor
        self._destaques: list = []
        self._resultado_atual = -1
        self._resultados: list = []

        self._timer_rebuscar = QTimer(self)
        self._timer_rebuscar.setSingleShot(True)
        self._timer_rebuscar.setInterval(300)
        self._timer_rebuscar.timeout.connect(self._buscar)
        # IMP-07 fix: NÃO conectar contentsChanged do editor ao timer.
        # Fazer isso fazia setExtraSelections() rolar o viewport até o resultado
        # ativo toda vez que o usuário digitava no editor — cursor puxado sozinho.

        self._construir_ui()
        self.hide()

    # ------------------------------------------------------------------
    # Construção da interface
    # ------------------------------------------------------------------

    # ⚠️  função grande (103 linhas)
    def _construir_ui(self):
        self.setObjectName("painel_busca")
        self.setStyleSheet("""
            #painel_busca {
                background-color: #1a1a2e;
                border: 1px solid #4a90d9;
                border-radius: 6px;
            }
            QPlainTextEdit, QLineEdit {
                background-color: #0d0d0d;
                color: #e0e0e0;
                border: 1px solid #333;
                border-radius: 3px;
                padding: 4px 8px;
                font-size: 13px;
                min-width: 200px;
            }
            QPlainTextEdit:focus, QLineEdit:focus { border-color: #4a90d9; }
            QPushButton {
                background-color: #2a2a2a;
                color: #e0e0e0;
                border: 1px solid #333;
                border-radius: 3px;
                padding: 4px 10px;
                font-size: 12px;
            }
            QPushButton:hover { background-color: #3a3a3a; }
            QLabel { color: #888; font-size: 12px; }
            QCheckBox { color: #888; font-size: 12px; }
        """)

        layout_principal = QVBoxLayout(self)
        layout_principal.setContentsMargins(8, 6, 8, 6)
        layout_principal.setSpacing(4)

        # ── Linha de busca ──
        linha_busca = QHBoxLayout()
        linha_busca.setSpacing(4)
        linha_busca.setAlignment(Qt.AlignTop)

        self._campo_busca = _CampoBuscaExpandivel("Buscar...", parent=self)
        self._campo_busca.document().contentsChanged.connect(self._ao_campo_busca_mudou)

        self._label_resultado = QLabel("0/0")
        self._label_resultado.setAlignment(Qt.AlignVCenter)

        btn_anterior = QPushButton("▲")
        btn_anterior.setFixedWidth(30)
        btn_anterior.setToolTip("Resultado anterior (Shift+F3)")
        btn_anterior.clicked.connect(self._anterior)

        btn_proximo = QPushButton("▼")
        btn_proximo.setFixedWidth(30)
        btn_proximo.setToolTip("Próximo resultado (F3)")
        btn_proximo.clicked.connect(self._proximo)

        self._chk_maiuscula = QCheckBox("Aa")
        self._chk_maiuscula.setToolTip("Diferenciar maiúsculas")
        self._chk_maiuscula.stateChanged.connect(self._buscar)

        self._chk_regex = QCheckBox(".*")
        self._chk_regex.setToolTip("Usar expressão regular")
        self._chk_regex.stateChanged.connect(self._buscar)

        btn_fechar = QPushButton("✕")
        btn_fechar.setFixedWidth(28)
        btn_fechar.setToolTip("Fechar (Esc)")
        btn_fechar.clicked.connect(self.fechar)

        linha_busca.addWidget(self._campo_busca)
        linha_busca.addWidget(self._label_resultado)
        linha_busca.addWidget(btn_anterior)
        linha_busca.addWidget(btn_proximo)
        linha_busca.addWidget(self._chk_maiuscula)
        linha_busca.addWidget(self._chk_regex)
        linha_busca.addStretch()
        linha_busca.addWidget(btn_fechar)

        layout_principal.addLayout(linha_busca)

        # ── Linha de substituição ──
        self._widget_substituicao = QWidget()
        linha_sub = QHBoxLayout(self._widget_substituicao)
        linha_sub.setContentsMargins(0, 0, 0, 0)
        linha_sub.setSpacing(4)

        self._campo_substituicao = QLineEdit()
        self._campo_substituicao.setPlaceholderText("Substituir por...")

        btn_substituir = QPushButton("Substituir")
        btn_substituir.clicked.connect(self._substituir)

        btn_substituir_tudo = QPushButton("Substituir tudo")
        btn_substituir_tudo.clicked.connect(self._substituir_tudo)

        linha_sub.addWidget(self._campo_substituicao)
        linha_sub.addWidget(btn_substituir)
        linha_sub.addWidget(btn_substituir_tudo)

        layout_principal.addWidget(self._widget_substituicao)
        self._widget_substituicao.hide()

        self.adjustSize()

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    def abrir_busca(self):
        self._cursor_antes_busca = QTextCursor(self._editor.textCursor())
        self._widget_substituicao.hide()
        self.show()
        self._reposicionar()
        self._campo_busca.setFocus()
        self._campo_busca.selectAll()
        QTimer.singleShot(0, self._buscar)

    def abrir_substituicao(self):
        self._widget_substituicao.show()
        self.show()
        self._reposicionar()
        self.adjustSize()
        self._campo_busca.setFocus()
        self._campo_busca.selectAll()

    def fechar(self):
        self._limpar_destaques()
        self.hide()
        self._editor.setFocus()
        if hasattr(self, '_cursor_antes_busca'):
            self._editor.setTextCursor(self._cursor_antes_busca)
            self._editor.ensureCursorVisible()

    # ------------------------------------------------------------------
    # Busca interna
    # ------------------------------------------------------------------

    # ⚠️  função grande (54 linhas)
    def _buscar(self):
        """Atualiza resultados e destaques SEM mover o cursor do editor.

        Usado quando o conteúdo do editor muda (IMP-03).
        Para busca interativa (usuário digitou algo), use _buscar_e_ir().
        """
        texto = self._campo_busca.toPlainText()
        self._limpar_destaques()
        self._resultados = []
        self._resultado_atual = -1

        if not texto:
            self._label_resultado.setText("0/0")

            return

        flags = QTextDocument.FindFlags()
        if self._chk_maiuscula.isChecked():
            flags |= QTextDocument.FindCaseSensitively

        documento = self._editor.document()
        cursor_busca = QTextCursor(documento)

        if self._chk_regex.isChecked():
            expressao = QRegularExpression(texto)
            if not self._chk_maiuscula.isChecked():
                expressao.setPatternOptions(
                    QRegularExpression.CaseInsensitiveOption
                )
            while True:
                cursor_busca = documento.find(expressao, cursor_busca)
                if cursor_busca.isNull():
                    break
                self._resultados.append(QTextCursor(cursor_busca))
        else:
            while True:
                cursor_busca = documento.find(texto, cursor_busca, flags)
                if cursor_busca.isNull():
                    break
                self._resultados.append(QTextCursor(cursor_busca))

        total = len(self._resultados)
        if not total:
            self._label_resultado.setText("Não encontrado")

            return

        # Resultado mais próximo do cursor atual (sem mover o editor)
        pos_atual = self._editor.textCursor().position()
        indice = min(range(total),
                     key=lambda i: abs(self._resultados[i].selectionStart() - pos_atual))
        self._resultado_atual = indice
        self._label_resultado.setText(f"{indice + 1}/{total}")
        self._atualizar_highlight_ativo(indice)

    def _ao_campo_busca_mudou(self):
        """Rebusca e rola apenas se o campo de busca tem foco (digitação do usuário).
        Se não tem foco, apenas atualiza os destaques sem mover o cursor — impede
        que mudanças programáticas no campo saltem o cursor do editor (IMP-07)."""
        if self._campo_busca.hasFocus():
            self._buscar_e_ir()
        else:
            self._buscar()

    def _buscar_e_ir(self):
        """Busca e rola o editor até o resultado mais próximo do cursor atual.

        Usado quando o usuário digita no campo de busca ou abre o painel.
        """
        self._buscar()
        if self._resultados and self._resultado_atual >= 0:
            self._editor.setTextCursor(
                QTextCursor(self._resultados[self._resultado_atual])
            )
            self._editor.ensureCursorVisible()

    def _proximo(self):
        if not self._resultados:

            return

        self._resultado_atual = (self._resultado_atual + 1) % len(self._resultados)
        self._ir_para_resultado(self._resultado_atual)

    def _anterior(self):
        if not self._resultados:

            return

        self._resultado_atual = (self._resultado_atual - 1) % len(self._resultados)
        self._ir_para_resultado(self._resultado_atual)

    def _atualizar_highlight_ativo(self, indice_ativo: int):
        from _CONFIGURA_.gerenciador_tema import tema_global
        _cor_hex  = tema_global().dados().get("editor.selecao", "#264f78")
        _base     = QColor(_cor_hex)
        _cor_norm = QColor(_base.red(), _base.green(), _base.blue(), 60)
        fmt_normal = QTextCharFormat()
        fmt_normal.setBackground(_cor_norm)
        fmt_ativo = QTextCharFormat()
        fmt_ativo.setBackground(QColor(_cor_hex))
        novas = []
        for i, cur in enumerate(self._resultados):
            sel = QTextEdit.ExtraSelection()
            sel.cursor = QTextCursor(cur)
            sel.format = fmt_ativo if i == indice_ativo else fmt_normal
            novas.append(sel)
        existentes_wave = [s for s in self._editor.extraSelections()
                           if s.format.underlineStyle() == QTextCharFormat.WaveUnderline]
        self._editor.setExtraSelections(existentes_wave + novas)
        self._destaques = novas

    def _ir_para_resultado(self, indice: int):
        if not self._resultados:

            return

        cursor = self._resultados[indice]
        self._editor.setTextCursor(cursor)
        self._editor.ensureCursorVisible()
        total = len(self._resultados)
        self._label_resultado.setText(f"{indice + 1}/{total}")
        self._atualizar_highlight_ativo(indice)

    def _limpar_destaques(self):
        existentes = [s for s in self._editor.extraSelections()
                      if s.format.underlineStyle() == QTextCharFormat.WaveUnderline]
        self._editor.setExtraSelections(existentes)
        self._destaques = []

    # ------------------------------------------------------------------
    # Substituição
    # ------------------------------------------------------------------

    def _substituir(self):
        if not self._resultados or self._resultado_atual < 0:

            return

        novo = self._campo_substituicao.text()
        cursor = self._resultados[self._resultado_atual]
        cursor.insertText(novo)
        self._buscar()

    def _substituir_tudo(self):
        if not self._resultados:

            return

        novo = self._campo_substituicao.text()
        for cursor in reversed(self._resultados):
            cursor.insertText(novo)
        self._buscar()

    # ------------------------------------------------------------------
    # Reposicionamento
    # ------------------------------------------------------------------

    def _reposicionar(self):
        """Reposiciona no canto superior direito, sem sobrepor o outline."""
        margem = 10
        largura = self.sizeHint().width()
        outline_w = self._editor._outline.width() if hasattr(self._editor, '_outline') else 0
        x = self._editor.width() - outline_w - largura - margem
        self.move(x, margem)
        self.adjustSize()
