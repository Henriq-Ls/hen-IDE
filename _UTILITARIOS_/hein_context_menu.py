# 📁 _UTILITARIOS_/hein_context_menu.py
"""
Menu de contexto universal da hein IDE.
Cores vêm de thema.json > "menu_contexto".
Fallbacks hardcoded em _CONFIGURA_/__init__.py seção 22.

Uso:
    from _UTILITARIOS_.hein_context_menu import heinContextMenu
    itens = [
        ("Novo Arquivo", "mdi.file-plus-outline", self._criar_arquivo),
        None,  # separador
        ("Renomear",     "mdi.pencil-outline",     self._renomear),
        ("Apagar",       "mdi.delete-outline",     self._apagar),
    ]
    menu = heinContextMenu(parent=self, itens=itens)
    menu.acao("Apagar").setEnabled(False)  # desabilitar se necessário
    menu.exec(pos_global)
"""
from _UTILITARIOS_.icones import icone_tema
from PySide6.QtWidgets import QMenu
from _CONFIGURA_.gerenciador_tema import tema_global
from _CONFIGURA_ import (
    COR_MENU_CONTEXTO_FUNDO,
    COR_MENU_CONTEXTO_TEXTO,
    COR_MENU_CONTEXTO_TEXTO_DESATIV,
    COR_MENU_CONTEXTO_HOVER,
    COR_MENU_CONTEXTO_BORDA,
    COR_MENU_CONTEXTO_SEPARADOR,
    COR_MENU_CONTEXTO_ICONE,
    MENU_CONTEXTO_RAIO
)

class heinContextMenu(QMenu):
    """
    Menu de contexto estilizado, universal, sem emojis.
    Segue o tema ativo — editável pelo usuário em thema.json > "menu_contexto".
    """

    def __init__(self, parent=None, itens: list = None):
        super().__init__(parent)
        self._acoes: dict = {}
        self._aplicar_qss()
        if itens:
            self._popular(itens)

    # ── Estilo ────────────────────────────────────────────────────────

    def _aplicar_qss(self):
        t = tema_global()
        # Primário: thema.json | Fallback: __init__.py seção 22
        fundo       = t.cor("menu_contexto.fundo",            COR_MENU_CONTEXTO_FUNDO)
        texto       = t.cor("menu_contexto.texto",            COR_MENU_CONTEXTO_TEXTO)
        texto_hover = t.cor("menu_contexto.texto_hover",      "#ffffff")
        desativ     = t.cor("menu_contexto.texto_desativado", COR_MENU_CONTEXTO_TEXTO_DESATIV)
        hover       = t.cor("menu_contexto.item_hover",       COR_MENU_CONTEXTO_HOVER)
        borda       = t.cor("menu_contexto.borda",            COR_MENU_CONTEXTO_BORDA)
        sep         = t.cor("menu_contexto.separador",        COR_MENU_CONTEXTO_SEPARADOR)
        self.setStyleSheet(f"""
            QMenu {{
                background-color: {fundo};
                color: {texto};
                border: 1px solid {borda};
                border-radius: {MENU_CONTEXTO_RAIO};
                padding: 4px 0;
                font-size: 11px;
            }}
            QMenu::item {{
                padding: 5px 24px 5px 8px;
            }}
            QMenu::item:selected {{
                background-color: {hover};
                color: {texto_hover};
            }}
            QMenu::item:disabled {{
                color: {desativ};
            }}
            QMenu::separator {{
                height: 1px;
                background: {sep};
                margin: 3px 8px;
            }}
            QMenu::icon {{
                padding-left: 4px;
            }}
        """)

    # ── Montagem ──────────────────────────────────────────────────────

    def _popular(self, itens: list):
        t         = tema_global()
        cor_icone = t.cor("menu_contexto.icone", COR_MENU_CONTEXTO_ICONE)

        for item in itens:
            if item is None:
                self.addSeparator()
                continue

            label, icon_name, callback = item
            try:
                icone = icone_tema(icon_name, color=cor_icone)
                acao  = self.addAction(icone, label)
            except Exception:
                acao  = self.addAction(label)

            if callback is not None:
                acao.triggered.connect(callback)

            self._acoes[label] = acao

    # ── API pública ───────────────────────────────────────────────────

    def acao(self, label: str):
        """Retorna a QAction pelo label para habilitar/desabilitar externamente."""

        return self._acoes.get(label)

    def adicionar_submenu(self, label: str, icon_name: str, itens: list,
                          antes_de: str | None = None) -> 'heinContextMenu':
        """Adiciona item com submenu estilizado (mesmo visual do heinContextMenu).

        label     — texto do item pai no menu principal
        icon_name — ícone do item pai (ex: "mdi.file-plus-outline")
        itens     — lista de (label, icon, callback) | None para separadores
        antes_de  — label de outro item antes do qual inserir; None = no fim
        """
        from PySide6.QtWidgets import QMenu as _QMenu
        t         = tema_global()
        cor_icone = t.cor("menu_contexto.icone", COR_MENU_CONTEXTO_ICONE)

        # Cria o QMenu filho com o mesmo estilo
        sub = heinContextMenu(parent=self)
        sub._aplicar_qss()
        sub._popular(itens)
        sub.setTitle(label)

        try:
            icone   = icone_tema(icon_name, color=cor_icone)
            sub_acao = self.addMenu(sub)
            if sub_acao:
                sub_acao.setIcon(icone)
        except Exception:
            self.addMenu(sub)

        self._acoes[label] = sub.menuAction()

        if antes_de:
            ref = self._acoes.get(antes_de)
            if ref:
                self.removeAction(sub.menuAction())
                self.insertMenu(ref, sub)

        return sub

def aplicar_estilo_menu(menu) -> None:
    """Aplica o QSS do heinContextMenu em qualquer QMenu existente."""
    heinContextMenu._aplicar_qss(menu)

def aplicar_estilo_tooltip() -> None:
    """
    Aplica estilo unificado ao QToolTip da aplicação inteira.
    Usa as mesmas cores de menu_contexto.* do thema.json, garantindo
    visual consistente entre menus de contexto e tooltips.
    Chame sempre que o tema mudar (gerenciador_tema.aplicar_na_janela).
    """
    import re
    from PySide6.QtWidgets import QApplication
    t = tema_global()
    fundo = t.cor("menu_contexto.fundo",  COR_MENU_CONTEXTO_FUNDO)
    texto = t.cor("menu_contexto.texto",  COR_MENU_CONTEXTO_TEXTO)
    borda = t.cor("menu_contexto.borda",  COR_MENU_CONTEXTO_BORDA)
    raio  = MENU_CONTEXTO_RAIO
    qss_tip = (
        f"QToolTip {{"
        f" background-color: {fundo};"
        f" color: {texto};"
        f" border: 1px solid {borda};"
        f" border-radius: {raio};"
        f" padding: 4px 8px;"
        f" font-size: 11px;"
        f"}}"
    )
    app = QApplication.instance()
    if app is None:

        return

    atual = app.styleSheet()
    # Remove bloco QToolTip anterior para nao acumular
    atual = re.sub(r'QToolTip\s*\{[^}]*\}', '', atual, flags=re.DOTALL).strip()
    app.setStyleSheet((atual + "\n" + qss_tip) if atual else qss_tip)
