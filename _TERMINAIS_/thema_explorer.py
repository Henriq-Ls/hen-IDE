# 📁 _TERMINAIS_/thema_explorer.py
"""
ThemaExplorer — painel visual para thema.json.

Cada entrada de cor exibe:  [■ swatch clicável]  [nome da chave]  [input hex]
Clicar no swatch abre QColorDialog (com canal alpha).
Valores "transparent" mostram swatch xadrez e campo de texto livre.
Sub-seções (editor.sintaxe, terminal.cores_ansi) são exibidas indentadas.
"""

import json
import os
from PySide6.QtCore import Qt, QFileSystemWatcher
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QColorDialog, QComboBox, QFrame, QGridLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QScrollArea, QSizePolicy,
    QVBoxLayout, QWidget,
)

from _CONFIGURA_ import ARQUIVO_TEMA
from _CONFIGURA_.gerenciador_tema import tema_global
from _LOG_.log import log
from _UTILITARIOS_.icones import icone_tema
_ARQ = "thema_explorer.py"

# ─────────────────────────────────────────────────────────────────────
# Funções auxiliares de UI
# ─────────────────────────────────────────────────────────────────────

def _e_cor(valor: str) -> bool:
    if not isinstance(valor, str):

        return False

    v = valor.strip().lower()
    if v == "transparent":

        return True

    return valor.strip().startswith("#") and len(valor.strip()) in (4, 5, 7, 9)

def _css_swatch(hex_val: str) -> str:
    v = hex_val.strip()
    if not v or v.lower() == "transparent":

        return (

            "background: qlineargradient(x1:0,y1:0,x2:1,y2:1,"
            "stop:0 #555,stop:0.49 #555,stop:0.5 #222,stop:1 #222);"
        )

    return f"background:{v};"

# 💡 cor_opc = Literal["#4a90d9"] ← defina os valores válidos
def _mk_titulo(texto: str, cor: str = "#4a90d9") -> QLabel:
    lbl = QLabel(texto)
    lbl.setStyleSheet(
        f"font-size:11px;font-weight:bold;color:{cor};"
        "font-family:Consolas;padding:6px 0 3px 0;letter-spacing:1px;"
    )

    return lbl

def _mk_subtitulo(texto: str) -> QLabel:
    lbl = QLabel(texto)
    lbl.setStyleSheet(
        "font-size:10px;font-weight:bold;color:#6b8f6b;"
        "font-family:Consolas;padding:4px 0 2px 16px;"
    )

    return lbl

def _mk_sep() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.HLine)
    f.setFixedHeight(1)
    f.setStyleSheet("background:#1a2e1a;")

    return f

def _mk_label(texto: str, largura: int = 195) -> QLabel:
    lbl = QLabel(texto)
    lbl.setFixedWidth(largura)
    lbl.setStyleSheet("font-size:10px;color:#888;font-family:Consolas;")

    return lbl

def _mk_hex_edit(valor: str) -> QLineEdit:
    w = QLineEdit(str(valor))
    w.setFixedHeight(22)
    w.setFixedWidth(115)
    w.setStyleSheet(
        "QLineEdit{background:#0a0e14;color:#e0e0e0;border:1px solid #1a2e4a;"
        "border-radius:3px;padding:1px 5px;font-size:10px;font-family:Consolas;}"
        "QLineEdit:focus{border-color:#4a90d9;}"
    )

    return w

def _mk_text_edit(valor: str) -> QLineEdit:
    w = QLineEdit(str(valor))
    w.setFixedHeight(22)
    w.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    w.setStyleSheet(
        "QLineEdit{background:#0a0e14;color:#e0e0e0;border:1px solid #1a2e4a;"
        "border-radius:3px;padding:1px 5px;font-size:10px;font-family:Consolas;}"
        "QLineEdit:focus{border-color:#4a90d9;}"
    )

    return w

def _mk_row_meta(chave: str, widget: QWidget) -> QWidget:
    row = QWidget()
    lay = QHBoxLayout(row)
    lay.setContentsMargins(0, 2, 0, 2)
    lay.setSpacing(8)
    lay.addWidget(_mk_label(chave))
    lay.addWidget(widget)
    lay.addStretch()

    return row

# ─────────────────────────────────────────────────────────────────────
# Swatch clicável com QColorDialog
# ─────────────────────────────────────────────────────────────────────

class _Swatch(QLabel):
    def __init__(self, valor: str, line_edit: QLineEdit, parent=None):
        super().__init__(parent)
        self._le = line_edit
        self.setFixedSize(20, 20)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("Clique para escolher cor")
        self._atualizar(valor)
        self._le.textChanged.connect(self._atualizar)

    def _atualizar(self, valor: str = ""):
        v = (valor or self._le.text()).strip()
        self.setStyleSheet(f"border:1px solid #333;border-radius:2px;{_css_swatch(v)}")

    def mousePressEvent(self, event):
        if event.button() != Qt.LeftButton:

            return

        txt = self._le.text().strip()
        inicial = QColor(txt) if txt.startswith("#") else QColor("#121212")
        cor = QColorDialog.getColor(
            inicial, self, "Escolher Cor", QColorDialog.ShowAlphaChannel
        )
        if cor.isValid():
            hex_val = cor.name(QColor.HexArgb) if cor.alpha() < 255 else cor.name()
            self._le.setText(hex_val)

# ─────────────────────────────────────────────────────────────────────
# Widget principal
# ─────────────────────────────────────────────────────────────────────

_SECOES_COR = [
    ("interface",       "#4a90d9", "◈  INTERFACE"),
    ("editor",          "#61afef", "◈  EDITOR"),
    ("terminal",        "#4ec994", "◈  TERMINAL"),
    ("terminal_run",    "#56b6c2", "◈  TERMINAL RUN"),
    ("painel_arquivos", "#e5c07b", "◈  PAINEL ARQUIVOS"),
    ("painel_outline",  "#c678dd", "◈  PAINEL OUTLINE"),
    ("painel_git",      "#98c379", "◈  PAINEL GIT"),
    ("log",             "#e06c75", "◈  LOG"),
    ("grafo",           "#56b6c2", "◈  GRAFO"),
    ("menu_contexto",   "#d19a66", "◈  MENU CONTEXTO"),
]

class ThemaExplorer(QWidget):
    """Painel visual para thema.json — swatches de cor com edição direta."""

    def __init__(self, caminho: str = None, parent=None):
        super().__init__(parent)
        self._caminho = caminho or ARQUIVO_TEMA
        self._dados: dict = {}
        self._ultimo_mtime: float = 0.0
        # "secao.chave" ou "secao.sub.chave" → QLineEdit
        self._campos: dict[str, QLineEdit] = {}
        self._cb_aparencia: QComboBox | None = None
        self._le_nome: QLineEdit | None = None
        self._le_autor: QLineEdit | None = None

        self._watcher = QFileSystemWatcher(self)
        self._watcher.fileChanged.connect(self._ao_arquivo_mudar)
        if os.path.exists(self._caminho):
            self._watcher.addPath(self._caminho)

        self._construir_ui()
        self._carregar()

    # ── Esqueleto da janela ───────────────────────────────────────────

    # ⚠️  função grande (66 linhas)
    def _construir_ui(self):
        tema = tema_global().dados()
        fundo = tema.get("interface", {}).get("fundo", "#121212")
        toolbar = tema.get("interface", {}).get("fundo_toolbar", "#0d0d0d")
        texto_c = tema.get("interface", {}).get("texto", "#e0e0e0")

        self.setStyleSheet(f"background:{fundo};color:{texto_c};")

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(0)

        # ── cabeçalho ─────────────────────────────────────────────────
        cab = QWidget()
        cab.setFixedHeight(38)
        cab.setStyleSheet(
            f"background:{toolbar};border-bottom:1px solid #1a2e1a;"
        )
        cab_lay = QHBoxLayout(cab)
        cab_lay.setContentsMargins(12, 0, 12, 0)
        cab_lay.setSpacing(8)

        ico = QLabel()
        ico.setPixmap(icone_tema("mdi.palette-outline").pixmap(16, 16))
        cab_lay.addWidget(ico)

        self._lbl_titulo = QLabel(f"{os.path.basename(self._caminho)}  —  Tema Visual")
        self._lbl_titulo.setStyleSheet(
            f"font-size:11px;font-weight:bold;color:{texto_c};"
            "font-family:Consolas;background:transparent;"
        )
        cab_lay.addWidget(self._lbl_titulo)
        cab_lay.addStretch()

        btn = QPushButton("  Salvar")
        btn.setIcon(icone_tema("mdi.content-save-outline"))
        btn.setFixedHeight(26)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setStyleSheet(
            "QPushButton{background:#082C3A;color:#e0e0e0;border:1px solid #1a3a4a;"
            "border-radius:3px;font-size:10px;font-family:Consolas;padding:0 10px;}"
            "QPushButton:hover{background:#0d3d50;}"
            "QPushButton:pressed{background:#051e28;}"
        )
        btn.clicked.connect(self._salvar)
        cab_lay.addWidget(btn)
        raiz.addWidget(cab)

        # ── scroll ────────────────────────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(
            f"QScrollArea{{background:{fundo};border:none;}}"
            "QScrollBar:vertical{background:#0a0a0a;width:6px;border-radius:3px;}"
            "QScrollBar::handle:vertical{background:#1a3a1a;border-radius:3px;}"
            "QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{height:0;}"
        )

        self._area = QWidget()
        self._area.setStyleSheet(f"background:{fundo};")
        self._lay = QVBoxLayout(self._area)
        self._lay.setContentsMargins(16, 10, 16, 20)
        self._lay.setSpacing(4)

        scroll.setWidget(self._area)
        raiz.addWidget(scroll)

    # ── Carregar e popular ────────────────────────────────────────────

    def _carregar(self):
        if not os.path.exists(self._caminho):

            return

        try:
            mtime = os.path.getmtime(self._caminho)
            with open(self._caminho, "r", encoding="utf-8") as f:
                self._dados = json.load(f)
            self._ultimo_mtime = mtime
        except Exception as e:
            log.erro(_ARQ, "_carregar", str(e))

            return

        self._campos.clear()
        self._cb_aparencia = None
        self._le_nome = None
        self._le_autor = None
        self._limpar_layout()
        self._popular()

        if self._lbl_titulo is not None:
            self._lbl_titulo.setText(f"{os.path.basename(self._caminho)}  —  Tema Visual")

        if self._caminho not in self._watcher.files():
            self._watcher.addPath(self._caminho)

    def _limpar_layout(self):
        while self._lay.count():
            item = self._lay.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    # ⚠️  função grande (62 linhas)
    def _popular(self):
        lay = self._lay
        d = self._dados

        # ── Meta ──────────────────────────────────────────────────────
        lay.addWidget(_mk_titulo("◈  META", "#4ec994"))
        lay.addWidget(_mk_sep())
        lay.addSpacing(4)

        self._le_nome = _mk_text_edit(d.get("nome", ""))
        self._le_autor = _mk_text_edit(d.get("autor", ""))
        lay.addWidget(_mk_row_meta("nome", self._le_nome))
        lay.addWidget(_mk_row_meta("autor", self._le_autor))

        cb = QComboBox()
        cb.addItems(["escuro", "claro"])
        cb.setCurrentText(d.get("aparencia", "escuro"))
        cb.setFixedHeight(22)
        cb.setStyleSheet(
            "QComboBox{background:#0a0e14;color:#e0e0e0;border:1px solid #1a2e4a;"
            "border-radius:3px;padding:1px 5px;font-size:10px;font-family:Consolas;}"
            "QComboBox::drop-down{border:none;}"
            "QComboBox QAbstractItemView{background:#0d1a1a;color:#e0e0e0;"
            "selection-background-color:#1a3a3a;}"
        )
        self._cb_aparencia = cb
        lay.addWidget(_mk_row_meta("aparencia", cb))
        lay.addSpacing(12)

        # ── Seções de cor ──────────────────────────────────────────────
        for chave_secao, cor_titulo, label_titulo in _SECOES_COR:
            secao = d.get(chave_secao)
            if not isinstance(secao, dict):
                continue

            lay.addWidget(_mk_titulo(label_titulo, cor_titulo))
            lay.addWidget(_mk_sep())
            lay.addSpacing(4)

            grid = QWidget()
            gl = QGridLayout(grid)
            gl.setContentsMargins(0, 0, 0, 0)
            gl.setHorizontalSpacing(6)
            gl.setVerticalSpacing(3)
            linha = 0

            for k, v in secao.items():
                if isinstance(v, dict):
                    # sub-seção (ex: sintaxe, cores_ansi)
                    gl.addWidget(_mk_subtitulo(f"▸ {k}"), linha, 0, 1, 3)
                    linha += 1
                    for sk, sv in v.items():
                        linha = self._linha_grid(gl, linha, f"  {sk}", str(sv),
                                                 f"{chave_secao}.{k}.{sk}")
                else:
                    linha = self._linha_grid(gl, linha, k, str(v),
                                             f"{chave_secao}.{k}")

            lay.addWidget(grid)
            lay.addSpacing(14)

        lay.addStretch()

    def _linha_grid( self, gl: QGridLayout, linha: int, chave_display: str, valor: str, chave_interna: str ) -> int:
        e_cor = _e_cor(valor)
        le = _mk_hex_edit(valor) if e_cor else _mk_text_edit(valor)
        self._campos[chave_interna] = le

        if e_cor:
            swatch = _Swatch(valor, le)
        else:
            dot = QLabel("·")
            dot.setFixedSize(20, 20)
            dot.setAlignment(Qt.AlignCenter)
            dot.setStyleSheet("color:#444;font-size:14px;")
            swatch = dot

        gl.addWidget(swatch, linha, 0, Qt.AlignVCenter)
        gl.addWidget(_mk_label(chave_display), linha, 1, Qt.AlignVCenter)
        gl.addWidget(le, linha, 2, Qt.AlignVCenter)

        return linha + 1

    # ── Salvar ────────────────────────────────────────────────────────

    # ⚠️  except genérico vazio
    def _salvar(self):
        if not self._dados:

            return

        d = self._dados

        if self._le_nome is not None:
            d["nome"] = self._le_nome.text()
        if self._le_autor is not None:
            d["autor"] = self._le_autor.text()
        if self._cb_aparencia is not None:
            d["aparencia"] = self._cb_aparencia.currentText()

        for chave_interna, le in self._campos.items():
            valor = le.text().strip()
            partes = chave_interna.split(".")
            try:
                if len(partes) == 2:
                    sec, k = partes
                    if isinstance(d.get(sec), dict):
                        d[sec][k] = valor
                elif len(partes) == 3:
                    sec, sub, k = partes
                    if isinstance(d.get(sec), dict) and isinstance(d[sec].get(sub), dict):
                        d[sec][sub][k] = valor
            except Exception:
                pass

        self._watcher.removePath(self._caminho)
        try:
            with open(self._caminho, "w", encoding="utf-8") as f:
                json.dump(d, f, ensure_ascii=False, indent=2)
            self._ultimo_mtime = os.path.getmtime(self._caminho)
            log.ok(_ARQ, "_salvar", "thema.json salvo")
        except Exception as e:
            log.erro(_ARQ, "_salvar", str(e))
        finally:
            self._watcher.addPath(self._caminho)

    # ── Sincronização ─────────────────────────────────────────────────

    def _ao_arquivo_mudar(self, _: str = ""):
        try:
            mtime = os.path.getmtime(self._caminho)
        except OSError:

            return

        if abs(mtime - self._ultimo_mtime) < 0.05:

            return

        self._carregar()

    def recarregar(self):
        self._carregar()

    def abrir(self, caminho: str) -> None:
        """Retarget o explorer para editar um arquivo de tema diferente.
        Usado quando a mesma aba e reaproveitada para outro arquivo de
        AppData/temas/ (ex.: usuario troca o tema ativo pelo menu)."""
        if caminho == self._caminho:
            self._recarregar_se_necessario()
            return

        if self._caminho and self._caminho in self._watcher.files():
            self._watcher.removePath(self._caminho)

        self._caminho = caminho
        self._carregar()

    def _recarregar_se_necessario(self):
        try:
            mtime = os.path.getmtime(self._caminho)
        except OSError:

            return

        if abs(mtime - self._ultimo_mtime) > 0.05:
            self._carregar()
