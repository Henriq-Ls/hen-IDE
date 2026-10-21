# _EDITOR_/Mult_Linguas/Makefile/realce.py
"""
Realce de sintaxe Makefile — usa chaves do tema hein.
Suporta: targets (nome:), variáveis $(VAR)/${VAR}, variáveis automáticas
         $@ $< $^ $*, diretivas make, .PHONY/.DEFAULT, comentários #,
         receitas (linhas com TAB).
"""
from PySide6.QtCore import QRegularExpression
from PySide6.QtGui  import QSyntaxHighlighter, QTextCharFormat, QColor, QFont


class RealceSintaxeMakefile(QSyntaxHighlighter):
    def __init__(self, documento, tema: dict = None):
        super().__init__(documento)
        self._regras: list = []
        self.aplicar_tema(tema or {})

    def aplicar_tema(self, tema: dict):
        sintaxe = tema.get("editor", {}).get("sintaxe", {})

        def cor(chave, fallback="#e0e0e0") -> QColor:
            v = sintaxe.get(chave, fallback)
            if isinstance(v, str) and len(v) == 9 and v.startswith("#"):
                v = v[:7]
            return QColor(v)

        def fmt(qcor, negrito=False, italico=False) -> QTextCharFormat:
            f = QTextCharFormat()
            f.setForeground(qcor)
            if negrito: f.setFontWeight(QFont.Bold)
            if italico: f.setFontItalic(True)
            return f

        estilo_cmt = sintaxe.get("comentario_estilo", "italic")
        italico_cmt = "italic" in estilo_cmt

        diretivas = [
            "ifeq","ifneq","ifdef","ifndef","else","endif",
            "include","sinclude","-include","define","endef",
            "override","export","unexport","vpath","undefine",
        ]

        self._regras = [
            # 1. Comentários #
            (QRegularExpression(r'#[^\n]*'),
             fmt(cor("comentario", "#5c6370"), italico=italico_cmt), 0),

            # 2. Receita (linha começa com TAB) — cor de string
            (QRegularExpression(r'^\t.*$'),
             fmt(cor("string", "#98c379")), 0),

            # 3. Target especial .PHONY .DEFAULT .PRECIOUS etc.
            (QRegularExpression(r'^\.[A-Z][A-Z_]*(?=\s*:)'),
             fmt(cor("atributo", "#e5c07b"), negrito=True), 0),

            # 4. Target normal (nome antes de :, não começa com TAB ou #)
            (QRegularExpression(r'^([^\t#\s][^:=\n]*)(?=\s*:)'),
             fmt(cor("funcao", "#61afef"), negrito=True), 1),

            # 5. Variáveis $(VAR) e ${VAR}
            (QRegularExpression(r'\$[({][^)}]+[)}]'),
             fmt(cor("variavel_especial", "#fd971f")), 0),

            # 6. Variáveis automáticas $@ $< $^ $* $? $| $%
            (QRegularExpression(r'\$[@<^*?|%D]'),
             fmt(cor("variavel_especial", "#fd971f")), 0),

            # 7. Atribuição de variável: VAR = / VAR := / VAR ?= / VAR +=
            (QRegularExpression(r'^([A-Z_a-z]\w*)(?=\s*(?::=|\?=|\+=|=))'),
             fmt(cor("tipo", "#56b6c2")), 1),

            # 8. Strings "..."
            (QRegularExpression(r'"([^"\\]|\\.)*"'),
             fmt(cor("string", "#98c379")), 0),

            # 9. Continuação de linha \
            (QRegularExpression(r'\\\s*$'),
             fmt(cor("operador", "#c678dd")), 0),
        ]

        # 10. Diretivas make
        for d in diretivas:
            self._regras.append((
                QRegularExpression(rf'^\s*{d}\b'),
                fmt(cor("palavra_chave", "#c678dd"), negrito=True), 0
            ))

        self.rehighlight()

    def highlightBlock(self, texto: str):
        for regra in self._regras:
            expr, fmto, grupo = regra
            it = expr.globalMatch(texto)
            while it.hasNext():
                m = it.next()
                s = m.capturedStart(grupo); n = m.capturedLength(grupo)
                if s >= 0 and n > 0:
                    self.setFormat(s, n, fmto)
        self.setCurrentBlockState(0)
