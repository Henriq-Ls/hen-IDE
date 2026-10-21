# _EDITOR_/Mult_Linguas/C_CPP/realce.py
"""
Realce de sintaxe C/C++ — usa chaves do tema hein.
Suporta: palavras-chave C e C++, tipos primitivos, diretivas #,
         strings "..." e chars '...', números (dec/hex/oct/float),
         comentários // e /* */, operadores.
"""
from PySide6.QtCore import QRegularExpression
from PySide6.QtGui  import QSyntaxHighlighter, QTextCharFormat, QColor, QFont

_NORMAL           = 0
_COMENTARIO_BLOCO = 1


class RealceSintaxeC(QSyntaxHighlighter):
    def __init__(self, documento, tema: dict = None):
        super().__init__(documento)
        self._regras: list = []
        self._fmt_cmt_bloco: QTextCharFormat | None = None
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
        fmt_cmt = fmt(cor("comentario", "#5c6370"), italico=italico_cmt)
        self._fmt_cmt_bloco = fmt_cmt

        kw_c = [
            "auto","break","case","const","continue","default","do","else",
            "enum","extern","for","goto","if","inline","register","return",
            "sizeof","static","struct","switch","typedef","union","volatile",
            "while","NULL","nullptr","true","false",
        ]
        kw_cpp = [
            "class","public","private","protected","virtual","override","final",
            "new","delete","this","namespace","using","template","typename",
            "try","catch","throw","noexcept","operator","friend","mutable",
            "explicit","constexpr","consteval","constinit","static_assert",
            "decltype","auto","co_await","co_return","co_yield",
        ]
        tipos = [
            "void","int","char","short","long","float","double","signed",
            "unsigned","bool","wchar_t","char8_t","char16_t","char32_t",
            "int8_t","int16_t","int32_t","int64_t","uint8_t","uint16_t",
            "uint32_t","uint64_t","size_t","ptrdiff_t","intptr_t","uintptr_t",
            "FILE","string","vector","map","set","list","array","pair",
            "tuple","optional","variant","any","function","thread","mutex",
        ]

        self._regras = []

        # 1. Diretivas de pré-processador #include #define #ifdef ...
        self._regras.append((
            QRegularExpression(r'^\s*#\s*[a-zA-Z_]\w*(?:\s.*)?'),
            fmt(cor("atributo", "#e5c07b")), 0
        ))

        # 2. Strings "..."
        self._regras.append((
            QRegularExpression(r'"([^"\\]|\\.)*"'),
            fmt(cor("string", "#98c379")), 0
        ))

        # 3. Char '.'
        self._regras.append((
            QRegularExpression(r"'(?:[^'\\]|\\.)'"),
            fmt(cor("string", "#98c379")), 0
        ))

        # 4. Palavras-chave C
        for w in kw_c:
            self._regras.append((
                QRegularExpression(rf'\b{w}\b'),
                fmt(cor("palavra_chave", "#c678dd"), negrito=True), 0
            ))

        # 5. Palavras-chave C++
        for w in kw_cpp:
            self._regras.append((
                QRegularExpression(rf'\b{w}\b'),
                fmt(cor("palavra_chave", "#c678dd"), negrito=True), 0
            ))

        # 6. Tipos primitivos e stdlib
        for t in tipos:
            self._regras.append((
                QRegularExpression(rf'\b{t}\b'),
                fmt(cor("tipo", "#56b6c2")), 0
            ))

        # 7. Nomes de funções (antes de '(')
        self._regras.append((
            QRegularExpression(r'\b([a-zA-Z_]\w*)\s*(?=\()'),
            fmt(cor("funcao", "#61afef")), 1
        ))

        # 8. Números: hex 0x, octal 0, binário 0b, float, sufixos u/l/f
        self._regras.append((
            QRegularExpression(r'\b(?:0[xX][0-9a-fA-F]+[uUlL]*|0[bB][01]+[uUlL]*|0[0-7]+[uUlL]*|\d+\.?\d*(?:[eE][+-]?\d+)?[fFlL]*)\b'),
            fmt(cor("numero", "#d19a66")), 0
        ))

        # 9. Operadores
        self._regras.append((
            QRegularExpression(r'(?:->|::|\.\.\.|<<|>>|&&|\|\||[+\-*/%&|^~!=<>]=?|[?:])'),
            fmt(cor("operador", "#c678dd")), 0
        ))

        # 10. Comentário de linha //
        self._regras.append((
            QRegularExpression(r'//[^\n]*'),
            fmt_cmt, 0
        ))

        self.rehighlight()

    def highlightBlock(self, texto: str):
        if self.previousBlockState() == _COMENTARIO_BLOCO:
            fim = texto.find("*/")
            if fim == -1:
                self.setFormat(0, len(texto), self._fmt_cmt_bloco)
                self.setCurrentBlockState(_COMENTARIO_BLOCO)
                return
            self.setFormat(0, fim + 2, self._fmt_cmt_bloco)

        self.setCurrentBlockState(_NORMAL)

        for expr, fmto, grupo in self._regras:
            it = expr.globalMatch(texto)
            while it.hasNext():
                m = it.next()
                s = m.capturedStart(grupo); n = m.capturedLength(grupo)
                if s >= 0 and n > 0:
                    self.setFormat(s, n, fmto)

        i = 0
        while i < len(texto):
            if texto[i:i+2] == '/*':
                fim = texto.find('*/', i + 2)
                if fim == -1:
                    self.setFormat(i, len(texto) - i, self._fmt_cmt_bloco)
                    self.setCurrentBlockState(_COMENTARIO_BLOCO)
                    return
                self.setFormat(i, fim + 2 - i, self._fmt_cmt_bloco)
                i = fim + 2
            else:
                i += 1
