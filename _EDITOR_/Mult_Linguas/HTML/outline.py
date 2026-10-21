# _EDITOR_/Mult_Linguas/HTML/outline.py
"""
Preview de HTML para o PainelOutline.
Extraído de _EDITOR_/Outline/painel_outline.py na Fase 2.
"""


def popular_preview_html(preview_widget, codigo: str) -> None:
    """Exibe HTML renderizado no QTextBrowser do outline."""
    from _CONFIGURA_.gerenciador_tema import tema_global
    t     = tema_global()
    fundo = t.cor("editor.fundo", "#080808")
    preview_widget.setHtml(
        f'<div style="background:{fundo};min-height:100%;padding:4px;">'
        + codigo
        + '</div>'
    )
