# _EDITOR_/Funcionalidades/validador_imports.py
# ── SHIM DE COMPATIBILIDADE ───────────────────────────────────────────────────
# Este módulo foi movido para:
#   _EDITOR_/Mult_Linguas/Python/validador.py
# Este arquivo existe apenas para não quebrar imports existentes.
# ---------------------------------------------------------------------------
from _EDITOR_.Mult_Linguas.Python.validador import (  # noqa: F401
    ValidadorImports,
    _ThreadValidador,
)

__all__ = ['ValidadorImports', '_ThreadValidador']
