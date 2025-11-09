#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""填充实验报告模板的小工具（python-docx 的薄封装）。

模板是老师给的版式：正文 Times New Roman + 宋体 10.5pt、色值 #162C46、
标题 Arial + 微软雅黑 13pt 加粗。这里把「复制模板格式」这件事封装掉，
写报告内容时只关心文字，不关心 run 属性。
"""

from __future__ import annotations

import copy
import re

from docx.enum.table import WD_ALIGN_VERTICAL
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor
from docx.table import Table
from docx.text.paragraph import Paragraph

INK = "162C46"      # 正文深藏青
MUTED = "5D6B7B"    # 次要文字/图注
BLUE = "2F5D8A"     # 强调

ALIGN = {
    "left": WD_ALIGN_PARAGRAPH.LEFT,
    "center": WD_ALIGN_PARAGRAPH.CENTER,
    "right": WD_ALIGN_PARAGRAPH.RIGHT,
    "justify": WD_ALIGN_PARAGRAPH.JUSTIFY,
}

# 宋体没有下标字符 ₂（U+2082），所以在文本里用 _{2} 表示真下标，
# 由 Word 的 vertAlign 实现，既不依赖字符集，排版也更像教材。
_MARKUP = re.compile(r"\*\*(.+?)\*\*|_\{(.+?)\}|\^\{(.+?)\}")


def parse_markup(text: str):
    """把 '**粗体**'、'_{下标}'、'^{上标}' 解析成 [(文本, {样式覆盖}), ...]。"""
    pieces = []
    pos = 0
    for m in _MARKUP.finditer(text):
        if m.start() > pos:
            pieces.append((text[pos:m.start()], {}))
        if m.group(1) is not None:
            pieces.append((m.group(1), {"bold": True}))
        elif m.group(2) is not None:
            pieces.append((m.group(2), {"sub": True}))
        else:
            pieces.append((m.group(3), {"sup": True}))
        pos = m.end()
    if pos < len(text):
        pieces.append((text[pos:], {}))
    return pieces or [(text, {})]


# ---------------------------------------------------------------------------
# run / 段落
# ---------------------------------------------------------------------------
def style_run(run, size: float = 10.5, bold: bool = False, italic: bool = False,
              color: str = INK, ea: str = "宋体", ascii_: str = "Times New Roman",
              sub: bool = False, sup: bool = False) -> None:
    run.font.size = Pt(size)
    run.bold = bold
    run.italic = italic
    run.font.color.rgb = RGBColor.from_string(color)
    run.font.name = ascii_
    if sub:
        run.font.subscript = True
    if sup:
        run.font.superscript = True
    rpr = run._element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.insert(0, rfonts)
    rfonts.set(qn("w:ascii"), ascii_)
    rfonts.set(qn("w:hAnsi"), ascii_)
    rfonts.set(qn("w:eastAsia"), ea)


def new_paragraph(doc, anchor, before: bool = False) -> Paragraph:
    """在 anchor 元素前/后插入一个空段落。

    先用 doc.add_paragraph() 生成（这样 Paragraph.part 能正确解析到文档部件），
    再把 <w:p> 搬到 anchor 旁边；直接构造 CT_P 会因为父节点是 body 元素而取不到 part。
    """
    p = doc.add_paragraph()
    if before:
        anchor.addprevious(p._element)
    else:
        anchor.addnext(p._element)
    return p


def write_para(p: Paragraph, pieces, size: float = 10.5, color: str = INK,
               align: str = "left", space_before: float = 0, space_after: float = 4,
               line: float = 1.4167, indent_first: float | None = None,
               left_indent: float | None = None, keep_with_next: bool = False) -> Paragraph:
    """pieces: 带简单标记的字符串（**粗体**、_{下标}）或 [(文本, {覆盖样式}), ...]。"""
    if isinstance(pieces, str):
        pieces = parse_markup(pieces)
    for text, override in pieces:
        run = p.add_run(text)
        kw = dict(size=size, color=color)
        kw.update(override)
        style_run(run, **kw)
    pf = p.paragraph_format
    pf.alignment = ALIGN[align]
    pf.space_before = Pt(space_before)
    pf.space_after = Pt(space_after)
    pf.line_spacing = line
    if indent_first is not None:
        pf.first_line_indent = Pt(indent_first)
    if left_indent is not None:
        pf.left_indent = Pt(left_indent)
    pf.keep_with_next = keep_with_next
    return p


def add_para(doc, anchor, pieces, **kw) -> Paragraph:
    """在 anchor 后插入一段正文。"""
    return write_para(new_paragraph(doc, anchor), pieces, **kw)


def add_caption(doc, anchor, text: str) -> Paragraph:
    p = new_paragraph(doc, anchor)
    write_para(p, [(text, {})], size=9, color=MUTED, align="center",
               space_before=2, space_after=8, line=1.2)
    return p


def add_picture(doc, anchor, path: str, width_cm: float = 16.0, space_after: float = 2) -> Paragraph:
    p = new_paragraph(doc, anchor)
    p.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(6)
    p.paragraph_format.space_after = Pt(space_after)
    p.paragraph_format.line_spacing = 1.0
    p.add_run().add_picture(path, width=Cm(width_cm))
    return p


def add_heading3(doc, anchor, text: str) -> Paragraph:
    """小节标题：沿用模板正文的字体，但加粗、深色、与下文同页。"""
    p = new_paragraph(doc, anchor)
    write_para(p, [(text, {"bold": True, "size": 10.5, "color": INK})],
               space_before=8, space_after=3, keep_with_next=True)
    return p


def drop_page_breaks(doc) -> None:
    """模板的部分二级标题带「段前分页」直接格式，会把每节都顶到新页、留下大片空白。

    报告内容比空白模板长得多，这里统一去掉，让版式连续；标题本身仍靠边框线区分。
    """
    for p in doc.paragraphs:
        if p.style.name.startswith("Heading"):
            if p.paragraph_format.page_break_before:
                p.paragraph_format.page_break_before = False


def delete(el) -> None:
    el.getparent().remove(el)


# ---------------------------------------------------------------------------
# 表格
# ---------------------------------------------------------------------------
def set_cell(cell, text: str, size: float = 10.5, bold: bool = False,
             color: str = INK, align: str = "left") -> None:
    """写单元格但保留原段落格式；'\\n' 变成段内换行，支持 **粗体** 与 _{下标}。"""
    p = cell.paragraphs[0]
    for r in list(p.runs):
        r._element.getparent().remove(r._element)
    lines = str(text).split("\n")
    for i, line in enumerate(lines):
        if i:
            br = p.add_run()
            br.add_break()
            style_run(br, size=size, bold=bold, color=color)
        for chunk, override in parse_markup(line):
            run = p.add_run(chunk)
            kw = dict(size=size, bold=bold, color=color)
            kw.update(override)
            style_run(run, **kw)
    p.paragraph_format.alignment = ALIGN[align]
    p.paragraph_format.space_before = Pt(1)
    p.paragraph_format.space_after = Pt(1)
    p.paragraph_format.line_spacing = 1.25
    cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER


def clone_row(table: Table) -> int:
    """复制最后一行（连同格式），返回新行下标。"""
    tr = copy.deepcopy(table.rows[-1]._tr)
    table._tbl.append(tr)
    return len(table.rows) - 1


def set_col_widths(table: Table, widths_cm: list) -> None:
    table.autofit = False
    for row in table.rows:
        for i, w in enumerate(widths_cm):
            if i < len(row.cells):
                row.cells[i].width = Cm(w)
    for i, w in enumerate(widths_cm):
        if i < len(table.columns):
            table.columns[i].width = Cm(w)


def _borders(table: Table, color: str = "D5DFEA", sz: int = 4) -> None:
    tblPr = table._tbl.tblPr
    old = tblPr.find(qn("w:tblBorders"))
    if old is not None:
        tblPr.remove(old)
    borders = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        e = OxmlElement(f"w:{edge}")
        e.set(qn("w:val"), "single")
        e.set(qn("w:sz"), str(sz))
        e.set(qn("w:color"), color)
        borders.append(e)
    tblPr.append(borders)


def shade(cell, fill: str = "EEF3F9") -> None:
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill)
    tcPr.append(shd)


def add_table(doc, anchor, header: list, rows: list, widths_cm: list,
              size: float = 9.0, header_fill: str = "162C46",
              header_color: str = "FFFFFF") -> Table:
    """在 anchor 后插入一张新表（样式对齐模板：细边框 + 深藏青表头白字）。"""
    table = doc.add_table(rows=1 + len(rows), cols=len(header))
    table.alignment = 1  # center
    _borders(table)
    set_col_widths(table, widths_cm)
    for i, h in enumerate(header):
        set_cell(table.rows[0].cells[i], h, size=size, bold=True, align="center",
                 color=header_color)
        shade(table.rows[0].cells[i], header_fill)
    for r, values in enumerate(rows, start=1):
        for c, v in enumerate(values):
            align = "center" if c == 0 and len(str(v)) <= 4 else "left"
            set_cell(table.rows[r].cells[c], v, size=size, align=align)
    # 移动到位
    anchor.addnext(table._tbl)
    return table


def find_paragraph(doc, needle: str) -> Paragraph | None:
    for p in doc.paragraphs:
        if needle in p.text:
            return p
    return None


def find_table(doc, first_cell: str) -> Table | None:
    for t in doc.tables:
        try:
            if first_cell in t.rows[0].cells[0].text:
                return t
        except IndexError:
            continue
    return None


def index_of(doc, paragraph: Paragraph) -> int:
    for i, p in enumerate(doc.paragraphs):
        if p._element is paragraph._element:
            return i
    return -1
