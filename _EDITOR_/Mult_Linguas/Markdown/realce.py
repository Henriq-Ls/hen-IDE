# _EDITOR_/Mult_Linguas/Markdown/realce.py
"""
Realce de sintaxe Markdown — usa chaves do tema hein.
Suporta: headings # ## ###, bold **text**, italic *text*,
         inline code `...`, code blocks ```, links [](url),
         images ![](), blockquotes >, listas - * 1., separadores ---.
"""
from PySide6.QtCore import QRegularExpression
from PySide6.QtGui  import QSyntaxHighlighter, QTextCharFormat, QColor, QFont

_NORMAL      = 0
_CODE_BLOCK  = 1   # ``` ... ```


class RealceSintaxeMD(QSyntaxHighlighter):
    def __init__(self, documento, tema: dict = None):
        super().__init__(documento)
        self._regras: list = []
        self._fmt: dict    = {}
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

        self._fmt = {
            "h1":       fmt(cor("funcao",       "#61afef"), negrito=True),
            "h2":       fmt(cor("funcao",       "#61afef"), negrito=True),
            "h3":       fmt(cor("chave_json",   "#56b6c2"), negrito=True),
            "hN":       fmt(cor("chave_json",   "#56b6c2")),
            "bold":     fmt(cor("palavra_chave","#c678dd"), negrito=True),
            "italic":   fmt(cor("comentario",   "#5c6370"), italico=True),
            "code":     fmt(cor("chave_json",   "#CE9178")),
            "code_blk": fmt(cor("string",       "#98c379")),
            "link_txt": fmt(cor("atributo",     "#d19a66")),
            "link_url": fmt(cor("tipo",         "#56b6c2")),
            "quote":    fmt(cor("comentario",   "#5c6370"), italico=True),
            "lista":    fmt(cor("numero",       "#d19a66")),
            "sep":      fmt(cor("pontuacao",    "#abb2bf")),
            "fence":    fmt(cor("string",       "#98c379")),
        }

        self._regras = [
            # Headings (ordem: H1 > H2 > H3 > H4+)
            (QRegularExpression(r'^#{1}\s+.*$'),      self._fmt["h1"]),
            (QRegularExpression(r'^#{2}\s+.*$'),      self._fmt["h2"]),
            (QRegularExpression(r'^#{3}\s+.*$'),      self._fmt["h3"]),
            (QRegularExpression(r'^#{4,}\s+.*$'),     self._fmt["hN"]),

            # Blockquote
            (QRegularExpression(r'^>\s.*$'),          self._fmt["quote"]),

            # Separadores --- === *** (linha inteira)
            (QRegularExpression(r'^(?:[-*_]{3,})\s*$'), self._fmt["sep"]),

            # Marcadores de lista - * + e numerados 1.
            (QRegularExpression(r'^\s*(?:[-*+]|\d+\.)\s'),  self._fmt["lista"]),

            # Bold+italic ***text*** (antes de bold e italic separados)
            (QRegularExpression(r'\*{3}([^*]+)\*{3}'), self._fmt["bold"]),
            (QRegularExpression(r'_{3}([^_]+)_{3}'),   self._fmt["bold"]),

            # Bold **text** __text__
            (QRegularExpression(r'\*{2}([^*]+)\*{2}'), self._fmt["bold"]),
            (QRegularExpression(r'_{2}([^_]+)_{2}'),   self._fmt["bold"]),

            # Italic *text* _text_
            (QRegularExpression(r'\*([^*\s][^*]*[^*\s]|\S)\*'), self._fmt["italic"]),
            (QRegularExpression(r'_([^_\s][^_]*[^_\s]|\S)_'),   self._fmt["italic"]),

            # Inline code `code`
            (QRegularExpression(r'`[^`\n]+`'),          self._fmt["code"]),

            # Links e imagens [text](url)
            (QRegularExpression(r'!?\[([^\]]*)\]'),     self._fmt["link_txt"]),
            (QRegularExpression(r'\]\(([^)]*)\)'),      self._fmt["link_url"]),
        ]

        self.rehighlight()

    def highlightBlock(self, texto: str):
        estado = self.previousBlockState()

        # ── Bloco de código ``` ───────────────────────────────────────
        stripped = texto.strip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            self.setFormat(0, len(texto), self._fmt["fence"])
            if estado == _CODE_BLOCK:
                self.setCurrentBlockState(_NORMAL)
            else:
                self.setCurrentBlockState(_CODE_BLOCK)
            return

        if estado == _CODE_BLOCK:
            self.setFormat(0, len(texto), self._fmt["code_blk"])
            self.setCurrentBlockState(_CODE_BLOCK)
            return

        self.setCurrentBlockState(_NORMAL)

        # ── Regras de regex ───────────────────────────────────────────
        for regra in self._regras:
            expr, fmto = regra[0], regra[1]
            grupo = regra[2] if len(regra) > 2 else 0
            it = expr.globalMatch(texto)
            while it.hasNext():
                m = it.next()
                s = m.capturedStart(grupo); n = m.capturedLength(grupo)
                if s >= 0 and n > 0:
                    self.setFormat(s, n, fmto)
