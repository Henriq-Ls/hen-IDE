# 📁 _EDITOR_/Funcionalidades/multiplos_cursores.py
"""
Múltiplos cursores reais — arquitetura unificada.

source of truth: self._cursores (lista única de QTextCursor)
principal:       self._cursores[self._principal_idx]
extras:          todos os demais (propriedade _cursores_extras)

Ctrl+Alt+Click              → adiciona cursor
Ctrl+Alt+Drag (↑/↓)        → seleção de coluna
Ctrl+Alt+↑/↓               → adiciona cursor linha acima/abaixo
Esc                         → cancela todos
"""
from PySide6.QtCore import Qt
from PySide6.QtGui  import QTextCursor, QTextCharFormat, QColor, QTextFormat
from PySide6.QtWidgets import QTextEdit

class GerenciadorMultiplosCursores:
    def __init__(self, editor):
        self._editor          = editor
        self._cursores: list[QTextCursor] = []
        self._principal_idx   = 0
        self._ativo           = False
        self._arrastando_coluna   = False
        self._coluna_arrasto      = 0
        self._linhas_arrasto: set[int] = set()
        # IMP-08: Ctrl+Alt pendente — decide click vs drag no movimento/release
        self._ctrl_alt_pendente   = False
        self._ctrl_alt_pos_inicio = None
        # rastreia a última linha visitada no drag para preencher intermediárias
        self._ultima_linha_arrasto = -1

    # ------------------------------------------------------------------
    # Propriedade de compatibilidade — usada pelo renderer em Editor.py
    # ------------------------------------------------------------------

    @property
    def _cursores_extras(self) -> list:
        """Cursores sem o principal — para compatibilidade com o renderer."""

        return [c for i, c in enumerate(self._cursores)

                if i != self._principal_idx]

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    def esta_ativo(self) -> bool:
        return self._ativo and len(self._cursores) > 1

    def cancelar(self):
        """
        Esc / clique fora — mantém apenas o cursor principal.
        Remove APENAS os ExtraSelections marcados como multi-cursor
        (UserProperty+1 = True), preservando lint, breakpoints e outros.
        """
        import logging
        log = logging.getLogger("hein")
        if self._cursores:
            p = QTextCursor(self._cursores[self._principal_idx])
            log.debug(
                f"[multi-cursor] cancelar: principal "
                f"anchor={p.anchor()} pos={p.position()}"
            )
            self._cursores = [p]
            self._principal_idx = 0
        else:
            log.debug("[multi-cursor] cancelar: sem cursores ativos")
        self._ativo = False
        # Remove apenas highlights marcados com UserProperty+1 (multi-cursor).
        # Preserva lint, breakpoints e highlight de linha atual.
        outros = [
            s for s in self._editor.extraSelections()
            if not s.format.property(QTextFormat.UserProperty + 1)
        ]
        self._editor.setExtraSelections(outros)
        # Limpa a seleção do cursor principal (Esc deve deselecionar tudo)
        cur = self._editor.textCursor()
        if cur.hasSelection():
            cur.clearSelection()
            self._editor.setTextCursor(cur)
        self._editor.viewport().update()
        # IMP-14: limpa destaque do gutter
        self._notificar_gutter()

    # ------------------------------------------------------------------
    # Manutenção interna da lista
    # ------------------------------------------------------------------

    def _garantir_principal(self):
        """Sincroniza self._cursores[principal_idx] com o textCursor do editor."""
        cp = QTextCursor(self._editor.textCursor())
        if not self._cursores:
            self._cursores = [cp]
            self._principal_idx = 0
        else:
            self._cursores[self._principal_idx] = cp

    # ⚠️  função grande (64 linhas)
    def _normalizar_cursores(self):
        """
        Após cada edição:
          1. ordena por selectionStart
          2. faz merge de seleções sobrepostas (A=[10..20], B=[18..30] → [10..30])
          3. remove pontos duplicados (sem seleção, mesma position)
          4. re-localiza o cursor principal (pode ter sido consumido por merge)
        """
        if len(self._cursores) <= 1:

            return

        principal = self._cursores[self._principal_idx]
        p_pos     = principal.position()

        self._cursores.sort(key=lambda c: c.selectionStart())

        doc    = self._cursores[0].document()
        merged: list[QTextCursor] = []

        for c in self._cursores:
            c_start = c.selectionStart() if c.hasSelection() else c.position()
            c_end   = c.selectionEnd()   if c.hasSelection() else c.position()

            if not merged:
                nc = QTextCursor(doc)
                nc.setPosition(c_start)
                if c_end != c_start:
                    nc.setPosition(c_end, QTextCursor.KeepAnchor)
                merged.append(nc)
                continue

            prev       = merged[-1]
            prev_start = prev.selectionStart() if prev.hasSelection() else prev.position()
            prev_end   = prev.selectionEnd()   if prev.hasSelection() else prev.position()

            # Overlap ou adjacência (prev_end >= c_start) → merge
            if prev_end >= c_start:
                new_start = min(prev_start, c_start)
                new_end   = max(prev_end,   c_end)
                nc = QTextCursor(doc)
                nc.setPosition(new_start)
                if new_end != new_start:
                    nc.setPosition(new_end, QTextCursor.KeepAnchor)
                merged[-1] = nc
            else:
                nc = QTextCursor(doc)
                nc.setPosition(c_start)
                if c_end != c_start:
                    nc.setPosition(c_end, QTextCursor.KeepAnchor)
                merged.append(nc)

        self._cursores = merged

        # Re-localiza o principal: qual cursor merged contém a position original?
        try:
            self._principal_idx = next(
                i for i, c in enumerate(self._cursores)
                if (c.selectionStart() if c.hasSelection() else c.position())
                   <= p_pos <=
                   (c.selectionEnd() if c.hasSelection() else c.position())
            )
        except StopIteration:
            self._principal_idx = 0

    # ------------------------------------------------------------------
    # Clique e arrasto
    # ------------------------------------------------------------------

    def ao_click(self, event) -> bool:
        mods         = event.modifiers()
        ctrl_alt     = mods == (Qt.ControlModifier | Qt.AltModifier)

        if event.button() == Qt.LeftButton and ctrl_alt:
            # IMP-08: guarda posição — decide click ou drag no movimento/release
            self._ctrl_alt_pendente   = True
            self._ctrl_alt_pos_inicio = event.pos()

            return True

        if event.button() == Qt.LeftButton and self.esta_ativo():
            self.cancelar()

        return False

    def _iniciar_arrasto_coluna(self, pos):
        self.cancelar()
        cursor = self._editor.cursorForPosition(pos)
        self._editor.setTextCursor(cursor)
        self._coluna_arrasto       = cursor.positionInBlock()
        self._linhas_arrasto       = {cursor.blockNumber()}
        self._ultima_linha_arrasto = cursor.blockNumber()
        self._arrastando_coluna    = True

    def ao_mover_coluna(self, pos) -> bool: # IMP-08: Ctrl+Alt pendente e saiu da linha de origem → ativa coluna
        if self._ctrl_alt_pendente and not self._arrastando_coluna:
            cursor_atual = self._editor.cursorForPosition(pos)
            cursor_ini   = self._editor.cursorForPosition(self._ctrl_alt_pos_inicio)
            if cursor_atual.blockNumber() != cursor_ini.blockNumber():
                self._ctrl_alt_pendente = False
                self._iniciar_arrasto_coluna(self._ctrl_alt_pos_inicio)
            else:

                return True

        if not self._arrastando_coluna:

            return False

        cursor_pos  = self._editor.cursorForPosition(pos)
        linha_atual = cursor_pos.blockNumber()
        if linha_atual == self._ultima_linha_arrasto:

            return True

        # Preenche TODAS as linhas entre a última visitada e a atual (inclusive),
        # para que o drag rápido não pule linhas intermediárias.
        doc      = self._editor.document()
        ultima   = self._ultima_linha_arrasto
        direcao  = 1 if linha_atual > ultima else -1
        self._garantir_principal()

        for ln in range(ultima + direcao, linha_atual + direcao, direcao):
            if ln in self._linhas_arrasto:
                continue
            self._linhas_arrasto.add(ln)
            bloco = doc.findBlockByNumber(ln)
            if not bloco.isValid():
                continue
            novo = QTextCursor(bloco)
            novo.movePosition(QTextCursor.Right, QTextCursor.MoveAnchor,
                              min(self._coluna_arrasto, bloco.length() - 1))
            self._cursores.append(novo)

        self._ultima_linha_arrasto = linha_atual
        self._ativo = True
        self._atualizar_destaques()

        return True

    def finalizar_arrasto_coluna(self) -> bool:
        """Retorna True se tratou um Ctrl+Alt click ou drag (caller deve bloquear super())."""
        tratou = self._ctrl_alt_pendente or self._arrastando_coluna
        # IMP-08: se Ctrl+Alt soltou sem arrastar → é click (adicionar cursor)
        if self._ctrl_alt_pendente:
            self._ctrl_alt_pendente = False
            self._adicionar_cursor_em(self._ctrl_alt_pos_inicio)
        self._ctrl_alt_pos_inicio  = None
        self._arrastando_coluna    = False
        self._ultima_linha_arrasto = -1
        self._linhas_arrasto.clear()

        return tratou

    def _adicionar_cursor_em(self, pos) -> bool:
        cursor = self._editor.cursorForPosition(pos)
        p = cursor.position()
        self._garantir_principal()
        for c in self._cursores:
            if c.position() == p:

                return True

        self._cursores.append(QTextCursor(cursor))
        self._ativo = True
        self._normalizar_cursores()
        self._atualizar_destaques()
        self._editor.viewport().update()  # cursor extra visível imediatamente

        return True

    def adicionar_cursor_acima(self):
        """Ctrl+Alt+↑ — adiciona cursor na linha acima do cursor mais alto."""
        self._garantir_principal()
        col = self._cursores[self._principal_idx].positionInBlock()
        ref = min(self._cursores, key=lambda c: c.selectionStart())
        novo = QTextCursor(ref)
        if not novo.movePosition(QTextCursor.Up):

            return

        novo.movePosition(QTextCursor.StartOfBlock)
        novo.movePosition(QTextCursor.Right, QTextCursor.MoveAnchor,
                          min(col, novo.block().length() - 1))
        self._cursores.append(novo)
        self._ativo = True
        self._normalizar_cursores()
        self._atualizar_destaques()

    def adicionar_cursor_abaixo(self):
        """Ctrl+Alt+↓ — adiciona cursor na linha abaixo do cursor mais baixo."""
        self._garantir_principal()
        col = self._cursores[self._principal_idx].positionInBlock()
        ref = max(self._cursores, key=lambda c: c.selectionStart())
        novo = QTextCursor(ref)
        if not novo.movePosition(QTextCursor.Down):

            return

        novo.movePosition(QTextCursor.StartOfBlock)
        novo.movePosition(QTextCursor.Right, QTextCursor.MoveAnchor,
                          min(col, novo.block().length() - 1))
        self._cursores.append(novo)
        self._ativo = True
        self._normalizar_cursores()
        self._atualizar_destaques()

    # ------------------------------------------------------------------
    # Processamento de tecla — núcleo arquitetural
    # ------------------------------------------------------------------

    # ⚠️  função grande (222 linhas)
    def ao_tecla(self, event) -> bool:
        """
        Processa a tecla para TODOS os cursores uniformemente.
        Regras:
          - Cursores ordenados do maior para o menor position → sem drift
          - Um único beginEditBlock/endEditBlock → um único Ctrl+Z
          - Enter usa auto_indent em todos (principal não tem privilégio)
          - Tab com seleção → indenta linhas (não destrói seleção)
          - Backtab → recua linhas
          - Home/End/setas → move TODOS os cursores (não só o principal)
        Retorna True se consumiu o evento.
        """
        import logging
        log = logging.getLogger("hein")

        if not self.esta_ativo():

            return False

        key   = event.key()
        mod   = event.modifiers()
        texto = event.text()

        if key == Qt.Key_Escape:
            self.cancelar()

            return True

        ctrl  = bool(mod & Qt.ControlModifier)
        shift = bool(mod & Qt.ShiftModifier)

        # ── Navegação: Home/End/setas aplicadas em TODOS os cursores ────────
        # ANTES do ctrl-gate — Ctrl+Left/Right são navegação válida.
        e_home  = key == Qt.Key_Home
        e_end   = key == Qt.Key_End
        e_left  = key == Qt.Key_Left
        e_right = key == Qt.Key_Right
        e_up    = key == Qt.Key_Up
        e_down  = key == Qt.Key_Down
        e_nav   = e_home or e_end or e_left or e_right or e_up or e_down

        # Ctrl+Alt+↑/↓ → adicionar cursor, NÃO navegar — keyPressEvent trata
        ctrl_alt = bool(mod & Qt.ControlModifier) and bool(mod & Qt.AltModifier)
        if ctrl_alt and (e_up or e_down):

            return False

        if e_nav:
            anchor = QTextCursor.KeepAnchor if shift else QTextCursor.MoveAnchor
            for i in range(len(self._cursores)):
                c = self._cursores[i]
                if e_home:
                    # Smart Home: vai para o primeiro caractere não-espaço.
                    # Se já está lá (ou não há indentação), vai para col 0.
                    col_atual   = c.positionInBlock()
                    texto_bloco = c.block().text()
                    col_texto   = len(texto_bloco) - len(texto_bloco.lstrip())
                    c.movePosition(QTextCursor.StartOfLine, anchor)
                    if col_atual != col_texto and col_texto > 0:
                        c.movePosition(QTextCursor.Right, anchor, col_texto)
                elif e_end:
                    c.movePosition(QTextCursor.EndOfLine, anchor)
                elif e_left:
                    if ctrl:
                        c.movePosition(QTextCursor.PreviousWord, anchor)
                    else:
                        c.movePosition(QTextCursor.PreviousCharacter, anchor)
                elif e_right:
                    if ctrl:
                        c.movePosition(QTextCursor.NextWord, anchor)
                    else:
                        c.movePosition(QTextCursor.NextCharacter, anchor)
                elif e_up:
                    c.movePosition(QTextCursor.Up, anchor)
                elif e_down:
                    c.movePosition(QTextCursor.Down, anchor)
                self._cursores[i] = c  # PySide6 value-type: re-assign garante update na lista

            log.debug(
                f"[multi-cursor] nav key={key} shift={shift} ctrl={ctrl} "
                f"cursores={len(self._cursores)} principal_idx={self._principal_idx}"
            )
            self._editor.setTextCursor(self._cursores[self._principal_idx])
            self._normalizar_cursores()
            self._atualizar_destaques()
            self._editor.viewport().update()  # repaint garante que _desenhar_cursor exibe extras

            return True

        # IMP-13 ─ Ctrl+C / V / X com multi-cursor ──────────────────────────
        if ctrl and key == Qt.Key_C:
            from PySide6.QtGui import QGuiApplication
            partes = [c.selectedText() for c in
                      sorted(self._cursores, key=lambda c: c.selectionStart())]
            QGuiApplication.clipboard().setText('\n'.join(partes))

            return True

        if ctrl and key == Qt.Key_X:
            from PySide6.QtGui import QGuiApplication
            partes = [c.selectedText() for c in
                      sorted(self._cursores, key=lambda c: c.selectionStart())]
            QGuiApplication.clipboard().setText('\n'.join(partes))
            self._garantir_principal()
            doc    = self._editor.document()
            master = QTextCursor(doc)
            master.beginEditBlock()
            for c in sorted(self._cursores,
                            key=lambda c: c.selectionStart(), reverse=True):
                if c.hasSelection():
                    nc = QTextCursor(doc)
                    nc.setPosition(c.selectionStart())
                    nc.setPosition(c.selectionEnd(), QTextCursor.KeepAnchor)
                    nc.removeSelectedText()
            master.endEditBlock()
            self.cancelar()

            return True

        if ctrl and key == Qt.Key_V:
            from PySide6.QtGui import QGuiApplication
            texto_clip = QGuiApplication.clipboard().text()
            partes     = texto_clip.split('\n')
            self._garantir_principal()
            doc    = self._editor.document()
            # Índices ordenados pelo selectionStart ascendente
            ord_asc = sorted(range(len(self._cursores)),
                             key=lambda i: self._cursores[i].selectionStart())
            usa_partes = len(partes) == len(self._cursores)
            master = QTextCursor(doc)
            master.beginEditBlock()
            # Aplica do fim para o início para não deslocar posições
            for rev_i, orig_i in enumerate(reversed(ord_asc)):
                c  = self._cursores[orig_i]
                nc = QTextCursor(doc)
                nc.setPosition(c.anchor())
                nc.setPosition(c.position(), QTextCursor.KeepAnchor)
                parte = partes[len(ord_asc) - 1 - rev_i] if usa_partes else texto_clip
                nc.insertText(parte)
            master.endEditBlock()
            self.cancelar()

            return True

        # Ctrl+qualquer_coisa (exceto Backspace/Delete) → não consumir
        if ctrl and key not in (Qt.Key_Backspace, Qt.Key_Delete):

            return False

        e_backspace = key == Qt.Key_Backspace
        e_delete    = key == Qt.Key_Delete
        e_enter     = key in (Qt.Key_Return, Qt.Key_Enter)
        e_tab       = key == Qt.Key_Tab
        e_backtab   = key == Qt.Key_Backtab
        e_texto     = bool(texto and texto.isprintable())

        if not (e_backspace or e_delete or e_enter or e_tab or e_backtab or e_texto):

            return False

        self._garantir_principal()
        doc = self._editor.document()

        # ── Reconstrói todos os cursores frescos, do maior para o menor ──
        todos: list[tuple[QTextCursor, bool]] = []
        for i, c in enumerate(self._cursores):
            nc = QTextCursor(doc)
            nc.setPosition(c.anchor())
            nc.setPosition(c.position(), QTextCursor.KeepAnchor)
            todos.append((nc, i == self._principal_idx))
        todos.sort(key=lambda x: x[0].position(), reverse=True)

        # ── Bloco único de undo — um único Ctrl+Z reverte tudo ───────────
        master = todos[0][0]
        master.beginEditBlock()

        for c, _e_principal in todos:
            if e_tab or e_backtab:
                if c.hasSelection():
                    self._aplicar_indent_linhas(c, recuar=e_backtab)
                elif e_tab:
                    c.insertText("    ")
                else:
                    self._recuar_linha_cursor(c)

            elif e_backspace:
                if c.hasSelection():
                    c.removeSelectedText()
                elif not c.atStart():
                    c.deletePreviousChar()

            elif e_delete:
                if c.hasSelection():
                    c.removeSelectedText()
                elif not c.atEnd():
                    c.deleteChar()

            elif e_enter:
                if c.hasSelection():
                    c.removeSelectedText()
                linha  = c.block().text()[:c.positionInBlock()]
                indent = self._editor.auto_indent.processar_enter(c, linha)
                c.insertText("\n" + indent)

            elif e_texto:
                if c.hasSelection():
                    c.removeSelectedText()
                c.insertText(texto)

        master.endEditBlock()

        # ── Reconstrói self._cursores com as novas posições ──────────────
        principal_novo = next((c for c, e_p in todos if e_p), todos[0][0])
        extras_novos   = [c for c, e_p in todos if not e_p]
        self._cursores      = [principal_novo] + extras_novos
        self._principal_idx = 0

        self._editor.setTextCursor(self._cursores[self._principal_idx])
        self._normalizar_cursores()
        self._atualizar_destaques()

        return True

    # ------------------------------------------------------------------
    # Helpers de indentação estrutural
    # ------------------------------------------------------------------

    def _aplicar_indent_linhas(self, cursor: QTextCursor, recuar: bool):
        """
        Tab com seleção: indenta/recua todas as linhas cobertas.
        Não destrói a seleção — comportamento IDE correto.
        Opera de baixo para cima para não deslocar posições.
        """
        doc   = cursor.document()
        start = cursor.selectionStart()
        end   = cursor.selectionEnd()

        b_ini = doc.findBlock(start)
        b_fim = doc.findBlock(end)
        # Se end está exatamente no início de um bloco, não incluir essa linha
        if b_fim.position() == end and b_fim != b_ini:
            b_fim = b_fim.previous()

        blocos = []
        b = b_ini
        while b.isValid() and b.blockNumber() <= b_fim.blockNumber():
            blocos.append(b)
            b = b.next()

        for bloco in reversed(blocos):
            c = QTextCursor(bloco)
            c.movePosition(QTextCursor.StartOfBlock)
            if recuar:
                txt = bloco.text()
                n = 0
                while n < 4 and n < len(txt) and txt[n] == ' ':
                    n += 1
                if n > 0:
                    c.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, n)
                    c.removeSelectedText()
            else:
                c.insertText("    ")

        # Ajusta a seleção do cursor para cobrir as linhas modificadas
        ultimo = blocos[-1]
        cursor.setPosition(b_ini.position())
        cursor.setPosition(ultimo.position() + ultimo.length() - 1,
                           QTextCursor.KeepAnchor)

    def _recuar_linha_cursor(self, cursor: QTextCursor):
        """Backtab sem seleção: remove até 4 espaços do início da linha."""
        bloco = cursor.block()
        txt   = bloco.text()
        n = 0
        while n < 4 and n < len(txt) and txt[n] == ' ':
            n += 1
        if n > 0:
            c = QTextCursor(bloco)
            c.movePosition(QTextCursor.StartOfBlock)
            c.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, n)
            c.removeSelectedText()

    # ------------------------------------------------------------------
    # Visual — highlights dos cursores extras
    # ------------------------------------------------------------------

    def _notificar_gutter(self):
        """IMP-14: atualiza o gutter com as linhas que têm cursor extra (1-based)."""
        gutter = getattr(self._editor, 'area_numeros', None)
        if gutter is None:

            return

        fn = getattr(gutter, 'set_linhas_multi', None)
        if fn is None:

            return

        if self.esta_ativo():
            linhas = {c.blockNumber() + 1 for c in self._cursores}
        else:
            linhas = set()
        fn(linhas)

    def _atualizar_destaques(self):
        """
        Adiciona ExtraSelection apenas para cursores extras COM seleção.
        Cursores sem seleção são desenhados como blocos em _desenhar_cursor
        (Editor.py) — sem 1-char fallback que causava conflito visual.
        Cores vêm do tema global — proibido hardcode.
        """
        from _CONFIGURA_.gerenciador_tema import tema_global as _tema_fn
        _tema = _tema_fn()

        fmt = QTextCharFormat()
        fmt.setBackground(QColor(_tema.cor("editor.selecao",  "#264f78")))
        fmt.setForeground(QColor(_tema.cor("editor.texto",    "#e0e0e0")))
        fmt.setProperty(QTextFormat.UserProperty + 1, True)  # marcador multi-cursor

        selecoes = []
        for c in self._cursores_extras:
            if not c.hasSelection():
                continue
            sel = QTextEdit.ExtraSelection()
            nc  = QTextCursor(self._editor.document())
            nc.setPosition(c.anchor())
            nc.setPosition(c.position(), QTextCursor.KeepAnchor)
            sel.cursor = nc
            sel.format = fmt
            selecoes.append(sel)

        # Remove apenas os highlights de multi-cursor anteriores (UserProperty+1).
        # Preserva lint, breakpoints e highlight de linha atual.
        outros = [
            s for s in self._editor.extraSelections()
            if not s.format.property(QTextFormat.UserProperty + 1)
        ]
        self._editor.setExtraSelections(outros + selecoes)

        # IMP-14: notifica o gutter das linhas com cursor extra
        self._notificar_gutter()
