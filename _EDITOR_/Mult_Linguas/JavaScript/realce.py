# _EDITOR_/Mult_Linguas/JavaScript/realce.py
"""
Realce de sintaxe JavaScript / TypeScript — usa as chaves do tema hein.
Suporta: palavras-chave JS+TS, tipos TS, strings simples e template literals,
         comentários // e /* */, decoradores @, números, operadores.
CSS/SCSS: recebem realce parcial (strings, números, comentários).
"""
from PySide6.QtCore import QRegularExpression
from PySide6.QtGui  import QSyntaxHighlighter, QTextCharFormat, QColor, QFont

_NORMAL            = 0
_COMENTARIO_BLOCO  = 1   # /* ... */
_TEMPLATE_STRING   = 2   # `...`


class RealceSintaxeJS(QSyntaxHighlighter):
    def __init__(self, documento, tema: dict = None):
        super().__init__(documento)
        self._regras: list = []
        self._fmt: dict    = {}
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
            "kw":       fmt(cor("palavra_chave",    "#c678dd"), negrito=True),
            "tipo":     fmt(cor("tipo",             "#56b6c2")),
            "funcao":   fmt(cor("funcao",           "#61afef")),
            "string":   fmt(cor("string",           "#98c379")),
            "template": fmt(cor("string",           "#98c379")),
            "numero":   fmt(cor("numero",           "#d19a66")),
            "operador": fmt(cor("operador",         "#c678dd")),
            "decorador":fmt(cor("atributo",         "#e5c07b")),
            "coment_l": fmt(cor("comentario",       "#5c6370"), italico=italico_cmt),
            "coment_b": fmt(cor("comentario",       "#5c6370"), italico=italico_cmt),
        }

        kw_js = [
            "break","case","catch","class","const","continue","debugger",
            "default","delete","do","else","export","extends","finally",
            "for","function","if","import","in","instanceof","let","new",
            "of","return","static","super","switch","this","throw","try",
            "typeof","var","void","while","with","yield","async","await",
            "from","null","undefined","true","false",
            # TypeScript
            "interface","type","enum","namespace","module","declare",
            "implements","abstract","readonly","override","as","satisfies",
        ]
        kw_tipos_ts = [
            "string","number","boolean","object","symbol","bigint","any",
            "never","unknown","void","Array","Promise","Map","Set","Record",
            "Partial","Required","Readonly","Pick","Omit","Exclude","Extract",
            "NonNullable","ReturnType","InstanceType","Parameters","keyof","infer",
        ]

        self._regras = []

        # Palavras-chave JS+TS
        for w in kw_js:
            self._regras.append((QRegularExpression(rf"\b{w}\b"), self._fmt["kw"], 0))

        # Tipos TypeScript
        for t in kw_tipos_ts:
            self._regras.append((QRegularExpression(rf"\b{t}\b"), self._fmt["tipo"], 0))

        # Strings duplas e simples
        self._regras.append((QRegularExpression(r'"([^"\\]|\\.)*"'),  self._fmt["string"], 0))
        self._regras.append((QRegularExpression(r"'([^'\\]|\\.)*'"),  self._fmt["string"], 0))

        # Números (decimal, hex, octal, binário, float)
        self._regras.append((
            QRegularExpression(r'\b(0[xX][0-9a-fA-F]+|0[bB][01]+|0[oO][0-7]+|\d+\.?\d*([eE][+-]?\d+)?)\b'),
            self._fmt["numero"], 0
        ))

        # Funções (nome antes de '(')
        self._regras.append((QRegularExpression(r'\b([a-zA-Z_$][\w$]*)\s*(?=\()'), self._fmt["funcao"], 1))

        # Decoradores @...
        self._regras.append((QRegularExpression(r'@[a-zA-Z_$][\w$.]*'), self._fmt["decorador"], 0))

        # Operador arrow =>
        self._regras.append((QRegularExpression(r'=>'),                  self._fmt["operador"], 0))

        # Comentário de linha //
        self._regras.append((QRegularExpression(r'//[^\n]*'),            self._fmt["coment_l"], 0))

        self.rehighlight()

    # ──────────────────────────────────────────────────────────────────
    def highlightBlock(self, texto: str):
        estado = self.previousBlockState()

        # ── Continua bloco /* */ da linha anterior ─────────────────────
        if estado == _COMENTARIO_BLOCO:
            fim = texto.find("*/")
            if fim == -1:
                self.setFormat(0, len(texto), self._fmt["coment_b"])
                self.setCurrentBlockState(_COMENTARIO_BLOCO)
                return
            self.setFormat(0, fim + 2, self._fmt["coment_b"])
            inicio_scan = fim + 2
        elif estado == _TEMPLATE_STRING:
            fim = texto.find("`")
            if fim == -1:
                self.setFormat(0, len(texto), self._fmt["template"])
                self.setCurrentBlockState(_TEMPLATE_STRING)
                return
            self.setFormat(0, fim + 1, self._fmt["template"])
            inicio_scan = fim + 1
        else:
            inicio_scan = 0

        self.setCurrentBlockState(_NORMAL)

        # ── Regras de regex simples ───────────────────────────────────
        for regra in self._regras:
            if len(regra) == 3:
                expr, fmto, grupo = regra
            else:
                expr, fmto = regra; grupo = 0
            it = expr.globalMatch(texto)
            while it.hasNext():
                m = it.next()
                s = m.capturedStart(grupo)
                n = m.capturedLength(grupo)
                if s >= 0 and n > 0:
                    self.setFormat(s, n, fmto)

        # ── Template strings `` (abertura) ─────────────────────────────
        i = inicio_scan
        while i < len(texto):
            if texto[i] == '`':
                fim_t = texto.find('`', i + 1)
                if fim_t == -1:
                    self.setFormat(i, len(texto) - i, self._fmt["template"])
                    self.setCurrentBlockState(_TEMPLATE_STRING)
                    return
                self.setFormat(i, fim_t - i + 1, self._fmt["template"])
                i = fim_t + 1
            elif texto[i:i+2] == '/*':
                fim_b = texto.find('*/', i + 2)
                if fim_b == -1:
                    self.setFormat(i, len(texto) - i, self._fmt["coment_b"])
                    self.setCurrentBlockState(_COMENTARIO_BLOCO)
                    return
                self.setFormat(i, fim_b + 2 - i, self._fmt["coment_b"])
                i = fim_b + 2
            else:
                i += 1
