# 📁 _UTILITARIOS_/gerenciador_pacotes.py
# -*- coding: utf-8 -*-
"""
Aba "Pacotes" do terminal hein.
Lista os pacotes registrados em hein_packages.json e permite desinstalar.
"""
import os
import platform
import sys
import subprocess
import json
import ast
import warnings
from _UTILITARIOS_.icones import icone_tema
from PySide6.QtCore import Qt, QProcess, Signal, QSize
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QScrollArea, QFrame, QMessageBox, QLineEdit
)
from _CONFIGURA_.gerenciador_tema import tema_global
from _CONFIGURA_ import COR_BTN_ICONE_BG_qta
from _UTILITARIOS_.hein_pacotes_util import listar, remover
from _UTILITARIOS_.processo_sem_console import opcoes_processo_sem_console

class _LinhaPacote(QFrame):
    desinstalar_solicitado = Signal(str)
    instalar_solicitado = Signal(str)

    # ⚠️  função grande (79 linhas)
    def __init__(self, nome: str, versao: str, data: str, desatualizado: bool = False, eh_fantasma: bool = False, parent=None):
        super().__init__(parent)
        self._nome = nome
        self._versao = versao

        cor_borda = "#00ff88" if eh_fantasma else "#ffcc00" if desatualizado else "#1e1e30"
        self.setStyleSheet(f"""
            QFrame {{
                background: #12121f;
                border: 1px solid {cor_borda};
                border-radius: 4px;
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 7, 10, 7)
        layout.setSpacing(8)

        col = QVBoxLayout()
        col.setSpacing(1)

        lbl_nome = QLabel(f"{nome} {'[FANTASMA]' if eh_fantasma else ''}")
        lbl_nome.setStyleSheet("font-size:12px; font-weight:bold; color:#f8f8f2; background:transparent; border:none;")
        col.addWidget(lbl_nome)

        detalhe_partes = []
        if versao:
            detalhe_partes.append(f"v{versao} {'[ATUALIZAR]' if desatualizado else ''}")
        if data:
            detalhe_partes.append(data[:10])
        if detalhe_partes:
            cor_texto = "#00ff88" if eh_fantasma else "#ffcc00" if desatualizado else "#555"
            lbl_det = QLabel(" • ".join(detalhe_partes))
            lbl_det.setStyleSheet(f"font-size:10px; color:{cor_texto}; background:transparent; border:none;")
            col.addWidget(lbl_det)

        layout.addLayout(col)
        layout.addStretch()

        if eh_fantasma:
            btn_inst = QPushButton("Instalar")
            btn_inst.setIcon(icone_tema("mdi.package-down", color="#00ff88"))
            btn_inst.setIconSize(QSize(14, 14))
            btn_inst.setStyleSheet("""
                QPushButton { background: #003322; color: #00ff88; border: 1px solid #005544; padding: 4px 12px; border-radius: 3px; font-size: 11px; }
                QPushButton:hover { background: #004433; }
            """)
            btn_inst.clicked.connect(lambda: self.instalar_solicitado.emit(self._nome))
            layout.addWidget(btn_inst)

        if desatualizado and not eh_fantasma:
            btn_upd = QPushButton("Atualizar")
            btn_upd.setIcon(icone_tema("mdi.arrow-up-bold", color="#ffcc00"))
            btn_upd.setIconSize(QSize(14, 14))
            btn_upd.setStyleSheet("""
                QPushButton { background: #332a00; color: #ffcc00; border: 1px solid #554400; padding: 4px 12px; border-radius: 3px; font-size: 11px; }
                QPushButton:hover { background: #443800; }
            """)
            btn_upd.clicked.connect(lambda: self.instalar_solicitado.emit(self._nome))
            layout.addWidget(btn_upd)

        if not eh_fantasma:
            self._btn = QPushButton("Desinstalar")
            self._btn.setIcon(icone_tema("mdi.delete", color=tema_global().cor("editor.erro","#ff5555")))
            self._btn.setIconSize(QSize(14, 14))
            self._btn.setStyleSheet("""
                QPushButton {
                    background: #2a1010;
                    color: #ff5555;
                    border: 1px solid #441818;
                    padding: 4px 12px;
                    border-radius: 3px;
                    font-size: 11px;
                }
                QPushButton:hover { background: #3a1010; }
                QPushButton:disabled { color: #555; border-color: #222; background: #151515; }
            """)
            self._btn.clicked.connect(lambda: self.desinstalar_solicitado.emit(self._nome))
            layout.addWidget(self._btn)

    def set_aguardando(self, ativo: bool):
        if hasattr(self, '_btn'): self._btn.setEnabled(not ativo)
        if hasattr(self, '_btn'): self._btn.setText("Desinstalando…" if ativo else "Desinstalar")

class GerenciadorPacotes(QWidget):
    """Widget principal da aba Pacotes — montado pelo TerminalTabWidget."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._projeto: str = ""
        self._processos: list[QProcess] = []
        self._linhas: dict[str, _LinhaPacote] = {}
        self._pacotes_outdated: dict = {}
        self._pacotes_fantasma: set = set()
        self._construir_ui()

    def set_projeto(self, caminho: str) -> None:
        self._projeto = caminho or ""
        self._escanear_fantasmas()
        self._atualizar()

    def atualizar(self) -> None:
        self._escanear_fantasmas()
        self._atualizar()

    # ⚠️  função grande (100 linhas)
    def _construir_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(6)

        # PESO DO PROJETO
        self._lbl_peso = QLabel("Tamanho do.venv: Calculando...")
        self._lbl_peso.setStyleSheet("font-size:10px; color:#555; margin-bottom:2px;")
        root.addWidget(self._lbl_peso)

        # FILTRO
        self._filtro = QLineEdit()
        self._filtro.setPlaceholderText("Filtrar pacotes...")
        self._filtro.setStyleSheet("background: #1e1e30; border: 1px solid #2a2a44; border-radius: 3px; padding: 4px; color: #aaa;")
        self._filtro.textChanged.connect(self._filtrar_lista)
        root.addWidget(self._filtro)

        # cabeçalho
        header = QHBoxLayout()
        header.setSpacing(6)

        icone_hdr = QLabel()
        icone_hdr.setPixmap(icone_tema("mdi.cube-outline", color=tema_global().cor("painel_outline.cor_classe","#bd93f9")).pixmap(QSize(16, 16)))
        icone_hdr.setStyleSheet("background:transparent; border:none;")
        header.addWidget(icone_hdr)

        lbl = QLabel("Pacotes do projeto")
        lbl.setStyleSheet("font-size:13px; font-weight:bold; color:#bd93f9;")
        header.addWidget(lbl)
        header.addStretch()

        btn_scan = QPushButton("Escanear Imports")
        btn_scan.setIcon(icone_tema("mdi.magnify", color="#aaa"))
        btn_scan.setIconSize(QSize(14, 14))
        btn_scan.setStyleSheet(f"QPushButton {{ background: #1e1e30; color: #aaa; border: 1px solid #2a2a44; padding: 4px 12px; border-radius: 3px; font-size: 11px; }} QPushButton:hover {{ background: {COR_BTN_ICONE_BG_qta}; color: #ddd; }}")
        btn_scan.clicked.connect(self._escanear_fantasmas)
        header.addWidget(btn_scan)

        btn_inst_req = QPushButton("Instalar requirements.txt")
        btn_inst_req.setIcon(icone_tema("mdi.file-upload-outline", color="#aaa"))
        btn_inst_req.setIconSize(QSize(14, 14))
        btn_inst_req.setStyleSheet(f"QPushButton {{ background: #1e1e30; color: #aaa; border: 1px solid #2a2a44; padding: 4px 12px; border-radius: 3px; font-size: 11px; }} QPushButton:hover {{ background: {COR_BTN_ICONE_BG_qta}; color: #ddd; }}")
        btn_inst_req.clicked.connect(self._instalar_requirements)
        header.addWidget(btn_inst_req)

        btn_req = QPushButton("Gerar requirements.txt")
        btn_req.setIcon(icone_tema("mdi.file-download-outline", color="#aaa"))
        btn_req.setIconSize(QSize(14, 14))
        btn_req.setStyleSheet(f"QPushButton {{ background: #1e1e30; color: #aaa; border: 1px solid #2a2a44; padding: 4px 12px; border-radius: 3px; font-size: 11px; }} QPushButton:hover {{ background: {COR_BTN_ICONE_BG_qta}; color: #ddd; }}")
        btn_req.clicked.connect(self._gerar_requirements)
        header.addWidget(btn_req)

        self._btn_out = QPushButton("Verificar Atualizações")
        self._btn_out.setIcon(icone_tema("mdi.cloud-download-outline", color="#aaa"))
        self._btn_out.setIconSize(QSize(14, 14))
        self._btn_out.setStyleSheet(f"QPushButton {{ background: #1e1e30; color: #aaa; border: 1px solid #2a2a44; padding: 4px 12px; border-radius: 3px; font-size: 11px; }} QPushButton:hover {{ background: {COR_BTN_ICONE_BG_qta}; color: #ddd; }}")
        self._btn_out.clicked.connect(self._verificar_outdated)
        header.addWidget(self._btn_out)

        btn_ref = QPushButton("Atualizar")
        btn_ref.setIcon(icone_tema("mdi.refresh", color="#aaa"))
        btn_ref.setIconSize(QSize(14, 14))
        btn_ref.setStyleSheet("""
            QPushButton {
                background: #1e1e30;
                color: #aaa;
                border: 1px solid #2a2a44;
                padding: 4px 12px;
                border-radius: 3px;
                font-size: 11px;
            }
            QPushButton:hover { background: #26263a; color: #ddd; }
        """)
        btn_ref.clicked.connect(self.atualizar)
        header.addWidget(btn_ref)
        root.addLayout(header)

        nota = QLabel("Somente pacotes instalados via editor ou terminal monitorado são registrados — sem dependências transitivas.")
        nota.setWordWrap(True)
        nota.setStyleSheet("font-size:10px; color:#444; margin-bottom:4px;")
        root.addWidget(nota)

        self._area = QScrollArea()
        self._area.setWidgetResizable(True)
        self._area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._area.setStyleSheet("border: none; background: #0a0a12;")
        self._container = QWidget()
        self._container.setStyleSheet("background: #0a0a12;")
        self._lista = QVBoxLayout(self._container)
        self._lista.setContentsMargins(0, 0, 0, 0)
        self._lista.setSpacing(4)
        self._lista.addStretch()
        self._area.setWidget(self._container)
        root.addWidget(self._area)

        self._lbl_vazio = QLabel("Nenhum pacote registrado ainda.")
        self._lbl_vazio.setAlignment(Qt.AlignCenter)
        self._lbl_vazio.setStyleSheet("color:#333; font-size:12px; padding:30px;")
        self._lbl_vazio.hide()
        root.addWidget(self._lbl_vazio)

    def _filtrar_lista(self, texto):
        for nome, linha in self._linhas.items():
            linha.setVisible(texto.lower() in nome.lower())

    # ⚠️  except genérico vazio
    def _calcular_peso(self):
        if not self._projeto:
            self._lbl_peso.setText("Tamanho do.venv: N/A")

            return

        total = 0
        site_packages = os.path.join(self._projeto, ".venv", "Lib", "site-packages")
        if os.path.exists(site_packages):
            for dirpath, _, filenames in os.walk(site_packages):
                for f in filenames:
                    fp = os.path.join(dirpath, f)
                    try: total += os.path.getsize(fp)
                    except: pass
        self._lbl_peso.setText(f"Tamanho do.venv: {total / 1024 / 1024:.2f} MB")

    # ⚠️  except genérico vazio
    # Dirs que nunca devem ser escaneados em busca de imports do usuario
    _DIRS_SKIP = {'.venv', '.git', '__pycache__', 'node_modules',
                  '.mypy_cache', '.pytest_cache', 'dist', 'build',
                  '.tox', 'venv', 'env', '.env', '.hg', '.svn'}
    # Nomes que nao sao pacotes instaláveis (dunder, internos C, compat Python 2)
    _NOMES_SKIP = {
        '__main__', '__builtin__', '__future__', '__pypy__',
        '__version__', '__init__', '__all__',
        'ConfigParser', 'HTMLParser', 'Queue', 'StringIO',
        '_abcoll', '_pypy', '_compat',
    }

    def _escanear_fantasmas(self):
        self._pacotes_fantasma.clear()
        if not self._projeto: return
        imports_projeto = set()
        for root, dirs, files in os.walk(self._projeto):
            dirs[:] = [d for d in dirs
                       if d not in self._DIRS_SKIP and not d.startswith('.')
                       and not d.startswith('_')]
            for file in files:
                if file.endswith(".py"):
                    try:
                        fp_arq = os.path.join(root, file)
                        with open(fp_arq, "r", encoding="utf-8") as f:
                            src = f.read()
                        with warnings.catch_warnings():
                            warnings.simplefilter("ignore")
                            tree = ast.parse(src, filename=fp_arq)
                        for node in ast.walk(tree):
                            if isinstance(node, ast.Import):
                                for n in node.names: imports_projeto.add(n.name.split('.')[0])
                            if isinstance(node, ast.ImportFrom) and node.module:
                                imports_projeto.add(node.module.split('.')[0])
                    except: pass

        pacotes_instalados = set(listar(self._projeto).keys())
        try: std_libs = set(sys.stdlib_module_names)
        except: std_libs = set()
        self._pacotes_fantasma = {
            n for n in imports_projeto - pacotes_instalados - std_libs
            if n and not n.startswith('_') and n not in self._NOMES_SKIP
        }

    def _sem_venv_aviso(self) -> bool:
        """Retorna True se nao ha .venv valida — mostra aviso e bloqueia a acao."""
        if not self._projeto:
            QMessageBox.warning(self, "Sem projeto", "Nenhum projeto aberto.\nAbra um projeto primeiro.")
            return True
        if not self._achar_pip():
            QMessageBox.warning(self, "Sem ambiente virtual",
                "Nenhuma .venv encontrada no projeto.\n"
                "Crie o projeto pelo hein IDE para gerar a .venv automaticamente.")
            return True
        return False

    def _instalar_requirements(self):
        if self._sem_venv_aviso(): return
        caminho_req = os.path.join(self._projeto, "requirements.txt")
        if not os.path.isfile(caminho_req):
            QMessageBox.warning(self, "Atenção", f"Arquivo não encontrado:\n{caminho_req}")
            return
        pip = self._achar_pip()
        comando = [pip, "install", "-r", caminho_req]
        proc = QProcess(self)
        proc.start(comando[0], comando[1:])
        QMessageBox.information(self, "Instalando", "Instalando pacotes do requirements.txt...\nVeja o progresso no terminal.")
        proc.finished.connect(self.atualizar)

    def _gerar_requirements(self):
        if self._sem_venv_aviso(): return
        caminho_req = os.path.join(self._projeto, "requirements.txt")
        try:
            pip_venv = self._achar_pip()
            cmd_freeze = [pip_venv, "freeze"]
            with open(caminho_req, "w", encoding="utf-8") as f:
                subprocess.run(
                    cmd_freeze, stdout=f, check=True, text=True,
                    **opcoes_processo_sem_console(),
                )
            QMessageBox.information(self, "Sucesso", f"requirements.txt criado em:\n{caminho_req}")
            janela = self.window()
            if hasattr(janela, "tabs"):
                janela.tabs.add_new_tab_com_conteudo(open(caminho_req, 'r', encoding='utf-8').read(), "requirements.txt")
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Não foi possível gerar o arquivo:\n{e}")

    def _verificar_outdated(self):
        self._btn_out.setEnabled(False)
        self._btn_out.setText("Verificando...")
        pip = self._achar_pip()
        if not pip:
            self._btn_out.setEnabled(True)
            self._btn_out.setText("Verificar Atualizações")
            return
        comando = [pip, "list", "--outdated", "--format=json"]
        proc = QProcess(self)
        proc.finished.connect(self._processar_outdated)
        proc.start(comando[0], comando[1:])

    def _processar_outdated(self, code, status):
        proc = self.sender()
        if code == 0:
            try:
                data = json.loads(proc.readAllStandardOutput().data().decode())
                self._pacotes_outdated = {p['name']: p['latest_version'] for p in data}
            except: self._pacotes_outdated = {}
        self._btn_out.setEnabled(True)
        self._btn_out.setText("Verificar Atualizações")
        self._atualizar()

    def _atualizar(self):
        for linha in self._linhas.values():
            self._lista.removeWidget(linha)
            linha.deleteLater()
        self._linhas.clear()
        pacotes = listar(self._projeto)

        if not pacotes and not self._pacotes_fantasma:
            self._lbl_vazio.show()
            self._area.hide()
        else:
            self._lbl_vazio.hide()
            self._area.show()

        for i, (nome, info) in enumerate(sorted(pacotes.items())):
            is_outdated = nome in self._pacotes_outdated
            linha = _LinhaPacote(nome, info.get("versao", ""), info.get("instalado_em", ""), is_outdated)
            linha.desinstalar_solicitado.connect(self._desinstalar)
            linha.instalar_solicitado.connect(self._instalar_pacote) # serve pra atualizar tb
            self._lista.insertWidget(i, linha)
            self._linhas[nome] = linha

        # ADICIONA FANTASMAS
        for nome_fantasma in sorted(self._pacotes_fantasma):
            linha = _LinhaPacote(nome_fantasma, "", "", eh_fantasma=True)
            linha.instalar_solicitado.connect(self._instalar_pacote)
            self._lista.insertWidget(self._lista.count()-1, linha)
            self._linhas[nome_fantasma] = linha

        self._calcular_peso()

    def _instalar_pacote(self, modulo):
        if self._sem_venv_aviso(): return
        pip = self._achar_pip()
        comando = [pip, "install", "-U", modulo]
        proc = QProcess(self)
        proc.start(comando[0], comando[1:])
        QMessageBox.information(self, "Instalando/Atualizando", f"Rodando: pip install -U {modulo}")
        proc.finished.connect(self.atualizar)

    def _desinstalar(self, modulo: str):
        linha = self._linhas.get(modulo)
        if linha: linha.set_aguardando(True)
        janela = self.window()
        if hasattr(janela, "statusBar"): janela.statusBar().showMessage(f"Desinstalando '{modulo}'...")
        pip = self._achar_pip()
        proc = QProcess(self)
        self._processos.append(proc)
        if not pip:
            if linha: linha.set_aguardando(False)
            QMessageBox.warning(self, "Sem ambiente virtual", "Nenhuma .venv encontrada no projeto.")
            return
        proc.start(pip, ["uninstall", "-y", modulo])
        def _terminou(code, _status):
            if code == 0:
                remover(self._projeto, modulo)
                if linha:
                    self._lista.removeWidget(linha)
                    linha.deleteLater()
                self._linhas.pop(modulo, None)
                if not self._linhas and not self._pacotes_fantasma:
                    self._lbl_vazio.show(); self._area.hide()
                if hasattr(janela, "statusBar"): janela.statusBar().showMessage(f"'{modulo}' desinstalado", 4000)
            else:
                if linha: linha.set_aguardando(False)
                if hasattr(janela, "statusBar"): janela.statusBar().showMessage(f"Falha ao desinstalar '{modulo}'", 4000)
        proc.finished.connect(_terminou)

    def _achar_pip(self) -> str:
        if not self._projeto: return ""
        scripts = "Scripts" if platform.system() == "Windows" else "bin"
        exe = "pip.exe" if platform.system() == "Windows" else "pip"
        pip = os.path.join(self._projeto, ".venv", scripts, exe)

        return pip if os.path.isfile(pip) else ""
