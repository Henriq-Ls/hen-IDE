# 📁 _CONFIGURA_/fontes.py
"""
Carrega as fontes customizadas hen antes de qualquer widget ser criado.
"""
import os
from PySide6.QtGui import QFontDatabase
_PASTA_FONTES = os.path.join(os.path.dirname(__file__), "Fontes_hen")

_FONTES = [
    "hen_16Bits.ttf",
    "hen_Codigo.ttf",
    "hen_Editor.ttf",
    "hen_Escritor.ttf",
    "hen_Italico.ttf",
    "hen_Monstro.ttf",
    "hen_Pedras.ttf",
    "hen.ttf",
]

def carregar_fontes():
    """Registra todas as fontes hen no Qt. Chamar após QApplication."""
    carregadas = []
    for arquivo in _FONTES:
        caminho = os.path.join(_PASTA_FONTES, arquivo)
        if os.path.isfile(caminho):
            id_ = QFontDatabase.addApplicationFont(caminho)
            if id_ != -1:
                familias = QFontDatabase.applicationFontFamilies(id_)
                carregadas.extend(familias)

    return carregadas  # retorna os nomes reais registrados pelo Qt
