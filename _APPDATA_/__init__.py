# 📁 _APPDATA_/__init__.py
"""
_APPDATA_ — Pacote de gerenciamento do AppData da hein IDE.

Ponto de entrada público:
    from _APPDATA_ import appdata          # instância pronta
    from _APPDATA_ import GerenciadorAppData  # classe, se necessário
Inicialização (uma vez, no startup da IDE):
    appdata.inicializar()
"""

from _APPDATA_.gerenciador import GerenciadorAppData
appdata: GerenciadorAppData = GerenciadorAppData.instancia()

__all__ = ["GerenciadorAppData", "appdata"]
