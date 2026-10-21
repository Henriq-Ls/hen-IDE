# 📁 _EDITOR_/Funcionalidades/corretor_ortografico.py
# -*- coding: utf-8 -*-
"""
Corretor ortográfico PT-BR da hein IDE — modo 100 % manual.

Duas formas de ativação:
  1. Menu de contexto (botão direito) → "Corretor ortográfico"
       Varre a página inteira em background e sublinha erros em cinza.
       Passar o mouse sobre uma palavra sublinhada mostra o popup de sugestões.

  2. Clique com o botão do meio (scroll) sobre qualquer palavra
       Verifica aquela palavra imediatamente e mostra o popup de sugestões.
       Palavras corretas: popup não aparece.

Nenhuma varredura automática — não conecta textChanged, não usa timer interno.

Dicionário
----------
  pt_BR_basico.txt   — PT-BR geral
  tech_whitelist.txt — termos técnicos/inglês a ignorar
  pt_BR_usuario.txt  — palavras adicionadas pelo usuário

Integração no CodeEditor
------------------------
    from _EDITOR_.Funcionalidades.corretor_ortografico import CorretorOrtografico
    self._corretor = CorretorOrtografico(self, modo="python")
    # verificar_pagina_inteira() — chamar do menu de contexto
    # limpar()                  — ao trocar aba / fechar arquivo
"""

from __future__ import annotations

import io
import os
import re
import tokenize

from PySide6.QtCore import (
    QEvent, QObject, QRunnable, QThreadPool, Qt, Signal,
)
from PySide6.QtGui import (
    QColor, QTextCharFormat, QTextCursor,
)
from PySide6.QtWidgets import (
    QFrame, QLabel, QPushButton,
    QTextEdit, QVBoxLayout,
)
from _THREADS_.diagnostico_workers import weak_editor

from _EDITOR_.popup_base import PopupBase
from _LOG_.log import log

_ARQ = "corretor_ortografico.py"

# Palavra válida: apenas letras (inclusive acentuadas/ç), mínimo 3 caracteres.
_RE_PALAVRA = re.compile(
    r"[a-záéíóúàâêôãõüçäëïöœæ]{3,}",
    re.IGNORECASE | re.UNICODE,
)

# Cor do sublinhado — cinza neutro (não conflita com vermelho de import nem amarelo de lint)
_COR_SUBLINHADO = "#808080"


# ─── Dicionário ───────────────────────────────────────────────────────────────

_dicionario: set[str] | None = None  # cache; None = não carregado ainda


def _caminhos_dicionario() -> list[str]:
    try:
        from _APPDATA_ import appdata
        base = appdata.dicionarios
        return [
            os.path.join(base, "pt_BR_basico.txt"),
            os.path.join(base, "tech_whitelist.txt"),
            os.path.join(base, "pt_BR_usuario.txt"),
        ]
    except Exception:
        return []


def _carregar_dicionario() -> set[str]:
    global _dicionario
    if _dicionario is not None:
        return _dicionario

    palavras: set[str] = set()
    for caminho in _caminhos_dicionario():
        if not os.path.isfile(caminho):
            continue
        try:
            with open(caminho, encoding="utf-8") as f:
                for linha in f:
                    p = linha.strip().lower()
                    if p and not p.startswith("#"):
                        palavras.add(p)
        except Exception as exc:
            log.aviso(_ARQ, "_carregar_dicionario",
                      f"falha ao ler {caminho}", str(exc))

    _dicionario = palavras
    log.ok(_ARQ, "_carregar_dicionario",
           f"{len(palavras)} palavras carregadas")
    return _dicionario


def invalidar_dicionario() -> None:
    """Força recarga do dicionário na próxima verificação."""
    global _dicionario
    _dicionario = None


def _esta_correto(palavra: str) -> bool:
    return palavra.lower() in _carregar_dicionario()


def _sugestoes(palavra: str, max_sug: int = 5) -> list[str]:
    dicio = _carregar_dicionario()
    alvo  = palavra.lower()
    n     = len(alvo)

    inicial    = alvo[0] if alvo else ""
    candidatos = [
        p for p in dicio
        if p.startswith(inicial) and abs(len(p) - n) <= 2
    ]
    if len(candidatos) < 15:
        candidatos = [p for p in dicio if abs(len(p) - n) <= 1]

    scored: list[tuple[int, str]] = []
    for cand in candidatos:
        d = _levenshtein(alvo, cand)
        if d <= 2:
            scored.append((d, cand))

    scored.sort(key=lambda x: (x[0], x[1]))
    return [c for _, c in scored[:max_sug]]


def _levenshtein(a: str, b: str) -> int:
    m, n = len(a), len(b)
    if m > 30 or n > 30:
        return abs(m - n) + 5
    dp = list(range(n + 1))
    for i in range(1, m + 1):
        prev  = dp[0]
        dp[0] = i
        for j in range(1, n + 1):
            tmp   = dp[j]
            dp[j] = (prev if a[i - 1] == b[j - 1]
                     else 1 + min(prev, dp[j], dp[j - 1]))
            prev  = tmp
    return dp[n]


# ─── Extração de tokens por modo ──────────────────────────────────────────────

def _extrair_python(codigo: str) -> list[tuple[int, int, int, str]]:
    """Extrai palavras de comentários e strings de uma linha em Python."""
    resultado: list[tuple[int, int, int, str]] = []
    try:
        reader = io.StringIO(codigo).readline
        for tok in tokenize.generate_tokens(reader):
            if tok.type == tokenize.COMMENT:
                linha, col = tok.start
                m_ini  = re.match(r'^#+\s*', tok.string)
                offset = m_ini.end() if m_ini else 1
                texto  = tok.string[offset:]
                for m in _RE_PALAVRA.finditer(texto):
                    c0 = col + offset + m.start()
                    c1 = c0 + len(m.group())
                    resultado.append((linha, c0, c1, m.group().lower()))

            elif tok.type == tokenize.STRING:
                linha_ini, col_ini = tok.start
                linha_fim, _       = tok.end
                if linha_ini != linha_fim:
                    continue
                raw      = tok.string
                m_pref   = re.match(r'^[rRbBuUfF]*', raw)
                pref_len = m_pref.end()
                if pref_len >= len(raw):
                    continue
                if raw[pref_len: pref_len + 3] in ('"""', "'''"):
                    continue
                c_ini    = pref_len + 1
                c_fim    = len(raw) - 1
                if c_fim <= c_ini:
                    continue
                conteudo = raw[c_ini:c_fim]
                for m in _RE_PALAVRA.finditer(conteudo):
                    c0 = col_ini + c_ini + m.start()
                    c1 = c0 + len(m.group())
                    resultado.append((linha_ini, c0, c1, m.group().lower()))

    except tokenize.TokenError:
        pass
    return resultado


def _extrair_texto(codigo: str) -> list[tuple[int, int, int, str]]:
    resultado: list[tuple[int, int, int, str]] = []
    for i, linha in enumerate(codigo.splitlines(), start=1):
        for m in _RE_PALAVRA.finditer(linha):
            resultado.append((i, m.start(), m.end(), m.group().lower()))
    return resultado


def _extrair_markdown(codigo: str) -> list[tuple[int, int, int, str]]:
    resultado: list[tuple[int, int, int, str]] = []
    em_bloco = False
    for i, linha in enumerate(codigo.splitlines(), start=1):
        stripped = linha.strip()
        if stripped.startswith("```"):
            em_bloco = not em_bloco
            continue
        if em_bloco:
            continue
        linha_limpa = re.sub(r'`[^`]*`', '', linha)
        linha_limpa = re.sub(r'https?://\S+', '', linha_limpa)
        for m in _RE_PALAVRA.finditer(linha_limpa):
            resultado.append((i, m.start(), m.end(), m.group().lower()))
    return resultado


# ─── Thread de verificação ────────────────────────────────────────────────────

class _SinaisCorretor(QObject):
    concluido = Signal(object)  # list[tuple[int, int, int, str]]


class _RunnableCorretor(QRunnable):
    """Roda extração + verificação ortográfica em background. Dados puros, sem Qt."""

    def __init__(self, codigo: str, modo: str, task: str = "",
                 editor=None, edit_generation: int = 0) -> None:
        super().__init__()
        self.setAutoDelete(True)
        self._codigo = codigo
        self._modo   = modo
        self.signals = _SinaisCorretor()
        self._hein_diag_task = task
        self._hein_diag_component = "CORRETOR"
        self._hein_diag_editor = weak_editor(editor)
        self._hein_diag_edit_generation = edit_generation
        from _THREADS_.diagnostico_workers import bind
        bind(self.signals, "CORRETOR", task, editor, edit_generation)

    def run(self) -> None:
        from _THREADS_.diagnostico_workers import event
        event("RUN_ENTER", "CORRETOR", self._hein_diag_task,
              obj=self.signals, editor=self._hein_diag_editor)
        try:
            extratores = {
                "python":   _extrair_python,
                "markdown": _extrair_markdown,
                "texto":    _extrair_texto,
            }
            extrair = extratores.get(self._modo, _extrair_texto)
            tokens  = extrair(self._codigo)
            erros   = [t for t in tokens if not _esta_correto(t[3])]
            self.signals.concluido.emit(erros)
            event("RESULT_EMITTED", "CORRETOR", self._hein_diag_task,
                  obj=self.signals, editor=self._hein_diag_editor,
                  error_count=len(erros))
        except Exception as exc:
            log.aviso(_ARQ, "_RunnableCorretor.run", str(exc))
            self.signals.concluido.emit([])
            event("RESULT_EMITTED", "CORRETOR", self._hein_diag_task,
                  obj=self.signals, editor=self._hein_diag_editor,
                  error_count=0, exception=True)
        finally:
            event("RUN_EXIT", "CORRETOR", self._hein_diag_task,
                  obj=self.signals, editor=self._hein_diag_editor)


# ─── Popup de sugestões ───────────────────────────────────────────────────────

class _PopupSugestoes(PopupBase):
    """
    Popup flutuante com sugestões ortográficas.
    Debounce de 200 ms: fecha quando o mouse sai sem entrar no popup.
    """

    palavra_substituida = Signal(str, str)  # (original, substituta)

    def __init__(self, parent=None) -> None:
        super().__init__(parent, debounce_ms=200)
        self._palavra_atual = ""
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(10, 7, 10, 7)
        self._layout.setSpacing(2)
        self._widgets_dinamicos: list = []

    def mostrar(self, pos_global, palavra: str, sugestoes: list[str]) -> None:
        self._palavra_atual = palavra
        self._reconstruir(palavra, sugestoes)
        self._posicionar_e_exibir(pos_global)

    def _reconstruir(self, palavra: str, sugestoes: list[str]) -> None:
        for w in self._widgets_dinamicos:
            try:
                w.deleteLater()
            except RuntimeError:
                pass
        self._widgets_dinamicos.clear()

        cor_fraco    = self._cor_texto_fraco()
        cor_destaque = self._cor_destaque()
        cor_texto    = self._cor_texto()
        cor_hover    = self._cor_hover()
        cor_borda    = self._cor_borda()

        titulo = QLabel(
            f'<span style="color:{cor_fraco};font-size:9pt;">Erro ortográfico: </span>'
            f'<b style="color:{cor_destaque};">{palavra}</b>'
        )
        titulo.setTextFormat(Qt.RichText)
        self._layout.addWidget(titulo)
        self._widgets_dinamicos.append(titulo)

        if sugestoes:
            for sug in sugestoes:
                btn = QPushButton(f"→  {sug}")
                btn.setFlat(True)
                btn.setCursor(Qt.PointingHandCursor)
                btn.setStyleSheet(
                    f"QPushButton{{text-align:left;padding:3px 8px;"
                    f"font-size:10pt;color:{cor_texto};border:none;}}"
                    f"QPushButton:hover{{background:{cor_hover};"
                    f"border-radius:3px;}}"
                )
                btn.clicked.connect(lambda _, s=sug: self._substituir(s))
                self._layout.addWidget(btn)
                self._widgets_dinamicos.append(btn)
        else:
            sem = QLabel(
                f'<i style="color:{cor_fraco};font-size:9pt;">'
                f'Nenhuma sugestão encontrada.</i>'
            )
            sem.setTextFormat(Qt.RichText)
            self._layout.addWidget(sem)
            self._widgets_dinamicos.append(sem)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(f"color:{cor_borda};")
        self._layout.addWidget(sep)
        self._widgets_dinamicos.append(sep)

        btn_add = QPushButton("+ Adicionar ao dicionário")
        btn_add.setFlat(True)
        btn_add.setCursor(Qt.PointingHandCursor)
        btn_add.setStyleSheet(
            f"QPushButton{{text-align:left;padding:2px 8px;"
            f"font-size:9pt;color:{cor_fraco};border:none;}}"
            f"QPushButton:hover{{color:{cor_texto};}}"
        )
        btn_add.clicked.connect(self._adicionar_ao_dicionario)
        self._layout.addWidget(btn_add)
        self._widgets_dinamicos.append(btn_add)

        self._aplicar_estilo_base()

    def _substituir(self, substituta: str) -> None:
        self.palavra_substituida.emit(self._palavra_atual, substituta)
        self.hide()

    def _adicionar_ao_dicionario(self) -> None:
        try:
            from _APPDATA_ import appdata
            caminho = os.path.join(appdata.dicionarios, "pt_BR_usuario.txt")
            with open(caminho, "a", encoding="utf-8") as f:
                f.write(self._palavra_atual.lower() + "\n")
            invalidar_dicionario()
            log.ok(_ARQ, "_adicionar_ao_dicionario",
                   f"'{self._palavra_atual}' adicionada ao dicionário do usuário")
        except Exception as exc:
            log.aviso(_ARQ, "_adicionar_ao_dicionario", str(exc))
        self.hide()


# ─── Gerenciador principal ────────────────────────────────────────────────────

class CorretorOrtografico(QObject):
    """
    Corretor ortográfico 100 % manual da hein IDE.

    Modo 1 — varredura da página (menu de contexto):
        verificar_pagina_inteira() → roda em background → sublinha erros em cinza
        Hover sobre palavra sublinhada → popup de sugestões

    Modo 2 — palavra sob o cursor (clique do meio):
        Clique com botão do scroll → verifica a palavra instantaneamente →
        popup de sugestões (só aparece se a palavra estiver errada)

    Sem varredura automática: não conecta textChanged nem usa timer interno.
    """

    def __init__(self, editor, modo: str = "texto") -> None:
        super().__init__(editor)
        self._editor = editor
        self._modo   = modo

        self._erros_atuais: list[tuple[int, int, int, str]] = []
        self._signals: _SinaisCorretor | None = None

        self._popup = _PopupSugestoes()
        self._popup.palavra_substituida.connect(self._aplicar_substituicao)

        # Tracker de hover (evita reposicionar popup para a mesma palavra)
        self._palavra_hover: str = ""

        # Posição da palavra verificada pelo clique do meio (para substituição)
        self._pos_inicio: int = -1
        self._pos_fim:    int = -1

        editor.viewport().installEventFilter(self)

    # ── API pública ───────────────────────────────────────────────────────────

    def verificar_pagina_inteira(self) -> None:
        """
        Varre o arquivo inteiro em background e sublinha palavras erradas em cinza.
        Chamar do menu de contexto do editor.
        """
        codigo = self._editor.toPlainText()
        if not codigo.strip():
            self.limpar()
            return

        # Cancela corrida anterior
        if self._signals is not None:
            try:
                self._signals.concluido.disconnect()
            except RuntimeError:
                pass
            from _THREADS_.diagnostico_workers import reference
            reference("ZERO", "CORRETOR", self, "_signals",
                      before=self._signals, after=None, editor=self._editor,
                      task=getattr(self._signals, "_hein_diag_task", ""))

        from _THREADS_.diagnostico_workers import edit_generation, new_task
        _edit = edit_generation(self._editor)
        _task = new_task("CORRETOR", self._editor, _edit)
        r              = _RunnableCorretor(
            codigo, self._modo, _task, self._editor, _edit
        )
        reference("REPLACE", "CORRETOR", self, "_signals",
                  before=self._signals, after=r.signals,
                  editor=self._editor, task=_task)
        self._signals  = r.signals
        self._signals.concluido.connect(self._ao_concluir)
        event("START_REQUESTED", "CORRETOR", _task,
              obj=r.signals, editor=self._editor)
        QThreadPool.globalInstance().start(r)
        log.info(_ARQ, "verificar_pagina_inteira",
                 f"varredura iniciada (modo={self._modo})")

    def verificar_agora(self) -> None:
        """Compatibilidade com chamadas legadas do editor — sem efeito."""

    def limpar(self) -> None:
        """Remove sublinhados e esconde popup."""
        self._erros_atuais = []
        self._aplicar_selecoes([])
        self._popup.hide()

    def trocar_modo(self, novo_modo: str) -> None:
        """Atualiza o modo de extração e limpa sublinhados."""
        self._modo = novo_modo
        self.limpar()

    # ── Resultado da thread ───────────────────────────────────────────────────

    def _ao_concluir(self, erros: list) -> None:
        self._erros_atuais = erros
        try:
            selecoes = self._construir_selecoes(erros)
            self._aplicar_selecoes(selecoes)
            log.ok(_ARQ, "_ao_concluir",
                   f"{len(erros)} erro(s) marcado(s)")
        except RuntimeError:
            pass  # editor destruído

    # ── Destaques visuais (sublinhado cinza) ──────────────────────────────────

    def _construir_selecoes(self, erros: list) -> list:
        fmt = QTextCharFormat()
        fmt.setUnderlineStyle(QTextCharFormat.SpellCheckUnderline)
        fmt.setUnderlineColor(QColor(_COR_SUBLINHADO))

        doc      = self._editor.document()
        selecoes = []
        for linha, c0, c1, _ in erros:
            bloco = doc.findBlockByLineNumber(linha - 1)
            if not bloco.isValid():
                continue
            pos_bloco = bloco.position()
            cursor    = QTextCursor(doc)
            cursor.setPosition(pos_bloco + c0)
            cursor.setPosition(pos_bloco + c1, QTextCursor.KeepAnchor)
            sel        = QTextEdit.ExtraSelection()
            sel.cursor = cursor
            sel.format = fmt
            selecoes.append(sel)
        return selecoes

    def _aplicar_selecoes(self, novas: list) -> None:
        """Mescla seleções do corretor com as demais (lint, busca, import)."""
        try:
            existentes = [
                s for s in self._editor.extraSelections()
                if s.format.underlineColor() != QColor(_COR_SUBLINHADO)
            ]
            self._editor.setExtraSelections(existentes + novas)
        except RuntimeError:
            pass

    # ── eventFilter — hover (página inteira) + clique do meio ────────────────

    def eventFilter(self, obj, event) -> bool:  # noqa: N802
        t = event.type()

        # Clique do meio → verifica palavra sob o cursor imediatamente
        if t == QEvent.MouseButtonPress and event.button() == Qt.MiddleButton:
            self._verificar_no_clique(event.pos())
            return True  # consome — evita comportamento padrão do clique do meio

        # Hover sobre palavras sublinhadas (só após varredura)
        if t == QEvent.MouseMove:
            self._verificar_hover(event.pos())
        elif t == QEvent.Leave:
            self._popup.iniciar_fechar()

        return False

    # ── Clique do meio — palavra única ────────────────────────────────────────

    def _verificar_no_clique(self, pos_viewport) -> None:
        """Verifica a palavra sob o cursor do mouse e mostra popup se errada."""
        cursor = self._editor.cursorForPosition(pos_viewport)
        cursor.select(QTextCursor.WordUnderCursor)
        palavra = cursor.selectedText().strip()

        # Só processa palavras puras (letras, sem _, dígitos, operadores, etc.)
        if not re.fullmatch(
            r"[a-záéíóúàâêôãõüçäëïöœæ]{3,}",
            palavra,
            re.IGNORECASE | re.UNICODE,
        ):
            self._popup.hide()
            return

        if _esta_correto(palavra):
            self._popup.hide()
            return

        self._pos_inicio = cursor.selectionStart()
        self._pos_fim    = cursor.selectionEnd()

        sugs       = _sugestoes(palavra)
        rect       = self._editor.cursorRect(cursor)
        pos_global = self._editor.viewport().mapToGlobal(rect.bottomLeft())
        pos_global.setY(pos_global.y() + 4)
        self._popup.mostrar(pos_global, palavra, sugs)

    # ── Hover — sublinhados da varredura ──────────────────────────────────────

    def _verificar_hover(self, pos_viewport) -> None:
        """Exibe popup ao passar o mouse sobre uma palavra sublinhada pela varredura."""
        if not self._erros_atuais:
            return

        cursor = self._editor.cursorForPosition(pos_viewport)
        linha  = cursor.blockNumber() + 1
        col    = cursor.positionInBlock()

        for err_linha, c0, c1, palavra in self._erros_atuais:
            if err_linha == linha and c0 <= col <= c1:
                if self._popup.isVisible() and self._palavra_hover == palavra:
                    self._popup.adiar_fechar()
                    return
                sugs       = _sugestoes(palavra)
                rect       = self._editor.cursorRect(cursor)
                pos_ancora = self._editor.viewport().mapToGlobal(rect.bottomLeft())
                pos_ancora.setY(pos_ancora.y() + 4)
                self._palavra_hover = palavra
                # Registra posição para substituição via hover também
                bloco = self._editor.document().findBlockByLineNumber(linha - 1)
                if bloco.isValid():
                    self._pos_inicio = bloco.position() + c0
                    self._pos_fim    = bloco.position() + c1
                self._popup.mostrar(pos_ancora, palavra, sugs)
                return

        self._palavra_hover = ""
        self._popup.iniciar_fechar()

    # ── Substituição ──────────────────────────────────────────────────────────

    def _aplicar_substituicao(self, original: str, substituta: str) -> None:
        if self._pos_inicio < 0:
            return
        doc    = self._editor.document()
        cursor = QTextCursor(doc)
        cursor.setPosition(self._pos_inicio)
        cursor.setPosition(self._pos_fim, QTextCursor.KeepAnchor)
        if cursor.selectedText().strip().lower() == original.lower():
            cursor.insertText(substituta)
            log.ok(_ARQ, "_aplicar_substituicao", f"'{original}' → '{substituta}'")
        else:
            log.aviso(_ARQ, "_aplicar_substituicao",
                      "texto mudou desde a verificação — substituição cancelada")
        self._pos_inicio = -1
        self._pos_fim    = -1
