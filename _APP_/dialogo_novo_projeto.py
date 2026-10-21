# 📁 _APP_/dialogo_novo_projeto.py
"""
Painel de criação de novo projeto da hen IDE.
Abre no TabWidget como aba especial — não é QDialog flutuante. 
"""

import os
from PySide6.QtCore import Qt, Signal, QTimer, QSettings
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFileDialog,
    QFrame, QScrollArea, QMessageBox, QComboBox,
    QTextEdit,
)

from _CONFIGURA_ import (
    PASTA_PROJETOS,
    CINZA_ESCURO,
    BRANCO,
    VERDE,
    VERDE_AZULADO,
    VERDE_PETROLEO,
    COR_CINZA_TEXTO,
    COR_SUCESSO,
    COR_SEPARADOR,
    FONTE_UI,
    FONTE_UI_FALLBACK,
    BORDA_GERAL,
    PRETO_FOSCO,
)
from _CONFIGURA_.gerenciador_tema import tema_global
from _CONFIGURA_.gerenciador_templates import carregar as _carregar_templates, salvar as _salvar_templates
# ──────────────────────────────────────────────────────────────────────────────
# Widget de uma linha de template
# ──────────────────────────────────────────────────────────────────────────────

class _LinhaTemplate(QWidget):
    """
    Uma linha expansível de template de arquivo.
    Linha compacta com nome + extensão + botão remover.
    Clica em "▼ conteúdo" para expandir e editar o conteúdo inicial.
    """
    removido = Signal(object)

    _EXTENSOES = [".py", ".json", ".md", ".txt", ".html", ".css",
                  ".js", ".ts", ".yaml", ".toml", ".sql", ".sh",
                  ".bat", ".xml", ".csv", "(sem extensão)"]

    # ⚠️  função grande (77 linhas)
    # 💡 ext_opc = Literal[".py"] ← defina os valores válidos
    def __init__(self, nome: str = "", ext: str = ".py", conteudo: str = "", parent=None):
        super().__init__(parent)
        self._expandido = False

        lay_externo = QVBoxLayout(self)
        lay_externo.setContentsMargins(0, 2, 0, 2)
        lay_externo.setSpacing(2)

        # ── Linha superior: nome | ext | ▼ | ✕ ──────────────────────────────
        linha_topo = QWidget()
        lay_topo = QHBoxLayout(linha_topo)
        lay_topo.setContentsMargins(0, 0, 0, 0)
        lay_topo.setSpacing(6)

        self._campo = QLineEdit()
        self._campo.setPlaceholderText("nome do arquivo")
        self._campo.setFixedHeight(28)
        if nome:
            self._campo.setText(nome)

        self._combo = QComboBox()
        self._combo.setFixedHeight(28)
        self._combo.setFixedWidth(110)
        for e in self._EXTENSOES:
            self._combo.addItem(e)
        if ext in self._EXTENSOES:
            self._combo.setCurrentText(ext)
        # Atualiza placeholder do conteúdo quando a extensão muda
        self._combo.currentTextChanged.connect(self._ao_mudar_extensao)

        self._btn_expandir = QPushButton("▼ conteúdo")
        self._btn_expandir.setFixedHeight(24)
        self._btn_expandir.setCursor(Qt.PointingHandCursor)
        self._btn_expandir.setToolTip("Editar conteúdo inicial do arquivo")
        self._btn_expandir.setStyleSheet(
            "QPushButton { background: transparent; border: none; font-size: 10px; }"
            "QPushButton:hover { text-decoration: underline; }"
        )
        self._btn_expandir.clicked.connect(self._toggle_conteudo)

        btn_rem = QPushButton("✕")
        btn_rem.setFixedSize(24, 24)
        btn_rem.setCursor(Qt.PointingHandCursor)
        btn_rem.setToolTip("Remover este arquivo do template")
        btn_rem.setStyleSheet(
            "QPushButton { background: transparent; border: none; }"
            "QPushButton:hover { color: #e05252; }"
        )
        btn_rem.clicked.connect(lambda: self.removido.emit(self))

        lay_topo.addWidget(self._campo, 1)
        lay_topo.addWidget(self._combo)
        lay_topo.addWidget(self._btn_expandir)
        lay_topo.addWidget(btn_rem)
        lay_externo.addWidget(linha_topo)

        # ── Área de conteúdo (oculta por padrão) ─────────────────────────────
        self._area_conteudo = QWidget()
        lay_conteudo = QVBoxLayout(self._area_conteudo)
        lay_conteudo.setContentsMargins(0, 0, 0, 4)
        lay_conteudo.setSpacing(2)

        lbl = QLabel("Conteúdo inicial do arquivo:")
        lbl.setStyleSheet("font-size: 10px; color: #888;")
        lay_conteudo.addWidget(lbl)

        self._editor = QTextEdit()
        self._editor.setFixedHeight(120)
        self._editor.setPlaceholderText(self._placeholder_para_ext(ext))
        self._editor.setLineWrapMode(QTextEdit.NoWrap)
        self._editor.setStyleSheet("font-family: monospace; font-size: 11px;")
        if conteudo:
            self._editor.setPlainText(conteudo)
        lay_conteudo.addWidget(self._editor)

        self._area_conteudo.setVisible(False)
        lay_externo.addWidget(self._area_conteudo)

    # ── helpers ───────────────────────────────────────────────────────────────

    def _placeholder_para_ext(self, ext: str) -> str:
        placeholders = {
            ".py":   "# código Python inicial...\n\ndef main():\n    pass",
            ".json": '{\n  "chave": "valor"\n}',
            ".md":   "# Título\n\nDescrição do projeto...",
            ".html": "<!DOCTYPE html>\n<html>\n<body>\n</body>\n</html>",
            ".yaml": "chave: valor",
            ".toml": '[projeto]\nnome = "meu_projeto"',
            ".sh":   "#!/bin/bash\nset -e",
            ".bat":  "@echo off",
        }

        return placeholders.get(ext, "Conteúdo inicial do arquivo...")

    def _ao_mudar_extensao(self, ext: str):
        self._editor.setPlaceholderText(self._placeholder_para_ext(ext))

    def _toggle_conteudo(self):
        self._expandido = not self._expandido
        self._area_conteudo.setVisible(self._expandido)
        self._btn_expandir.setText("▲ conteúdo" if self._expandido else "▼ conteúdo")

    # ── dado público ──────────────────────────────────────────────────────────

    def dados(self) -> dict:
        nome = self._campo.text().strip()
        ext  = self._combo.currentText()
        if ext == "(sem extensão)":
            ext = ""
        conteudo = self._editor.toPlainText()

        return {"tipo": "arquivo", "nome": nome, "ext": ext, "conteudo": conteudo}

# ──────────────────────────────────────────────────────────────────────────────
# Widget de pasta (agrupa arquivos filhos)
# ──────────────────────────────────────────────────────────────────────────────

class _LinhaPasta(QWidget):
    """
    Uma entrada de pasta no template.
    Mostra nome da pasta + lista expansível de arquivos filhos.
    """
    removido = Signal(object)

    def __init__(self, nome: str = "", filhos: list | None = None, parent=None):
        super().__init__(parent)
        self._expandido = True
        self._filhos: list[_LinhaTemplate] = []

        lay_externo = QVBoxLayout(self)
        lay_externo.setContentsMargins(0, 4, 0, 4)
        lay_externo.setSpacing(2)

        # ── Cabeçalho da pasta ────────────────────────────────────────────────
        linha_topo = QWidget()
        lay_topo = QHBoxLayout(linha_topo)
        lay_topo.setContentsMargins(0, 0, 0, 0)
        lay_topo.setSpacing(6)

        lbl_icone = QLabel("📁")
        lbl_icone.setFixedWidth(20)
        lbl_icone.setStyleSheet("background: transparent;")
        lay_topo.addWidget(lbl_icone)

        self._campo = QLineEdit()
        self._campo.setPlaceholderText("nome da pasta")
        self._campo.setFixedHeight(28)
        if nome:
            self._campo.setText(nome)

        self._btn_expandir = QPushButton("▲ arquivos")
        self._btn_expandir.setFixedHeight(24)
        self._btn_expandir.setCursor(Qt.PointingHandCursor)
        self._btn_expandir.setToolTip("Mostrar/ocultar arquivos desta pasta")
        self._btn_expandir.setStyleSheet(
            "QPushButton { background: transparent; border: none; font-size: 10px; }"
            "QPushButton:hover { text-decoration: underline; }"
        )
        self._btn_expandir.clicked.connect(self._toggle)

        btn_rem = QPushButton("✕")
        btn_rem.setFixedSize(24, 24)
        btn_rem.setCursor(Qt.PointingHandCursor)
        btn_rem.setToolTip("Remover esta pasta do template")
        btn_rem.setStyleSheet(
            "QPushButton { background: transparent; border: none; }"
            "QPushButton:hover { color: #e05252; }"
        )
        btn_rem.clicked.connect(lambda: self.removido.emit(self))

        lay_topo.addWidget(self._campo, 1)
        lay_topo.addWidget(self._btn_expandir)
        lay_topo.addWidget(btn_rem)
        lay_externo.addWidget(linha_topo)

        # ── Área interior (arquivos filhos) ───────────────────────────────────
        self._area_filhos = QWidget()
        self._lay_filhos = QVBoxLayout(self._area_filhos)
        self._lay_filhos.setContentsMargins(24, 4, 0, 4)
        self._lay_filhos.setSpacing(2)

        self._btn_add_filho = QPushButton("＋  arquivo")
        self._btn_add_filho.setCursor(Qt.PointingHandCursor)
        self._btn_add_filho.setFixedHeight(24)
        self._btn_add_filho.setStyleSheet(
            "QPushButton { background: transparent; border: 1px dashed #3a4a3a;"
            " border-radius: 3px; font-size: 10px; }"
            "QPushButton:hover { border-color: #4ec994; color: #4ec994; }"
        )
        self._btn_add_filho.clicked.connect(lambda _=False: self._adicionar_filho())
        self._lay_filhos.addWidget(self._btn_add_filho)

        lay_externo.addWidget(self._area_filhos)

        # Carrega filhos iniciais
        if filhos:
            for filho in filhos:
                self._adicionar_filho(
                    filho.get("nome", ""),
                    filho.get("ext", ".py"),
                    filho.get("conteudo", ""),
                )

    # ── helpers ───────────────────────────────────────────────────────────────

    def _toggle(self):
        self._expandido = not self._expandido
        self._area_filhos.setVisible(self._expandido)
        self._btn_expandir.setText("▲ arquivos" if self._expandido else "▼ arquivos")

    def _adicionar_filho(self, nome: str = "", ext: str = ".py", conteudo: str = ""):
        filho = _LinhaTemplate(nome, ext, conteudo, self)
        filho.removido.connect(self._remover_filho)
        self._filhos.append(filho)
        # Insere antes do botão "＋ arquivo"
        idx = self._lay_filhos.indexOf(self._btn_add_filho)
        self._lay_filhos.insertWidget(idx, filho)

    def _remover_filho(self, filho: _LinhaTemplate):
        if filho in self._filhos:
            self._filhos.remove(filho)
        self._lay_filhos.removeWidget(filho)
        filho.deleteLater()

    # ── dado público ──────────────────────────────────────────────────────────

    def dados(self) -> dict:
        nome   = self._campo.text().strip()
        filhos = [f.dados() for f in self._filhos if f.dados()["nome"]]
        return {"tipo": "pasta", "nome": nome, "filhos": filhos}

# ──────────────────────────────────────────────────────────────────────────────
# Painel principal
# ──────────────────────────────────────────────────────────────────────────────

class PainelNovoProjeto(QWidget):
    criar_projeto = Signal(str, str)   # nome, destino
    voltar        = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._linhas_template: list[_LinhaTemplate] = []
        self._montar_ui()
        self._carregar_templates()

    def _cor(self, chave: str, fallback: str) -> str:
        return tema_global().cor(chave, fallback)

    # ── UI ───────────────────────────────────────────────────────────────────

    # ⚠️  função grande (204 linhas)
    def _montar_ui(self):
        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(0)

        # ── Barra de topo com botão voltar ────────────────────────────────────
        barra_topo = QWidget()
        barra_topo.setFixedHeight(40)
        lay_topo = QHBoxLayout(barra_topo)
        lay_topo.setContentsMargins(12, 0, 12, 0)

        btn_voltar = QPushButton("← Voltar")
        btn_voltar.setCursor(Qt.PointingHandCursor)
        btn_voltar.setFixedWidth(90)
        btn_voltar.clicked.connect(self.voltar.emit)

        lbl_titulo = QLabel("Novo Projeto")

        lay_topo.addWidget(btn_voltar)
        lay_topo.addSpacing(12)
        lay_topo.addWidget(lbl_titulo)
        lay_topo.addStretch()
        raiz.addWidget(barra_topo)

        sep_topo = QFrame()
        sep_topo.setFrameShape(QFrame.HLine)
        sep_topo.setFixedHeight(1)
        raiz.addWidget(sep_topo)

        # ── Scroll principal ──────────────────────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        corpo = QWidget()
        scroll.setWidget(corpo)
        raiz.addWidget(scroll, 1)

        # ── Duas colunas ──────────────────────────────────────────────────────
        lay_corpo = QHBoxLayout(corpo)
        lay_corpo.setContentsMargins(40, 32, 40, 32)
        lay_corpo.setSpacing(40)
        lay_corpo.setAlignment(Qt.AlignTop)

        # ── COLUNA ESQUERDA ───────────────────────────────────────────────────
        col_esq = QVBoxLayout()
        col_esq.setSpacing(0)
        col_esq.setAlignment(Qt.AlignTop)

        col_esq.addWidget(self._rotulo_secao("PROJETO"))
        col_esq.addSpacing(12)

        col_esq.addWidget(self._rotulo_campo("Nome do projeto"))
        col_esq.addSpacing(4)
        self._campo_nome = QLineEdit()
        self._campo_nome.setPlaceholderText("Ex: meu_projeto")
        self._campo_nome.setFixedHeight(30)
        col_esq.addWidget(self._campo_nome)

        col_esq.addSpacing(12)
        col_esq.addWidget(self._rotulo_campo("Pasta de destino"))
        col_esq.addSpacing(4)
        row_dest = QHBoxLayout()
        row_dest.setSpacing(6)
        self._campo_destino = QLineEdit()
        self._campo_destino.setPlaceholderText("Onde criar o projeto")
        self._campo_destino.setFixedHeight(30)
        self._campo_destino.setReadOnly(True)
        _ultima_pasta = QSettings("hen", "hen_IDE").value("ultima_pasta_destino", "")
        if _ultima_pasta and os.path.isdir(_ultima_pasta):
            self._campo_destino.setText(_ultima_pasta)
        btn_dest = QPushButton("Navegar...")
        btn_dest.setFixedHeight(30)
        btn_dest.setCursor(Qt.PointingHandCursor)
        btn_dest.clicked.connect(self._ao_navegar_destino)
        row_dest.addWidget(self._campo_destino)
        row_dest.addWidget(btn_dest)
        col_esq.addLayout(row_dest)

        col_esq.addSpacing(24)
        col_esq.addWidget(self._separador())
        col_esq.addSpacing(20)

        col_esq.addSpacing(28)

        self._btn_criar = QPushButton("✦  Criar estrutura")
        self._btn_criar.setFixedHeight(36)
        self._btn_criar.setCursor(Qt.PointingHandCursor)
        self._btn_criar.clicked.connect(self._ao_criar)
        col_esq.addWidget(self._btn_criar)

        col_esq.addStretch()

        # ── SEPARADOR VERTICAL ────────────────────────────────────────────────
        vsep = QFrame()
        vsep.setFrameShape(QFrame.VLine)
        vsep.setFixedWidth(1)

        # ── COLUNA DIREITA: templates ─────────────────────────────────────────
        col_dir = QVBoxLayout()
        col_dir.setSpacing(0)
        col_dir.setAlignment(Qt.AlignTop)

        col_dir.addWidget(self._rotulo_secao("ARQUIVOS DO PROJETO"))
        col_dir.addSpacing(6)

        lbl_desc = QLabel(
            "Arquivos criados em todo novo projeto.\n"
            "Clique em ▼ conteúdo para definir o conteúdo inicial de cada arquivo.\n"
            "Salvo permanentemente."
        )
        col_dir.addWidget(lbl_desc)
        col_dir.addSpacing(12)

        self._container_templates = QWidget()
        self._lay_templates = QVBoxLayout(self._container_templates)
        self._lay_templates.setContentsMargins(0, 0, 0, 0)
        self._lay_templates.setSpacing(2)
        col_dir.addWidget(self._container_templates)

        col_dir.addSpacing(8)

        row_add = QHBoxLayout()
        row_add.setSpacing(6)

        btn_add = QPushButton("＋  Arquivo")
        btn_add.setCursor(Qt.PointingHandCursor)
        btn_add.setFixedHeight(28)
        # FIX: lambda para não deixar o sinal clicked passar bool como argumento
        btn_add.clicked.connect(lambda _=False: self._adicionar_linha())
        row_add.addWidget(btn_add)

        btn_add_pasta = QPushButton("📁  Pasta")
        btn_add_pasta.setCursor(Qt.PointingHandCursor)
        btn_add_pasta.setFixedHeight(28)
        btn_add_pasta.clicked.connect(lambda _=False: self._adicionar_pasta())
        row_add.addWidget(btn_add_pasta)

        col_dir.addLayout(row_add)

        col_dir.addSpacing(16)
        col_dir.addWidget(self._separador())
        col_dir.addSpacing(12)

        btn_salvar_tmpl = QPushButton("💾  Salvar templates")
        btn_salvar_tmpl.setFixedHeight(30)
        btn_salvar_tmpl.setCursor(Qt.PointingHandCursor)
        btn_salvar_tmpl.clicked.connect(self._salvar_templates)
        col_dir.addWidget(btn_salvar_tmpl)

        self._lbl_tmpl_ok = QLabel("")
        self._lbl_tmpl_ok.setStyleSheet(f"color: {COR_SUCESSO}; font-size: 10px;")
        col_dir.addWidget(self._lbl_tmpl_ok)
        col_dir.addStretch()

        lay_corpo.addLayout(col_esq, 1)
        lay_corpo.addWidget(vsep)
        lay_corpo.addLayout(col_dir, 1)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _rotulo_secao(self, texto: str) -> QLabel:
        lbl = QLabel(texto)
        lbl.setStyleSheet(
            f"font-size: 9px; font-weight: 700;"
            f" color: {COR_SEPARADOR}; letter-spacing: 1.8px;"
        )

        return lbl

    def _rotulo_campo(self, texto: str) -> QLabel:
        lbl = QLabel(texto)
        lbl.setStyleSheet("font-size: 11px; font-weight: 500;")

        return lbl

    def _separador(self) -> QFrame:
        f = QFrame()
        f.setFrameShape(QFrame.HLine)
        f.setFixedHeight(1)

        return f

    # ── Templates ─────────────────────────────────────────────────────────────

    def _carregar_templates(self):
        for linha in list(self._linhas_template):
            self._lay_templates.removeWidget(linha)
            linha.deleteLater()
        self._linhas_template.clear()
        for tmpl in _carregar_templates():
            if tmpl.get("tipo") == "pasta":
                self._adicionar_pasta(
                    tmpl.get("nome", ""),
                    tmpl.get("filhos", []),
                )
            else:
                self._adicionar_linha(
                    tmpl.get("nome", ""),
                    tmpl.get("ext", ".py"),
                    tmpl.get("conteudo", ""),
                )

    # 💡 ext_opc = Literal[".py"] ← defina os valores válidos
    def _adicionar_linha(self, nome: str = "", ext: str = ".py", conteudo: str = ""):
        linha = _LinhaTemplate(nome, ext, conteudo, self)
        linha.removido.connect(self._remover_linha)
        self._linhas_template.append(linha)
        self._lay_templates.addWidget(linha)

    def _adicionar_pasta(self, nome: str = "", filhos: list | None = None):
        pasta = _LinhaPasta(nome, filhos or [], self)
        pasta.removido.connect(self._remover_linha)
        self._linhas_template.append(pasta)
        self._lay_templates.addWidget(pasta)

    def _remover_linha(self, linha):
        if linha in self._linhas_template:
            self._linhas_template.remove(linha)
        self._lay_templates.removeWidget(linha)
        linha.deleteLater()

    def _salvar_templates(self):
        dados = [l.dados() for l in self._linhas_template if l.dados()["nome"]]
        _salvar_templates(dados)
        self._lbl_tmpl_ok.setText("✔  Salvo")
        QTimer.singleShot(2500, lambda: self._lbl_tmpl_ok.setText(""))

    def _templates_atuais(self) -> list[dict]:
        return [l.dados() for l in self._linhas_template if l.dados()["nome"]]

    def _ao_navegar_destino(self):
        pasta_inicial = QSettings("hen", "hen_IDE").value("ultima_pasta_destino", PASTA_PROJETOS)
        pasta = QFileDialog.getExistingDirectory(self, "Pasta de destino", pasta_inicial)
        if pasta:
            self._campo_destino.setText(pasta)
            QSettings("hen", "hen_IDE").setValue("ultima_pasta_destino", pasta)

    # ── Criação do projeto ────────────────────────────────────────────────────

    # ⚠️  função grande (88 linhas)
    def _ao_criar(self):
        nome    = self._campo_nome.text().strip()
        destino = self._campo_destino.text().strip()

        erros = []
        if not nome:
            erros.append("• Informe o nome do projeto.")
        if not destino:
            erros.append("• Escolha a pasta de destino.")

        if erros:
            QMessageBox.warning(self, "Campos obrigatórios", "\n".join(erros))

            return

        caminho = os.path.join(destino, nome)

        if os.path.exists(caminho):
            resp = QMessageBox.question(
                self, "Já existe",
                "Já existe uma pasta com esse nome. Sobrescrever?",
                QMessageBox.Yes | QMessageBox.No,
            )
            if resp == QMessageBox.No:
                return

        os.makedirs(caminho, exist_ok=True)

        # Cria arquivos e pastas dos templates
        primeiro_py = None

        def _criar_arquivo(base: str, tmpl: dict) -> None:
            nonlocal primeiro_py
            nome_arq    = tmpl["nome"] + tmpl["ext"]
            caminho_arq = os.path.join(base, nome_arq)
            conteudo    = tmpl.get("conteudo", "").strip()
            with open(caminho_arq, "w", encoding="utf-8") as f:
                if conteudo:
                    f.write(conteudo)
                    if not conteudo.endswith("\n"):
                        f.write("\n")
                elif tmpl["ext"] == ".py":
                    f.write(f"# 📁 {nome_arq}\n")
                    if primeiro_py is None:
                        f.write(
                            "\n\ndef main():\n"
                            '    print("Olá, mundo!")\n\n\n'
                            'if __name__ == "__main__":\n'
                            "    main()\n"
                        )
                # outros tipos sem conteúdo ficam vazios
            if tmpl["ext"] == ".py" and primeiro_py is None:
                primeiro_py = caminho_arq

        for tmpl in self._templates_atuais():
            if tmpl.get("tipo") == "pasta":
                pasta_path = os.path.join(caminho, tmpl["nome"])
                os.makedirs(pasta_path, exist_ok=True)
                for filho in tmpl.get("filhos", []):
                    if filho.get("nome"):
                        _criar_arquivo(pasta_path, filho)
            else:
                _criar_arquivo(caminho, tmpl)

        if primeiro_py is None:
            main_py = os.path.join(caminho, "main.py")
            with open(main_py, "w", encoding="utf-8") as f:
                f.write(
                    "# 📁 main.py\n\n\n"
                    "def main():\n"
                    '    print("Olá, mundo!")\n\n\n'
                    'if __name__ == "__main__":\n'
                    "    main()\n"
                )
            primeiro_py = main_py

        self._main_py         = primeiro_py
        self._caminho_projeto = caminho

        self._btn_criar.setEnabled(False)
        self._campo_nome.setReadOnly(True)
        self._campo_destino.setReadOnly(True)

        self.criar_projeto.emit(nome, destino)
