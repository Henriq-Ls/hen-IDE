# 📁 _EDITOR_/Core/editor_dobramento.py
"""
_EditorDobramentoMixin — dobramento de blocos e integração projeto/CodeLens.
Parte 2 de 3 do split do Editor.
"""
import os
import re
import logging
from PySide6.QtGui  import QTextCursor, QTextBlockFormat
from PySide6.QtCore import QTimer
log = logging.getLogger("hein")


def _es_dobravel_para_extensao(texto: str, extensao: str) -> bool:
    """Delega ao provider da linguagem via LanguageManager."""
    from _EDITOR_.Mult_Linguas import get_provider, is_registered
    if not is_registered(extensao):
        return True  # extensão desconhecida: sem filtro, usa só indentação
    return get_provider(extensao).folding_fn(texto, extensao)

class FoldRegion:
    """
    Representa uma região de código dobrada.
    start_block: QTextBlock do cabeçalho (def/class/if etc.) — permanece visível.
    end_block:   QTextBlock do último bloco oculto da região.
    collapsed:   True enquanto a região está recolhida.
    """
    def __init__(self, start_block, end_block):
        self.start_block = start_block
        self.end_block   = end_block
        self.collapsed   = False

class _EditorDobramentoMixin:
    """Mixin com dobramento de código e integração com projeto e CodeLens."""

    # ══════════════════════════════════════════════════════════════════
    # Helpers internos
    # ══════════════════════════════════════════════════════════════════

    def _get_fold_region(self, bloco) -> "FoldRegion | None":
        """Retorna a FoldRegion cujo start_block coincide com o bloco, ou None."""
        num = bloco.blockNumber()
        for r in self._fold_regions:
            if r.start_block.blockNumber() == num:

                return r

        return None

    @staticmethod
    def _nivel_indentacao(texto: str) -> int:
        return len(texto) - len(texto.lstrip())

    # ══════════════════════════════════════════════════════════════════
    # Dobramento de blocos
    # ══════════════════════════════════════════════════════════════════

    # ⚠️  função grande (53 linhas)
    def recolher_bloco(self, bloco=None):
        """
        Recolhe o bloco indicado (ou o bloco do textCursor se None).
        NÃO chama setTextCursor — preserva posição do cursor do usuário.
        Cria um FoldRegion e oculta os blocos do range calculado por indentação.
        """
        if bloco is None:
            bloco = self.textCursor().block()

        if not bloco.isValid():

            return

        if self._get_fold_region(bloco) is not None:

            return  # já recolhido

        nivel_base = self._nivel_indentacao(bloco.text())
        proximo    = bloco.next()
        ultimo     = None
        ocultos    = 0
        pendentes  = []   # linhas em branco aguardando decisão

        while proximo.isValid():
            nivel = self._nivel_indentacao(proximo.text())
            if proximo.text().strip() == "":
                pendentes.append(proximo)   # acumula — decide ao ver próxima linha real
                proximo = proximo.next()
                continue
            if nivel <= nivel_base:
                break   # pendentes ficam visíveis — pertencem ao escopo externo
            # linha com conteúdo dentro do bloco: ocultar pendentes e esta
            for p in pendentes:
                p.setVisible(False)
                ocultos += 1
                ultimo = p
            pendentes.clear()
            proximo.setVisible(False)
            ultimo  = proximo
            ocultos += 1
            proximo = proximo.next()

        log.debug(
            f"[fold] recolher bloco={bloco.blockNumber()} "
            f"nivel_base={nivel_base} ocultos={ocultos}"
        )

        if ocultos > 0 and ultimo is not None:
            region           = FoldRegion(bloco, ultimo)
            region.collapsed = True
            self._fold_regions.append(region)

        self._refresh_layout()

    def expandir_bloco(self, bloco=None):
        """
        Expande a FoldRegion cujo start_block coincide com o bloco.
        NÃO chama setTextCursor — preserva posição do cursor do usuário.
        Expande APENAS os blocos dessa região — nunca vaza para outras regiões.
        """
        if bloco is None:
            bloco = self.textCursor().block()

        regiao = self._get_fold_region(bloco)
        if regiao is None:

            return

        fim_num = regiao.end_block.blockNumber()
        b       = regiao.start_block.next()
        visiveis = 0

        while b.isValid():
            b.setVisible(True)
            visiveis += 1
            if b.blockNumber() >= fim_num:
                break
            b = b.next()

        log.debug(
            f"[fold] expandir bloco={bloco.blockNumber()} "
            f"end={fim_num} visiveis={visiveis}"
        )

        regiao.collapsed = False
        try:
            self._fold_regions.remove(regiao)
        except ValueError:
            pass

        self._refresh_layout()

    def recolher_tudo(self):
        """Recolhe todos os def/class/async def do documento."""
        bloco = self.document().begin()
        while bloco.isValid():
            if re.match(r"^(def |class |async def )", bloco.text().lstrip()):
                self.recolher_bloco(bloco)
            bloco = bloco.next()

    def expandir_tudo(self):
        """Expande todos os blocos recolhidos."""
        for r in list(self._fold_regions):
            fim_num = r.end_block.blockNumber()
            b       = r.start_block.next()
            while b.isValid():
                b.setVisible(True)
                if b.blockNumber() >= fim_num:
                    break
                b = b.next()
        self._fold_regions.clear()
        self._refresh_layout()

    def toggle_dobramento(self, linha_1based: int):
        """
        Alterna recolher/expandir no bloco da linha indicada (1-based).
        NÃO move o cursor do usuário — só opera nos blocos do documento.
        """
        bloco = self.document().findBlockByNumber(linha_1based - 1)
        if not bloco.isValid():

            return

        sb           = self.verticalScrollBar()
        scroll_antes = sb.value()

        regiao = self._get_fold_region(bloco)
        if regiao is not None:
            log.debug(
                f"[fold] toggle → expandir | bloco={bloco.blockNumber()} "
                f"end={regiao.end_block.blockNumber()} collapsed=True"
            )
            self.expandir_bloco(bloco)
        else:
            log.debug(
                f"[fold] toggle → recolher | bloco={bloco.blockNumber()}"
            )
            self.recolher_bloco(bloco)

        QTimer.singleShot(0, lambda v=scroll_antes: sb.setValue(v))

    def _linha_e_dobravel(self, bloco) -> bool:
        """
        True se o bloco é dobrável: já está recolhido, ou tem bloco com
        indentação maior logo abaixo E passa no critério por extensão (7.1).
        """
        if not bloco.isValid():

            return False

        if self._get_fold_region(bloco) is not None:

            return True

        texto    = bloco.text()
        extensao = os.path.splitext(getattr(self, 'file_path', '') or '')[1].lower()
        if extensao and not _es_dobravel_para_extensao(texto, extensao):

            return False

        proximo = bloco.next()
        while proximo.isValid() and proximo.text().strip() == "":
            proximo = proximo.next()

        if not proximo.isValid():

            return False

        nivel_base = self._nivel_indentacao(bloco.text())
        nivel_prox = self._nivel_indentacao(proximo.text())

        return nivel_prox > nivel_base

    # ══════════════════════════════════════════════════════════════════
    # Persistência do estado de fold (6.1)
    # ══════════════════════════════════════════════════════════════════

    def serializar_fold_state(self) -> list:
        """Retorna lista de blockNumbers (0-based) dos blocos colapsados.
        Persistir em sessao.json junto com o caminho do arquivo."""

        return [r.start_block.blockNumber() for r in self._fold_regions if r.collapsed]

    def restaurar_fold_state(self, linhas: list):
        """Recolhe os blocos nos blockNumbers indicados (0-based).
        Chamar após carregar o conteúdo do arquivo na aba."""
        for num in linhas:
            bloco = self.document().findBlockByNumber(num)
            if bloco.isValid():
                self.recolher_bloco(bloco)

    # ══════════════════════════════════════════════════════════════════
    # Integração com projeto e CodeLens
    # ══════════════════════════════════════════════════════════════════

    def set_projeto(self, caminho: str):
        """Define o projeto ativo e agenda primeira atualização do CodeLens."""
        self._caminho_projeto = caminho
        QTimer.singleShot(500, self._atualizar_code_lens)

    # ⚠️  except genérico vazio
    def _atualizar_code_lens(self):
        """Lê usages do indexador e atualiza contadores na calha."""
        if not getattr(self, "file_path", None):

            return

        indexador = getattr(self.window(), "_indexador", None)
        if not indexador:

            return

        try:
            usages = indexador.consultas.usages_por_arquivo(self.file_path)
            self.area_numeros.atualizar_usages(usages)
        except Exception:
            pass
