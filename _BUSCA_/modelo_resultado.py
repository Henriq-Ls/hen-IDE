# 📁 _BUSCA_/modelo_resultado.py
# coding: utf-8
from dataclasses import dataclass
from enum import Enum, auto

class TipoBusca(Enum):
    ARQUIVO  = auto()
    GREP     = auto()
    SIMBOLO  = auto()
    ANOTACAO = auto()
    LINHA    = auto()
    COMANDO  = auto()
    RECENTE  = auto()

@dataclass
class ResultadoBusca:
    tipo:      TipoBusca
    titulo:    str
    subtitulo: str    = ""
    caminho:   str    = ""
    linha:     int    = -1
    coluna:    int    = 0
    termo:     str    = ""
    icone:     str    = ""
    acao:      object = None
