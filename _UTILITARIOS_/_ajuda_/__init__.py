# 📁 _UTILITARIOS_/_ajuda_/__init__.py
"""
Módulo central dos botões de ajuda (?) da IDE.

Objetivo: toda tela que tiver um botãozinho de "?" usa a MESMA função pra
criar o botão e o MESMO jeito de mostrar o popup — assim o visual fica
padronizado (ícone minimalista, só acende no hover) e o conteúdo de cada
tela fica isolado em um arquivo próprio, fácil de achar e editar depois.

Como usar em uma tela nova (ex: dentro do __init__ de um painel/barra):

    from _UTILITARIOS_._ajuda_ import criar_botao_ajuda
    from _UTILITARIOS_._ajuda_.conteudos import minha_tela as _ajuda_minha_tela

    self._btn_ajuda = criar_botao_ajuda(
        _ajuda_minha_tela.texto,
        titulo="Como usar X",
        tooltip="Como usar X",
        parent=self,
    )
    layout.addWidget(self._btn_ajuda)

Onde fica o conteúdo:
- Cada tela tem seu próprio arquivo em `_ajuda_/conteudos/<nome>.py`,
  expondo uma função `texto() -> str` que devolve o HTML (RichText) do
  popup. Ver `_ajuda_/conteudos/busca.py` (dinâmico, lê atalhos.json na
  hora) e `_ajuda_/conteudos/tarefas.py` (estático) como exemplo.
- `texto()` é chamada só no clique — então se o conteúdo depender de algo
  que muda em tempo real (atalho remapeado, curso sendo editado, etc.),
  ele sempre mostra o estado atual, nunca fica desatualizado.

Link para o site:
- Se a tela tiver uma página de ajuda completa no site, passe
  `link="https://..."` pra `criar_botao_ajuda` — aparece um botão extra
  "Abrir no site" dentro do popup.

Cores:
- O botão em si é sempre transparente/neutro (ver `_ESTILO_ICONE` abaixo).
- Dentro do texto de ajuda, pegue a cor de destaque do tema ATUAL — nunca
  hardcode uma cor fixa:
      from _CONFIGURA_.gerenciador_tema import tema_global
      verde = tema_global().cor("grafo.no_texto", "#4ec994")
  (é o mesmo padrão usado em qualquer outro lugar da IDE que lê cor do tema)
"""
from PySide6.QtCore import Qt, QSize
from PySide6.QtWidgets import QPushButton, QMessageBox
from _UTILITARIOS_.icones import icone_tema
from _CONFIGURA_.gerenciador_tema import tema_global

_ESTILO_ICONE = (
    "QPushButton { background: transparent; border: none; }"
    "QPushButton:hover { background: rgba(255,255,255,0.07); border-radius: 3px; }"
)


def criar_botao_ajuda(conteudo, *, titulo: str = "Ajuda", link: str | None = None,
                       tooltip: str = "Ajuda", parent=None) -> QPushButton:
    """
    Cria o botão-ícone (?) padrão — mesmo estilo minimalista em toda a IDE
    (ícone só, 22x22, transparente, só acende no hover).

    conteudo: string ou função `() -> str` com o HTML (RichText) do popup.
              Use função quando o texto depender de algo que pode mudar
              (atalhos, config do usuário, etc.) — ela só é chamada no
              clique, então nunca fica desatualizada.
    link:     URL opcional. Se informado, o popup ganha um botão
              "Abrir no site" que abre essa URL no navegador padrão.
    """
    btn = QPushButton(parent)
    btn.setIcon(icone_tema("mdi.help-circle-outline"))
    btn.setIconSize(QSize(14, 14))
    btn.setFixedSize(22, 22)
    btn.setCursor(Qt.PointingHandCursor)
    btn.setToolTip(tooltip)
    btn.setStyleSheet(_ESTILO_ICONE)
    btn.clicked.connect(lambda: mostrar_ajuda(btn, titulo, conteudo, link))

    return btn


def mostrar_ajuda(parent, titulo: str, conteudo, link: str | None = None) -> None:
    """
    Abre o popup de ajuda (QMessageBox com RichText), no estilo/cores do
    tema atual. Chamado automaticamente pelo botão do `criar_botao_ajuda`
    — só use direto se precisar disparar a ajuda sem passar por um botão.
    """
    html = conteudo() if callable(conteudo) else str(conteudo)
    t = tema_global()

    msg = QMessageBox(parent)
    msg.setWindowTitle(titulo)
    msg.setTextFormat(Qt.TextFormat.RichText)
    msg.setText(html)
    msg.setStyleSheet(
        f"QMessageBox {{ background: {t.cor('grafo.no_fundo', '#0d1a0d')}; "
        f"color: {t.cor('interface.texto', '#e0e0e0')}; }}"
    )

    if link:
        btn_site = msg.addButton("Abrir no site  ↗", QMessageBox.ActionRole)
        btn_site.clicked.connect(lambda: _abrir_link(link))

    msg.exec()


def _abrir_link(url: str) -> None:
    from PySide6.QtGui import QDesktopServices
    from PySide6.QtCore import QUrl
    QDesktopServices.openUrl(QUrl(url))
