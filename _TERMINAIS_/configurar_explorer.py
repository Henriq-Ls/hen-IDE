# 📁 _TERMINAIS_/configurar_explorer.py
"""
ConfigurarExplorer — painel visual para editar configurar.json.

Layout de 2 colunas com controles adaptados por tipo:
  - texto  → QLineEdit  (perfil: nome, github, etc.)
  - enum   → QComboBox  (borda_estilo, cursor_forma, etc.)
  - fonte  → QComboBox hein + sistema com preview ao vivo
  - int    → QSpinBox com limites e sufixo
  - bool   → QCheckBox

Sincronização bidirecional via QFileSystemWatcher:
  explorer → JSON: botão Salvar
  JSON → explorer: watcher detecta mudança em disco → recarrega
"""

import json
import os
import re
from PySide6.QtCore import Qt, QTimer, QFileSystemWatcher, Signal
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from _CONFIGURA_ import ARQUIVO_CONFIG
from _CONFIGURA_.gerenciador_tema import tema_global
from _LOG_.log import log
_ARQ = "configurar_explorer.py"

# ── Fontes hein registradas pela IDE ──────────────────────────────────
_FONTES_HEIN = [
    "hein", "hein_Codigo", "hein_16Bits", "hein_Editor",
    "hein_Escritor", "hein_Italico", "hein_Monstro", "hein_Pedras",
]

# ── Seções do configurar.json (chave, título, descrição curta) ────────
_SECOES = [
    ("perfil",          "Perfil do Usuário",       "Nome, GitHub e preferências pessoais"),
    ("ui",              "Interface Geral",          "Menus, abas, botões e barra de status"),
    ("editor",          "Editor de Código",         "Janela central de escrita"),
    ("gutter",          "Gutter do Editor",         "Larguras das colunas marginais"),
    ("terminal",        "Terminal",                 "PowerShell / Bash"),
    ("outline",         "Outline",                  "Painel lateral de estrutura do código"),
    ("painel_arquivos", "Árvore de Arquivos",       "Painel esquerdo — arquivos e pastas"),
    ("git",             "Git / Projeto / Logs",     "Painel esquerdo inferior"),
]

# ── Campos booleanos: chave → rótulo ─────────────────────────────────
_BOOL_CAMPOS = {
    "wrap_linha":       "Quebrar linha na borda",
    "fechar_pares":     "Fechar parênteses / chaves automaticamente",
    "destacar_linha":   "Destacar linha do cursor",
    "numeros_linha":    "Mostrar números de linha",
    "quebra_linha":     "Quebrar linhas longas",
    "cursor_piscar":    "Cursor piscante",
}

# ── Campos inteiros: chave → (min, max, sufixo, rótulo) ──────────────
_INT_CAMPOS = {
    # editor
    "tamanho_minimo":              (4,   72,  "pt",  "Tamanho mínimo de fonte"),
    "tamanho_maximo":              (6,   72,  "pt",  "Tamanho máximo de fonte"),
    "espacamento_linha":           (10,  300, "%",   "Espaçamento entre linhas"),
    "tab_tamanho":                 (1,   8,   "esp", "Largura do Tab"),
    "limite_caracteres_por_linha": (0,   500, "col", "Guia vertical (0=deslig.)"),
    "cursor_largura":              (1,   10,  "px",  "Largura do cursor (barra)"),
    # ui
    "borda_raio":                  (0,   30,  "px",  "Raio das bordas"),
    "borda_larg":                  (0,   10,  "px",  "Espessura da borda"),
    "margem_painel":               (0,   40,  "px",  "Margem dos painéis"),
    "altura_aba":                  (16,  60,  "px",  "Altura das abas"),
    "tamanho_fonte_aba":           (6,   20,  "pt",  "Fonte das abas"),
    "padding_aba_h":               (0,   40,  "px",  "Padding horiz. aba"),
    "padding_aba_v":               (0,   20,  "px",  "Padding vert. aba"),
    # gutter — layout: [git][pad][BP][pad][números auto][seta][pad] | código
    "largura_git":                 (0,   40,  "px",  "Barra de diff Git"),
    "paddings":                    (0,   40,  "px",  "Espaçamento entre elementos"),
    "largura_guiter":              (0,   200, "px",  "Zona breakpoint / bookmark"),
    "largura_seta":                (0,   40,  "px",  "Seta de dobramento"),
}

# ── Campos enum (QComboBox): chave → ([opções], rótulo) ───────────────
_COMBO_CAMPOS = {
    "borda_estilo":         (["solid", "dashed", "dotted", "double", "none"], "Estilo de borda"),
    "cursor_forma":         (["beam", "block", "underline"],                  "Forma do cursor"),
    "cursor_piscar_estilo": (["smooth", "step"],                              "Piscar — estilo"),
    "seta_estilo":          (["triangulo", "chevron", "classico"],            "Estilo da seta"),
}

# ── Campos de texto livre (QLineEdit): chave → rótulo ────────────────
_TEXTO_CAMPOS = {
    "nome":                   "Nome do usuário",
    "github":                 "Usuário GitHub",
    "avatar_path":            "Caminho do avatar",
    "saudacao_personalizada": "Saudação personalizada",
    "idioma":                 "Idioma (ex: pt_BR)",
    "data_inicio_uso":        "Data de início",
}

# ═════════════════════════════════════════════════════════════════════
# Utilitários internos
# ═════════════════════════════════════════════════════════════════════

def _carregar_json(caminho: str) -> dict:
    """Lê o JSON ignorando comentários // ."""
    try:
        with open(caminho, "r", encoding="utf-8") as f:
            texto = f.read()
        texto = re.sub(
            r'"(?:[^"\\]|\\.)*"|//[^\n]*',
            lambda m: m.group(0) if m.group(0).startswith('"') else '',
            texto,
        )

        return json.loads(texto)

    except Exception as e:
        log.erro(_ARQ, "_carregar_json", str(e))

        return {}

def _salvar_json(caminho: str, dados: dict) -> bool:
    """Grava o JSON formatado com 2 espaços."""
    try:
        with open(caminho, "w", encoding="utf-8") as f:
            json.dump(dados, f, ensure_ascii=False, indent=2)

        return True

    except Exception as e:
        log.erro(_ARQ, "_salvar_json", str(e))

        return False

def _fontes_sistema() -> list[str]:
    try:

        return sorted(QFontDatabase.families())

    except Exception:

        return []

# ═════════════════════════════════════════════════════════════════════
# Linha de fonte: ComboBox + preview ao vivo
# ═════════════════════════════════════════════════════════════════════

class _FonteRow(QWidget):
    """Combo de seleção de fonte + preview renderizado com a fonte."""

    def __init__(self, fonte_atual: str, tamanho_pt: int, parent=None):
        super().__init__(parent)
        self._pt = max(tamanho_pt, 8)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)

        self._combo = QComboBox()
        self._combo.setFixedHeight(26)
        self._combo.setMinimumWidth(180)

        for nome in _FONTES_HEIN:
            self._combo.addItem(f"◆  {nome}", nome)
        self._combo.insertSeparator(len(_FONTES_HEIN))
        for nome in _fontes_sistema():
            if nome not in _FONTES_HEIN:
                self._combo.addItem(nome, nome)

        for i in range(self._combo.count()):
            if self._combo.itemData(i) == fonte_atual:
                self._combo.setCurrentIndex(i)
                break

        self._preview = QLabel()
        self._preview.setFixedHeight(26)
        self._preview.setMinimumWidth(180)
        self._preview.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        self._preview.setStyleSheet("background:#111; border-radius:3px; padding:2px 6px;")

        self._atualizar_preview(fonte_atual)
        self._combo.currentIndexChanged.connect(
            lambda _: self._atualizar_preview(self.fonte())
        )

        lay.addWidget(self._combo, 1)
        lay.addWidget(self._preview, 1)

    def _atualizar_preview(self, nome: str):
        self._preview.setFont(QFont(nome, self._pt))
        self._preview.setText(f"Aa Bb 123  — {nome}")

    def fonte(self) -> str:

        return self._combo.currentData() or self._combo.currentText()

    def set_tamanho(self, pt: int):
        self._pt = max(pt, 8)
        self._atualizar_preview(self.fonte())

# ═════════════════════════════════════════════════════════════════════
# Widget principal
# ═════════════════════════════════════════════════════════════════════

class ConfigurarExplorer(QWidget):
    """
    Painel visual para configurar.json — abre no terminal inferior
    quando o arquivo é aberto no editor.
    Sincronização bidirecional: salvar no explorer grava o JSON;
    editar o JSON no editor e salvar atualiza o explorer via watcher.
    """

    configuracao_salva = Signal()  # emitido após salvar com sucesso (BUG-01)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._dados: dict = {}
        self._controles: dict[str, dict] = {}
        self._arquivo = ARQUIVO_CONFIG
        self._salvando = False

        self._construir_ui()
        self._carregar()
        self._aplicar_tema()
        self._iniciar_watcher()

    # ─────────────────────────────────────────────────────────────────
    # Watcher — JSON → explorer
    # ─────────────────────────────────────────────────────────────────

    def _iniciar_watcher(self):
        self._watcher_ext = QFileSystemWatcher()
        if os.path.isfile(self._arquivo):
            self._watcher_ext.addPath(self._arquivo)
        self._watcher_ext.fileChanged.connect(self._ao_arquivo_alterado_ext)
        self._timer_reload_ext = QTimer()
        self._timer_reload_ext.setSingleShot(True)
        self._timer_reload_ext.setInterval(700)
        self._timer_reload_ext.timeout.connect(self._recarregar_externo)

    def _ao_arquivo_alterado_ext(self, _caminho: str):
        if self._salvando:

            return

        if self._arquivo not in self._watcher_ext.files():
            self._watcher_ext.addPath(self._arquivo)
        self._timer_reload_ext.start()

    def _recarregar_externo(self):
        if self._salvando:

            return

        self._carregar()
        self._notificar("\u21ba  Recarregado (arquivo alterado no editor)", cor="#4a90d9", duracao=3000)

    # ─────────────────────────────────────────────────────────────────
    # UI estática (cabeçalho + scroll + rodapé)
    # ─────────────────────────────────────────────────────────────────

    # ⚠️  função grande (70 linhas)
    def _construir_ui(self):
        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(0)

        # Cabeçalho
        self._cab = QWidget()
        self._cab.setFixedHeight(36)
        lay_cab = QHBoxLayout(self._cab)
        lay_cab.setContentsMargins(12, 0, 10, 0)
        lay_cab.setSpacing(8)

        self._lbl_titulo = QLabel("\u2699  Configurações")
        self._lbl_titulo.setStyleSheet(
            "font-size:12px; font-weight:bold; font-family:Consolas; color:#e0e0e0;"
        )
        lay_cab.addWidget(self._lbl_titulo)
        lay_cab.addStretch()

        self._lbl_status = QLabel("")
        self._lbl_status.setStyleSheet("font-size:10px; color:#666;")
        lay_cab.addWidget(self._lbl_status)

        btn_recarregar = QPushButton("\u21ba  Recarregar")
        btn_recarregar.setFixedHeight(24)
        btn_recarregar.setStyleSheet(
            "QPushButton { background:#1a1a1a; color:#888; border:none;"
            " padding:2px 10px; font-size:10px; border-radius:3px; }"
            "QPushButton:hover { color:#e0e0e0; }"
        )
        btn_recarregar.clicked.connect(self._carregar)
        lay_cab.addWidget(btn_recarregar)

        self._btn_salvar = QPushButton("\u2b06  Salvar configurar.json")
        self._btn_salvar.setFixedHeight(24)
        self._btn_salvar.setStyleSheet(
            "QPushButton { background:#1a3a1a; color:#98c379; border:none;"
            " padding:2px 14px; font-size:10px; border-radius:3px; }"
            "QPushButton:hover { background:#264f28; }"
        )
        self._btn_salvar.clicked.connect(self._salvar)
        lay_cab.addWidget(self._btn_salvar)
        raiz.addWidget(self._cab)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setFixedHeight(1)
        raiz.addWidget(sep)

        # Área scrollável
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self._corpo = QWidget()
        self._lay_corpo = QVBoxLayout(self._corpo)
        self._lay_corpo.setContentsMargins(12, 10, 12, 20)
        self._lay_corpo.setSpacing(10)
        self._lay_corpo.addStretch()

        self._scroll.setWidget(self._corpo)
        raiz.addWidget(self._scroll, 1)

        # Rodapé
        self._rodape = QLabel(
            "Edite e clique em 'Salvar' — hot-reload aplica sem reiniciar a IDE."
        )
        self._rodape.setFixedHeight(20)
        self._rodape.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        raiz.addWidget(self._rodape)

    # ─────────────────────────────────────────────────────────────────
    # Construção dinâmica das seções
    # ─────────────────────────────────────────────────────────────────

    def _construir_secoes(self):
        """Remove seções anteriores e reconstrói a partir de self._dados."""
        while self._lay_corpo.count() > 1:
            item = self._lay_corpo.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        self._controles.clear()

        for chave_secao, titulo, descricao in _SECOES:
            dados_secao = self._dados.get(chave_secao)
            if not dados_secao:
                continue
            bloco = self._criar_bloco(chave_secao, titulo, descricao, dados_secao)
            self._lay_corpo.insertWidget(self._lay_corpo.count() - 1, bloco)

    # ⚠️  função grande (128 linhas)
    def _criar_bloco(self, chave_secao: str, titulo: str, descricao: str, dados: dict) -> QFrame:
        """Cria um bloco de seção com layout de 2 colunas."""
        frame = QFrame()
        frame.setObjectName("BlocoSecao")
        outer = QVBoxLayout(frame)
        outer.setContentsMargins(12, 10, 12, 12)
        outer.setSpacing(6)

        # Cabeçalho da seção
        lbl_t = QLabel(f"  {titulo}")
        lbl_t.setStyleSheet(
            "font-size:11px; font-weight:bold; font-family:Consolas; color:#4ec994;"
        )
        outer.addWidget(lbl_t)

        lbl_d = QLabel(f"  {descricao}")
        lbl_d.setStyleSheet("font-size:10px; color:#555;")
        outer.addWidget(lbl_d)

        linha = QFrame()
        linha.setFrameShape(QFrame.HLine)
        linha.setStyleSheet("color:#1a3a1a;")
        linha.setFixedHeight(1)
        outer.addWidget(linha)

        self._controles[chave_secao] = {}
        processados: set[str] = set()

        # ── Fonte (ocupa largura total) ───────────────────────────────
        if "fonte" in dados:
            row = self._criar_row_fonte(
                chave_secao,
                str(dados.get("fonte", "hein")),
                self._raw_para_pt(dados.get("tamanho_fonte", 12)),
                dados.get("tamanho_fonte", 12),
            )
            outer.addWidget(row)
            processados.update({"fonte", "tamanho_fonte"})

        # ── Coletar campos restantes ──────────────────────────────────
        items: list[tuple] = []   # (label_ou_None, widget)

        for campo, desc in _TEXTO_CAMPOS.items():
            if campo in dados and campo not in processados:
                le = QLineEdit(str(dados.get(campo, "")))
                le.setFixedHeight(24)
                self._controles[chave_secao][campo] = le
                items.append((desc + ":", le))
                processados.add(campo)

        for campo, (opcoes, desc) in _COMBO_CAMPOS.items():
            if campo in dados and campo not in processados:
                combo = QComboBox()
                combo.addItems(opcoes)
                val = str(dados.get(campo, opcoes[0]))
                idx = combo.findText(val)
                combo.setCurrentIndex(max(idx, 0))
                combo.setFixedHeight(24)
                combo.setFixedWidth(110)
                self._controles[chave_secao][campo] = combo
                items.append((desc + ":", combo))
                processados.add(campo)

        for campo, (mn, mx, suf, desc) in _INT_CAMPOS.items():
            if campo in dados and campo not in processados:
                try:
                    val = int(dados[campo])
                except Exception:
                    val = mn
                spin = QSpinBox()
                spin.setRange(mn, mx)
                spin.setValue(max(mn, min(mx, val)))
                spin.setSuffix(f"  {suf}")
                spin.setFixedHeight(24)
                spin.setFixedWidth(88)
                self._controles[chave_secao][campo] = spin
                items.append((desc + ":", spin))
                processados.add(campo)

        for campo, desc in _BOOL_CAMPOS.items():
            if campo in dados and campo not in processados:
                chk = QCheckBox(desc)
                chk.setChecked(bool(dados[campo]))
                self._controles[chave_secao][campo] = chk
                items.append((None, chk))
                processados.add(campo)

        if not items:

            return frame

        # ── Grid de 2 colunas ────────────────────────────────────────
        # Colunas: 0=lbl_E, 1=ctrl_E, 2=espaço, 3=lbl_D, 4=ctrl_D
        grid_w = QWidget()
        grid = QGridLayout(grid_w)
        grid.setContentsMargins(0, 4, 0, 0)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(5)
        grid.setColumnMinimumWidth(2, 14)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(4, 1)

        LBL_W = 160

        row_idx = 0
        col = 0   # 0=esquerda, 1=direita

        for label_text, widget in items:
            base_col = col * 3   # 0→cols 0,1  |  1→cols 3,4
            if label_text is None:
                # Checkbox: já tem label embutido, ocupa 2 colunas
                grid.addWidget(widget, row_idx, base_col, 1, 2)
            else:
                lbl = QLabel(label_text)
                lbl.setFixedWidth(LBL_W)
                lbl.setStyleSheet("font-size:10px; color:#aaa;")
                lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
                grid.addWidget(lbl, row_idx, base_col)
                grid.addWidget(widget, row_idx, base_col + 1)

            col += 1
            if col >= 2:
                col = 0
                row_idx += 1

        outer.addWidget(grid_w)

        return frame

    # ─────────────────────────────────────────────────────────────────
    # Linha especial: fonte + tamanho
    # ─────────────────────────────────────────────────────────────────

    def _criar_row_fonte(self, secao: str, fonte_atual: str, tam_pt: int, tam_raw) -> QWidget:
        row = QWidget()
        lay = QHBoxLayout(row)
        lay.setContentsMargins(0, 2, 0, 2)
        lay.setSpacing(8)

        lbl = QLabel("Fonte:")
        lbl.setFixedWidth(80)
        lbl.setStyleSheet("font-size:10px; color:#aaa;")
        lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        lay.addWidget(lbl)

        fonte_row = _FonteRow(fonte_atual, tam_pt)
        lay.addWidget(fonte_row, 1)

        lbl_tam = QLabel("Tamanho:")
        lbl_tam.setStyleSheet("font-size:10px; color:#aaa;")
        lay.addWidget(lbl_tam)

        spin = QSpinBox()
        spin.setRange(6, 72)
        spin.setValue(tam_pt)
        spin.setSuffix(" pt")
        spin.setFixedWidth(72)
        spin.setFixedHeight(26)
        spin.valueChanged.connect(fonte_row.set_tamanho)
        lay.addWidget(spin)

        self._controles[secao]["fonte"]         = fonte_row
        self._controles[secao]["tamanho_fonte"] = (spin, tam_raw)

        return row

    # ─────────────────────────────────────────────────────────────────
    # Carregamento / Salvamento
    # ─────────────────────────────────────────────────────────────────

    def _carregar(self):
        self._dados = _carregar_json(self._arquivo)
        self._ultimo_mtime = os.path.getmtime(self._arquivo) if os.path.isfile(self._arquivo) else 0.0
        self._construir_secoes()
        self._aplicar_tema()
        self._notificar("Carregado.", cor="#555", duracao=2000)
        log.ok(_ARQ, "_carregar", "configurar.json carregado no ConfigurarExplorer")

    def _coletar_dados(self) -> dict:
        """Lê todos os controles e retorna o dict atualizado."""
        dados_novos: dict = {}
        for chave_secao, controles in self._controles.items():
            secao_orig = self._dados.get(chave_secao, {})
            secao_nova = dict(secao_orig)
            for chave, ctrl in controles.items():
                if chave == "fonte":
                    secao_nova["fonte"] = ctrl.fonte()
                elif chave == "tamanho_fonte":
                    spin, raw = ctrl
                    if isinstance(raw, str) and "px" in raw:
                        secao_nova["tamanho_fonte"] = f"{spin.value()}px"
                    else:
                        secao_nova["tamanho_fonte"] = spin.value()
                elif isinstance(ctrl, QSpinBox):
                    secao_nova[chave] = ctrl.value()
                elif isinstance(ctrl, QCheckBox):
                    secao_nova[chave] = ctrl.isChecked()
                elif isinstance(ctrl, QComboBox):
                    secao_nova[chave] = ctrl.currentText()
                elif isinstance(ctrl, QLineEdit):
                    secao_nova[chave] = ctrl.text().strip()
            dados_novos[chave_secao] = secao_nova

        return dados_novos

    def _salvar(self):
        self._salvando = True
        try:
            dados = self._coletar_dados()
            if _salvar_json(self._arquivo, dados):
                self._dados = dados
                self.configuracao_salva.emit()
                self._notificar(
                    "\u2713  Salvo! Hot-reload aplicar\u00e1 as mudan\u00e7as em instantes.",
                    cor="#98c379",
                )
                log.ok(_ARQ, "_salvar", "configurar.json salvo pelo ConfigurarExplorer")
            else:
                self._notificar("\u26a0  Erro ao salvar \u2014 verifique o log.", cor="#e06c75")
        finally:
            QTimer.singleShot(1200, lambda: setattr(self, "_salvando", False))

    # ─────────────────────────────────────────────────────────────────
    # Utilitários
    # ─────────────────────────────────────────────────────────────────

    @staticmethod
    def _raw_para_pt(raw) -> int:
        if isinstance(raw, (int, float)):

            return int(raw)

        try:

            return int(re.sub(r'[^0-9]', '', str(raw)) or 12)

        except Exception:

            return 12

    # 💡 cor_opc = Literal["#e0e0e0"] ← defina os valores válidos
    def _notificar(self, msg: str, cor: str = "#e0e0e0", duracao: int = 4000):
        self._lbl_status.setText(msg)
        self._lbl_status.setStyleSheet(f"font-size:10px; color:{cor};")
        QTimer.singleShot(duracao, lambda: self._lbl_status.setText(""))

    # ─────────────────────────────────────────────────────────────────
    # Tema
    # ─────────────────────────────────────────────────────────────────

    # ⚠️  função grande (94 linhas)
    def _aplicar_tema(self):
        t      = tema_global()
        fundo  = t.cor("terminal.fundo",             "#020202")
        toolbar= t.cor("interface.fundo_toolbar",    "#0F1210")
        borda  = t.cor("interface.borda",            "#1a2e1a")
        texto  = t.cor("interface.texto",            "#e0e0e0")
        fraco  = t.cor("editor.numero_linha",        "#555555")
        inputs = t.cor("interface.inputs",           "#252530")
        hover  = t.cor("interface.fundo_item_hover", "#1a2e1a")
        sel    = t.cor("interface.texto_destaque",   "#4ec994")
        thumb  = t.cor("interface.scrollbar_thumb",  "#264f78")

        self._cab.setStyleSheet(
            f"background:{toolbar}; border-bottom:1px solid {borda};"
        )
        self._rodape.setStyleSheet(
            f"font-size:10px; color:{fraco}; background:{fundo}; padding-right:10px;"
        )
        self.setStyleSheet(f"""
            QWidget {{
                background: {fundo};
                color: {texto};
            }}
            QFrame#BlocoSecao {{
                background: {t.cor('terminal.fundo','#010108')};
                border: 1px solid {borda};
                border-radius: 5px;
            }}
            QLineEdit {{
                background: {inputs};
                color: {texto};
                border: 1px solid {borda};
                border-radius: 3px;
                padding: 2px 6px;
                font-size: 10px;
            }}
            QLineEdit:focus {{
                border-color: {sel};
            }}
            QComboBox {{
                background: {inputs};
                color: {texto};
                border: 1px solid {borda};
                border-radius: 3px;
                padding: 2px 6px;
                font-size: 10px;
            }}
            QComboBox::drop-down {{ border: none; width: 16px; }}
            QComboBox QAbstractItemView {{
                background: {t.cor('interface.fundo', '#070706')};
                color: {texto};
                selection-background-color: {hover};
                border: 1px solid {borda};
            }}
            QSpinBox {{
                background: {inputs};
                color: {texto};
                border: 1px solid {borda};
                border-radius: 3px;
                padding: 2px 4px;
                font-size: 10px;
            }}
            QSpinBox::up-button, QSpinBox::down-button {{
                background: {hover};
                border: none;
                width: 14px;
            }}
            QCheckBox {{
                color: {texto};
                font-size: 10px;
                spacing: 6px;
            }}
            QCheckBox::indicator {{
                width: 14px; height: 14px;
                border: 1px solid {borda};
                border-radius: 2px;
                background: {inputs};
            }}
            QCheckBox::indicator:checked {{
                background: {sel};
                border-color: {sel};
            }}
            QScrollArea {{ border: none; background: {fundo}; }}
            QScrollBar:vertical {{
                background: transparent; width: 8px; border: none;
            }}
            QScrollBar::handle:vertical {{
                background: {thumb}; border-radius: 4px; min-height: 20px;
            }}
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {{ height: 0; }}
            QLabel {{ background: transparent; }}
            QFrame[frameShape="4"] {{ color: {borda}; }}
        """)

    def atualizar_tema(self, tema: dict = None):
        self._aplicar_tema()
