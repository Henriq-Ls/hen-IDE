# 📁 _TRADUTION_/tradutor_erros.py
#
# Ponto de entrada público do módulo de tradução.
# Os terminais importam daqui — este arquivo não muda nunca.
#
# USO:
#     from _TRADUTION_.tradutor_erros import traduzir
#     texto_pt = traduzir("NameError: name 'x' is not defined")

from ._motor import traduzir
__all__ = ["traduzir"]
