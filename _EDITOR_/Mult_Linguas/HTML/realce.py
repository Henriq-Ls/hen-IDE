# 📁 _EDITOR_/Funcionalidades/realce_sintaxe_html.py
"""
Realce de sintaxe HTML — suporta:
  - Tags <div>, </div>, <br/>          → palavra-chave (roxo)
  - Atributos class=, id=, href=       → função (azul)
  - Valores de string "..." e '...'    → string (verde)
  - Comentários <!-- ... --> (multi-linha)
  - Entidades &amp; &lt; &#123;        → número (laranja)
  - DOCTYPE <!DOCTYPE html>            → destaque especial
  - Pontuação < > / = ; :              → neutro
"""
from PySide6.QtCore import QRegularExpression
from PySide6.QtGui  import QSyntaxHighlighter, QTextCharFormat, QColor, QFont
_ESTADO_NORMAL     = 0
_ESTADO_COMENTARIO = 1

class RealceSintaxeHTML(QSyntaxHighlighter):
    def __init__(self, documento, tema: dict = None):
        super().__init__(documento)
        self._fmt: dict = {}
        self.aplicar_tema(tema or {})

    # ──────────────────────────────────────────────────────────────
    # Tema
    # ──────────────────────────────────────────────────────────────

    def aplicar_tema(self, tema: dict):
        sintaxe = tema.get("editor", {}).get("sintaxe", {})

        # 💡 fallback_opc = Literal["#e0e0e0"] ← defina os valores válidos
        def cor(chave, fallback="#e0e0e0") -> QColor:
            valor = sintaxe.get(chave, fallback)
            if isinstance(valor, str) and len(valor) == 9 and valor.startswith("#"):
                valor = valor[:7]

            return QColor(valor)

        def fmt(qcor, negrito=False, italico=False) -> QTextCharFormat:
            f = QTextCharFormat()
            f.setForeground(qcor)
            if negrito:
                f.setFontWeight(QFont.Bold)
            if italico:
                f.setFontItalic(True)

            return f

        estilo_cmt = sintaxe.get("comentario_estilo", "italic")

        self._fmt = {
            # nome da tag (<div  </span)
            "tag":        fmt(cor("palavra_chave",      "#c678dd"), negrito=True),
            # nome da tag de fechamento (mesma cor, sem bold extra p/ diferenciar)
            "tag_fim":    fmt(cor("palavra_chave",      "#c678dd")),
            # nome de atributo (class= id= href= style=)
            "atributo":   fmt(cor("funcao",             "#61afef")),
            # valor de string ("valor" ou 'valor')
            "string":     fmt(cor("string",             "#98c379")),
            # entidades HTML (&amp; &#123;)
            "entidade":   fmt(cor("numero",             "#d19a66")),
            # < > / = pontuação neutra
            "pontuacao":  fmt(cor("pontuacao",          "#abb2bf")),
            # DOCTYPE
            "doctype":    fmt(cor("chave_json",         "#CE9178"), negrito=True),
            # comentário <!-- -->
            "comentario": fmt(
                cor("comentario", "#5c6370"),
                italico=("italic" in estilo_cmt)
            ),
        }

        self.rehighlight()

    # ──────────────────────────────────────────────────────────────
    # highlightBlock — ponto de entrada do Qt
    # ──────────────────────────────────────────────────────────────

    def highlightBlock(self, texto: str):
        estado = (
            _ESTADO_COMENTARIO
            if self.previousBlockState() == _ESTADO_COMENTARIO
            else _ESTADO_NORMAL
        )

        pos = 0
        while pos < len(texto):
            if estado == _ESTADO_COMENTARIO:
                fim = texto.find("-->", pos)
                if fim == -1:
                    self.setFormat(pos, len(texto) - pos, self._fmt["comentario"])
                    self.setCurrentBlockState(_ESTADO_COMENTARIO)

                    return

                self.setFormat(pos, fim + 3 - pos, self._fmt["comentario"])
                pos = fim + 3
                estado = _ESTADO_NORMAL

            else:
                inicio_cmt = texto.find("<!--", pos)
                limite = inicio_cmt if inicio_cmt != -1 else len(texto)
                self._realcar_trecho(texto[pos:limite], pos)

                if inicio_cmt == -1:
                    break

                # procura fim do comentário na mesma linha
                fim_cmt = texto.find("-->", inicio_cmt + 4)
                if fim_cmt == -1:
                    self.setFormat(inicio_cmt, len(texto) - inicio_cmt, self._fmt["comentario"])
                    self.setCurrentBlockState(_ESTADO_COMENTARIO)

                    return

                self.setFormat(inicio_cmt, fim_cmt + 3 - inicio_cmt, self._fmt["comentario"])
                pos = fim_cmt + 3

        self.setCurrentBlockState(_ESTADO_NORMAL)

    # ──────────────────────────────────────────────────────────────
    # Realce de trecho fora de comentário
    # ──────────────────────────────────────────────────────────────

    # ⚠️  função grande (59 linhas)
    def _realcar_trecho(self, trecho: str, offset: int):
        if not trecho:

            return

        def ap(regex_str: str, chave: str, grupo: int = 0):
            re = QRegularExpression(regex_str)
            it = re.globalMatch(trecho)
            while it.hasNext():
                m = it.next()
                s = m.capturedStart(grupo)
                n = m.capturedLength(grupo)
                if s >= 0 and n > 0:
                    self.setFormat(offset + s, n, self._fmt[chave])

        # ── 1. DOCTYPE ────────────────────────────────────────────
        ap(r'<!DOCTYPE[^>]*>', "doctype")

        # ── 2. Valores de atributo (string — antes dos atributos) ─
        ap(r'"[^"<>]*"', "string")
        ap(r"'[^'<>]*'", "string")

        # ── 3. Atributos (palavra imediatamente antes de = ou só)  ─
        ap(r'\b([\w\-]+)(?=\s*=)', "atributo", grupo=1)

        # ── 4. Tags de fechamento </tag ───────────────────────────
        re_close = QRegularExpression(r'</([a-zA-Z][\w\-:]*)')
        it = re_close.globalMatch(trecho)
        while it.hasNext():
            m = it.next()
            # </ → pontuação
            self.setFormat(offset + m.capturedStart(), 2, self._fmt["pontuacao"])
            # nome → tag_fim
            self.setFormat(
                offset + m.capturedStart(1),
                m.capturedLength(1),
                self._fmt["tag_fim"]
            )

        # ── 5. Tags de abertura <tag ──────────────────────────────
        re_open = QRegularExpression(r'<([a-zA-Z][\w\-:]*)')
        it = re_open.globalMatch(trecho)
        while it.hasNext():
            m = it.next()
            # < → pontuação
            self.setFormat(offset + m.capturedStart(), 1, self._fmt["pontuacao"])
            # nome → tag
            self.setFormat(
                offset + m.capturedStart(1),
                m.capturedLength(1),
                self._fmt["tag"]
            )

        # ── 6. Pontuação: > /> = ──────────────────────────────────
        ap(r'(?<!=)(/>|>)', "pontuacao")
        ap(r'(?<![=!<>])=(?!=)', "pontuacao")

        # ── 7. Entidades &name; &#nnn; ────────────────────────────
        ap(r'&(?:[a-zA-Z]\w*|#\d+|#x[\da-fA-F]+);', "entidade")
