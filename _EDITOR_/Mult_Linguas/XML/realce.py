# _EDITOR_/Mult_Linguas/XML/realce.py
"""
Realce de sintaxe XML — mesma estrutura do HTML, reutiliza chaves do tema hein.
Suporta: tags, atributos, valores, comentários <!-- -->, declaração <?xml ?>,
         CDATA <![CDATA[...]]>, entidades &amp; &#nnn;.
"""
from PySide6.QtCore import QRegularExpression
from PySide6.QtGui  import QSyntaxHighlighter, QTextCharFormat, QColor, QFont

_NORMAL     = 0
_COMENTARIO = 1
_CDATA      = 2


class RealceSintaxeXML(QSyntaxHighlighter):
    def __init__(self, documento, tema: dict = None):
        super().__init__(documento)
        self._fmt: dict = {}
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

        self._fmt = {
            "tag":       fmt(cor("tag",          "#e06c75"), negrito=True),
            "tag_fim":   fmt(cor("tag",          "#e06c75")),
            "atributo":  fmt(cor("atributo",     "#d19a66")),
            "string":    fmt(cor("string",       "#98c379")),
            "entidade":  fmt(cor("numero",       "#d19a66")),
            "pontuacao": fmt(cor("pontuacao",    "#abb2bf")),
            "declaracao":fmt(cor("chave_json",   "#56b6c2"), negrito=True),
            "cdata":     fmt(cor("string",       "#98c379")),
            "comentario":fmt(cor("comentario",   "#5c6370"), italico="italic" in estilo_cmt),
        }
        self.rehighlight()

    def highlightBlock(self, texto: str):
        estado = self.previousBlockState()

        # ── Continua comentário da linha anterior ───────────────────────
        if estado == _COMENTARIO:
            fim = texto.find("-->")
            if fim == -1:
                self.setFormat(0, len(texto), self._fmt["comentario"])
                self.setCurrentBlockState(_COMENTARIO)
                return
            self.setFormat(0, fim + 3, self._fmt["comentario"])
            pos = fim + 3
        # ── Continua CDATA da linha anterior ────────────────────────────
        elif estado == _CDATA:
            fim = texto.find("]]>")
            if fim == -1:
                self.setFormat(0, len(texto), self._fmt["cdata"])
                self.setCurrentBlockState(_CDATA)
                return
            self.setFormat(0, fim + 3, self._fmt["cdata"])
            pos = fim + 3
        else:
            pos = 0

        self.setCurrentBlockState(_NORMAL)

        def ap(regex_str, chave, grupo=0):
            re_ = QRegularExpression(regex_str)
            it  = re_.globalMatch(texto)
            while it.hasNext():
                m = it.next()
                s = m.capturedStart(grupo); n = m.capturedLength(grupo)
                if s >= 0 and n > 0:
                    self.setFormat(s, n, self._fmt[chave])

        # Valores de atributo
        ap(r'"[^"<>]*"', "string")
        ap(r"'[^'<>]*'", "string")

        # Atributos (antes de =)
        ap(r'\b([\w:\-]+)(?=\s*=)', "atributo", 1)

        # Declaração XML <?xml ?> e PI <?...?>
        ap(r'<\?[\w][\s\S]*?\?>', "declaracao")

        # Tags de fechamento </tag
        re_close = QRegularExpression(r'</([a-zA-Z][\w:\-]*)')
        it = re_close.globalMatch(texto)
        while it.hasNext():
            m = it.next()
            self.setFormat(m.capturedStart(), 2, self._fmt["pontuacao"])
            self.setFormat(m.capturedStart(1), m.capturedLength(1), self._fmt["tag_fim"])

        # Tags de abertura <tag
        re_open = QRegularExpression(r'<([a-zA-Z][\w:\-]*)')
        it = re_open.globalMatch(texto)
        while it.hasNext():
            m = it.next()
            self.setFormat(m.capturedStart(), 1, self._fmt["pontuacao"])
            self.setFormat(m.capturedStart(1), m.capturedLength(1), self._fmt["tag"])

        # Pontuação > />
        ap(r'(?:/>|>)', "pontuacao")

        # Entidades &nome; &#nnn; &#xhh;
        ap(r'&(?:[a-zA-Z]\w*|#\d+|#x[\da-fA-F]+);', "entidade")

        # CDATA abertura nesta linha
        i = pos
        while i < len(texto):
            if texto[i:i+9] == '<![CDATA[':
                fim_cd = texto.find(']]>', i + 9)
                if fim_cd == -1:
                    self.setFormat(i, len(texto) - i, self._fmt["cdata"])
                    self.setCurrentBlockState(_CDATA)
                    return
                self.setFormat(i, fim_cd + 3 - i, self._fmt["cdata"])
                i = fim_cd + 3
            elif texto[i:i+4] == '<!--':
                fim_cm = texto.find('-->', i + 4)
                if fim_cm == -1:
                    self.setFormat(i, len(texto) - i, self._fmt["comentario"])
                    self.setCurrentBlockState(_COMENTARIO)
                    return
                self.setFormat(i, fim_cm + 3 - i, self._fmt["comentario"])
                i = fim_cm + 3
            else:
                i += 1
