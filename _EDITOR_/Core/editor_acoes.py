# 📁 _EDITOR_/Core/editor_acoes.py
"""
_EditorAcoesMixin — ações de teclado e manipulação de texto do CodeEditor.
Parte 1 de 3 do split do Editor.
"""
import re
from PySide6.QtWidgets import QTextEdit, QApplication, QToolTip
from PySide6.QtGui import (
    QColor, QTextCharFormat, QTextCursor, QKeySequence, QTextBlockFormat
)
from PySide6.QtCore import Qt, QMimeData
from _CONFIGURA_ import FONTE_EDITOR_MIN, FONTE_EDITOR_MAX, FONTE_EDITOR_PADRAO
_PARES      = {"(": ")", "[": "]", "{": "}", '"': '"', "'": "'"}
_FECHADORES = set(_PARES.values())

_MIME_LINHA = "application/x-hein-line-copy"

def _fonte_padrao() -> int:
    """Lê o tamanho de fonte do configurar.json. Retorna fallback se indisponível."""
    try:
        from _CONFIGURA_.gerenciador_configurar import config_global

        return int(config_global().obter("editor", "tamanho_fonte", FONTE_EDITOR_PADRAO))

    except Exception:

        return FONTE_EDITOR_PADRAO

def _clipboard_e_linha() -> bool:
    """
    Retorna True se o clipboard foi preenchido por um Ctrl+C/X de linha inteira
    do hein. O marcador vive dentro do QMimeData — qualquer outro app que
    escreva no clipboard não inclui esse MIME type, então a detecção é automática.
    """

    return QApplication.clipboard().mimeData().hasFormat(_MIME_LINHA)

def _clipboard_texto_linha() -> str:
    """Retorna o texto do clipboard quando ele contém uma linha inteira."""

    return QApplication.clipboard().mimeData().text()

class _EditorAcoesMixin:
    """Mixin com todas as ações de teclado e manipulação de texto."""

    def _invalidar_popups_interacao(self) -> None:
        """Fecha e invalida popups quando o usuário muda o contexto visual.

        ``TooltipSignature`` é um ``Qt.ToolTip`` separado do editor. Por isso
        um clique na Outline, um scroll ou um arraste de seleção podem ocorrer
        sem passar pelo ``mousePressEvent`` do editor. Usar a API pública do
        autocomplete aqui também incrementa ``_geracao_signature`` e descarta
        respostas Jedi que ainda estejam em voo.
        """
        autocomplete = getattr(self, "_autocomplete", None)
        if autocomplete is not None:
            try:
                autocomplete.fechar()
            except (AttributeError, RuntimeError):
                pass

        quick_fix = getattr(self, "_popup_quick_fix", None)
        if quick_fix is not None:
            try:
                quick_fix.fechar()
            except (AttributeError, RuntimeError):
                pass

    def _fechar_popups_esc(self) -> bool:
        """Fecha pop-ups pertencentes a este editor quando Esc é pressionado.

        Pop-ups criados com ``Qt.ToolTip`` podem continuar visíveis sem que o
        foco volte para o editor. Por isso o fechamento não depende apenas do
        ``keyPressEvent`` local: esta mesma rotina também é chamada pelo
        filtro global do autocomplete.
        """
        fechou = False

        QToolTip.hideText()

        def _fechar(widget, metodo: str = "fechar") -> None:
            nonlocal fechou
            try:
                if widget is not None and widget.isVisible():
                    fechar = getattr(widget, metodo, None)
                    if callable(fechar):
                        fechar()
                    else:
                        widget.hide()
                    fechou = True
            except RuntimeError:
                pass

        # Componentes com API própria de fechamento.
        autocomplete = getattr(self, '_autocomplete', None)
        if autocomplete is not None:
            try:
                visivel = (
                    autocomplete._lista.isVisible()
                    or autocomplete._tooltip.isVisible()
                )
                if visivel:
                    autocomplete.fechar()
                    fechou = True
            except (AttributeError, RuntimeError):
                pass

        quick_fix = getattr(self, '_popup_quick_fix', None)
        _fechar(quick_fix)
        _fechar(getattr(quick_fix, '_toast', None) if quick_fix else None)
        _fechar(getattr(self, '_diff_inline', None))
        _fechar(getattr(self, '_painel_busca', None))

        find_refs = getattr(self, '_find_refs', None)
        _fechar(getattr(find_refs, '_painel', None) if find_refs else None)

        corretor = getattr(self, '_corretor', None)
        _fechar(getattr(corretor, '_popup', None) if corretor else None)

        float_menu = getattr(self, '_float_menu', None)
        _fechar(getattr(float_menu, '_painel', None) if float_menu else None)
        if float_menu is not None and getattr(float_menu, '_painel_aberto', False):
            try:
                float_menu.fechar_painel()
                fechou = True
            except (AttributeError, RuntimeError):
                pass

        outline = getattr(self, '_outline', None)
        _fechar(getattr(outline, '_popup_atalhos', None) if outline else None)

        # Captura outros pop-ups Qt pertencentes ao editor, inclusive filhos
        # internos do viewport que não têm uma referência pública no editor.
        try:
            from PySide6.QtWidgets import QApplication
            flags_popup = Qt.ToolTip | Qt.Popup

            for widget in QApplication.allWidgets():
                if widget is self or not widget.isVisible():
                    continue
                if not (widget.windowFlags() & flags_popup):
                    continue

                pertence = False
                atual = widget
                while atual is not None:
                    if atual is self:
                        pertence = True
                        break
                    atual = atual.parentWidget()
                if pertence:
                    widget.hide()
                    fechou = True
        except (AttributeError, RuntimeError):
            pass

        return fechou

    # ══════════════════════════════════════════════════════════════════
    # Eventos de teclado
    # ══════════════════════════════════════════════════════════════════

    # ⚠️  função grande (306 linhas)
    def keyPressEvent(self, event):
        key            = event.key()
        mod            = event.modifiers()
        ctrl           = mod == Qt.ControlModifier
        alt            = mod == Qt.AltModifier
        ctrl_alt       = mod == (Qt.ControlModifier | Qt.AltModifier)
        ctrl_shift     = mod == (Qt.ControlModifier | Qt.ShiftModifier)
        ctrl_alt_shift = mod == (Qt.ControlModifier | Qt.AltModifier | Qt.ShiftModifier)
        shift          = mod == Qt.ShiftModifier
        texto          = event.text()

        if key == Qt.Key_Escape and self._fechar_popups_esc():

            return

        if self._autocomplete.interceptar_tecla(event):

            return

        limite = getattr(self, '_limite_linha', 0)
        if limite > 0 and texto and texto not in ('\n', '\r') and not (mod & Qt.ControlModifier):
            cursor = self.textCursor()
            if not cursor.hasSelection() and cursor.block().length() - 1 >= limite:

                return

        if self._multi_cursor.ao_tecla(event):

            return

        if key == Qt.Key_Escape:
            QToolTip.hideText()

            if self._multi_cursor.esta_ativo():
                self._multi_cursor.cancelar()

                return

        if event.matches(QKeySequence.Find):
            self._abrir_busca()

            return

        if key == Qt.Key_H and ctrl:
            self._abrir_substituicao()

            return

        if key == Qt.Key_F12:
            self._ir_definicao.ir_para_definicao()

            return

        if key == Qt.Key_Left and alt:
            self._ir_definicao.voltar()

            return

        if key == Qt.Key_Up   and alt: self.mover_linha_cima();  return
        if key == Qt.Key_Down and alt: self.mover_linha_baixo(); return

        if key == Qt.Key_Up   and ctrl_alt: self.adicionar_cursor_acima();        return
        if key == Qt.Key_Down and ctrl_alt: self.adicionar_cursor_abaixo();       return
        if key == Qt.Key_L    and ctrl_alt: self.selecionar_todas_ocorrencias();  return
        if key == Qt.Key_P    and ctrl_alt: self.selecionar_proxima_ocorrencia(); return  # IMP-10
        if key == Qt.Key_D    and ctrl:     self.duplicar_linha(); return

        if key == Qt.Key_F and ctrl_shift:
            cursor = self.textCursor()
            termo  = cursor.selectedText() if cursor.hasSelection() else ""
            janela = self.window()
            if hasattr(janela, 'abrir_busca'):
                janela.abrir_busca(termo)

            return

        # ── Fold — teclas +, =, - ────────────────────────────────────────
        # ABNT2: '+' requer Shift, então Ctrl++ chega como Ctrl+Shift ao Qt.
        # Máscara: ignora Shift, verifica só ControlModifier.
        # Ctrl++ e Ctrl+- fazem a mesma coisa: toggle fold.
        if key in (Qt.Key_Plus, Qt.Key_Equal, Qt.Key_Minus):
            _m = mod & (Qt.ControlModifier | Qt.AltModifier)  # ignora Shift
            # Ctrl+Alt+- → recolher tudo  |  Ctrl+Alt++ → expandir tudo
            if _m == (Qt.ControlModifier | Qt.AltModifier):
                if key == Qt.Key_Minus:
                    self.recolher_tudo()
                elif key in (Qt.Key_Plus, Qt.Key_Equal):
                    self.expandir_tudo()

                return

            if _m == Qt.ControlModifier:
                # Ctrl+- → só fechar  |  Ctrl++ → só abrir  (sem toggle)
                _abrir = key in (Qt.Key_Plus, Qt.Key_Equal)
                _c = self.textCursor()
                if _c.hasSelection():
                    # Comparar blockNumber em vez de position() — evita incluir o
                    # bloco seguinte quando selectionEnd() cai no seu início.
                    _bloco_fim = self.document().findBlock(_c.selectionEnd())
                    _fim_num   = _bloco_fim.blockNumber()
                    _bloco     = self.document().findBlock(_c.selectionStart())
                    _para_agir = []
                    while _bloco.isValid() and _bloco.blockNumber() <= _fim_num:
                        if _abrir:
                            # Ctrl++ → apenas blocos já colapsados (têm FoldRegion)
                            if self._get_fold_region(_bloco) is not None:
                                _para_agir.append(_bloco.blockNumber())
                        else:
                            # Ctrl+- → apenas blocos visíveis/dobráveis ainda abertos
                            if (_bloco.isVisible()
                                    and self._linha_e_dobravel(_bloco)
                                    and self._get_fold_region(_bloco) is None):
                                _para_agir.append(_bloco.blockNumber())
                        _bloco = _bloco.next()
                    # 3.2 — seleção parcial dentro de um bloco: nenhum cabeçalho
                    # encontrado no range → subir a partir do início da seleção
                    # para achar o bloco pai que contém toda a seleção.
                    if not _abrir and not _para_agir:
                        _b = self.document().findBlock(_c.selectionStart())
                        _nivel_filho = (
                            self._nivel_indentacao(_b.text())
                            if _b.text().strip() else 999
                        )
                        _pai = _b.previous()
                        while _pai.isValid():
                            _t = _pai.text()
                            if _t.strip():
                                if self._nivel_indentacao(_t) < _nivel_filho:
                                    if (self._linha_e_dobravel(_pai)
                                            and self._get_fold_region(_pai) is None):
                                        _para_agir.append(_pai.blockNumber())
                                    break
                            _pai = _pai.previous()
                    # Minus → fechar de baixo pra cima (filhos antes dos pais).
                    # Plus  → abrir  de cima pra baixo (pais antes dos filhos).
                    _ordem = list(_para_agir) if _abrir else list(reversed(_para_agir))
                    for _num in _ordem:
                        _b = self.document().findBlockByNumber(_num)
                        if _abrir:
                            self.expandir_bloco(_b)
                        else:
                            self.recolher_bloco(_b)
                else:
                    _bloco = _c.block()
                    if _abrir:
                        self.expandir_bloco(_bloco)
                    else:
                        self.recolher_bloco(_bloco)

                return

        if key == Qt.Key_0 and ctrl:
            self.resetar_fonte(); return

        if key == Qt.Key_Slash and ctrl:
            self.comentar_linha(); return

        if key == Qt.Key_K and ctrl_shift: self.deletar_linha();  return
        if key == Qt.Key_D and ctrl_shift: self.duplicar_linha(); return

        if key == Qt.Key_C and ctrl:
            cursor = self.textCursor()
            if not cursor.hasSelection():
                self._copiar_linha_inteira()

                return

            super().keyPressEvent(event)

            return

        if key == Qt.Key_X and ctrl:
            cursor = self.textCursor()
            if not cursor.hasSelection():
                self._recortar_linha_inteira()

                return

            super().keyPressEvent(event)

            return

        # FIX 5: Enter usa cursor.insertText dentro de editBlock para preservar Undo
        if key in (Qt.Key_Return, Qt.Key_Enter):
            cursor = self.textCursor()
            linha  = cursor.block().text()[:cursor.positionInBlock()]
            indent = self.auto_indent.processar_enter(cursor, linha)
            cursor.beginEditBlock()
            cursor.insertText("\n" + indent)
            cursor.endEditBlock()
            self.setTextCursor(cursor)

            return

        if key == Qt.Key_Tab:
            cursor = self.textCursor()
            if cursor.hasSelection():
                self._indentar_selecao(cursor, True)
            else:
                self.insertPlainText("    ")

            return

        if key == Qt.Key_Backtab:
            self._indentar_selecao(self.textCursor(), False)

            return

        # FIX 1 (MIME): Ctrl+V detecta linha-inteira via MIME type proprietário.
        # Qualquer cópia de outro app não inclui _MIME_LINHA → paste normal automático.
        if key == Qt.Key_V and ctrl:
            cursor = self.textCursor()
            if not cursor.hasSelection() and _clipboard_e_linha():
                texto_clip = _clipboard_texto_linha()
                cursor.movePosition(QTextCursor.EndOfLine)
                # FIX 6: remove só o último \n, preserva newlines intencionais do meio
                clip = texto_clip[:-1] if texto_clip.endswith("\n") else texto_clip
                cursor.insertText("\n" + clip)
                self.setTextCursor(cursor)

                return

            super().keyPressEvent(event)

            return

        # FIX 2: triple-quote só dispara quando NÃO há seleção ativa.
        # Com seleção, cai no bloco _PARES que faz o auto-surround corretamente.
        if texto == '"':
            cursor = self.textCursor()
            if not cursor.hasSelection():
                pos = cursor.position()
                doc = self.toPlainText()
                # Caso 1: cursor logo após "" sem "" à frente → inicia triple → """|"""
                if pos >= 2 and doc[pos-2:pos] == '""' and not (pos < len(doc) and doc[pos] == '"'):
                    cursor.insertText('""""')
                    cursor.movePosition(QTextCursor.PreviousCharacter, QTextCursor.MoveAnchor, 3)
                    self.setTextCursor(cursor)

                    return

                # Caso 2: já tem """" à frente — completa para """"""
                if pos >= 2 and doc[pos-2:pos] == '""' and doc[pos:pos+2] == '""':
                    cursor.movePosition(QTextCursor.NextCharacter, QTextCursor.KeepAnchor, 2)
                    cursor.removeSelectedText()
                    cursor.insertText('"""')
                    cursor.movePosition(QTextCursor.PreviousCharacter, QTextCursor.MoveAnchor, 3)
                    self.setTextCursor(cursor)

                    return

        if texto in _PARES and getattr(self, '_fechar_pares', True):
            fechador = _PARES[texto]
            cursor   = self.textCursor()
            if cursor.hasSelection():
                sel = cursor.selectedText()
                cursor.insertText(texto + sel + fechador)
            else:
                pos = cursor.position()
                doc = self.toPlainText()
                if texto == fechador and pos < len(doc) and doc[pos] == fechador:
                    cursor.movePosition(QTextCursor.NextCharacter)
                    self.setTextCursor(cursor)
                else:
                    self.insertPlainText(texto + fechador)
                    cursor = self.textCursor()
                    cursor.movePosition(QTextCursor.PreviousCharacter)
                    self.setTextCursor(cursor)
            if texto == "(":
                self._autocomplete.ao_parentese_aberto()
            else:
                self._autocomplete.ao_tecla_pressionada()

            return

        if texto in _FECHADORES:
            cursor = self.textCursor()
            pos    = cursor.position()
            doc    = self.toPlainText()
            if pos < len(doc) and doc[pos] == texto:
                cursor.movePosition(QTextCursor.NextCharacter)
                self.setTextCursor(cursor)
                if texto == ")":
                    self._autocomplete.ao_parentese_fechado()

                return

        if key == Qt.Key_Backspace and not self.textCursor().hasSelection() and getattr(self, '_fechar_pares', True):
            cursor = self.textCursor()
            pos    = cursor.position()
            doc    = self.toPlainText()
            if 0 < pos < len(doc) and _PARES.get(doc[pos - 1]) == doc[pos]:
                cursor.deletePreviousChar()
                cursor.deleteChar()

                return

        super().keyPressEvent(event)

        if texto == ",":
            self._autocomplete.ao_parentese_aberto()
        elif texto and (texto.isalnum() or texto in ("_", ".")):
            self._autocomplete.ao_tecla_pressionada()
        elif key == Qt.Key_Backspace:
            self._autocomplete.ao_tecla_pressionada()
        else:
            self._autocomplete.fechar()

    # ══════════════════════════════════════════════════════════════════
    # Copiar / Recortar linha inteira (sem seleção)
    # FIX 1 (MIME): clipboard recebe MIME type proprietário junto com o texto.
    # Qualquer app externo que sobrescreva o clipboard não inclui esse tipo →
    # detecção automática sem nenhum estado interno no editor.
    # ══════════════════════════════════════════════════════════════════

    def _copiar_linha_inteira(self):
        cursor = self.textCursor()
        texto  = cursor.block().text() + "\n"
        mime   = QMimeData()
        mime.setText(texto)
        mime.setData(_MIME_LINHA, b"1")
        QApplication.clipboard().setMimeData(mime)

    def _recortar_linha_inteira(self):
        """
        Ctrl+X sem seleção — copia a linha para o clipboard E deleta a linha
        inteira (igual deletar_linha): a linha de baixo sobe, não fica uma
        linha vazia no lugar.
        """
        cursor = self.textCursor()
        texto  = cursor.block().text() + "\n"
        mime   = QMimeData()
        mime.setText(texto)
        mime.setData(_MIME_LINHA, b"1")
        QApplication.clipboard().setMimeData(mime)
        self.deletar_linha()

    # ══════════════════════════════════════════════════════════════════
    # Tamanho de fonte
    # ══════════════════════════════════════════════════════════════════

    def aumentar_fonte(self):
        self._tamanho_fonte = min(self._tamanho_fonte + 1, FONTE_EDITOR_MAX)
        self._aplicar_fonte()

    def diminuir_fonte(self):
        self._tamanho_fonte = max(self._tamanho_fonte - 1, FONTE_EDITOR_MIN)
        self._aplicar_fonte()

    def resetar_fonte(self):
        self._tamanho_fonte = _fonte_padrao()
        self._aplicar_fonte()

    def atualizar_fonte(self, tamanho: int):
        self._tamanho_fonte = max(FONTE_EDITOR_MIN, min(FONTE_EDITOR_MAX, tamanho))
        self._aplicar_fonte()

    # ══════════════════════════════════════════════════════════════════
    # Mover linhas
    # ══════════════════════════════════════════════════════════════════

    def mover_linha_cima(self):  self._trocar_linha(-1)
    def mover_linha_baixo(self): self._trocar_linha(1)
    def _trocar_linha(self, direcao: int):
        cursor      = self.textCursor()
        bloco_atual = cursor.block()
        coluna      = cursor.positionInBlock()

        if direcao == -1 and bloco_atual.blockNumber() == 0:

            return

        if direcao == 1 and not bloco_atual.next().isValid():

            return

        bloco_alvo  = bloco_atual.previous() if direcao == -1 else bloco_atual.next()
        texto_atual = bloco_atual.text()
        texto_alvo  = bloco_alvo.text()

        cursor.beginEditBlock()
        c_atual = QTextCursor(bloco_atual)
        c_atual.movePosition(QTextCursor.StartOfBlock)
        c_atual.movePosition(QTextCursor.EndOfBlock, QTextCursor.KeepAnchor)
        c_atual.insertText(texto_alvo)
        c_alvo = QTextCursor(bloco_alvo)
        c_alvo.movePosition(QTextCursor.StartOfBlock)
        c_alvo.movePosition(QTextCursor.EndOfBlock, QTextCursor.KeepAnchor)
        c_alvo.insertText(texto_atual)
        cursor.endEditBlock()

        numero_destino = bloco_atual.blockNumber() + direcao
        bloco_destino  = self.document().findBlockByNumber(numero_destino)
        novo_cursor    = QTextCursor(bloco_destino)
        novo_cursor.movePosition(
            QTextCursor.NextCharacter, QTextCursor.MoveAnchor,
            min(coluna, max(0, bloco_destino.length() - 1))
        )
        self.setTextCursor(novo_cursor)

    # ══════════════════════════════════════════════════════════════════
    # Múltiplos cursores / seleções
    # ══════════════════════════════════════════════════════════════════

    def adicionar_cursor_acima(self):  self._multi_cursor.adicionar_cursor_acima()
    def adicionar_cursor_abaixo(self): self._multi_cursor.adicionar_cursor_abaixo()
    # ⚠️  função grande (62 linhas)
    def selecionar_proxima_ocorrencia(self):
        """
        Ctrl+D — comportamento VS Code:
          1ª vez: seleciona a palavra sob o cursor (sem mover)
          2ª vez: adiciona cursor extra na PRÓXIMA ocorrência da mesma palavra
        """
        import logging
        log = logging.getLogger("hein")

        cursor = self.textCursor()
        if not cursor.hasSelection():
            cursor.select(QTextCursor.WordUnderCursor)
            self.setTextCursor(cursor)

            return

        texto = cursor.selectedText()
        if not texto:

            return

        pos_atual = cursor.selectionEnd()
        novo = self.document().find(texto, pos_atual)
        if novo.isNull():
            novo = self.document().find(texto, 0)

        if novo.isNull() or novo.selectionStart() == cursor.selectionStart():

            return

        mc = self._multi_cursor
        mc._garantir_principal()

        # Congela a seleção atual no cursor que já está no principal
        p_idx = mc._principal_idx
        nc_atual = QTextCursor(self.document())
        nc_atual.setPosition(cursor.selectionStart())
        nc_atual.setPosition(cursor.selectionEnd(), QTextCursor.KeepAnchor)
        mc._cursores[p_idx] = nc_atual

        # Nova ocorrência → novo cursor, vira o principal
        nc_novo = QTextCursor(self.document())
        nc_novo.setPosition(novo.selectionStart())
        nc_novo.setPosition(novo.selectionEnd(), QTextCursor.KeepAnchor)
        mc._cursores.append(nc_novo)
        mc._principal_idx = len(mc._cursores) - 1
        mc._ativo = True
        mc._normalizar_cursores()

        log.debug(
            f"[multi-cursor] proxima_ocorrencia: total={len(mc._cursores)} "
            f"principal_idx={mc._principal_idx}"
        )
        for i, c in enumerate(mc._cursores):
            log.debug(
                f"  cursor[{i}{'*' if i == mc._principal_idx else ''}] "
                f"anchor={c.anchor()} pos={c.position()} "
                f"sel=[{c.selectionStart()}..{c.selectionEnd()}]"
            )

        self.setTextCursor(mc._cursores[mc._principal_idx])
        mc._atualizar_destaques()

    # ⚠️  função grande (71 linhas)
    def selecionar_todas_ocorrencias(self):
        """
        Ctrl+Alt+L — seleciona TODAS as ocorrências da palavra/seleção atual
        e ativa multi-cursor REAL em cada uma delas.
        Digitar depois edita todas as ocorrências simultaneamente.
        """
        import logging
        log = logging.getLogger("hein")

        cursor = self.textCursor()
        sel_start_orig = cursor.selectionStart()
        if not cursor.hasSelection():
            cursor.select(QTextCursor.WordUnderCursor)
            sel_start_orig = cursor.selectionStart()
        texto = cursor.selectedText()
        if not texto:

            return

        doc   = self.document()
        busca = QTextCursor(doc)
        ocorrencias = []
        while True:
            encontrado = doc.find(texto, busca)
            if encontrado.isNull():
                break
            ocorrencias.append(encontrado)
            busca = encontrado

        if not ocorrencias:

            return

        # ── Limpa estado anterior ─────────────────────────────────────────
        self._multi_cursor.cancelar()

        # ── Constrói lista de QTextCursor reais para TODAS as ocorrências ─
        # BUG ANTERIOR: _cursores_extras é @property → .append() era no-op.
        # Fix: popula self._multi_cursor._cursores diretamente.
        cursores_novos = []
        principal_idx  = 0
        for i, oc in enumerate(ocorrencias):
            nc = QTextCursor(doc)
            nc.setPosition(oc.selectionStart())
            nc.setPosition(oc.selectionEnd(), QTextCursor.KeepAnchor)
            cursores_novos.append(nc)
            # A ocorrência que contém a seleção original do usuário vira o principal
            if oc.selectionStart() <= sel_start_orig <= oc.selectionEnd():
                principal_idx = i

        self._multi_cursor._cursores      = cursores_novos
        self._multi_cursor._principal_idx = principal_idx
        if len(ocorrencias) > 1:
            self._multi_cursor._ativo = True

        # ── Log de rastreamento ───────────────────────────────────────────
        log.debug(
            f"[multi-cursor] todas_ocorrencias: '{texto}' "
            f"total={len(cursores_novos)} principal_idx={principal_idx}"
        )
        for i, c in enumerate(cursores_novos):
            log.debug(
                f"  cursor[{i}{'*' if i == principal_idx else ''}] "
                f"anchor={c.anchor()} pos={c.position()} "
                f"sel=[{c.selectionStart()}..{c.selectionEnd()}]"
            )

        # Sincroniza o editor com a ocorrência que o usuário estava
        # (NÃO pula para a primeira — isso era o teleporte)
        self.setTextCursor(cursores_novos[principal_idx])
        self._multi_cursor._atualizar_destaques()

    # ══════════════════════════════════════════════════════════════════
    # Edição de linha
    # ══════════════════════════════════════════════════════════════════

    def comentar_linha(self):
        cursor = self.textCursor()
        inicio = self.document().findBlock(cursor.selectionStart())
        fim    = self.document().findBlock(cursor.selectionEnd())
        todas_comentadas = all(
            self.document().findBlockByNumber(n).text().lstrip().startswith("#")
            for n in range(inicio.blockNumber(), fim.blockNumber() + 1)
            if self.document().findBlockByNumber(n).text().strip()
        )
        cursor.beginEditBlock()
        bloco = inicio
        while True:
            texto    = bloco.text()
            c        = QTextCursor(bloco)
            stripped = texto.lstrip()
            espacos  = len(texto) - len(stripped)
            c.setPosition(bloco.position() + espacos)
            if todas_comentadas:
                if stripped.startswith("# "):
                    c.deleteChar(); c.deleteChar()
                elif stripped.startswith("#"):
                    c.deleteChar()
            else:
                c.insertText("# ")
            if bloco == fim:
                break
            bloco = bloco.next()
        cursor.endEditBlock()

    def deletar_linha(self):
        cursor = self.textCursor()
        cursor.beginEditBlock()
        cursor.select(QTextCursor.BlockUnderCursor)
        cursor.removeSelectedText()
        if cursor.atBlockStart() and not cursor.atStart():
            cursor.deletePreviousChar()
        cursor.endEditBlock()
        self.setTextCursor(cursor)

    def duplicar_linha(self):
        cursor    = self.textCursor()
        bloco     = cursor.block()
        texto     = bloco.text()
        coluna    = cursor.positionInBlock()
        cursor.beginEditBlock()
        fim_bloco = QTextCursor(bloco)
        fim_bloco.movePosition(QTextCursor.EndOfBlock)
        fim_bloco.insertText("\n" + texto)
        cursor.endEditBlock()
        novo        = self.document().findBlockByNumber(bloco.blockNumber() + 1)
        novo_cursor = QTextCursor(novo)
        novo_cursor.movePosition(
            QTextCursor.NextCharacter, QTextCursor.MoveAnchor,
            min(coluna, novo.length() - 1)
        )
        self.setTextCursor(novo_cursor)

    # ══════════════════════════════════════════════════════════════════
    # Highlight da linha atual
    # ══════════════════════════════════════════════════════════════════

    def _destacar_linha_atual(self):
        if not hasattr(self, "_cor_linha_ativa"):

            return

        selecao = QTextEdit.ExtraSelection()
        selecao.format = QTextCharFormat()
        selecao.format.setBackground(self._cor_linha_ativa)
        selecao.format.setProperty(QTextCharFormat.FullWidthSelection, True)
        selecao.cursor = self.textCursor()
        selecao.cursor.clearSelection()

        # ── Highlight de breakpoints (fundo vermelho na linha inteira) ──
        bps = getattr(getattr(self, 'area_numeros', None), '_breakpoints', set())
        selecoes_bp = []
        if bps:
            cor_bp = QColor("#e06c75")
            cor_bp.setAlpha(40)
            for linha_bp in bps:
                bloco_bp = self.document().findBlockByNumber(linha_bp - 1)
                if bloco_bp.isValid():
                    sel_bp = QTextEdit.ExtraSelection()
                    sel_bp.format = QTextCharFormat()
                    sel_bp.format.setBackground(cor_bp)
                    sel_bp.format.setProperty(QTextCharFormat.FullWidthSelection, True)
                    sel_bp.cursor = QTextCursor(bloco_bp)
                    sel_bp.cursor.clearSelection()
                    selecoes_bp.append(sel_bp)

        from PySide6.QtGui import QTextFormat
        lint = getattr(self, '_selecoes_lint', [])
        outros = [s for s in self.extraSelections()
                if not s.format.boolProperty(QTextCharFormat.FullWidthSelection)
                and not s.format.property(QTextFormat.UserProperty + 100)]
        self.setExtraSelections(lint + outros + selecoes_bp + [selecao])
        self._atualizar_sticky_scroll()

    # ══════════════════════════════════════════════════════════════════
    # Indentação de bloco
    # FIX 4: restaura a seleção após indentar/desindentar o bloco.
    # Usa números de bloco (estáveis após edição) para recriar a seleção.
    # ══════════════════════════════════════════════════════════════════

    def _indentar_selecao(self, cursor: QTextCursor, aumentar: bool):
        inicio   = self.document().findBlock(cursor.selectionStart())
        fim      = self.document().findBlock(cursor.selectionEnd())
        n_inicio = inicio.blockNumber()
        n_fim    = fim.blockNumber()

        cursor.beginEditBlock()
        bloco = inicio
        while True:
            texto = bloco.text()
            c     = QTextCursor(bloco)
            c.movePosition(QTextCursor.StartOfBlock)
            if aumentar:
                c.insertText("    ")
            else:
                espacos = len(texto) - len(texto.lstrip())
                for _ in range(min(4, espacos)):
                    c.deleteChar()
            if bloco == fim:
                break
            bloco = bloco.next()
        cursor.endEditBlock()

        b_inicio = self.document().findBlockByNumber(n_inicio)
        b_fim    = self.document().findBlockByNumber(n_fim)
        novo     = QTextCursor(self.document())
        novo.setPosition(b_inicio.position())
        novo.setPosition(b_fim.position() + max(0, b_fim.length() - 1), QTextCursor.KeepAnchor)
        self.setTextCursor(novo)

    # ──────────────────────────────────────────────────────────────────────────
    # IMP-09 — Realce de todas as ocorrências da seleção atual
    # ──────────────────────────────────────────────────────────────────────────

    # ⚠️  função grande (56 linhas)
    def _realcar_ocorrencias(self):
        """
        IMP-09: ao selecionar texto, destaca todas as outras ocorrências
        idênticas no documento com fundo suave (mesma cor da seleção, alpha=60).
        Chamado via _timer_realce (debounce 300 ms) em cursorPositionChanged.
        """
        from PySide6.QtGui import QTextCharFormat, QColor, QTextFormat, QTextCursor
        from PySide6.QtWidgets import QTextEdit
        cursor = self.textCursor()

        if not cursor.hasSelection():
            self._limpar_realce_ocorrencias()

            return

        texto = cursor.selectedText()
        # Ignora seleções multi-linha ou muito longas (performance)
        if not texto or '\n' in texto or '\u2029' in texto or len(texto) > 300:
            self._limpar_realce_ocorrencias()

            return

        from _CONFIGURA_.gerenciador_tema import tema_global
        _cor_hex = tema_global().dados().get("editor.selecao", "#264f78")
        _base    = QColor(_cor_hex)
        _cor_realce = QColor(_base.red(), _base.green(), _base.blue(), 60)

        fmt = QTextCharFormat()
        fmt.setBackground(_cor_realce)
        fmt.setProperty(QTextFormat.UserProperty + 2, True)  # marcador IMP-09

        doc       = self.document()
        sel_start = cursor.selectionStart()
        sel_end   = cursor.selectionEnd()
        busca     = QTextCursor(doc)
        selecoes: list = []
        while True:
            encontrado = doc.find(texto, busca)
            if encontrado.isNull():
                break
            # Pula a própria seleção principal — já está destacada pelo Qt
            if (encontrado.selectionStart() == sel_start
                    and encontrado.selectionEnd() == sel_end):
                busca = encontrado
                continue
            sel = QTextEdit.ExtraSelection()
            sel.cursor = encontrado
            sel.format = fmt
            selecoes.append(sel)
            busca = encontrado

        from PySide6.QtGui import QTextFormat as _QTF
        outros = [s for s in self.extraSelections()
                  if not s.format.property(_QTF.UserProperty + 2)]
        self._selecoes_realce = selecoes
        self.setExtraSelections(outros + selecoes)

    def _limpar_realce_ocorrencias(self):
        """Remove ExtraSelections de realce de ocorrências (IMP-09)."""
        if not getattr(self, '_selecoes_realce', []):

            return

        from PySide6.QtGui import QTextFormat as _QTF
        outros = [s for s in self.extraSelections()
                  if not s.format.property(_QTF.UserProperty + 2)]
        self._selecoes_realce = []
        self.setExtraSelections(outros)
