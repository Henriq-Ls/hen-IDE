# 📁 _EDITOR_/Funcionalidades/auto_indentacao.py
_DEDENT_PALAVRAS = ('return', 'pass', 'break', 'continue', 'raise')  # ← nível de módulo

class AutoIndentacao:
    def __init__(self, editor):
        self.editor = editor

    def processar_enter(self, cursor, linha_atual):
        indentacao = len(linha_atual) - len(linha_atual.lstrip())

        linha_strip = linha_atual.strip()

        if linha_atual.rstrip().endswith(':'):
            indentacao += 4
        elif any(linha_strip == p or linha_strip.startswith(p + ' ') or linha_strip.startswith(p + '(')
                 for p in _DEDENT_PALAVRAS):
            indentacao = max(0, indentacao - 4)

        return ' ' * indentacao
