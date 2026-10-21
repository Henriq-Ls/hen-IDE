# 📁 _APP_/janela_primeiro_acesso.py

import os
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QFileDialog, QFrame, QApplication
)
from PySide6.QtCore import Qt
from _CONFIGURA_.gerenciador_tema import tema_global
from _CONFIGURA_.gerenciador_perfil import (
    salvar_perfil, salvar_caminho_projetos, obter_caminho_projetos
)
from _CONFIGURA_.gerenciador_licenca import obter_hwid, gerar_chave_licenca
from _UTILITARIOS_.icones import icone_tema

class JanelaPrimeiroAcesso(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Bem-vindo — hein IDE")
        self.setFixedSize(480, 560)
        self.setWindowFlags(Qt.Window | Qt.CustomizeWindowHint | Qt.WindowTitleHint)

        _t = tema_global()
        self._cor_fundo   = _t.cor("interface.fundo",        "#0d1117")
        self._cor_card    = _t.cor("interface.fundo_painel", "#161b22")
        self._cor_texto   = _t.cor("interface.texto",        "#e6edf3")
        self._cor_fraco   = _t.cor("interface.texto_fraco",  "#8b949e")
        self._cor_verde   = _t.cor("interface.destaque",     "#4ec994")
        self._cor_borda   = _t.cor("interface.borda",        "#21262d")
        self._cor_erro    = "#f85149"

        self._hwid_maquina = obter_hwid()
        self._montar_layout()

    def _montar_layout(self):
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {self._cor_fundo};
                border: 1px solid {self._cor_borda};
            }}
            QLabel {{
                color: {self._cor_texto};
                font-family: 'Segoe UI', sans-serif;
                background: transparent;
            }}
            QLineEdit {{
                background-color: {self._cor_card};
                border: 1px solid {self._cor_borda};
                border-radius: 6px;
                padding: 8px 12px;
                color: {self._cor_texto};
                font-size: 13px;
            }}
            QLineEdit:focus {{
                border-color: {self._cor_verde};
            }}
            QPushButton {{
                font-weight: bold;
                font-size: 13px;
                border-radius: 6px;
                padding: 10px 16px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(12)

        # ── Cabeçalho ──────────────────────────────────────────────────────
        lbl_boas_vindas = QLabel("Bem-vindo à hein IDE! 👋")
        lbl_boas_vindas.setStyleSheet(f"color: {self._cor_verde}; font-size: 20px; font-weight: bold;")
        layout.addWidget(lbl_boas_vindas)

        lbl_sub = QLabel("A hein IDE está em fase gratuita — só precisamos de alguns dados pra personalizar sua experiência.")
        lbl_sub.setStyleSheet(f"color: {self._cor_fraco}; font-size: 11px;")
        lbl_sub.setWordWrap(True)
        layout.addWidget(lbl_sub)

        linha = QFrame()
        linha.setFixedHeight(1)
        linha.setStyleSheet(f"background-color: {self._cor_borda};")
        layout.addWidget(linha)

        # ── Campo: Nome e Email (Essencial para a licença) ────────────────
        layout.addWidget(QLabel("Como quer ser chamado? *"))
        self.input_nome = QLineEdit()
        self.input_nome.setPlaceholderText("Ex: Henrique")
        layout.addWidget(self.input_nome)

        layout.addWidget(QLabel("Seu e-mail de compra/cadastro: *"))
        self.input_email = QLineEdit()
        self.input_email.setPlaceholderText("Ex: contato@exemplo.com")
        layout.addWidget(self.input_email)

        # ── Campo: Pasta de Projetos ──────────────────────────────────────
        layout.addWidget(QLabel("Local padrão para salvar seus códigos:"))
        layout_caminho = QHBoxLayout()
        layout_caminho.setSpacing(8)

        self.input_caminho = QLineEdit()
        self.input_caminho.setText(obter_caminho_projetos())
        layout_caminho.addWidget(self.input_caminho)

        btn_procurar = QPushButton()
        btn_procurar.setCursor(Qt.PointingHandCursor)
        btn_procurar.setFixedSize(36, 36)
        btn_procurar.setIcon(icone_tema("mdi.folder-open-outline"))
        btn_procurar.setStyleSheet(f"""
            QPushButton {{
                background-color: {self._cor_card};
                border: 1px solid {self._cor_borda};
                color: {self._cor_texto};
            }}
            QPushButton:hover {{
                border-color: {self._cor_verde};
            }}
        """)
        btn_procurar.clicked.connect(self._selecionar_pasta)
        layout_caminho.addWidget(btn_procurar)
        layout.addLayout(layout_caminho)

        # ── Bloco: Identificador da Máquina (HWID) — usado no futuro p/ licenciamento ──
        layout.addWidget(QLabel("Identificador do seu computador (HWID):"))
        layout_hwid = QHBoxLayout()
        layout_hwid.setSpacing(8)

        self.input_hwid = QLineEdit()
        self.input_hwid.setText(self._hwid_maquina)
        self.input_hwid.setReadOnly(True)
        self.input_hwid.setStyleSheet(f"background-color: #0d1117; color: {self._cor_fraco}; font-size: 11px;")
        layout_hwid.addWidget(self.input_hwid)

        btn_copiar = QPushButton("Copiar")
        btn_copiar.setCursor(Qt.PointingHandCursor)
        btn_copiar.setStyleSheet(f"""
            QPushButton {{
                background-color: {self._cor_card};
                border: 1px solid {self._cor_borda};
                color: {self._cor_texto};
                font-size: 11px;
                padding: 6px 12px;
            }}
            QPushButton:hover {{
                border-color: {self._cor_verde};
            }}
        """)
        btn_copiar.clicked.connect(self._copiar_hwid)
        layout_hwid.addWidget(btn_copiar)
        layout.addLayout(layout_hwid)

        # Aviso de Erros
        self.lbl_erro = QLabel("")
        self.lbl_erro.setStyleSheet(f"color: {self._cor_erro}; font-size: 11px; font-weight: bold;")
        self.lbl_erro.setWordWrap(True)
        layout.addWidget(self.lbl_erro)

        layout.addStretch()

        # ── Botão Ativar ──────────────────────────────────────────────────
        self.btn_comecar = QPushButton("Começar a usar 🚀")
        self.btn_comecar.setCursor(Qt.PointingHandCursor)
        self.btn_comecar.setStyleSheet(f"""
            QPushButton {{
                background-color: {self._cor_verde};
                color: {self._cor_fundo};
                border: none;
                font-size: 14px;
                padding: 12px;
            }}
            QPushButton:hover {{
                background-color: #3cb080;
            }}
        """)
        self.btn_comecar.clicked.connect(self._validar_e_salvar)
        layout.addWidget(self.btn_comecar)

    def _copiar_hwid(self):
        QApplication.clipboard().setText(self._hwid_maquina)
        self.lbl_erro.setStyleSheet(f"color: {self._cor_verde}; font-size: 11px;")
        self.lbl_erro.setText("✓ ID do Computador copiado para a Área de Transferência!")

    def _selecionar_pasta(self):
        diretorio_atual = self.input_caminho.text() or os.path.expanduser("~")
        diretorio = QFileDialog.getExistingDirectory(self, "Selecione a Pasta de Projetos", diretorio_atual)
        if diretorio:
            self.input_caminho.setText(os.path.normpath(diretorio))

    def _validar_e_salvar(self):
        # Restaura cor de erro por padrão
        self.lbl_erro.setStyleSheet(f"color: {self._cor_erro}; font-size: 11px; font-weight: bold;")

        nome = self.input_nome.text().strip()
        email = self.input_email.text().strip()
        caminho = self.input_caminho.text().strip()

        if not nome or nome.lower() == "usuário":
            self.lbl_erro.setText("⚠️ Por favor, insira o seu nome de usuário.")
            return
        if not email or "@" not in email:
            self.lbl_erro.setText("⚠️ Por favor, insira um endereço de e-mail válido.")
            return

        try:
            os.makedirs(caminho, exist_ok=True)
        except Exception as e:
            self.lbl_erro.setText(f"⚠️ Erro ao criar pasta de projetos: {str(e)}")
            return

        # 🔑 Fase gratuita: gera a chave localmente (mesma fórmula de gerenciador_licenca)
        # em vez de exigir compra. Quando cobrar de verdade, troque isso por uma
        # chave emitida por você/servidor e volte a validar antes de aceitar.
        chave = gerar_chave_licenca(self._hwid_maquina, email)

        # 💾 Grava perfil + pasta de projetos
        ok_perfil  = salvar_perfil(nome, email, chave)
        ok_caminho = salvar_caminho_projetos(caminho)

        if ok_perfil and ok_caminho:
            self.accept()
        else:
            self.lbl_erro.setText("⚠️ Falha crítica ao salvar as configurações.")
