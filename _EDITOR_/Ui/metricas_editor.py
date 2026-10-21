# 📁 _EDITOR_/Ui/metricas_editor.py
# -*- coding: utf-8 -*-
"""
MetricasEditor — cálculo de largura da calha e aplicação de margens do viewport.

╔══════════════════════════════════════════════════════════════════════════╗
║  ⚠️  ZONA CRÍTICA — NÃO MEXA SEM LER ESTE AVISO                         ║
╠══════════════════════════════════════════════════════════════════════════╣
║                                                                          ║
║  atualizar_margem — cache _cache_margem                                  ║
║     setViewportMargins redimensiona o viewport do QPlainTextEdit. Cada   ║
║     chamada desnecessária dispara ensureCursorVisible, que pode mover    ║
║     o scroll — causando o bug de salto visível na tela.                  ║
║     O cache (largura, topo) garante que setViewportMargins só é chamado  ║
║     quando as margens REALMENTE mudam.                                   ║
║     NUNCA remova o cache ou chame setViewportMargins incondicionalmente. ║
║                                                                          ║
║  Ordem de chamada correta em _pos_mostrar (sticky_scroll.py):            ║
║     1. metricas.atualizar_margem(topo=nova_h)   ← margem esq + topo     ║
║     2. editor._atualizar_geometria_outline()    ← corrige margem dir     ║
║     As duas devem sempre ser chamadas em sequência.                      ║
║                                                                          ║
╚══════════════════════════════════════════════════════════════════════════╝
"""
from _CONFIGURA_ import (
    LARGURA_GIT,    # barra git — fallback
    PADDINGS,       # espaço uniforme entre elementos — fallback
    LARGURA_GUITER, # zona BP — fallback
    LARGURA_SETA,   # seta de code folding — fallback
)

from _LOG_.log import log
_ARQ          = "metricas_editor.py"

class MetricasEditor:
    def __init__(self, editor):
        self.editor = editor
        self._cache_margem: tuple | None = None

    def largura_area_numeros(self) -> int: # Layout: [git][pad][BP][pad][números auto][seta][pad] | código
        area       = self.editor.area_numeros
        larg_digit = self.editor.fontMetrics().horizontalAdvance('0')
        digitos    = max(2, len(str(self.editor.document().blockCount())))

        return (area.larg_git

                + area.pad
                + area.larg_guiter
                + area.pad
                + larg_digit * digitos
                + area.pad
                + area.larg_seta
                + area.pad
                + area.pad)

    def atualizar_margem(self, topo: int | None = None):
        """Recalcula e aplica as margens do viewport.

        topo: altura do StickyScroll em pixels (margem superior do viewport).
              Se None, detecta automaticamente a partir de editor._sticky.

        Usa cache para evitar setViewportMargins redundantes — cada chamada
        desnecessária redimensiona o viewport, dispara ensureCursorVisible e
        causa saltos no scroll (BUG 3).
        """
        if topo is None:
            sticky = getattr(self.editor, '_sticky', None)
            topo = sticky.height() if sticky and sticky.isVisible() else 0
        largura = self.largura_area_numeros()
        chave   = (largura, topo)
        self.editor.area_numeros.setGeometry(
            0, 0, largura, self.editor.height()
        )
        if chave == self._cache_margem:

            return  # margens inalteradas — pula setViewportMargins

        self._cache_margem = chave
        self.editor.setViewportMargins(largura, topo, 0, 0)
