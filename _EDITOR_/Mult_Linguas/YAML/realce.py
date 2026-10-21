# _EDITOR_/Mult_Linguas/YAML/realce.py
"""
Realce de sintaxe YAML — usa as chaves do tema hein.
Suporta: chaves (key:), valores escalares, âncoras/aliases,
         booleanos, números, strings, comentários #.
"""
from PySide6.QtCore import QRegularExpression
from PySide6.QtGui  import QSyntaxHighlighter, QTextCharFormat, QColor, QFont


class RealceSintaxeYAML(QSyntaxHighlighter):
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

        self._regras = [
            # 1. Comentário # — aplicado primeiro para mascarar tudo
            (QRegularExpression(r'#[^\n]*'),
             fmt(cor("comentario", "#5c6370"), italico="italic" in estilo_cmt), 0),

            # 2. Strings com aspas duplas e simples
            (QRegularExpression(r'"([^"\\]|\\.)*"'),
             fmt(cor("string", "#98c379")), 0),
            (QRegularExpression(r"'([^'\\]|\\.)*'"),
             fmt(cor("string", "#98c379")), 0),

            # 3. Booleanos e null YAML (antes de chave para não colorir keys)
            (QRegularExpression(r'\b(true|false|null|yes|no|on|off|True|False|Null|YES|NO|ON|OFF)\b'),
             fmt(cor("palavra_chave", "#c678dd"), negrito=True), 0),

            # 4. Números (inteiros, floats, hex, octais, .inf, .nan)
            (QRegularExpression(r'\b(-?(?:0x[0-9a-fA-F]+|0o[0-7]+|\d+\.?\d*(?:[eE][+-]?\d+)?)|\.inf|\.nan)\b'),
             fmt(cor("numero", "#d19a66")), 0),

            # 5. Chave de mapeamento: "nome:" ou "nome :" no início da linha ou após -
            (QRegularExpression(r'(?:^|\-\s+)([a-zA-Z_$][\w.$-]*)(?=\s*:)'),
             fmt(cor("chave_json", "#CE9178"), negrito=True), 1),

            # 6. Âncoras &nome e aliases *nome
            (QRegularExpression(r'[&*][a-zA-Z_][\w-]*'),
             fmt(cor("atributo", "#e5c07b")), 0),

            # 7. Tags !!tipo
            (QRegularExpression(r'!![a-zA-Z]+'),
             fmt(cor("tipo", "#56b6c2")), 0),

            # 8. Indicadores de bloco | e >
            (QRegularExpression(r'(?<=:\s)[|>][+-]?'),
             fmt(cor("pontuacao", "#abb2bf")), 0),

            # 9. Marcador de lista "- " no início
            (QRegularExpression(r'^\s*-(?=\s)'),
             fmt(cor("pontuacao", "#abb2bf")), 0),

            # 10. Separadores de documento --- e ...
            (QRegularExpression(r'^(?:---|\.\.\.)\s*$'),
             fmt(cor("operador", "#c678dd")), 0),
        ]
        self.rehighlight()

    def highlightBlock(self, texto: str):
        for expr, fmto, grupo in self._regras:
            it = expr.globalMatch(texto)
            while it.hasNext():
                m = it.next()
                s = m.capturedStart(grupo)
                n = m.capturedLength(grupo)
                if s >= 0 and n > 0:
                    self.setFormat(s, n, fmto)
        self.setCurrentBlockState(0)
