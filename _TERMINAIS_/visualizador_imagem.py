# 📁 _TERMINAIS_/visualizador_imagem.py
"""
VisualizadorImagem — exibe imagem no TabWidget (área central do editor).
ControlesImagem    — ferramentas de edição no TerminalTabWidget.

Ferramentas disponíveis (ControlesImagem):
  • Converter para .ico      — tamanho configurável, requer Pillow
  • Redimensionar            — W×H com opção de manter proporção, requer Pillow
  • Converter formato        — PNG/JPG/BMP/WebP/GIF, requer Pillow
  • Girar / Espelhar         — 90°/180°/270° e flip H/V, requer Pillow
  • Recortar bordas          — remove N px de cada borda, requer Pillow
  • Base64                   — copia data URI para área de transferência (stdlib)
  • Escala de cinza          — salva variante _gray, requer Pillow
  • Gerar QR Code            — gera PNG a partir de texto/URL, requer qrcode+Pillow
  • Upload para nuvem        — catbox.moe, anônimo, copia URL (stdlib + QThread)
"""
import os
import uuid
import base64
import urllib.request
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QPushButton, QScrollArea, QSizePolicy,
    QFileDialog, QSpinBox, QGroupBox, QFormLayout,
    QComboBox, QCheckBox, QDialog, QTextBrowser,
    QApplication, QLineEdit,
)
from PySide6.QtCore import Qt, Signal, QThread, QObject
from PySide6.QtGui import QPixmap
from _CONFIGURA_.gerenciador_tema import tema_global
from _LOG_.log import log
# ─────────────────────────────────────────────────────────────────────────────
# Texto de ajuda (HTML)
# ─────────────────────────────────────────────────────────────────────────────
_AJUDA_HTML = """
<h3 style="margin-top:0">🖼️ Ferramentas de Imagem — hein IDE</h3>

<b>Arquivo</b><br>
Exibe nome, dimensões e tamanho do arquivo aberto.<br><br>

<b>Converter para .ico</b><br>
Converte a imagem para formato .ico em tamanho configurável (16–256 px).<br>
Requer: <code>pip install pillow</code><br><br>

<b>Redimensionar</b><br>
Define nova largura e altura em pixels. Com "Manter proporção" marcado,
a altura se ajusta automaticamente ao digitar a largura.<br>
Requer: <code>pip install pillow</code><br><br>

<b>Converter formato</b><br>
Salva a imagem em outro formato: PNG, JPG, BMP, WebP ou GIF.<br>
Nota: JPG não suporta transparência — canal alpha é descartado.<br>
Requer: <code>pip install pillow</code><br><br>

<b>Girar / Espelhar</b><br>
Gira 90°, 180° ou 270° (sentido horário) ou espelha H/V.<br>
Salva com sufixo <code>_rot90</code>, <code>_flipH</code>, etc.<br>
Requer: <code>pip install pillow</code><br><br>

<b>Recortar bordas</b><br>
Remove N pixels de cada borda (esquerda, topo, direita, baixo).<br>
Salva com sufixo <code>_crop</code>.<br>
Requer: <code>pip install pillow</code><br><br>

<b>Base64</b><br>
Converte a imagem para string Base64 (<code>data:image/...;base64,...</code>)
e copia para a área de transferência.<br>
Útil para embutir imagens em código Python, HTML ou CSS sem arquivo externo.<br>
<b>Não requer bibliotecas adicionais.</b><br><br>

<b>Escala de cinza</b><br>
Converte a imagem para preto e branco e salva com sufixo <code>_gray</code>.<br>
Útil para criar variantes "desativadas" de ícones em interfaces gráficas.<br>
Requer: <code>pip install pillow</code><br><br>

<b>Gerar QR Code</b><br>
Gera um QR Code a partir de qualquer texto ou URL e salva como PNG.<br>
Requer: <code>pip install qrcode pillow</code><br><br>

<b>Upload para nuvem (catbox.moe)</b><br>
Envia a imagem para <b>catbox.moe</b> (gratuito, sem cadastro, sem API key)
e copia a URL permanente para a área de transferência.<br>
O envio ocorre em background — a IDE não trava durante o upload.<br>
<b>Não requer bibliotecas adicionais</b> (usa urllib da stdlib).<br>
"""

# ─────────────────────────────────────────────────────────────────────────────
# Worker de upload (RG-02 — operação de rede em QThread, nunca na UI thread)
# ─────────────────────────────────────────────────────────────────────────────
class _UploadWorker(QObject):
    concluido = Signal(str)
    erro      = Signal(str)

    def __init__(self, caminho: str):
        super().__init__()
        self._caminho = caminho

    def rodar(self):
        try:
            boundary = uuid.uuid4().hex
            filename  = os.path.basename(self._caminho)
            ext       = os.path.splitext(filename)[1].lstrip(".").lower() or "png"

            with open(self._caminho, "rb") as f:
                file_data = f.read()

            cabecalho = (
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="reqtype"\r\n\r\n'
                f"fileupload\r\n"
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="userhash"\r\n\r\n'
                f"\r\n"
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="fileToUpload"; filename="{filename}"\r\n'
                f"Content-Type: image/{ext}\r\n\r\n"
            ).encode("utf-8")
            rodape = f"\r\n--{boundary}--\r\n".encode("utf-8")
            body   = cabecalho + file_data + rodape

            req = urllib.request.Request(
                "https://catbox.moe/user/api.php", data=body
            )
            req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
            req.add_header("User-Agent", "hein-IDE/1.0")

            with urllib.request.urlopen(req, timeout=30) as resp:
                url = resp.read().decode("utf-8").strip()

            if url.startswith("http"):
                self.concluido.emit(url)
            else:
                self.erro.emit(f"Resposta inesperada do servidor: {url}")
        except Exception as e:
            self.erro.emit(str(e))

# ─────────────────────────────────────────────────────────────────────────────
# VisualizadorImagem — área central do editor
# ─────────────────────────────────────────────────────────────────────────────
class VisualizadorImagem(QWidget):
    """Abre no TabWidget — mesma área dos arquivos de código."""

    def __init__(self, caminho: str, parent=None):
        super().__init__(parent)
        self.caminho = caminho
        self._zoom   = 1.0
        self._pixmap_original: QPixmap | None = None
        self._construir_ui()
        self._carregar(caminho)

    # ⚠️  função grande (56 linhas)
    def _construir_ui(self):
        t  = tema_global()
        bg = t.cor("editor.fundo", "#0a0a0a")
        tx = t.cor("editor.texto", "#e0e0e0")
        bd = t.cor("interface.borda", "#222")
        hl = t.cor("interface.fundo_item_hover", "#1e1e2e")
        self.setStyleSheet(f"background: {bg}; color: {tx};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        def _btn(rotulo, tooltip, slot):
            b = QPushButton(rotulo)
            b.setToolTip(tooltip)
            b.setCursor(Qt.PointingHandCursor)
            b.setStyleSheet(
                f"background: {hl}; color: {tx}; "
                f"border: 1px solid {bd}; border-radius: 3px; padding: 2px 10px;"
            )
            b.clicked.connect(slot)

            return b

        barra = QWidget()
        barra.setStyleSheet(
            f"background: {t.cor('interface.fundo','#111')}; "
            f"border-bottom: 1px solid {bd};"
        )
        b_lay = QHBoxLayout(barra)
        b_lay.setContentsMargins(8, 4, 8, 4)
        b_lay.setSpacing(6)
        b_lay.addWidget(_btn("−", "Diminuir zoom (scroll ↓)", self._zoom_out))
        self._lbl_zoom = QLabel("100%")
        self._lbl_zoom.setStyleSheet(f"color: {tx}; padding: 0 4px;")
        b_lay.addWidget(self._lbl_zoom)
        b_lay.addWidget(_btn("+", "Aumentar zoom (scroll ↑)", self._zoom_in))
        b_lay.addWidget(_btn("1:1", "Tamanho real", self._zoom_reset))
        b_lay.addWidget(_btn("Ajustar", "Ajustar à janela", self._zoom_fit))
        b_lay.addStretch()
        self._lbl_info = QLabel()
        self._lbl_info.setStyleSheet(
            f"color: {t.cor('interface.texto_fraco','#888')}; font-size: 11px;"
        )
        b_lay.addWidget(self._lbl_info)
        layout.addWidget(barra)

        self._scroll = QScrollArea()
        self._scroll.setAlignment(Qt.AlignCenter)
        self._scroll.setStyleSheet(f"background: {bg}; border: none;")
        self._lbl_img = QLabel()
        self._lbl_img.setAlignment(Qt.AlignCenter)
        self._lbl_img.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self._scroll.setWidget(self._lbl_img)
        self._scroll.setWidgetResizable(False)
        layout.addWidget(self._scroll)

    def _carregar(self, caminho: str):
        if not os.path.isfile(caminho):

            return

        px = QPixmap(caminho)
        if px.isNull():
            self._lbl_img.setText("Não foi possível carregar a imagem.")

            return

        self._pixmap_original = px
        kb  = os.path.getsize(caminho) // 1024
        ext = os.path.splitext(caminho)[1].upper().lstrip(".")
        self._lbl_info.setText(f"{px.width()} × {px.height()} px  |  {kb} KB  |  {ext}")
        self._aplicar_zoom()

    def _aplicar_zoom(self):
        if not self._pixmap_original:

            return

        w = int(self._pixmap_original.width()  * self._zoom)
        h = int(self._pixmap_original.height() * self._zoom)
        escalado = self._pixmap_original.scaled(
            w, h, Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        self._lbl_img.setPixmap(escalado)
        self._lbl_img.setFixedSize(escalado.width(), escalado.height())
        self._lbl_zoom.setText(f"{int(self._zoom * 100)}%")

    def _zoom_in(self):
        self._zoom = min(self._zoom + 0.25, 8.0)
        self._aplicar_zoom()

    def _zoom_out(self):
        self._zoom = max(self._zoom - 0.25, 0.1)
        self._aplicar_zoom()

    def _zoom_reset(self):
        self._zoom = 1.0
        self._aplicar_zoom()

    def _zoom_fit(self):
        if not self._pixmap_original:

            return

        area = self._scroll.viewport().size()
        zw   = area.width()  / max(self._pixmap_original.width(),  1)
        zh   = area.height() / max(self._pixmap_original.height(), 1)
        self._zoom = min(zw, zh) * 0.95
        self._aplicar_zoom()

    def wheelEvent(self, event):
        if event.angleDelta().y() > 0:
            self._zoom_in()
        else:
            self._zoom_out()

# ─────────────────────────────────────────────────────────────────────────────
# ControlesImagem — painel de ferramentas no TerminalTabWidget
# ─────────────────────────────────────────────────────────────────────────────
class ControlesImagem(QWidget):
    """Ferramentas de edição de imagem — abre no TerminalTabWidget."""

    def __init__(self, caminho: str, parent=None):
        super().__init__(parent)
        self.caminho = caminho
        self._orig_w = 0
        self._orig_h = 0
        self._upload_thread: QThread | None = None
        self._upload_worker: _UploadWorker | None = None
        self._construir_ui()
        self.set_caminho(caminho)

    # ── API pública ──────────────────────────────────────────────────────────

    def set_caminho(self, caminho: str):
        self.caminho = caminho
        self._lbl_arquivo.setText(os.path.basename(caminho))
        if os.path.isfile(caminho):
            px = QPixmap(caminho)
            if not px.isNull():
                kb = os.path.getsize(caminho) // 1024
                self._lbl_tamanho.setText(
                    f"{px.width()} × {px.height()} px  |  {kb} KB"
                )
                self._orig_w = px.width()
                self._orig_h = px.height()
                self._spin_larg.blockSignals(True)
                self._spin_alt.blockSignals(True)
                self._spin_larg.setValue(self._orig_w)
                self._spin_alt.setValue(self._orig_h)
                self._spin_larg.blockSignals(False)
                self._spin_alt.blockSignals(False)

    # ── Construção da UI ─────────────────────────────────────────────────────

    # ⚠️  função grande (255 linhas)
    def _construir_ui(self):
        t = tema_global()

        # Estilo mínimo para QGroupBox — só borda.
        # Todos os outros widgets herdam do QSS global da aplicação.
        _gbox = (
            f"QGroupBox {{ "
            f"border: 1px solid {t.cor('interface.fundo_aba_ativa', '#062B2A')}; "
            f"border-radius: 4px; margin-top: 8px; padding-top: 4px; }} "
            f"QGroupBox::title {{ subcontrol-origin: margin; left: 8px; "
            f"color: {t.cor('interface.texto_fraco', '#7094A1')}; }}"
        )

        # ── layout raiz ──
        raiz_lay = QVBoxLayout(self)
        raiz_lay.setContentsMargins(0, 0, 0, 0)
        raiz_lay.setSpacing(0)

        # ── barra de topo ──
        barra_top = QWidget()
        barra_top.setStyleSheet(
            f"background: {t.cor('interface.fundo_toolbar', '#121212')}; "
            f"border-bottom: 1px solid {t.cor('interface.fundo_aba_ativa', '#062B2A')};"
        )
        barra_top_lay = QHBoxLayout(barra_top)
        barra_top_lay.setContentsMargins(10, 4, 8, 4)
        lbl_titulo = QLabel("Ferramentas de Imagem")
        lbl_titulo.setStyleSheet("font-weight: bold; background: transparent;")
        barra_top_lay.addWidget(lbl_titulo)
        barra_top_lay.addStretch()
        btn_ajuda = QPushButton("?")
        btn_ajuda.setToolTip("Ajuda — o que cada ferramenta faz")
        btn_ajuda.setFixedSize(22, 22)
        btn_ajuda.setCursor(Qt.PointingHandCursor)
        btn_ajuda.clicked.connect(self._mostrar_ajuda)
        barra_top_lay.addWidget(btn_ajuda)
        raiz_lay.addWidget(barra_top)

        # ── scroll area ──
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; }")
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        conteudo = QWidget()

        # grade 3 colunas
        grid = QGridLayout(conteudo)
        grid.setContentsMargins(10, 8, 10, 10)
        grid.setSpacing(10)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(2, 1)
        scroll.setWidget(conteudo)
        raiz_lay.addWidget(scroll)

        # helpers locais ──────────────────────────────────────────────────────
        def _status():
            lbl = QLabel("")
            lbl.setStyleSheet("font-size: 11px;")
            lbl.setWordWrap(True)

            return lbl

        def _btn_h(texto, slot, tooltip=""):
            """Botão não-esticado: QHBox + addStretch."""
            h = QHBoxLayout()
            b = QPushButton(texto)
            b.setCursor(Qt.PointingHandCursor)
            if tooltip:
                b.setToolTip(tooltip)
            b.clicked.connect(slot)
            h.addWidget(b)
            h.addStretch()

            return h

        def _spin(minv=1, maxv=9999, val=100):
            s = QSpinBox()
            s.setRange(minv, maxv)
            s.setValue(val)

            return s

        # ── ROW 0: Arquivo (abrange 3 colunas) ───────────────────────────────
        info_box = QGroupBox("Arquivo")
        info_box.setStyleSheet(_gbox)
        info_lay = QFormLayout(info_box)
        self._lbl_arquivo = QLabel("—")
        self._lbl_tamanho = QLabel("—")
        info_lay.addRow("Nome:", self._lbl_arquivo)
        info_lay.addRow("Dimensões:", self._lbl_tamanho)
        grid.addWidget(info_box, 0, 0, 1, 3)

        # ── ROW 1 col 0: Converter para .ico ─────────────────────────────────
        ico_box = QGroupBox("Converter para .ico")
        ico_box.setStyleSheet(_gbox)
        ico_lay = QVBoxLayout(ico_box)
        row = QHBoxLayout()
        row.addWidget(QLabel("Tam. (px):"))
        self._spin_ico = _spin(16, 256, 32)
        self._spin_ico.setSingleStep(16)
        row.addWidget(self._spin_ico)
        row.addStretch()
        ico_lay.addLayout(row)
        ico_lay.addLayout(_btn_h("Converter e salvar .ico", self._converter_ico))
        self._lbl_ico_status = _status()
        ico_lay.addWidget(self._lbl_ico_status)
        ico_lay.addStretch()
        grid.addWidget(ico_box, 1, 0)

        # ── ROW 1 col 1: Redimensionar ───────────────────────────────────────
        res_box = QGroupBox("Redimensionar")
        res_box.setStyleSheet(_gbox)
        res_lay = QFormLayout(res_box)
        self._spin_larg = _spin(1, 9999, 100)
        self._spin_alt  = _spin(1, 9999, 100)
        self._chk_prop  = QCheckBox("Manter proporção")
        self._chk_prop.setChecked(True)
        self._spin_larg.valueChanged.connect(self._ao_mudar_largura)
        res_lay.addRow("Largura (px):", self._spin_larg)
        res_lay.addRow("Altura (px):",  self._spin_alt)
        res_lay.addRow("", self._chk_prop)
        _btn_res = QPushButton("Redimensionar e salvar")
        _btn_res.setCursor(Qt.PointingHandCursor)
        _btn_res.clicked.connect(self._redimensionar)
        res_lay.addRow("", _btn_res)
        self._lbl_res_status = _status()
        res_lay.addRow("", self._lbl_res_status)
        grid.addWidget(res_box, 1, 1)

        # ── ROW 1 col 2: Converter formato ───────────────────────────────────
        fmt_box = QGroupBox("Converter formato")
        fmt_box.setStyleSheet(_gbox)
        fmt_lay = QVBoxLayout(fmt_box)
        row = QHBoxLayout()
        row.addWidget(QLabel("Formato:"))
        self._combo_fmt = QComboBox()
        self._combo_fmt.addItems(["PNG", "JPG", "BMP", "WebP", "GIF"])
        row.addWidget(self._combo_fmt)
        row.addStretch()
        fmt_lay.addLayout(row)
        fmt_lay.addLayout(_btn_h("Converter", self._converter_formato))
        self._lbl_fmt_status = _status()
        fmt_lay.addWidget(self._lbl_fmt_status)
        fmt_lay.addStretch()
        grid.addWidget(fmt_box, 1, 2)

        # ── ROW 2 col 0: Girar / Espelhar ────────────────────────────────────
        gir_box = QGroupBox("Girar / Espelhar")
        gir_box.setStyleSheet(_gbox)
        gir_lay = QVBoxLayout(gir_box)
        rot_lay = QHBoxLayout()
        b90 = QPushButton("↻ 90°")
        b90.setToolTip("Girar 90° horário")
        b90.setCursor(Qt.PointingHandCursor)
        b90.clicked.connect(lambda: self._girar(90))
        b180 = QPushButton("↻ 180°")
        b180.setCursor(Qt.PointingHandCursor)
        b180.clicked.connect(lambda: self._girar(180))
        b270 = QPushButton("↻ 270°")
        b270.setToolTip("Girar 270° (= 90° anti-horário)")
        b270.setCursor(Qt.PointingHandCursor)
        b270.clicked.connect(lambda: self._girar(270))
        rot_lay.addWidget(b90)
        rot_lay.addWidget(b180)
        rot_lay.addWidget(b270)
        gir_lay.addLayout(rot_lay)
        flip_lay = QHBoxLayout()
        bfh = QPushButton("↔ Espelhar H")
        bfh.setCursor(Qt.PointingHandCursor)
        bfh.clicked.connect(self._espelhar_h)
        bfv = QPushButton("↕ Espelhar V")
        bfv.setCursor(Qt.PointingHandCursor)
        bfv.clicked.connect(self._espelhar_v)
        flip_lay.addWidget(bfh)
        flip_lay.addWidget(bfv)
        gir_lay.addLayout(flip_lay)
        self._lbl_gir_status = _status()
        gir_lay.addWidget(self._lbl_gir_status)
        gir_lay.addStretch()
        grid.addWidget(gir_box, 2, 0)

        # ── ROW 2 col 1: Recortar bordas ─────────────────────────────────────
        crop_box = QGroupBox("Recortar (bordas px)")
        crop_box.setStyleSheet(_gbox)
        crop_lay = QFormLayout(crop_box)
        def _sp0():
            s = QSpinBox()
            s.setRange(0, 9999)
            s.setValue(0)

            return s

        self._crop_esq = _sp0()
        self._crop_top = _sp0()
        self._crop_dir = _sp0()
        self._crop_bot = _sp0()
        crop_lay.addRow("Esq:", self._crop_esq)
        crop_lay.addRow("Top:", self._crop_top)
        crop_lay.addRow("Dir:", self._crop_dir)
        crop_lay.addRow("Bot:", self._crop_bot)
        _btn_crop = QPushButton("Recortar e salvar")
        _btn_crop.setCursor(Qt.PointingHandCursor)
        _btn_crop.clicked.connect(self._recortar)
        crop_lay.addRow("", _btn_crop)
        self._lbl_crop_status = _status()
        crop_lay.addRow("", self._lbl_crop_status)
        grid.addWidget(crop_box, 2, 1)

        # ── ROW 2 col 2: Base64 ───────────────────────────────────────────────
        b64_box = QGroupBox("Base64")
        b64_box.setStyleSheet(_gbox)
        b64_lay = QVBoxLayout(b64_box)
        b64_lay.addWidget(QLabel("Copia data URI para clipboard\n(Python, HTML, CSS)"))
        b64_lay.addLayout(_btn_h("Copiar Base64", self._gerar_base64))
        self._lbl_b64_status = _status()
        b64_lay.addWidget(self._lbl_b64_status)
        b64_lay.addStretch()
        grid.addWidget(b64_box, 2, 2)

        # ── ROW 3 col 0: Escala de cinza ─────────────────────────────────────
        gray_box = QGroupBox("Escala de cinza")
        gray_box.setStyleSheet(_gbox)
        gray_lay = QVBoxLayout(gray_box)
        gray_lay.addWidget(QLabel("Gera variante _gray\n(ícone desativado)"))
        gray_lay.addLayout(_btn_h("Converter e salvar", self._escala_cinza))
        self._lbl_gray_status = _status()
        gray_lay.addWidget(self._lbl_gray_status)
        gray_lay.addStretch()
        grid.addWidget(gray_box, 3, 0)

        # ── ROW 3 col 1: Gerar QR Code ───────────────────────────────────────
        qr_box = QGroupBox("Gerar QR Code")
        qr_box.setStyleSheet(_gbox)
        qr_lay = QVBoxLayout(qr_box)
        self._campo_qr = QLineEdit()
        self._campo_qr.setPlaceholderText("URL, texto...")
        qr_lay.addWidget(self._campo_qr)
        qr_lay.addLayout(_btn_h("Gerar QR Code (PNG)", self._gerar_qr,
                                "pip install qrcode pillow"))
        self._lbl_qr_status = _status()
        qr_lay.addWidget(self._lbl_qr_status)
        qr_lay.addStretch()
        grid.addWidget(qr_box, 3, 1)

        # ── ROW 3 col 2: Upload nuvem ─────────────────────────────────────────
        up_box = QGroupBox("Upload (catbox.moe)")
        up_box.setStyleSheet(_gbox)
        up_lay = QVBoxLayout(up_box)
        up_lay.addWidget(QLabel("Grátis · sem cadastro\nCopia URL permanente"))
        up_lay.addLayout(_btn_h("Enviar e copiar URL", self._upload_nuvem))
        self._lbl_up_status = _status()
        up_lay.addWidget(self._lbl_up_status)
        up_lay.addStretch()
        grid.addWidget(up_box, 3, 2)

        # ── Diálogo de ajuda ─────────────────────────────────────────────────────

    def _mostrar_ajuda(self):
        t  = tema_global()
        bg = t.cor("editor.fundo", "#0a0a0a")
        tx = t.cor("editor.texto", "#e0e0e0")
        bd = t.cor("interface.borda", "#222")
        hl = t.cor("interface.fundo_item_hover", "#1e1e2e")
        dlg = QDialog(self)
        dlg.setWindowTitle("Ajuda — Ferramentas de Imagem")
        dlg.resize(520, 560)
        dlg.setStyleSheet(f"background: {bg}; color: {tx};")
        lay = QVBoxLayout(dlg)
        browser = QTextBrowser()
        browser.setStyleSheet(f"background: {bg}; color: {tx}; border: none;")
        browser.setHtml(
            f'<style>body{{color:{tx};background:{bg};font-size:13px;}}'
            f'code{{color:#98c379;background:#1a1a1a;padding:1px 4px;border-radius:3px;}}</style>'
            + _AJUDA_HTML
        )
        lay.addWidget(browser)
        btn_fechar = QPushButton("Fechar")
        btn_fechar.setStyleSheet(
            f"background: {hl}; color: {tx}; border: 1px solid {bd}; "
            f"border-radius: 3px; padding: 4px 20px;"
        )
        btn_fechar.clicked.connect(dlg.accept)
        lay.addWidget(btn_fechar, alignment=Qt.AlignRight)
        dlg.exec()

    # ── Slots de redimensionar ────────────────────────────────────────────────

    def _ao_mudar_largura(self, valor: int):
        if self._chk_prop.isChecked() and self._orig_w > 0:
            nova_alt = max(1, int(valor * self._orig_h / self._orig_w))
            self._spin_alt.blockSignals(True)
            self._spin_alt.setValue(nova_alt)
            self._spin_alt.blockSignals(False)

    # ── Helpers internos ──────────────────────────────────────────────────────

    def _pillow(self, label):
        """Retorna PIL.Image ou None (e abre popup _venv_hein_ se não instalado)."""
        try:
            from PIL import Image  # noqa

            return Image

        except ImportError:
            from _UTILITARIOS_.hein_venv_guard import exigir_pacote  # noqa: PLC0415
            exigir_pacote(
                "PIL",
                "Ferramentas de imagem",
                nome_pip="pillow==12.2.0",
                parent=self,
            )

            return None

    def _salvar_dialog(self, titulo, sugestao, filtro):
        # IMP-11: se a sugestao vier sem pasta, usa a ultima pasta usada aqui
        from PySide6.QtCore import QSettings
        _settings = QSettings("hein", "hein_IDE")
        if sugestao and not os.path.dirname(sugestao):
            _dir_inicial = _settings.value("ultima_pasta_visualizador_imagem", "")
            if _dir_inicial:
                sugestao = os.path.join(_dir_inicial, sugestao)
        destino, _ = QFileDialog.getSaveFileName(self, titulo, sugestao, filtro)
        if destino:
            _settings.setValue("ultima_pasta_visualizador_imagem", os.path.dirname(destino))

        return destino or None

    # ── Slots de ferramentas ─────────────────────────────────────────────────

    def _converter_ico(self):
        if not self.caminho or not os.path.isfile(self.caminho):

            return

        Image = self._pillow(self._lbl_ico_status)
        if not Image:

            return

        tam = self._spin_ico.value()
        dest = self._salvar_dialog(
            "Salvar como .ico",
            os.path.splitext(self.caminho)[0] + ".ico",
            "Ícone (*.ico)"
        )
        if not dest:

            return

        try:
            img = Image.open(self.caminho).convert("RGBA")
            img = img.resize((tam, tam), Image.LANCZOS)
            img.save(dest, format="ICO", sizes=[(tam, tam)])
            self._lbl_ico_status.setText(f"Salvo: {os.path.basename(dest)}")
            log.ok("visualizador_imagem.py", "_converter_ico", f".ico {tam}px → {dest}")
        except Exception as e:
            self._lbl_ico_status.setText(f"Erro: {e}")
            log.erro("visualizador_imagem.py", "_converter_ico", str(e))

    def _redimensionar(self):
        if not self.caminho or not os.path.isfile(self.caminho):

            return

        Image = self._pillow(self._lbl_res_status)
        if not Image:

            return

        w, h = self._spin_larg.value(), self._spin_alt.value()
        base, ext = os.path.splitext(self.caminho)
        dest = self._salvar_dialog(
            "Salvar redimensionada",
            f"{base}_{w}x{h}{ext}",
            f"Imagem (*{ext})"
        )
        if not dest:

            return

        try:
            img = Image.open(self.caminho).resize((w, h), Image.LANCZOS)
            img.save(dest)
            self._lbl_res_status.setText(f"Salvo: {os.path.basename(dest)}")
            log.ok("visualizador_imagem.py", "_redimensionar", f"{w}×{h} → {dest}")
        except Exception as e:
            self._lbl_res_status.setText(f"Erro: {e}")
            log.erro("visualizador_imagem.py", "_redimensionar", str(e))

    def _converter_formato(self):
        if not self.caminho or not os.path.isfile(self.caminho):

            return

        Image = self._pillow(self._lbl_fmt_status)
        if not Image:

            return

        fmt = self._combo_fmt.currentText()
        _ext_map = {"PNG": ".png", "JPG": ".jpg", "BMP": ".bmp", "WebP": ".webp", "GIF": ".gif"}
        ext  = _ext_map[fmt]
        base = os.path.splitext(self.caminho)[0]
        dest = self._salvar_dialog(
            f"Salvar como {fmt}", base + ext, f"{fmt} (*{ext})"
        )
        if not dest:

            return

        try:
            img = Image.open(self.caminho)
            if fmt == "JPG":
                img = img.convert("RGB")
            img.save(dest)
            self._lbl_fmt_status.setText(f"Salvo: {os.path.basename(dest)}")
            log.ok("visualizador_imagem.py", "_converter_formato", f"{fmt} → {dest}")
        except Exception as e:
            self._lbl_fmt_status.setText(f"Erro: {e}")
            log.erro("visualizador_imagem.py", "_converter_formato", str(e))

    def _girar(self, angulo: int):
        if not self.caminho or not os.path.isfile(self.caminho):

            return

        Image = self._pillow(self._lbl_gir_status)
        if not Image:

            return

        base, ext = os.path.splitext(self.caminho)
        dest = self._salvar_dialog(
            f"Salvar girada {angulo}°",
            f"{base}_rot{angulo}{ext}",
            f"Imagem (*{ext})"
        )
        if not dest:

            return

        try:
            img = Image.open(self.caminho).rotate(-angulo, expand=True)
            img.save(dest)
            self._lbl_gir_status.setText(f"Salvo: {os.path.basename(dest)}")
            log.ok("visualizador_imagem.py", "_girar", f"{angulo}° → {dest}")
        except Exception as e:
            self._lbl_gir_status.setText(f"Erro: {e}")
            log.erro("visualizador_imagem.py", "_girar", str(e))

    def _espelhar_h(self):
        self._espelhar("FLIP_LEFT_RIGHT", "flipH")

    def _espelhar_v(self):
        self._espelhar("FLIP_TOP_BOTTOM", "flipV")

    def _espelhar(self, modo: str, sufixo: str):
        if not self.caminho or not os.path.isfile(self.caminho):

            return

        Image = self._pillow(self._lbl_gir_status)
        if not Image:

            return

        base, ext = os.path.splitext(self.caminho)
        dest = self._salvar_dialog(
            "Salvar espelhada",
            f"{base}_{sufixo}{ext}",
            f"Imagem (*{ext})"
        )
        if not dest:

            return

        try:
            transpose_enum = getattr(
                getattr(Image, "Transpose", Image),
                modo
            )
            img = Image.open(self.caminho).transpose(transpose_enum)
            img.save(dest)
            self._lbl_gir_status.setText(f"Salvo: {os.path.basename(dest)}")
            log.ok("visualizador_imagem.py", "_espelhar", f"{modo} → {dest}")
        except Exception as e:
            self._lbl_gir_status.setText(f"Erro: {e}")
            log.erro("visualizador_imagem.py", "_espelhar", str(e))

    def _recortar(self):
        if not self.caminho or not os.path.isfile(self.caminho):

            return

        Image = self._pillow(self._lbl_crop_status)
        if not Image:

            return

        try:
            img  = Image.open(self.caminho)
            w, h = img.size
            esq  = self._crop_esq.value()
            top  = self._crop_top.value()
            dir_ = w - self._crop_dir.value()
            bot  = h - self._crop_bot.value()
            if esq >= dir_ or top >= bot:
                self._lbl_crop_status.setText("Valores de recorte inválidos.")

                return

            base, ext = os.path.splitext(self.caminho)
            dest = self._salvar_dialog(
                "Salvar recorte",
                base + "_crop" + ext,
                f"Imagem (*{ext})"
            )
            if not dest:

                return

            img.crop((esq, top, dir_, bot)).save(dest)
            self._lbl_crop_status.setText(f"Salvo: {os.path.basename(dest)}")
            log.ok("visualizador_imagem.py", "_recortar", f"recorte salvo em {dest}")
        except Exception as e:
            self._lbl_crop_status.setText(f"Erro: {e}")
            log.erro("visualizador_imagem.py", "_recortar", f"falha ao recortar: {e}")

    def _gerar_base64(self):
        if not self.caminho or not os.path.isfile(self.caminho):

            return

        try:
            with open(self.caminho, "rb") as f:
                dados = f.read()
            ext     = os.path.splitext(self.caminho)[1].lstrip(".").lower()
            b64     = base64.b64encode(dados).decode("ascii")
            data_uri = f"data:image/{ext};base64,{b64}"
            QApplication.clipboard().setText(data_uri)
            kb = len(b64) // 1024
            self._lbl_b64_status.setText(f"Copiado! ({kb} KB em Base64)")
            log.ok("visualizador_imagem.py", "_gerar_base64", f"Base64 copiado ({kb} KB)")
        except Exception as e:
            self._lbl_b64_status.setText(f"Erro: {e}")
            log.erro("visualizador_imagem.py", "_gerar_base64", str(e))

    def _escala_cinza(self):
        if not self.caminho or not os.path.isfile(self.caminho):

            return

        Image = self._pillow(self._lbl_gray_status)
        if not Image:

            return

        base, ext = os.path.splitext(self.caminho)
        dest = self._salvar_dialog(
            "Salvar em escala de cinza",
            base + "_gray" + ext,
            f"Imagem (*{ext})"
        )
        if not dest:

            return

        try:
            img = Image.open(self.caminho).convert("L")
            img.save(dest)
            self._lbl_gray_status.setText(f"Salvo: {os.path.basename(dest)}")
            log.ok("visualizador_imagem.py", "_escala_cinza", f"cinza → {dest}")
        except Exception as e:
            self._lbl_gray_status.setText(f"Erro: {e}")
            log.erro("visualizador_imagem.py", "_escala_cinza", str(e))

    def _gerar_qr(self):
        texto = self._campo_qr.text().strip()
        if not texto:
            self._lbl_qr_status.setText("Digite o conteúdo do QR Code.")

            return

        try:
            import qrcode  # noqa: F401
            import qrcode.constants
        except ImportError:
            self._lbl_qr_status.setText(
                "qrcode não instalado. Execute: pip install qrcode pillow"
            )

            return

        base = os.path.splitext(self.caminho)[0]
        dest = self._salvar_dialog(
            "Salvar QR Code",
            base + "_qr.png",
            "PNG (*.png)"
        )
        if not dest:

            return

        try:
            import qrcode as qrc
            qr = qrc.QRCode(
                error_correction=qrc.constants.ERROR_CORRECT_M,
                box_size=10,
                border=4,
            )
            qr.add_data(texto)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            img.save(dest)
            self._lbl_qr_status.setText(f"Salvo: {os.path.basename(dest)}")
            log.ok("visualizador_imagem.py", "_gerar_qr", f"QR → {dest}")
        except Exception as e:
            self._lbl_qr_status.setText(f"Erro: {e}")
            log.erro("visualizador_imagem.py", "_gerar_qr", str(e))

    def _upload_nuvem(self):
        if not self.caminho or not os.path.isfile(self.caminho):

            return

        if self._upload_thread and self._upload_thread.isRunning():
            self._lbl_up_status.setText("Upload em andamento, aguarde...")

            return

        self._lbl_up_status.setText("Enviando...")
        self._upload_thread = QThread()
        self._upload_worker = _UploadWorker(self.caminho)
        self._upload_worker.moveToThread(self._upload_thread)
        self._upload_thread.started.connect(self._upload_worker.rodar)
        self._upload_worker.concluido.connect(self._ao_upload_concluido)
        self._upload_worker.erro.connect(self._ao_upload_erro)
        self._upload_worker.concluido.connect(self._upload_thread.quit)
        self._upload_worker.erro.connect(self._upload_thread.quit)
        self._upload_thread.finished.connect(self._upload_worker.deleteLater)
        self._upload_thread.start()

    def _ao_upload_concluido(self, url: str):
        QApplication.clipboard().setText(url)
        self._lbl_up_status.setText(f"✓ URL copiada: {url}")
        log.ok("visualizador_imagem.py", "_upload_nuvem", f"upload ok: {url}")

    def _ao_upload_erro(self, msg: str):
        self._lbl_up_status.setText(f"Erro: {msg}")
        log.erro("visualizador_imagem.py", "_upload_nuvem", f"upload falhou: {msg}")
