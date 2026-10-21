# 📁 _TERMINAIS_/Mult_Terminais/executor_explorer.py
"""
ExecutorExplorer — painel visual para configurar os executores de linguagem.

Abre automaticamente quando o usuário edita executores.json no editor
(atalho Ctrl+8 → abre o JSON → _ao_trocar_aba_editor_json roteia aqui).

Mostra cada linguagem configurada em executores.json com:
  - Nome da linguagem
  - Status: ✓ encontrado / ✗ não encontrado (shutil.which)
  - Campo de comando editável → salva em executores.json ao pressionar Enter
  - Botão "Como instalar" (só aparece quando há URL)
  - Botão "Verificar" para re-checar disponibilidade
"""
from __future__ import annotations
import shutil
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from _UTILITARIOS_.icones import icone_tema
from _CONFIGURA_.gerenciador_tema import tema_global
# ─────────────────────────────────────────────────────────────────────────────
_ESTILO_BTN = (
    "QPushButton { background: transparent; color: #555; border: 1px solid #333; "
    "padding: 3px 10px; font-size: 10px; border-radius: 3px; }"
    "QPushButton:hover { color: #98c379; border-color: #98c379; }"
)
_ESTILO_BTN_URL = (
    "QPushButton { background: #1a3a1a; color: #98c379; border: none; "
    "padding: 3px 10px; font-size: 10px; border-radius: 3px; }"
    "QPushButton:hover { background: #264f78; color: #fff; }"
)
# ─────────────────────────────────────────────────────────────────────────────

class _LinhaExecutor(QWidget):
    """Uma linha da tabela de executores (nome + status + campo + botões)."""

    def __init__(self, nome: str, cfg: dict, parent=None) -> None:
        super().__init__(parent)
        self._nome = nome
        self._cfg  = cfg
        self._build()
        self._verificar()

    def _build(self) -> None:
        t     = tema_global()
        fundo = t.cor("interface.fundo_painel_central", "#0A1210")
        self.setStyleSheet(f"background-color: {fundo};")

        v = QVBoxLayout(self)
        v.setContentsMargins(16, 12, 16, 12)
        v.setSpacing(6)

        # ── Linha 1: nome + status ─────────────────────────────────────
        h1 = QHBoxLayout()
        h1.setSpacing(8)

        lbl_nome = QLabel(self._nome)
        lbl_nome.setStyleSheet(
            "font-size: 12px; font-weight: bold; color: #e0e0e0; background: transparent;"
        )
        h1.addWidget(lbl_nome)

        self._lbl_status = QLabel()
        self._lbl_status.setStyleSheet("font-size: 11px; background: transparent;")
        h1.addWidget(self._lbl_status)
        h1.addStretch()

        v.addLayout(h1)

        # ── Linha 2: campo de comando + botões ─────────────────────────
        h2 = QHBoxLayout()
        h2.setSpacing(6)

        self._fld = QLineEdit(self._cfg.get("comando", ""))
        self._fld.setPlaceholderText("Comando ou caminho do executável…")
        self._fld.setFixedHeight(24)
        self._fld.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._fld.setStyleSheet(
            "QLineEdit { background: #0d1b0d; color: #98c379; border: 1px solid #333; "
            "border-radius: 3px; padding: 1px 6px; font-family: 'Consolas', monospace; "
            "font-size: 11px; }"
            "QLineEdit:focus { border-color: #98c379; }"
        )
        self._fld.returnPressed.connect(self._salvar)
        h2.addWidget(self._fld)

        btn_salvar = QPushButton("Salvar")
        btn_salvar.setFixedHeight(24)
        btn_salvar.setStyleSheet(_ESTILO_BTN)
        btn_salvar.clicked.connect(self._salvar)
        h2.addWidget(btn_salvar)

        btn_verificar = QPushButton("Verificar")
        btn_verificar.setFixedHeight(24)
        btn_verificar.setStyleSheet(_ESTILO_BTN)
        btn_verificar.clicked.connect(self._verificar)
        h2.addWidget(btn_verificar)

        url = self._cfg.get("instalacao_url", "")
        if url:
            btn_url = QPushButton("🌐  Como instalar")
            btn_url.setFixedHeight(24)
            btn_url.setStyleSheet(_ESTILO_BTN_URL)
            btn_url.clicked.connect(lambda: self._abrir_url(url))
            h2.addWidget(btn_url)

        v.addLayout(h2)

        # ── Dica de instalação (texto pequeno abaixo) ──────────────────
        dica = self._cfg.get("instalacao_dica", "")
        if dica:
            lbl_dica = QLabel(dica)
            lbl_dica.setWordWrap(True)
            lbl_dica.setStyleSheet(
                "font-size: 10px; color: #555; background: transparent;"
            )
            v.addWidget(lbl_dica)

    def _verificar(self) -> None:
        cmd    = self._fld.text().strip() or self._cfg.get("comando", "")
        bin_   = cmd.split()[0] if cmd else ""
        achado = bool(bin_ and shutil.which(bin_))
        if achado:
            self._lbl_status.setText(f"✓  {bin_} encontrado")
            self._lbl_status.setStyleSheet(
                "font-size: 11px; color: #4ec994; background: transparent;"
            )
        else:
            self._lbl_status.setText(f"✗  {bin_ or '?'} não encontrado no PATH")
            self._lbl_status.setStyleSheet(
                "font-size: 11px; color: #e06c75; background: transparent;"
            )

    def _salvar(self) -> None:
        cmd = self._fld.text().strip()
        if not cmd:

            return

        from _CONFIGURA_.gerenciador_executores import exec_global
        exec_global().set_comando(self._nome, cmd)
        self._verificar()

    def _abrir_url(self, url: str) -> None:
        from PySide6.QtGui import QDesktopServices
        from PySide6.QtCore import QUrl
        QDesktopServices.openUrl(QUrl(url))

    def recarregar(self, cfg: dict) -> None:
        self._cfg = cfg
        self._fld.setText(cfg.get("comando", ""))
        self._verificar()

# ─────────────────────────────────────────────────────────────────────────────

class ExecutorExplorer(QWidget):
    """
    Painel visual de configuração dos executores de linguagem.

    Aberto automaticamente quando executores.json é editado no editor
    (roteado por MainWindow._ao_trocar_aba_editor_json).
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._linhas: dict[str, _LinhaExecutor] = {}
        # Vínculo com a aba do editor — usado por _ao_fechar_aba_terminal
        from _CONFIGURA_ import ARQUIVO_EXECUTORES
        self._caminho = ARQUIVO_EXECUTORES
        self._build()
        self._carregar()

        # Hot-reload quando gerenciador salva
        from _CONFIGURA_.gerenciador_executores import exec_global
        exec_global().executores_alterados.connect(self._carregar)

    def _build(self) -> None:
        t     = tema_global()
        fundo = t.cor("terminal_run.fundo", "#000000")
        self.setStyleSheet(f"background-color: {fundo};")

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(0)

        # ── Cabeçalho ──────────────────────────────────────────────────
        cab = QWidget()
        cab.setFixedHeight(36)
        cab_cor = t.cor("interface.fundo_painel_central", "#0A1210")
        cab.setStyleSheet(f"background-color: {cab_cor};")
        h = QHBoxLayout(cab)
        h.setContentsMargins(16, 0, 16, 0)

        lbl = QLabel("⚙  Executores configurados")
        lbl.setStyleSheet(
            "font-size: 11px; font-weight: bold; color: #888; background: transparent;"
        )
        h.addWidget(lbl)
        h.addStretch()

        btn_verificar_tudo = QPushButton("↺  Verificar tudo")
        btn_verificar_tudo.setFixedHeight(22)
        btn_verificar_tudo.setStyleSheet(_ESTILO_BTN)
        btn_verificar_tudo.clicked.connect(self._verificar_tudo)
        h.addWidget(btn_verificar_tudo)

        raiz.addWidget(cab)

        # ── Área scrollável ────────────────────────────────────────────
        self._area_conteudo = QWidget()
        self._vlay = QVBoxLayout(self._area_conteudo)
        self._vlay.setContentsMargins(0, 0, 0, 0)
        self._vlay.setSpacing(0)
        self._vlay.addStretch()

        scroll = QScrollArea()
        scroll.setWidget(self._area_conteudo)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet(f"QScrollArea {{ background: {fundo}; border: none; }}")
        raiz.addWidget(scroll)

    def _carregar(self) -> None:
        from _CONFIGURA_.gerenciador_executores import exec_global
        gex = exec_global()

        for nome in gex.linguagens():
            cfg = gex.get_config(nome)
            if nome in self._linhas:
                self._linhas[nome].recarregar(cfg)
            else:
                linha = _LinhaExecutor(nome, cfg)
                sep   = QFrame()
                sep.setFrameShape(QFrame.HLine)
                sep.setStyleSheet("background-color: #1a2a1a;")
                sep.setFixedHeight(1)
                # insere ANTES do stretch
                idx = self._vlay.count() - 1
                self._vlay.insertWidget(idx, sep)
                self._vlay.insertWidget(idx + 1, linha)
                self._linhas[nome] = linha

    def _verificar_tudo(self) -> None:
        for linha in self._linhas.values():
            linha._verificar()

    def _recarregar_se_necessario(self) -> None:
        """Compatível com o padrão usado por _ao_trocar_aba_editor_json."""
        self._carregar()
