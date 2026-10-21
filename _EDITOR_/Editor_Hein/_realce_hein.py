# 📁 _EDITOR_/Editor_Hein/_realce_hein.py
"""
HighlighterHein — realçador do Editor Caderno (.hein).

Regras:
  • Linha sem recuo (col-0) → NEGRITO + COR_TOPICO_PAPEL     → tópico
  • Linha recuada           → peso normal                    → parágrafo
  • # em qualquer posição  → itálico + cor pauta             → comentário
  • #cod: / #cod; / #:     → Tags de Comentário hein
                             (igual ao Editor Python — fundo/fonte/herança)

API pública (chamada pelo Editor via cursorPositionChanged / selectionChanged):
  definir_linha_cursor_tag(numero_bloco)
  definir_selecao_tag(bloco_inicio, bloco_fim)
"""
from PySide6.QtCore import QRegularExpression
from PySide6.QtGui  import QSyntaxHighlighter, QTextCharFormat, QFont, QColor
from _CONFIGURA_    import COR_TOPICO_PAPEL, COR_PALTA_PAPEL

# ── Tags de Comentário hein ───────────────────────────────────────────────────
# Mesma paleta do realce Python — #cod: pinta FUNDO, #cod; pinta FONTE, #: herda
_PALETA_TAGS = {
    "al": "#3B82F6",  # azul
    "vo": "#E53935",  # vermelho
    "po": "#000000",  # preto
    "ao": "#FBC02D",  # amarelo
    "ca": "#9E9E9E",  # cinza
    "co": "#00ACC1",  # ciano
    "ba": "#F5F5F5",  # branca
    "ve": "#43A047",  # verde
    "ra": "#EC407A",  # rosa
    "ro": "#8E24AA",  # roxo
    "mm": "#8D6E43",  # marrom
    "la": "#FB8C00",  # laranja
}
_CODIGOS = list(_PALETA_TAGS.keys())
_N       = len(_CODIGOS)
_INDICE  = {c: i + 1 for i, c in enumerate(_CODIGOS)}


class HighlighterHein(QSyntaxHighlighter):
    """Realçador do Editor Caderno (.hein)."""

    def __init__(self, document):
        super().__init__(document)

        # Rastreio de foco — minimiza #cod: quando linha não está em foco
        self._linha_cursor_tag     = -1
        self._bloco_selecao_inicio = -1
        self._bloco_selecao_fim    = -1

        # ── Formatos base ────────────────────────────────────────────────
        # Qt6: peso é 100–900 (Bold=700, Normal=400)
        self._fmt_topico = QTextCharFormat()
        self._fmt_topico.setFontWeight(int(QFont.Weight.Bold))
        self._fmt_topico.setForeground(QColor(COR_TOPICO_PAPEL))

        self._fmt_paragrafo = QTextCharFormat()
        self._fmt_paragrafo.setFontWeight(int(QFont.Weight.Normal))

        # Comentário: qualquer # → itálico + cor das pautas/gutter
        self._fmt_comentario = QTextCharFormat()
        self._fmt_comentario.setFontItalic(True)
        self._fmt_comentario.setForeground(QColor(COR_PALTA_PAPEL))

        self._re_comentario = QRegularExpression(r"#[^\n]*")

        # ── Tags de Comentário ───────────────────────────────────────────
        _alt = "|".join(_CODIGOS)
        self._re_tag_fundo  = QRegularExpression(rf"#({_alt}):")
        self._re_tag_fonte  = QRegularExpression(rf"#({_alt});")
        self._re_tag_atalho = QRegularExpression(r"#:")

        self._fmts_tag_fundo = {}
        self._fmts_tag_fonte = {}
        for codigo, hexcor in _PALETA_TAGS.items():
            fmt_f = QTextCharFormat()
            c = QColor(hexcor)
            c.setAlpha(70)
            fmt_f.setBackground(c)
            self._fmts_tag_fundo[codigo] = fmt_f

            fmt_t = QTextCharFormat()
            fmt_t.setForeground(QColor(hexcor))
            self._fmts_tag_fonte[codigo] = fmt_t

        # Miniatura do código da tag quando linha não está em foco
        self._fmt_tag_mini = QTextCharFormat()
        self._fmt_tag_mini.setFontPointSize(6)
        c_mini = QColor(COR_PALTA_PAPEL)
        c_mini.setAlpha(120)
        self._fmt_tag_mini.setForeground(c_mini)

    # ── API pública ───────────────────────────────────────────────────────────

    def definir_linha_cursor_tag(self, numero_bloco: int):
        """Chamado pelo editor (cursorPositionChanged) — linha onde o código
        da tag deve aparecer por completo (sem miniaturizar)."""
        anterior = self._linha_cursor_tag
        if anterior == numero_bloco:
            return
        self._linha_cursor_tag = numero_bloco
        doc = self.document()
        for n in (anterior, numero_bloco):
            if 0 <= n < doc.blockCount():
                self.rehighlightBlock(doc.findBlockByNumber(n))

    def definir_selecao_tag(self, bloco_inicio: int, bloco_fim: int):
        """Chamado pelo editor (selectionChanged) — intervalo de blocos
        selecionados (-1, -1 quando não há seleção)."""
        ant_ini, ant_fim = self._bloco_selecao_inicio, self._bloco_selecao_fim
        if (ant_ini, ant_fim) == (bloco_inicio, bloco_fim):
            return
        self._bloco_selecao_inicio = bloco_inicio
        self._bloco_selecao_fim    = bloco_fim
        doc = self.document()
        candidatos = [x for x in (ant_ini, ant_fim, bloco_inicio, bloco_fim) if x >= 0]
        if not candidatos:
            return
        ini, fim = min(candidatos), max(candidatos)
        for n in range(ini, min(fim, doc.blockCount() - 1) + 1):
            self.rehighlightBlock(doc.findBlockByNumber(n))

    # ── Core ──────────────────────────────────────────────────────────────────

    def highlightBlock(self, text: str):
        # Estado de bloco = tag_ativa herdada do bloco anterior
        # (0 = nenhuma; 1..N = modo FUNDO; N+1..2N = modo FONTE)
        tag_ativa = self.previousBlockState()
        if tag_ativa < 0:
            tag_ativa = 0

        if not text:
            self.setCurrentBlockState(tag_ativa)
            return

        # 1. Formato base: tópico (col-0 bold+cor) ou parágrafo (normal)
        eh_topico = text[0] not in (' ', '\t')
        self.setFormat(0, len(text), self._fmt_topico if eh_topico else self._fmt_paragrafo)

        # 2. Comentário: # em qualquer posição → itálico + cor pauta
        #    (sobrescrito pelas tags logo abaixo, se a linha for tagged)
        it = self._re_comentario.globalMatch(text)
        while it.hasNext():
            m = it.next()
            self.setFormat(m.capturedStart(), m.capturedLength(), self._fmt_comentario)

        # 3. Tags de Comentário hein
        bloco_atual   = self.currentBlock().blockNumber()
        linha_em_foco = (
            bloco_atual == self._linha_cursor_tag
            or (self._bloco_selecao_inicio >= 0
                and self._bloco_selecao_inicio <= bloco_atual <= self._bloco_selecao_fim)
        )
        marcador_span = None

        m_fundo = self._re_tag_fundo.match(text)
        if m_fundo.hasMatch():
            codigo = m_fundo.captured(1)
            inicio = m_fundo.capturedStart()
            fmt = self._fmts_tag_fundo.get(codigo)
            if fmt:
                self.setFormat(inicio, len(text) - inicio, fmt)
            if codigo in _INDICE:
                tag_ativa = _INDICE[codigo]           # modo FUNDO
            marcador_span = (inicio, m_fundo.capturedLength())
        else:
            m_fonte = self._re_tag_fonte.match(text)
            if m_fonte.hasMatch():
                codigo = m_fonte.captured(1)
                inicio = m_fonte.capturedStart()
                fmt = self._fmts_tag_fonte.get(codigo)
                if fmt:
                    self.setFormat(inicio, len(text) - inicio, fmt)
                if codigo in _INDICE:
                    tag_ativa = _INDICE[codigo] + _N  # modo FONTE
                marcador_span = (inicio, m_fonte.capturedLength())
            elif tag_ativa:
                m_atalho = self._re_tag_atalho.match(text)
                if m_atalho.hasMatch():
                    if tag_ativa <= _N:
                        fmt = self._fmts_tag_fundo.get(_CODIGOS[tag_ativa - 1])
                    else:
                        fmt = self._fmts_tag_fonte.get(_CODIGOS[tag_ativa - _N - 1])
                    inicio = m_atalho.capturedStart()
                    if fmt:
                        self.setFormat(inicio, len(text) - inicio, fmt)
                    # #: só herda — não redefine nem encerra a cadeia
                    marcador_span = (inicio, m_atalho.capturedLength())

        # Miniaturiza o código da tag (#al:, #al;, #:) quando não está em foco
        if marcador_span is not None and not linha_em_foco:
            self.setFormat(marcador_span[0], marcador_span[1], self._fmt_tag_mini)

        self.setCurrentBlockState(tag_ativa)
