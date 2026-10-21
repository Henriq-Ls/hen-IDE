# 📁 _TERMINAIS_/Debug/__init__.py
"""
Pacote do depurador integrado da hein IDE.

Contém:
  cliente_dap.py  — ClienteDAP(QThread): protocolo DAP sobre TCP com debugpy
  painel_debug.py — PainelDebug(QWidget): UI de controle do depurador
"""

from _TERMINAIS_.Debug.cliente_dap  import ClienteDAP
from _TERMINAIS_.Debug.painel_debug import PainelDebug
