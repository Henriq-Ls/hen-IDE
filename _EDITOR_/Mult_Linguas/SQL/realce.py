# _EDITOR_/Mult_Linguas/SQL/realce.py
"""
Realce de sintaxe SQL — usa chaves do tema hein.
Suporta: palavras-chave DDL/DML/DCL, funções agregadas, tipos de dados,
         strings '...', números, comentários -- e /* */.
"""
from PySide6.QtCore import QRegularExpression
from PySide6.QtGui  import QSyntaxHighlighter, QTextCharFormat, QColor, QFont

_NORMAL           = 0
_COMENTARIO_BLOCO = 1


class RealceSintaxeSQL(QSyntaxHighlighter):
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

        kw_ddl = [
            "SELECT","FROM","WHERE","INSERT","INTO","VALUES","UPDATE","SET",
            "DELETE","CREATE","TABLE","VIEW","INDEX","TRIGGER","PROCEDURE",
            "FUNCTION","DROP","ALTER","ADD","MODIFY","COLUMN","CONSTRAINT",
            "PRIMARY","KEY","FOREIGN","REFERENCES","UNIQUE","NOT","NULL",
            "DEFAULT","CHECK","AUTO_INCREMENT","AUTOINCREMENT","SERIAL",
            "TEMPORARY","TEMP","IF","EXISTS","REPLACE",
        ]
        kw_dml = [
            "JOIN","LEFT","RIGHT","INNER","OUTER","FULL","CROSS","ON","AS",
            "UNION","ALL","INTERSECT","EXCEPT","DISTINCT","ORDER","BY","GROUP",
            "HAVING","LIMIT","OFFSET","FETCH","FIRST","ROWS","ONLY",
            "AND","OR","IN","NOT","LIKE","ILIKE","BETWEEN","IS","EXISTS",
            "CASE","WHEN","THEN","ELSE","END","WITH","RECURSIVE",
            "BEGIN","COMMIT","ROLLBACK","TRANSACTION","SAVEPOINT","RELEASE",
            "GRANT","REVOKE","TO","PUBLIC","PRIVILEGES",
            "RETURN","DECLARE","RETURNS","LANGUAGE","VOLATILE","STABLE",
            "RAISE","NOTICE","EXCEPTION","PERFORM",
        ]
        funcoes_sql = [
            "COUNT","SUM","AVG","MAX","MIN","COALESCE","NULLIF","IFNULL","NVL",
            "LENGTH","LEN","SUBSTR","SUBSTRING","UPPER","LOWER","TRIM","LTRIM",
            "RTRIM","REPLACE","CONCAT","CAST","CONVERT","ABS","ROUND","FLOOR",
            "CEILING","CEIL","MOD","POWER","SQRT","NOW","CURRENT_TIMESTAMP",
            "CURRENT_DATE","CURRENT_TIME","DATE","DATETIME","DATEADD","DATEDIFF",
            "EXTRACT","YEAR","MONTH","DAY","HOUR","MINUTE","SECOND",
            "ROW_NUMBER","RANK","DENSE_RANK","NTILE","LAG","LEAD",
            "FIRST_VALUE","LAST_VALUE","OVER","PARTITION",
            "JSON_EXTRACT","JSON_AGG","STRING_AGG","ARRAY_AGG","GROUP_CONCAT",
        ]
        tipos_sql = [
            "INTEGER","INT","BIGINT","SMALLINT","TINYINT","NUMERIC","DECIMAL",
            "FLOAT","REAL","DOUBLE","BOOLEAN","BOOL","TEXT","VARCHAR","CHAR",
            "NVARCHAR","NCHAR","CLOB","BLOB","BINARY","VARBINARY",
            "DATE","TIME","DATETIME","TIMESTAMP","INTERVAL","UUID","JSON","JSONB",
            "SERIAL","BIGSERIAL","SMALLSERIAL","BYTEA","BIT","MONEY","CIDR","INET",
        ]

        flags = QRegularExpression.PatternOption.CaseInsensitiveOption
        self._regras = []

        # 1. Palavras-chave DDL/DML (case-insensitive)
        for w in kw_ddl + kw_dml:
            self._regras.append((
                QRegularExpression(rf'\b{w}\b', flags),
                fmt(cor("palavra_chave", "#c678dd"), negrito=True), 0
            ))

        # 2. Funções SQL
        for f_ in funcoes_sql:
            self._regras.append((
                QRegularExpression(rf'\b{f_}\b', flags),
                fmt(cor("funcao", "#61afef")), 0
            ))

        # 3. Tipos de dados
        for t in tipos_sql:
            self._regras.append((
                QRegularExpression(rf'\b{t}\b', flags),
                fmt(cor("tipo", "#56b6c2")), 0
            ))

        # 4. Strings '...'
        self._regras.append((
            QRegularExpression(r"'([^'\\]|\\.)*'"),
            fmt(cor("string", "#98c379")), 0
        ))

        # 5. Identificadores com backtick `table` ou [table]
        self._regras.append((
            QRegularExpression(r'`[^`]+`|\[[^\]]+\]'),
            fmt(cor("chave_json", "#CE9178")), 0
        ))

        # 6. Parâmetros :nome e @nome
        self._regras.append((
            QRegularExpression(r'[:@][a-zA-Z_]\w*'),
            fmt(cor("atributo", "#e5c07b")), 0
        ))

        # 7. Números
        self._regras.append((
            QRegularExpression(r'\b\d+\.?\d*\b'),
            fmt(cor("numero", "#d19a66")), 0
        ))

        # 8. Comentário de linha --
        self._regras.append((
            QRegularExpression(r'--[^\n]*'),
            fmt_cmt, 0
        ))

        self.rehighlight()

    def highlightBlock(self, texto: str):
        # Continua bloco /* */ da linha anterior
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

        # Bloco /* */ abrindo nesta linha
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
