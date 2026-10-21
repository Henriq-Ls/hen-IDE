# _EDITOR_/Mult_Linguas/Markdown/outline.py
"""
Preview de Markdown para o PainelOutline.
popular_preview_md() e md_para_html() extraídos de
_EDITOR_/Outline/painel_outline.py na Fase 2.
"""
import re


def popular_preview_md(preview_widget, codigo: str) -> None:
    """Converte Markdown para HTML e exibe no QTextBrowser do outline."""
    from _CONFIGURA_.gerenciador_tema import tema_global
    t       = tema_global()
    fundo   = t.cor("editor.fundo",              "#080808")
    texto   = t.cor("editor.texto",              "#c0c0c0")
    link    = t.cor("editor.sintaxe.string",     "#87CEEB")
    header  = t.cor("painel_outline.cor_classe", "#4EC9B0")
    code_bg = t.cor("interface.inputs",          "#0d1a0d")
    hr_cor  = t.cor("interface.borda",           "#222222")
    html    = md_para_html(codigo, fundo, texto, link, header, code_bg, hr_cor)
    preview_widget.setHtml(html)


def md_para_html(md: str, fundo: str, texto: str, link: str,
                 header: str, code_bg: str, hr_cor: str) -> str:
    """Converte Markdown para HTML sem dependências externas."""

    def _esc(s: str) -> str:
        return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    def _inline(s: str) -> str:
        s = _esc(s)
        s = re.sub(r'\*\*\*(.+?)\*\*\*', r'<b><i>\1</i></b>', s)
        s = re.sub(r'___(.+?)___',        r'<b><i>\1</i></b>', s)
        s = re.sub(r'\*\*(.+?)\*\*',      r'<b>\1</b>', s)
        s = re.sub(r'__(.+?)__',          r'<b>\1</b>', s)
        s = re.sub(r'\*([^\*\n]+?)\*',    r'<i>\1</i>', s)
        s = re.sub(r'_([^_\n]+?)_',       r'<i>\1</i>', s)
        s = re.sub(
            r'`([^`\n]+?)`',
            lambda m: (
                f'<code style="background:{code_bg};padding:1px 3px;'
                f'border-radius:2px;font-family:monospace;">{m.group(1)}</code>'
            ),
            s,
        )
        s = re.sub(
            r'\[([^\]]+?)\]\(([^\)]+?)\)',
            lambda m: f'<a href="{m.group(2)}" style="color:{link};">{m.group(1)}</a>',
            s,
        )
        s = re.sub(r'!\[([^\]]*?)\]\([^\)]+?\)', r'[🖼 \1]', s)
        return s

    lines    = md.replace('\r\n', '\n').replace('\r', '\n').split('\n')
    out      = []
    in_code  = False
    code_buf: list = []
    in_list  = False
    list_tag = 'ul'

    def flush_list():
        nonlocal in_list, list_tag
        if in_list:
            out.append(f'</{list_tag}>')
            in_list = False

    for raw_line in lines:
        line = raw_line.rstrip()

        if line.startswith('```'):
            if not in_code:
                flush_list()
                in_code  = True
                code_buf = []
            else:
                body_code = _esc('\n'.join(code_buf))
                out.append(
                    f'<pre style="background:{code_bg};padding:6px 10px;'
                    f'border-radius:4px;margin:4px 0;'
                    f'font-family:monospace;font-size:11px;'
                    f'white-space:pre-wrap;">{body_code}</pre>'
                )
                in_code = False
            continue

        if in_code:
            code_buf.append(line)
            continue

        m = re.match(r'^(#{1,6})\s+(.*)', line)
        if m:
            flush_list()
            lvl = len(m.group(1))
            ht  = _inline(m.group(2))
            sz  = ['1.5em', '1.3em', '1.15em', '1.05em', '1em', '0.9em'][lvl - 1]
            clr = header if lvl <= 2 else texto
            bdr = (f'border-bottom:1px solid {hr_cor};padding-bottom:4px;'
                   if lvl <= 2 else '')
            out.append(
                f'<h{lvl} style="color:{clr};font-size:{sz};font-weight:bold;'
                f'margin:8px 0 4px 0;{bdr}">{ht}</h{lvl}>'
            )
            continue

        if re.match(r'^(-{3,}|\*{3,}|_{3,})\s*$', line):
            flush_list()
            out.append(
                f'<hr style="border:0;border-top:1px solid {hr_cor};margin:8px 0;">'
            )
            continue

        m = re.match(r'^>\s?(.*)', line)
        if m:
            flush_list()
            out.append(
                f'<blockquote style="border-left:3px solid {hr_cor};'
                f'margin:2px 0 2px 4px;padding:2px 8px;opacity:0.8;">'
                + _inline(m.group(1)) + '</blockquote>'
            )
            continue

        m = re.match(r'^[\-\*\+]\s+(.*)', line)
        if m:
            if not in_list or list_tag != 'ul':
                flush_list()
                out.append('<ul style="margin:3px 0;padding-left:20px;">')
                in_list  = True
                list_tag = 'ul'
            out.append(f'<li style="margin:1px 0;">{_inline(m.group(1))}</li>')
            continue

        m = re.match(r'^\d+\.\s+(.*)', line)
        if m:
            if not in_list or list_tag != 'ol':
                flush_list()
                out.append('<ol style="margin:3px 0;padding-left:20px;">')
                in_list  = True
                list_tag = 'ol'
            out.append(f'<li style="margin:1px 0;">{_inline(m.group(1))}</li>')
            continue

        flush_list()

        if not line:
            out.append('<div style="height:4px;"></div>')
            continue

        out.append(f'<p style="margin:1px 0;line-height:1.5;">{_inline(line)}</p>')

    flush_list()

    body = '\n'.join(out)
    return (
        f'<html><body style="background:{fundo};color:{texto};'
        f'font-family:Segoe UI,Arial,sans-serif;font-size:12px;'
        f'padding:8px 10px;margin:0;line-height:1.4;word-wrap:break-word;">'
        f'{body}</body></html>'
    )
