# 📁 _APP_/navegador_abas.py
from PySide6.QtCore    import Qt, QObject, QEvent
from PySide6.QtWidgets import QWidget, QVBoxLayout, QListWidget, QListWidgetItem, QApplication
from _CONFIGURA_.gerenciador_tema import tema_global

class NavegadorAbas(QObject):
    """
    Ctrl+Tab       → aba anterior na ordem MRU (Most Recently Used)
    Ctrl+Shift+Tab → avança na lista MRU
    Soltar Ctrl    → confirma seleção e fecha popup
    Clique no popup → navega direto para a aba clicada
    """

    def __init__(self, tab_widget, barra_aba_topo, parent=None):
        super().__init__(parent)
        self._tabs   = tab_widget
        self._barra  = barra_aba_topo
        self._popup  = None
        self._indice_mru = 0          # posição atual na lista MRU
        self._lista_mru: list[int] = []  # índices das abas por ordem de uso

        # conecta para atualizar MRU quando aba muda
        self._tabs.currentChanged.connect(self._ao_trocar_aba)

    def _ao_trocar_aba(self, indice: int):
        """Atualiza a lista MRU quando o usuário troca de aba normalmente."""
        if self._popup is not None:
            return  # durante navegação Ctrl+Tab, não atualiza MRU

        if indice in self._lista_mru:
            self._lista_mru.remove(indice)
        self._lista_mru.insert(0, indice)
        # limpa índices inválidos
        total = self._tabs.count()
        self._lista_mru = [i for i in self._lista_mru if i < total]

    def _mru_valida(self) -> list[int]:
        """Retorna lista MRU com apenas índices válidos e abas com arquivo."""
        total = self._tabs.count()
        validos = [i for i in self._lista_mru if i < total]
        for i in range(total):
            if i not in validos:
                validos.append(i)
        # ← ADICIONA ISSO: remove abas sem arquivo (vazias)
        validos = [i for i in validos
                   if getattr(self._tabs.widget(i), "file_path", None)
                   or self._tabs.tabText(i).strip()]

        return validos

    def eventFilter(self, obj, event):
        try:
            if event.type() == QEvent.KeyPress:
                key   = event.key()
                mod   = event.modifiers()
                ctrl  = bool(mod & Qt.ControlModifier)
                shift = bool(mod & Qt.ShiftModifier)

                if ctrl and key == Qt.Key_Tab:
                    self._navegar(1 if shift else -1)

                    return True

            if event.type() == QEvent.KeyRelease:
                if event.key() == Qt.Key_Control:
                    self._confirmar()

                    return False

            return False

        except Exception:
            return False

    def _navegar(self, direcao: int):
        mru = self._mru_valida()
        total = len(mru)
        if total < 2:
            return

        if self._popup is None:
            self._indice_mru = 0      # ← posição atual na MRU
            self._criar_popup(mru)
            # já move direto na primeira vez, sem esperar o segundo aperto
            self._indice_mru = 1      # ← MUDA ISSO: começa em 1, não em 0
            self._popup_lista.setCurrentRow(self._indice_mru)
            self._tabs.setCurrentIndex(mru[self._indice_mru])

            return

        self._indice_mru = (self._indice_mru + direcao) % total
        self._popup_lista.setCurrentRow(self._indice_mru)
        self._tabs.setCurrentIndex(mru[self._indice_mru])

    # ⚠️  função grande (54 linhas)
    def _criar_popup(self, mru: list[int]):
        self._popup = QWidget(self._tabs, Qt.Tool | Qt.FramelessWindowHint)
        self._popup.setObjectName("NavegadorAbasPopup")
        _t      = tema_global()
        _fundo  = _t.cor("menu_contexto.fundo",       "#1a1a2e")
        _borda  = _t.cor("menu_contexto.borda",       "#4a90d9")
        _texto  = _t.cor("menu_contexto.texto",       "#e0e0e0")
        _hover  = _t.cor("menu_contexto.hover",       "#1e3a5f")
        _sel    = _t.cor("menu_contexto.selecionado", "#264f78")
        self._popup.setStyleSheet(f"""
            QWidget#NavegadorAbasPopup {{
                background: {_fundo};
                border: 1px solid {_borda};
                border-radius: 6px;
            }}
            QListWidget {{
                background: transparent;
                color: {_texto};
                border: none;
                font-size: 12px;
                padding: 4px;
            }}
            QListWidget::item {{
                padding: 6px 12px;
                border-radius: 3px;
            }}
            QListWidget::item:selected {{
                background: {_sel};
                color: #ffffff;
            }}
            QListWidget::item:hover {{
                background: {_hover};
                cursor: pointer;
            }}
        """)

        layout = QVBoxLayout(self._popup)
        layout.setContentsMargins(4, 4, 4, 4)

        self._popup_lista = QListWidget()
        self._popup_lista.setMouseTracking(True)

        for idx in mru:
            texto = self._tabs.tabText(idx).lstrip("*").strip()
            item  = QListWidgetItem(f"  {texto}")
            self._popup_lista.addItem(item)

        # clique no item do popup navega direto
        self._popup_lista.itemClicked.connect(self._ao_clicar_item)

        layout.addWidget(self._popup_lista)
        self._popup.setFixedWidth(260)
        self._popup.setFixedHeight(min(40 + len(mru) * 32, 400))

        geo = self._tabs.geometry()
        cx  = self._tabs.mapToGlobal(geo.center())
        px  = cx.x() - self._popup.width()  // 2
        py  = cx.y() - self._popup.height() // 2
        self._popup.move(px, py)
        self._popup.show()

    def _ao_clicar_item(self, item):
        """Clique direto num item do popup — navega e fecha."""
        row = self._popup_lista.row(item)
        mru = self._mru_valida()
        if 0 <= row < len(mru):
            self._indice_mru = row
            self._confirmar()

    def _confirmar(self):
        if self._popup is None:
            return

        mru = self._mru_valida()
        self._popup.close()
        self._popup.deleteLater()
        self._popup = None

        if 0 <= self._indice_mru < len(mru):
            aba_alvo = mru[self._indice_mru]
            self._tabs.setCurrentIndex(aba_alvo)
            self._barra._reconstruir_abas()
