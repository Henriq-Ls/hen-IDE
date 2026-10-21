# 📁 _EDITOR_/Outline/item_outline.py
# -*- coding: utf-8 -*-
from PySide6.QtWidgets import QTreeWidgetItem

class ItemOutline(QTreeWidgetItem):
    def __init__(self, texto: str, caminho: str = "", linha: int = 0, tipo: str = "", parent=None):
        if parent is None:
            super().__init__([texto])
        else:
            super().__init__(parent, [texto])
        self.caminho_arquivo = caminho
        self.linha           = linha
        self.tipo            = tipo
