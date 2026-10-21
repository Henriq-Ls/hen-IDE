# 📁 _EDITOR_/Utilidades/texto_utils.py
# Versão única — usada por _EDITOR_ e _PAINEL_ESQUERDO_

def obter_indentacao(linha: str) -> int:
    """Retorna o número de espaços de indentação da linha."""

    return len(linha) - len(linha.lstrip())

def precisa_aumentar_indentacao(linha: str) -> bool:
    """Retorna True se a linha termina com ':', indicando que o próximo bloco deve ser indentado."""

    return linha.rstrip().endswith(':')
