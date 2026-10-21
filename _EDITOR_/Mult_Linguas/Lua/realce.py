# _EDITOR_/Mult_Linguas/Lua/realce.py
"""
Realce de sintaxe Lua — usa as chaves do tema hein.
Suporta: palavras-chave, strings simples/duplas/[[...]], comentários -- e --[[...]],
         números, nomes de função, atributos de tabela.
"""
from PySide6.QtCore import QRegularExpression
from PySide6.QtGui  import QSyntaxHighlighter, QTextCharFormat, QColor, QFont

_NORMAL          = 0
_COMENT_BLOCO    = 1   # --[[ ... ]]
_STRING_BLOCO    = 2   # [[ ... ]]


class RealceSintaxeLua(QSyntaxHighlighter):
    def __init__(self, documento, tema: dict = None):
        super().__init__(documento)
        self._regras: list = []
        self._fmt:   dict  = {}
        self.aplicar_tema(tema or {})

    # ──────────────────────────────────────────────────────────────────
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

        self._fmt = {
            "kw":      fmt(cor("palavra_chave", "#c678dd"), negrito=True),
            "builtin": fmt(cor("tipo",          "#56b6c2")),
            "funcao":  fmt(cor("funcao",        "#61afef")),
            "string":  fmt(cor("string",        "#98c379")),
            "numero":  fmt(cor("numero",        "#d19a66")),
            "operador":fmt(cor("operador",      "#c678dd")),
            "coment":  fmt(cor("comentario",    "#5c6370"), italico=italico_cmt),
            "self_":   fmt(cor("atributo",      "#e5c07b")),
        }

        kw_lua = [
            "and","break","do","else","elseif","end","false","for",
            "function","goto","if","in","local","nil","not","or",
            "repeat","return","then","true","until","while",
        ]
        builtins_lua = [
            # tabelas globais e funções padrão
            "print","tostring","tonumber","type","pairs","ipairs","next",
            "select","unpack","table","string","math","io","os","coroutine",
            "package","require","load","loadstring","dofile","loadfile",
            "pcall","xpcall","error","assert","rawget","rawset","rawequal",
            "rawlen","setmetatable","getmetatable","collectgarbage",
            "_G","_VERSION",
        ]

        self._regras = []

        # Palavras-chave
        for w in kw_lua:
            self._regras.append((QRegularExpression(rf"\b{w}\b"), self._fmt["kw"], 0))

        # Built-ins / stdlib
        for b in builtins_lua:
            self._regras.append((QRegularExpression(rf"\b{b}\b"), self._fmt["builtin"], 0))

        # self (auto-ref de objeto)
        self._regras.append((QRegularExpression(r'\bself\b'), self._fmt["self_"], 0))

        # Números (decimal, hex, scientific)
        self._regras.append((
            QRegularExpression(r'\b(0[xX][0-9a-fA-F]+|\d+\.?\d*([eE][+-]?\d+)?)\b'),
            self._fmt["numero"], 0
        ))

        # Funções (identificador antes de '(')
        self._regras.append((
            QRegularExpression(r'\b([a-zA-Z_]\w*)\s*(?=\()'),
            self._fmt["funcao"], 1
        ))

        # Strings simples e duplas
        self._regras.append((QRegularExpression(r'"([^"\\]|\\.)*"'), self._fmt["string"], 0))
        self._regras.append((QRegularExpression(r"'([^'\\]|\\.)*'"), self._fmt["string"], 0))

        # Comentário de linha --
        self._regras.append((QRegularExpression(r'--(?!\[)[^\n]*'), self._fmt["coment"], 0))

        self.rehighlight()

    # ──────────────────────────────────────────────────────────────────
    def highlightBlock(self, texto: str):
        estado = self.previousBlockState()

        # ── Comentário de bloco --[[ ... ]] ───────────────────────────
        if estado == _COMENT_BLOCO:
            fim = texto.find("]]")
            if fim == -1:
                self.setFormat(0, len(texto), self._fmt["coment"])
                self.setCurrentBlockState(_COMENT_BLOCO)
                return
            self.setFormat(0, fim + 2, self._fmt["coment"])
            inicio_scan = fim + 2
        # ── String de bloco [[ ... ]] ─────────────────────────────────
        elif estado == _STRING_BLOCO:
            fim = texto.find("]]")
            if fim == -1:
                self.setFormat(0, len(texto), self._fmt["string"])
                self.setCurrentBlockState(_STRING_BLOCO)
                return
            self.setFormat(0, fim + 2, self._fmt["string"])
            inicio_scan = fim + 2
        else:
            inicio_scan = 0

        # ── Linha nova ────────────────────────────────────────────────
        self.setCurrentBlockState(_NORMAL)

        i = inicio_scan
        while i < len(texto):
            trecho = texto[i:]

            # Abre --[[
            if trecho.startswith("--[["):
                fim = texto.find("]]", i + 4)
                if fim == -1:
                    self.setFormat(i, len(texto) - i, self._fmt["coment"])
                    self.setCurrentBlockState(_COMENT_BLOCO)
                    return
                self.setFormat(i, fim + 2 - i, self._fmt["coment"])
                i = fim + 2
                continue

            # Comentário de linha --
            if trecho.startswith("--"):
                self.setFormat(i, len(texto) - i, self._fmt["coment"])
                return

            # Abre [[
            if trecho.startswith("[["):
                fim = texto.find("]]", i + 2)
                if fim == -1:
                    self.setFormat(i, len(texto) - i, self._fmt["string"])
                    self.setCurrentBlockState(_STRING_BLOCO)
                    return
                self.setFormat(i, fim + 2 - i, self._fmt["string"])
                i = fim + 2
                continue

            # String " ou '
            if trecho[0] in ('"', "'"):
                delim = trecho[0]
                j = 1
                while j < len(trecho):
                    if trecho[j] == "\\":
                        j += 2
                        continue
                    if trecho[j] == delim:
                        j += 1
                        break
                    j += 1
                self.setFormat(i, j, self._fmt["string"])
                i += j
                continue

            i += 1

        # Aplica regras de token (palavras-chave, números, funções)
        for regex, fmt_obj, grupo in self._regras:
            it = regex.globalMatch(texto)
            while it.hasNext():
                m = it.next()
                self.setFormat(m.capturedStart(grupo), m.capturedLength(grupo), fmt_obj)
