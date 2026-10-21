"""Aba de configuração e abertura do builder de executáveis do projeto."""
from __future__ import annotations

import os
import re
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFileDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QMessageBox,
    QPushButton, QVBoxLayout, QWidget,
)

from _EXECUTAVEL_.config import (
    ler_config_executavel_se_existir,
    obter_arquivo_config,
    salvar_config_executavel,
)
from _UTILITARIOS_.icones import icone_tema
from _CONFIGURA_.gerenciador_tema import tema_global
from _LOG_.log import log

_ARQ = "painel_executavel.py"


class PainelExecutavel(QWidget):
    abrir_executavel_config = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._projeto: str | None = None
        self._construir()
        self.atualizar_tema()

    def _construir(self):
        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(12, 10, 12, 10)
        raiz.setSpacing(9)

        titulo = QLabel("CRIAR EXECUTÁVEL")
        titulo.setStyleSheet("font-weight: bold; font-size: 12px;")
        raiz.addWidget(titulo)
        descricao = QLabel(
            "Configure o projeto ativo. O build local usa a .venv do projeto; "
            "a publicação gera o workflow para o GitHub Actions."
        )
        descricao.setWordWrap(True)
        descricao.setStyleSheet("font-size: 10px;")
        raiz.addWidget(descricao)

        form = QFormLayout()
        form.setContentsMargins(0, 4, 0, 0)
        form.setSpacing(8)
        self._nome = QLineEdit()
        self._nome.setPlaceholderText("Nome do executável")
        self._versao = QLineEdit()
        self._versao.setPlaceholderText("0.1.0")
        self._entrada = QLineEdit()
        self._entrada.setPlaceholderText("main.py")
        self._icone = QLineEdit()
        self._icone.setPlaceholderText("Opcional; caminho relativo ao projeto")
        form.addRow("Nome:", self._nome)
        form.addRow("Versão:", self._versao)
        form.addRow("Arquivo inicial:", self._linha_com_botao(
            self._entrada, "Escolher…", self._escolher_entrada
        ))
        form.addRow("Ícone:", self._linha_com_botao(
            self._icone, "Escolher…", self._escolher_icone
        ))
        raiz.addLayout(form)

        self._status = QLabel("Abra ou crie um projeto para configurar o executável.")
        self._status.setWordWrap(True)
        self._status.setStyleSheet("font-size: 10px;")
        raiz.addWidget(self._status)

        botoes = QHBoxLayout()
        self._btn_local = QPushButton("Criar executável local")
        self._btn_release = QPushButton("Release no GitHub")
        self._btn_local.setIcon(icone_tema("mdi.package-variant-closed"))
        self._btn_release.setIcon(icone_tema("mdi.github"))
        self._btn_local.clicked.connect(lambda: self._salvar_e_abrir("executavel"))
        self._btn_release.clicked.connect(lambda: self._salvar_e_abrir("release"))
        botoes.addWidget(self._btn_local)
        botoes.addWidget(self._btn_release)
        raiz.addLayout(botoes)
        raiz.addStretch(1)

    @staticmethod
    def _linha_com_botao(campo, texto, callback):
        linha = QWidget()
        layout = QHBoxLayout(linha)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addWidget(campo, 1)
        botao = QPushButton(texto)
        botao.clicked.connect(callback)
        layout.addWidget(botao)
        return linha

    def set_projeto(self, caminho: str):
        self._projeto = str(Path(caminho).resolve()) if caminho else None
        if not self._projeto or not Path(self._projeto).is_dir():
            self._limpar()
            self._status.setText("Abra ou crie um projeto para configurar o executável.")
            self._habilitar(False)
            return
        dados = ler_config_executavel_se_existir(self._projeto)
        self._nome.setText(str(dados.get("nome", "")))
        self._versao.setText(str(dados.get("versao", "0.1.0")))
        self._entrada.setText(str(dados.get("ponto_entrada", "main.py")))
        self._icone.setText(str(dados.get("icone", "")))
        self._status.setText(f"Projeto: {self._projeto}")
        self._habilitar(True)

    def _limpar(self):
        for campo in (self._nome, self._versao, self._entrada, self._icone):
            campo.clear()

    def _habilitar(self, habilitado: bool):
        for campo in (self._nome, self._versao, self._entrada, self._icone,
                      self._btn_local, self._btn_release):
            campo.setEnabled(habilitado)

    def _escolher_entrada(self):
        if not self._projeto:
            return
        caminho, _ = QFileDialog.getOpenFileName(
            self, "Escolher arquivo inicial", self._projeto, "Arquivos Python (*.py)"
        )
        if caminho:
            self._entrada.setText(self._relativo(caminho))

    def _escolher_icone(self):
        if not self._projeto:
            return
        caminho, _ = QFileDialog.getOpenFileName(
            self, "Escolher ícone", self._projeto,
            "Ícones (*.ico *.png *.icns);;Todos os arquivos (*)",
        )
        if caminho:
            self._icone.setText(self._relativo(caminho))

    def _relativo(self, caminho: str) -> str:
        try:
            return Path(caminho).resolve().relative_to(Path(self._projeto).resolve()).as_posix()
        except ValueError:
            return caminho

    def _salvar_e_abrir(self, modo: str):
        if not self._projeto:
            QMessageBox.warning(self, "Projeto não selecionado", "Abra um projeto primeiro.")
            return
        nome = self._nome.text().strip()
        versao = self._versao.text().strip().lstrip("vV")
        entrada = self._entrada.text().strip()
        icone = self._icone.text().strip()
        if not nome or not re.fullmatch(r"[A-Za-z0-9_. -]+", nome) or nome in {".", ".."}:
            QMessageBox.warning(
                self, "Nome inválido",
                "Use letras, números, espaços, ponto, hífen ou sublinhado no nome.",
            )
            return
        if not re.fullmatch(r"\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?", versao):
            QMessageBox.warning(self, "Versão inválida", "Informe a versão no formato 1.2.3.")
            return
        if not entrada:
            QMessageBox.warning(self, "Arquivo inicial obrigatório", "Escolha o arquivo .py inicial.")
            return
        raiz = Path(self._projeto).resolve()
        arquivo_entrada = (raiz / entrada).resolve()
        try:
            arquivo_entrada.relative_to(raiz)
        except ValueError:
            QMessageBox.warning(self, "Caminho inválido", "O arquivo inicial deve estar no projeto.")
            return
        if not arquivo_entrada.is_file() or arquivo_entrada.suffix.lower() != ".py":
            QMessageBox.warning(self, "Arquivo inválido", "O arquivo inicial precisa existir e ser .py.")
            return
        if icone:
            arquivo_icone = (raiz / icone).resolve()
            try:
                arquivo_icone.relative_to(raiz)
            except ValueError:
                QMessageBox.warning(self, "Caminho inválido", "O ícone deve estar dentro do projeto.")
                return
            if not arquivo_icone.is_file():
                QMessageBox.warning(self, "Ícone não encontrado", "O arquivo de ícone não existe.")
                return
            icone = arquivo_icone.relative_to(raiz).as_posix()

        dados = ler_config_executavel_se_existir(self._projeto)
        dados.update({
            "nome": nome,
            "versao": versao,
            "ponto_entrada": arquivo_entrada.relative_to(raiz).as_posix(),
            "icone": icone,
            "modo": modo,
        })
        try:
            salvar_config_executavel(self._projeto, dados)
        except Exception as exc:
            log.erro(_ARQ, "_salvar_e_abrir", str(exc))
            QMessageBox.critical(self, "Erro ao salvar", f"Não foi possível salvar a configuração:\n{exc}")
            return
        self._status.setText(
            f"Configuração salva em {os.path.relpath(obter_arquivo_config(self._projeto), self._projeto)}"
        )
        self.abrir_executavel_config.emit(modo)

    def atualizar_tema(self, tema: dict | None = None):
        try:
            t = tema_global()
            fundo = t.cor("interface.fundo_painel", "#15191f")
            texto = t.cor("interface.texto", "#d0d0d0")
            borda = t.cor("interface.borda", "#343b45")
            self.setStyleSheet(
                f"QWidget {{ background: {fundo}; color: {texto}; }}"
                f"QLineEdit {{ border: 1px solid {borda}; padding: 3px; }}"
                f"QPushButton {{ padding: 4px 6px; }}"
            )
        except Exception as exc:
            log.aviso(_ARQ, "atualizar_tema", str(exc))
