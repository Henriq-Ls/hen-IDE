# _EDITOR_/Mult_Linguas/Dockerfile/realce.py
"""
Realce de sintaxe Dockerfile — usa chaves do tema hein.
Suporta: instruções FROM/RUN/COPY/..., nomes de estágio (AS nome),
         variáveis $VAR/${VAR}, strings "...", comentários #, números de porta.
"""
from PySide6.QtCore import QRegularExpression
from PySide6.QtGui  import QSyntaxHighlighter, QTextCharFormat, QColor, QFont


class RealceSintaxeDockerfile(QSyntaxHighlighter):
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

        instrucoes = [
            "FROM","RUN","CMD","COPY","ADD","WORKDIR","ENV","EXPOSE",
            "VOLUME","USER","ARG","LABEL","HEALTHCHECK","STOPSIGNAL",
            "ONBUILD","SHELL","ENTRYPOINT","MAINTAINER",
        ]
        flags = QRegularExpression.PatternOption.CaseInsensitiveOption

        self._regras = [
            # 1. Comentários #
            (QRegularExpression(r'#[^\n]*'),
             fmt(cor("comentario", "#5c6370"), italico=italico_cmt), 0),

            # 2. Strings "..."
            (QRegularExpression(r'"([^"\\]|\\.)*"'),
             fmt(cor("string", "#98c379")), 0),

            # 3. Continuação de linha \  (no fim)
            (QRegularExpression(r'\\\s*$'),
             fmt(cor("operador", "#c678dd")), 0),

            # 4. Variáveis $VAR e ${VAR}
            (QRegularExpression(r'\$\{[^}]+\}|\$[a-zA-Z_]\w*'),
             fmt(cor("variavel_especial", "#fd971f")), 0),

            # 5. Números de porta (após EXPOSE)
            (QRegularExpression(r'\b\d+(?:/(?:tcp|udp))?\b', flags),
             fmt(cor("numero", "#d19a66")), 0),
        ]

        # 6. Instruções Dockerfile (inicio de linha, case-insensitive)
        for inst in instrucoes:
            self._regras.append((
                QRegularExpression(rf'(?i)^{inst}\b'),
                fmt(cor("palavra_chave", "#c678dd"), negrito=True), 0
            ))

        # 7. Nome de estágio após AS
        self._regras.append((
            QRegularExpression(r'(?i)\bAS\s+([a-zA-Z_]\w*)', flags),
            fmt(cor("funcao", "#61afef"), negrito=True), 1
        ))

        # 8. Imagem base (após FROM, antes de AS ou fim da linha)
        self._regras.append((
            QRegularExpression(r'(?i)^FROM\s+([^\s]+)', flags),
            fmt(cor("tipo", "#56b6c2")), 1
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
