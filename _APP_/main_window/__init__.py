"""main_window/ — janela principal do hein IDE, dividida em módulos.

Antes um único arquivo main_window.py de 4607 linhas; agora organizada em:

- base.py                  MainWindowBase   (__init__, UI raiz, eventos de janela)
- mixin_projeto.py         MixinProjeto     (projeto, venv, salvar/abrir arquivo)
- mixin_abas.py            MixinAbas        (abas de editor, árvore, split de painéis)
- mixin_busca.py           MixinBusca       (busca global/local)
- mixin_terminal_debug.py  MixinTerminalDebug (execução, debug, terminal)
- mixin_atalhos.py         MixinAtalhos     (atalhos de edição/navegação)
- mixin_layout.py          MixinLayout      (toggles de painéis, layout, menu Projeto)
- painel_card.py           PainelCard       (widget de card com cantos arredondados)
- workers.py               threads de background (venv, análise de projeto)

A classe MainWindow combina tudo por herança múltipla. O import externo
continua o mesmo: `from _APP_.main_window import MainWindow`.
"""

from .base import MainWindowBase
from .mixin_abas import MixinAbas
from .mixin_atalhos import MixinAtalhos
from .mixin_busca import MixinBusca
from .mixin_layout import MixinLayout
from .mixin_projeto import MixinProjeto
from .mixin_terminal_debug import MixinTerminalDebug
from .painel_card import PainelCard
from .workers import _AnalisadorProjeto, _CriadorVenv


class MainWindow(
    MainWindowBase,
    MixinProjeto,
    MixinAbas,
    MixinBusca,
    MixinTerminalDebug,
    MixinAtalhos,
    MixinLayout,
):
    """Janela principal do hein IDE — combina MainWindowBase com todos os
    mixins de funcionalidade. Ver o docstring do módulo para o mapa completo."""
    pass


__all__ = ["MainWindow", "PainelCard"]
