# 📁 _APP_/painel_boas_vindas.py
"""
Tela de boas-vindas da hen IDE — painel inicial do Outdoor.
MODIFICADO: agora exibe nome do usuário e saudação dinâmica conforme hora.
"""
import json
import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame, QApplication,
)
from PySide6.QtCore import Qt, Signal, QUrl
from PySide6.QtGui import QDesktopServices, QMovie, QPixmap
from _CONFIGURA_ import PASTA_APPDATA, VERSAO_APP, TITULO_APP
from _CONFIGURA_.gerenciador_tema import tema_global
from _UTILITARIOS_.icones import icone_tema
_ARQUIVO_RECENTES = os.path.join(PASTA_APPDATA, "recentes.json")
_MAX_RECENTES = 8

def _carregar_recentes() -> list[str]:
    try:
        with open(_ARQUIVO_RECENTES, "r", encoding="utf-8") as f:
            dados = json.load(f)

        return [p for p in dados if os.path.isdir(p)][:_MAX_RECENTES]

    except Exception:
        return []

class PainelBoasVindas(QWidget):
    novo_projeto          = Signal()
    abrir_projeto_path    = Signal(str)
    abrir_projeto_dialogo = Signal()
    abrir_arquivo         = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._montar()

    # ⚠️  função grande (176 linhas)
    def _montar(self):
        _t = tema_global()
        self._cor_fundo  = _t.cor("interface.fundo",        "#0d1117")
        self._cor_card   = _t.cor("interface.fundo_painel", "#161b22")
        self._cor_texto  = _t.cor("interface.texto",        "#e6edf3")
        self._cor_fraco  = _t.cor("interface.texto_fraco",  "#8b949e")
        self._cor_verde  = _t.cor("interface.destaque",     "#4ec994")
        self._cor_borda  = _t.cor("interface.borda",        "#21262d")
        self._cor_hover  = _t.cor("interface.hover",        "#1c2128")

        self.setStyleSheet(f"background: {self._cor_fundo};")

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Banner de aviso: tema corrompido ─────────────────────────────────
        self._banner_tema = self._criar_banner_tema_corrompido()
        if self._banner_tema:
            root.addWidget(self._banner_tema)

        # ── cabeçalho ─────────────────────────────────────────────────
        header = QWidget()
        header.setFixedHeight(110)
        header.setStyleSheet(f"background: {self._cor_fundo};")
        h_lay = QVBoxLayout(header)
        h_lay.setContentsMargins(64, 26, 64, 0)
        h_lay.setSpacing(2)

        # linha: bandeira + "Sua IDE Python, em português"
        sub_widget = QWidget()
        sub_widget.setStyleSheet("background: transparent;")
        sub_lay = QHBoxLayout(sub_widget)
        sub_lay.setContentsMargins(0, 0, 0, 0)
        sub_lay.setSpacing(6)

        lbl_bandeira = QLabel()
        lbl_bandeira.setFixedSize(20, 14)
        lbl_bandeira.setScaledContents(True)
        lbl_bandeira.setStyleSheet("background: transparent;")
        pixmap_br = self._carregar_bandeira_brasil()
        if pixmap_br:
            lbl_bandeira.setPixmap(pixmap_br)
        sub_lay.addWidget(lbl_bandeira)

        lbl_sub = QLabel("Sua IDE Python, em português")
        lbl_sub.setStyleSheet(
            f"color: {self._cor_fraco}; font-size: 13px; background: transparent;"
        )
        sub_lay.addWidget(lbl_sub)
        sub_lay.addStretch()

        # saudação grande: "Boa tarde, Henrique"
        # DEPOIS



        # linha com "Boa tarde," + "Henrique" lado a lado
        saud_widget = QWidget()
        saud_widget.setStyleSheet("background: transparent;")
        saud_lay = QHBoxLayout(saud_widget)
        saud_lay.setContentsMargins(0, 0, 0, 0)
        saud_lay.setSpacing(10)
        saud_lay.setAlignment(Qt.AlignVCenter)


        saud_lay.addStretch()

        h_lay.addWidget(sub_widget)
        h_lay.addWidget(saud_widget)
        root.addWidget(header)

        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background: {self._cor_borda};")
        root.addWidget(sep)

        # ── corpo: recentes + iniciar ──────────────────────────────────
        corpo = QWidget()
        corpo.setStyleSheet(f"background: {self._cor_fundo};")
        corpo_lay = QHBoxLayout(corpo)
        corpo_lay.setContentsMargins(64, 40, 64, 40)
        corpo_lay.setSpacing(48)
        root.addWidget(corpo, 1)

        # coluna recentes
        col_rec = QWidget()
        col_rec.setStyleSheet("background: transparent;")
        lay_rec = QVBoxLayout(col_rec)
        lay_rec.setContentsMargins(0, 0, 0, 0)
        lay_rec.setSpacing(6)

        lbl_rec = QLabel("Recentes")
        lbl_rec.setStyleSheet(
            f"color: {self._cor_texto}; font-size: 13px;"
            f" font-weight: bold; background: transparent;"
        )
        lay_rec.addWidget(lbl_rec)

        self._container_recentes = QWidget()
        self._container_recentes.setStyleSheet("background: transparent;")
        self._lay_recentes = QVBoxLayout(self._container_recentes)
        self._lay_recentes.setContentsMargins(0, 0, 0, 0)
        self._lay_recentes.setSpacing(4)
        self._popular_recentes()

        lay_rec.addWidget(self._container_recentes)
        lay_rec.addStretch()
        corpo_lay.addWidget(col_rec, 3)

        # separador vertical
        vsep = QFrame()
        vsep.setFrameShape(QFrame.VLine)
        vsep.setFixedWidth(1)
        vsep.setStyleSheet(f"background: {self._cor_borda};")
        corpo_lay.addWidget(vsep)

        # coluna iniciar
        col_ini = QWidget()
        col_ini.setStyleSheet("background: transparent;")
        lay_ini = QVBoxLayout(col_ini)
        lay_ini.setContentsMargins(0, 0, 0, 0)
        lay_ini.setSpacing(6)

        lbl_ini = QLabel("Iniciar")
        lbl_ini.setStyleSheet(
            f"color: {self._cor_texto}; font-size: 13px;"
            f" font-weight: bold; background: transparent;"
        )
        lay_ini.addWidget(lbl_ini)

        for label, nome_icone, sinal in [
            ("  Novo Projeto",   "mdi.plus",                  self.novo_projeto),
            ("  Abrir Projeto",  "mdi.folder-open-outline",   self.abrir_projeto_dialogo),
            ("  Abrir Arquivo",  "mdi.file-document-outline", self.abrir_arquivo),
        ]:
            btn = self._btn_acao(label)
            btn.setIcon(icone_tema(nome_icone))
            btn.clicked.connect(sinal.emit)
            lay_ini.addWidget(btn)

        lay_ini.addStretch()
        corpo_lay.addWidget(col_ini, 2)

        # ── card de apoio ───────────────────────────
        card_apoio = self._criar_card_apoio()
        root.addWidget(card_apoio)

        # ── rodapé ────────────────────────────────────────────────────
        sep2 = QFrame()
        sep2.setFixedHeight(1)
        sep2.setStyleSheet(f"background: {self._cor_borda};")
        root.addWidget(sep2)

        rodape = QLabel(f"{VERSAO_APP}  ·  Python + PySide6  ·  por HenriqLs")
        rodape.setAlignment(Qt.AlignCenter)
        rodape.setFixedHeight(30)
        rodape.setStyleSheet(
            f"color: {self._cor_fraco}; font-size: 10px; background: {self._cor_fundo};"
        )
        root.addWidget(rodape)

    # ── Banner de tema corrompido ─────────────────────────────────────────────

    # ⚠️  função grande (72 linhas)
    def _criar_banner_tema_corrompido(self):
        """
        Retorna um QFrame laranja com aviso se thema.json está corrompido.
        Retorna None se o tema carregou normalmente.

        Exibido no topo do Outdoor para que o usuário veja imediatamente ao
        abrir a IDE — mesmo sem projeto carregado.
        Inclui botão 'Restaurar backup' para recuperar o último estado válido.
        """
        from _CONFIGURA_.gerenciador_tema import tema_global as _tg
        from _CONFIGURA_ import ARQUIVO_TEMA
        import os as _os
        _t = _tg()
        erro = getattr(_t, "_erro_json", "")
        if not erro:
            return None

        banner = QFrame()
        banner.setObjectName("bannerTemaCorrempido")
        banner.setStyleSheet("""
            QFrame#bannerTemaCorrempido {
                background: #3d1f00;
                border-bottom: 2px solid #c0392b;
            }
            QLabel { color: #ffd080; background: transparent; }
            QPushButton {
                background: #c0392b; color: #fff;
                border: none; border-radius: 3px;
                padding: 3px 10px; font-size: 11px;
            }
            QPushButton:hover { background: #e74c3c; }
            QPushButton#btnDispensa {
                background: transparent; color: #ffd080;
                border: 1px solid #ffd080; font-size: 10px;
                padding: 2px 8px;
            }
            QPushButton#btnDispensa:hover { background: #4d2800; }
        """)

        lay = QHBoxLayout(banner)
        lay.setContentsMargins(16, 6, 12, 6)
        lay.setSpacing(10)

        # DEPOIS
        ico = QLabel()
        ico.setPixmap(icone_tema("mdi.alert", color="#ffd080").pixmap(18, 18))
        lay.addWidget(ico)

        msg_curta = erro[:120] + ("…" if len(erro) > 120 else "")
        lbl = QLabel(
            f"<b>thema.json corrompido</b> — IDE usando tema de fallback.  "
            f"<span style='font-size:10px; color:#ffaa44;'>{msg_curta}</span>"
        )
        lbl.setWordWrap(True)
        lay.addWidget(lbl, 1)

        caminho_bak = ARQUIVO_TEMA + ".bak"
        if _os.path.isfile(caminho_bak):
            btn_restaurar = QPushButton("Restaurar backup")
            btn_restaurar.setToolTip(f"Copia {caminho_bak} → thema.json e recarrega o tema")
            btn_restaurar.clicked.connect(
                lambda: self._restaurar_backup_tema(caminho_bak, banner)
            )
            lay.addWidget(btn_restaurar)

        btn_dispensar = QPushButton("Dispensar")
        btn_dispensar.setObjectName("btnDispensa")
        btn_dispensar.clicked.connect(banner.hide)
        lay.addWidget(btn_dispensar)

        return banner

    def _restaurar_backup_tema(self, caminho_bak: str, banner: QFrame) -> None:
        """Copia thema.json.bak → thema.json e recarrega o tema."""
        from _CONFIGURA_ import ARQUIVO_TEMA
        from _CONFIGURA_.gerenciador_tema import tema_global as _tg
        import shutil as _sh
        try:
            _sh.copy2(caminho_bak, ARQUIVO_TEMA)
            _t = _tg()
            if _t.carregar():
                _t._erro_json = ""
                banner.hide()
                # Força reaplicação do tema na janela principal
                janela = self.window()
                if janela and hasattr(_t, "aplicar_na_janela"):
                    _t.aplicar_na_janela(janela)
        except Exception as e:
            from _LOG_.log import log
            log.erro("painel_boas_vindas.py", "_restaurar_backup_tema", str(e))

    def _criar_card_apoio(self) -> QWidget:
        """
        Faixa de apoio — altura natural ~96 px.
        [GIF 54px] | [titulo 13px + linha de acoes 12px] | [QR Pix 58px  QR WhatsApp 58px]
        """
        import os as _os
        _util    = _os.path.join(_os.path.dirname(_os.path.dirname(__file__)), "_UTILITARIOS_")
        _gif     = _os.path.join(_util, "smola.gif")
        _qrpix   = _os.path.join(_util, "qrcodePix.jpg")
        _qrwhats = _os.path.join(_util, "qrWhats.png")

        frame = QFrame()
        frame.setStyleSheet(
            f"QFrame {{ background: {self._cor_card};"
            f" border-top: 2px solid {self._cor_verde}; }}"
        )
        lay = QHBoxLayout(frame)
        lay.setContentsMargins(48, 14, 48, 14)
        lay.setSpacing(20)

        # GIF
        lbl_gif = QLabel()
        lbl_gif.setFixedSize(100, 100)
        lbl_gif.setAlignment(Qt.AlignCenter)
        lbl_gif.setStyleSheet("background: transparent;")
        if _os.path.isfile(_gif):
            self._movie_apoio = QMovie(_gif)
            self._movie_apoio.setScaledSize(lbl_gif.size())
            lbl_gif.setMovie(self._movie_apoio)
            self._movie_apoio.start()
        lay.addWidget(lbl_gif)

        # coluna central
        col = QWidget()
        col.setStyleSheet("background: transparent;")
        lay_col = QVBoxLayout(col)
        lay_col.setContentsMargins(0, 0, 0, 0)
        lay_col.setSpacing(8)
        lay_col.setAlignment(Qt.AlignVCenter)

        lbl_titulo = QLabel("Gostou da hen IDE? Considere apoiar \U0001f90d")
        lbl_titulo.setStyleSheet(
            f"color: {self._cor_texto}; font-size: 13px;"
            f" font-weight: bold; background: transparent;"
        )
        lay_col.addWidget(lbl_titulo)

        # linha de acoes
        acoes = QWidget()
        acoes.setStyleSheet("background: transparent;")
        lay_ac = QHBoxLayout(acoes)
        lay_ac.setContentsMargins(0, 0, 0, 0)
        lay_ac.setSpacing(12)

        lbl_pix = QLabel(
            f"<span style='color:{self._cor_verde}; font-size:12px;'>"
            f"<b>Pix</b> 008.064.101-67</span>"
        )
        lbl_pix.setStyleSheet("background: transparent;")
        lay_ac.addWidget(lbl_pix)

        btn_cp = QPushButton("Copiar")
        btn_cp.setCursor(Qt.PointingHandCursor)
        btn_cp.setFixedHeight(24)
        btn_cp.setStyleSheet(
            f"QPushButton {{ background: {self._cor_verde}; color: #0d1117;"
            f" border: none; border-radius: 4px;"
            f" padding: 0 12px; font-size: 11px; font-weight: bold; }}"
            f"QPushButton:hover {{ background: #6ee7b7; }}"
        )
        btn_cp.clicked.connect(lambda: QApplication.clipboard().setText("008.064.101-67"))
        lay_ac.addWidget(btn_cp)

        sep1 = QLabel("\u00b7")
        sep1.setStyleSheet(f"color:{self._cor_fraco}; background:transparent; font-size:12px;")
        lay_ac.addWidget(sep1)

        btn_pp = QPushButton("PayPal")
        btn_pp.setCursor(Qt.PointingHandCursor)
        btn_pp.setFixedHeight(24)
        btn_pp.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {self._cor_fraco};"
            f" border: 1px solid {self._cor_borda}; border-radius: 4px;"
            f" padding: 0 10px; font-size: 11px; }}"
            f"QPushButton:hover {{ border-color: {self._cor_texto}; color: {self._cor_texto}; }}"
        )
        btn_pp.clicked.connect(lambda: QDesktopServices.openUrl(
            QUrl("https://www.paypal.com/paypalme/henriqueliandro")))
        lay_ac.addWidget(btn_pp)

        sep2 = QLabel("\u00b7")
        sep2.setStyleSheet(f"color:{self._cor_fraco}; background:transparent; font-size:12px;")
        lay_ac.addWidget(sep2)

        btn_ig = QPushButton("\U0001f4f7  @hls_rustico")
        btn_ig.setCursor(Qt.PointingHandCursor)
        btn_ig.setFixedHeight(24)
        btn_ig.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {self._cor_fraco};"
            f" border: none; font-size: 11px; padding: 0 4px; }}"
            f"QPushButton:hover {{ color: {self._cor_texto}; }}"
        )
        btn_ig.clicked.connect(lambda: QDesktopServices.openUrl(
            QUrl("https://www.instagram.com/hls_rustico")))
        lay_ac.addWidget(btn_ig)

        btn_yt = QPushButton("\U0001f3ac  @henriqls")
        btn_yt.setCursor(Qt.PointingHandCursor)
        btn_yt.setFixedHeight(24)
        btn_yt.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {self._cor_fraco};"
            f" border: none; font-size: 11px; padding: 0 4px; }}"
            f"QPushButton:hover {{ color: {self._cor_texto}; }}"
        )
        btn_yt.clicked.connect(lambda: QDesktopServices.openUrl(
            QUrl("https://www.youtube.com/@henriqls")))
        lay_ac.addWidget(btn_yt)

        lay_ac.addStretch()
        lay_col.addWidget(acoes)
        lay.addWidget(col, 1)

        # QR Codes lado a lado
        def _qr(path, cap):
            cw = QWidget(); cw.setStyleSheet("background: transparent;")
            cv = QVBoxLayout(cw); cv.setContentsMargins(0,0,0,0); cv.setSpacing(3)
            cv.setAlignment(Qt.AlignVCenter | Qt.AlignHCenter)
            lbl = QLabel(); lbl.setFixedSize(100, 100)
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setToolTip(cap)
            lbl.setStyleSheet(
                "background: white; border-radius: 4px;"
                f" border: 1px solid {self._cor_borda};"
            )
            if _os.path.isfile(path):
                px = QPixmap(path).scaled(96, 96, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                lbl.setPixmap(px)
            else:
                lbl.setText("QR")
                lbl.setStyleSheet(f"color:{self._cor_fraco}; font-size:9px; background:{self._cor_card};")
            lcap = QLabel(cap); lcap.setAlignment(Qt.AlignCenter)
            lcap.setStyleSheet(f"color:{self._cor_fraco}; font-size:9px; background:transparent;")
            cv.addWidget(lbl); cv.addWidget(lcap)
            return cw

        col_qr = QWidget(); col_qr.setStyleSheet("background: transparent;")
        lay_qr = QHBoxLayout(col_qr)
        lay_qr.setContentsMargins(0,0,0,0); lay_qr.setSpacing(10)
        lay_qr.setAlignment(Qt.AlignVCenter)
        lay_qr.addWidget(_qr(_qrpix,   "Pix"))
        lay_qr.addWidget(_qr(_qrwhats, "WhatsApp"))
        lay.addWidget(col_qr)

        return frame
    def _btn_acao(self, texto: str) -> QPushButton:
        btn = QPushButton(texto)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setStyleSheet(f"""
            QPushButton {{
                text-align: left;
                color: {self._cor_texto};
                background: {self._cor_card};
                border: 1px solid {self._cor_borda};
                border-radius: 5px;
                padding: 10px 14px;
                font-size: 12px;
                min-width: 200px;
            }}
            QPushButton:hover {{
                background: {self._cor_hover};
                border-color: {self._cor_verde};
                color: {self._cor_verde};
            }}
        """)

        return btn

    def _popular_recentes(self):
        while self._lay_recentes.count():
            item = self._lay_recentes.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        recentes = _carregar_recentes()
        if recentes:
            for caminho in recentes:
                nome = os.path.basename(caminho)
                # DEPOIS
                btn = QPushButton(f"  {nome}")
                # DEPOIS
                btn.setIcon(icone_tema("mdi.source-repository"))
                btn.setToolTip(caminho)
                btn.setCursor(Qt.PointingHandCursor)
                btn.setStyleSheet(f"""
                    QPushButton {{
                        text-align: left;
                        color: {self._cor_texto};
                        background: {self._cor_card};
                        border: 1px solid {self._cor_borda};
                        border-radius: 5px;
                        padding: 8px 12px;
                        font-size: 12px;
                    }}
                    QPushButton:hover {{
                        background: {self._cor_hover};
                        border-color: {self._cor_verde};
                        color: {self._cor_verde};
                    }}
                """)
                btn.clicked.connect(
                    lambda checked, p=caminho: self.abrir_projeto_path.emit(p)
                )
                self._lay_recentes.addWidget(btn)
        else:
            lbl = QLabel("Nenhum projeto recente.")
            lbl.setStyleSheet(
                f"color: {self._cor_fraco}; font-size: 12px; background: transparent;"
            )
            self._lay_recentes.addWidget(lbl)

    def atualizar_recentes(self):
        """Recarrega a lista de projetos recentes sem recriar o widget inteiro."""
        self._popular_recentes()

    def _carregar_bandeira_brasil(self):
        """Bandeira do Brasil em SVG embutido — sem internet, funciona na roça."""
        from PySide6.QtSvg import QSvgRenderer
        from PySide6.QtGui import QPixmap, QPainter
        from PySide6.QtCore import QByteArray
        svg = b"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 14">
            <rect width="20" height="14" fill="#009c3b"/>
            <polygon points="10,1 19,7 10,13 1,7" fill="#ffdf00"/>
            <circle cx="10" cy="7" r="3.2" fill="#002776"/>
            <line x1="6.8" y1="7" x2="13.2" y2="7"
                stroke="#fff" stroke-width="0.9" opacity="0.6"/>
        </svg>"""

        try:
            renderer = QSvgRenderer(QByteArray(svg))
            px = QPixmap(20, 14)
            px.fill(Qt.transparent)
            painter = QPainter(px)
            renderer.render(painter)
            painter.end()

            return px

        except Exception as e:
            from _LOG_.log import log
            log.erro("painel_boas_vindas.py", "[bandeira] Erro svg::",f" {e}")

            return None
