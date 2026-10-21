# 📁 _TERMINAIS_/Mult_Terminais/__init__.py
"""
_TERMINAIS_/Mult_Terminais/__init__.py

Exporta os componentes de execução para linguagens não-Python.
"""
from _TERMINAIS_.Mult_Terminais.terminal_executor import ExecutorTerminal
from _TERMINAIS_.Mult_Terminais.executor_explorer import ExecutorExplorer
from _TERMINAIS_.Mult_Terminais.html_visor import HTMLVisorTerminal
__all__ = ['ExecutorTerminal', 'ExecutorExplorer', 'HTMLVisorTerminal']
