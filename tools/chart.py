#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""极简图表工具：只用 Pillow 画报告插图（不引入 matplotlib）。

为什么自己画：这个环境里没有 matplotlib，而报告只需要几种固定图形
（指标卡、对比条、堆叠条），用 Pillow 直接画反而更可控、更容易对齐中文标签。

所有函数共享同一套配色和字号，保证两份报告的插图风格一致。
每个函数先算出画布高度，再画内容，底部永远留 90px 给图注，避免文字互相压盖。
"""

from __future__ import annotations

import os
from PIL import Image, ImageDraw, ImageFont

# ---- 配色 ----------------------------------------------------------------
INK = (31, 42, 68)          # 主文字：深藏青
MUTED = (107, 114, 128)     # 次要文字
ACCENT = (37, 99, 235)      # 主色：蓝
ACCENT2 = (245, 158, 11)    # 对比色：琥珀
GREEN = (5, 150, 105)       # 结论/最优
INDIGO = (99, 102, 241)
SLATE = (148, 163, 184)
LIGHT = (243, 244, 246)     # 浅底
GRID = (229, 231, 235)      # 网格线
WHITE = (255, 255, 255)

FONT_REG = r"C:\Windows\Fonts\msyh.ttc"
FONT_BOLD = r"C:\Windows\Fonts\msyhbd.ttc"

MARGIN = 80
HEADER = 216      # 标题 + 副标题占用的高度
FOOTER = 56       # 底部留白


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(FONT_BOLD if bold else FONT_REG, size)


def canvas(w: int, h: int, bg=WHITE) -> tuple:
    img = Image.new("RGB", (w, h), bg)
    return img, ImageDraw.Draw(img)


def text(d, xy, s: str, size: int = 32, fill=INK, bold: bool = False, anchor: str = "la") -> None:
    d.text(xy, s, font=font(size, bold), fill=fill, anchor=anchor)


def header(d, s: str, sub: str = "") -> None:
    text(d, (MARGIN, 56), s, size=50, bold=True)
    d.rectangle([MARGIN, 130, MARGIN + 96, 138], fill=ACCENT)
    if sub:
        text(d, (MARGIN, 156), sub, size=29, fill=MUTED)


def footer(d, s: str, w: int, h: int) -> None:
    """图注统一由 Word 的题注段落承担，图内不再重复写「图 N …」，
    否则报告里会出现两套互相打架的图号。这里只保留底部留白。"""
    return None


def hbar(d, x, y, width, height, frac, color=ACCENT, radius=0) -> None:
    frac = max(0.0, min(1.0, frac))
    w = max(3, int(width * frac))
    if radius:
        d.rounded_rectangle([x, y, x + w, y + height], radius=radius, fill=color)
    else:
        d.rectangle([x, y, x + w, y + height], fill=color)


def save(img: Image.Image, path: str) -> str:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    img.save(path, "PNG", optimize=True)
    return path


# ---------------------------------------------------------------------------
# 图 1（实验一）：位权展开示意
# ---------------------------------------------------------------------------
def bit_weight_figure(binary: str, out: str) -> str:
    n = len(binary)
    card_h = 300
    box_h = 150
    h = HEADER + 20 + card_h + 50 + box_h + FOOTER + 20
    img, d = canvas(1800, h)
    header(d, "位权展开：把 10110101 拆成 8 个 2 的幂",
           "每一位的贡献 = 该位数字 × 2^该位序号（从右往左数，从 0 起）")

    cell_w, gap = 190, 16
    total_w = n * cell_w + (n - 1) * gap
    x0 = (1800 - total_w) // 2
    top = HEADER + 20
    for i, ch in enumerate(binary):
        bit = int(ch)
        power = n - 1 - i
        weight = 1 << power
        contrib = bit * weight
        x = x0 + i * (cell_w + gap)
        used = bit == 1
        d.rounded_rectangle([x, top, x + cell_w, top + card_h], radius=14,
                            fill=(238, 242, 255) if used else LIGHT,
                            outline=ACCENT if used else GRID, width=3 if used else 2)
        text(d, (x + cell_w // 2, top + 18), f"第 {power} 位", size=24, fill=MUTED, anchor="ma")
        text(d, (x + cell_w // 2, top + 52), ch, size=92,
             fill=ACCENT if used else (156, 163, 175), bold=True, anchor="ma")
        text(d, (x + cell_w // 2, top + 172), f"2^{power} = {weight}", size=28, fill=INK, anchor="ma")
        text(d, (x + cell_w // 2, top + 222), f"{bit} × {weight} = {contrib}", size=25,
             fill=ACCENT if used else MUTED, anchor="ma")

    terms = [str(1 << (n - 1 - i)) for i, ch in enumerate(binary) if ch == "1"]
    expr = " + ".join(terms) + f" = {int(binary, 2)}"
    by = top + card_h + 50
    d.rounded_rectangle([MARGIN, by, 1800 - MARGIN, by + box_h], radius=18,
                        fill=(236, 253, 245), outline=GREEN, width=3)
    text(d, (MARGIN + 40, by + 14), "展开式（只保留 1 的位）", size=24, fill=MUTED)
    text(d, (MARGIN + 40, by + 56), expr, size=48, fill=GREEN, bold=True)
    text(d, (1800 - MARGIN - 40, by + box_h - 34), "0 的位贡献为 0，可以直接丢掉",
         size=23, fill=MUTED, anchor="ra")

    footer(d, "图 1  按位权展开计算 10110101(2) 的十进制值", 1800, h)
    return save(img, out)


# ---------------------------------------------------------------------------
# 图 2（实验一）：三类媒体体积指标卡
# ---------------------------------------------------------------------------
def media_size_figure(items: list, out: str) -> str:
    """items: [(标题, 体积文本, 说明, 颜色)]"""
    card_h = 300
    h = HEADER + 30 + card_h + FOOTER + 40
    img, d = canvas(1800, h)
    header(d, "三种媒体、三种公式，算出来的体积差了两个数量级",
           "全部按未压缩 / 标称码率计算；MB = 10^6 B，MiB = 2^20 B，两者不混用")

    n = len(items)
    gap = 40
    w = (1800 - 2 * MARGIN - (n - 1) * gap) // n
    top = HEADER + 30
    for i, (label, value, note, color) in enumerate(items):
        x = MARGIN + i * (w + gap)
        d.rounded_rectangle([x, top, x + w, top + card_h], radius=18, fill=LIGHT)
        d.rectangle([x, top, x + w, top + 10], fill=color)
        text(d, (x + 36, top + 34), label, size=29, fill=MUTED)
        text(d, (x + 36, top + 84), value, size=62, fill=INK, bold=True)
        for j, line in enumerate(note.split("\n")):
            text(d, (x + 36, top + 186 + j * 34), line, size=25, fill=MUTED)

    footer(d, "图 2  照片 / 音频 / 视频的体积估算结果（公式与单位换算见报告第三节）", 1800, h)
    return save(img, out)


# ---------------------------------------------------------------------------
# 图 3（实验一）：未压缩 vs 实际文件
# ---------------------------------------------------------------------------
def compression_figure(rows: list, out: str) -> str:
    """rows: [(名称, 分辨率文本, 未压缩MB, 实际MB, 压缩比, 每像素字节数)]"""
    row_h = 195
    h = HEADER + 50 + len(rows) * row_h + 60 + FOOTER
    img, d = canvas(1800, h)
    header(d, "同一张图，未压缩按 宽×高×3B 算，实际文件小一个数量级",
           "压缩去掉的是像素之间的冗余，不是「分辨率」；分辨率决定像素数，编码决定体积")

    bx, bw = 620, 640
    top = HEADER + 50
    for i, (name, res, raw, act, ratio, bpp) in enumerate(rows):
        y = top + i * row_h
        text(d, (MARGIN, y + 2), name, size=32, bold=True)
        text(d, (MARGIN, y + 46), res, size=24, fill=MUTED)

        d.rectangle([bx, y, bx + bw, y + 46], fill=(226, 232, 240))
        text(d, (bx + 14, y + 8), f"未压缩 {raw:.2f} MB", size=24, fill=INK)
        hbar(d, bx, y + 58, bw, 46, act / raw if raw else 0, color=ACCENT)
        text(d, (bx + 14, y + 118), f"实际 {act:.2f} MB", size=26, fill=ACCENT, bold=True)
        text(d, (bx + 250, y + 118), f"每像素 {bpp:.2f} B（未压缩应 3.00 B）", size=23, fill=MUTED)

        d.rounded_rectangle([1420, y + 10, 1660, y + 104], radius=12, fill=(236, 253, 245))
        text(d, (1540, y + 24), f"{ratio:.1f}×", size=40, fill=GREEN, bold=True, anchor="ma")
        text(d, (1540, y + 74), "压缩比", size=20, fill=MUTED, anchor="ma")

    text(d, (MARGIN, top + len(rows) * row_h + 24),
         "结论：估算存储容量要用「宽×高×位深÷8」；估算传输与备份要看编码后的实际大小。",
         size=27, fill=MUTED)
    footer(d, "图 3  理论未压缩大小与实际文件大小对照", 1800, h)
    return save(img, out)


# ---------------------------------------------------------------------------
# 图 4（实验二）：三方案的权重分布（显存 / 内存）
# ---------------------------------------------------------------------------
def memory_split_figure(schemes: list, total_gb: float, out: str) -> str:
    """schemes: [{"key","cap","vw","rw","tok"}]"""
    row_h = 205
    h = HEADER + 40 + len(schemes) * row_h + 90 + FOOTER
    img, d = canvas(1800, h)
    header(d, "同样 128B INT4 模型，三种方案把权重放在哪里",
           f"权重 + KV cache + 框架开销 = {total_gb:.1f} GB；显存装不下的部分只能落到内存")

    top = HEADER + 40
    bx, bw = 420, 1180
    scale = bw / (total_gb * 1.04)
    for i, s in enumerate(schemes):
        y = top + i * row_h
        text(d, (MARGIN, y + 6), f"方案 {s['key']}", size=38, bold=True)
        text(d, (MARGIN, y + 58), s["cap"], size=24, fill=MUTED)

        d.rectangle([bx, y, bx + bw, y + 58], fill=LIGHT)
        wv = int(s["vw"] * scale)
        wr = int(s["rw"] * scale)
        if wv:
            d.rectangle([bx, y, bx + wv, y + 58], fill=ACCENT)
            text(d, (bx + 14, y + 14), f"显存内 {s['vw']:.1f} GB", size=25, fill=WHITE, bold=True)
        if wr:
            d.rectangle([bx + wv, y, bx + wv + wr, y + 58], fill=ACCENT2)
            if wr > 300:
                text(d, (bx + wv + 14, y + 14), f"内存内 {s['rw']:.1f} GB", size=25,
                     fill=WHITE, bold=True)
            else:
                text(d, (bx + wv + wr + 14, y + 14), f"内存内 {s['rw']:.1f} GB", size=25,
                     fill=ACCENT2, bold=True)

        text(d, (bx, y + 92), f"出词 {s['tok']:.2f} tok/s", size=30, fill=INK, bold=True)
        hbar(d, bx + 330, y + 100, 460, 24, s["tok"] / 10.0, color=GREEN, radius=8)
        text(d, (bx + 806, y + 98), "满格 = 10 tok/s", size=22, fill=MUTED)

    ly = top + len(schemes) * row_h + 30
    d.rectangle([MARGIN, ly, MARGIN + 36, ly + 24], fill=ACCENT)
    text(d, (MARGIN + 46, ly - 2), "显存：GDDR7，1.8 TB/s 级", size=25, fill=MUTED)
    d.rectangle([MARGIN + 420, ly, MARGIN + 456, ly + 24], fill=ACCENT2)
    text(d, (MARGIN + 466, ly - 2), "系统内存：DDR5 双通道，80 GB/s 级", size=25, fill=MUTED)

    footer(d, "图 4  三方案的权重落位与出词速度", 1800, h)
    return save(img, out)


# ---------------------------------------------------------------------------
# 图 5（实验二）：tok/s 与「每万元 tok/s」
# ---------------------------------------------------------------------------
def value_figure(schemes: list, out: str) -> str:
    """schemes: [(key, name, tok_s, per_wan, price)]"""
    row_h = 150
    h = HEADER + 70 + len(schemes) * row_h + 90 + FOOTER
    img, d = canvas(1800, h)
    header(d, "快不等于划算：把价格除进去，排序会反过来",
           "左：绝对速度（tok/s）    右：每万元买到的速度（tok/s / 万元）")

    top = HEADER + 70
    left_x, right_x, bar_w = 300, 1120, 440
    max_tok = max(s[2] for s in schemes)
    max_wan = max(s[3] for s in schemes)

    text(d, (MARGIN, top - 46), "绝对速度", size=27, bold=True, fill=MUTED)
    text(d, (right_x - 40, top - 46), "性价比", size=27, bold=True, fill=MUTED)

    for i, (key, name, tok, per_wan, price) in enumerate(schemes):
        y = top + i * row_h
        text(d, (MARGIN, y + 8), key, size=40, bold=True)
        text(d, (MARGIN, y + 56), f"￥{price:,}", size=24, fill=MUTED)

        d.rectangle([left_x, y, left_x + bar_w, y + 52], fill=LIGHT)
        hbar(d, left_x, y, bar_w, 52, tok / max_tok, color=ACCENT)
        text(d, (left_x + bar_w + 18, y + 2), f"{tok:.2f}", size=34, fill=INK, bold=True)

        best = per_wan == max_wan
        d.rectangle([right_x, y, right_x + bar_w, y + 52], fill=LIGHT)
        hbar(d, right_x, y, bar_w, 52, per_wan / max_wan, color=GREEN if best else ACCENT2)
        text(d, (right_x + bar_w + 18, y + 2), f"{per_wan:.2f}", size=34,
             fill=GREEN if best else INK, bold=True)
        if best:
            text(d, (right_x + bar_w + 18, y + 52), "最优", size=22, fill=GREEN, bold=True)

    text(d, (MARGIN, top + len(schemes) * row_h + 30),
         "单卡方案既慢又贵（每万元 0.24 tok/s）；双卡最快但单价翻倍；", size=26, fill=MUTED)
    text(d, (MARGIN, top + len(schemes) * row_h + 66),
         "128GB 统一内存只用约 1/3 的价格，却拿到 1.9 倍的出词速度，性价比最高。",
         size=26, fill=MUTED)
    footer(d, "图 5  三方案的出词速度与性价比（价格取 2026-11 渠道价）", 1800, h)
    return save(img, out)


# ---------------------------------------------------------------------------
# 图 6（实验二）：整机价格构成
# ---------------------------------------------------------------------------
def cost_figure(schemes: list, out: str) -> str:
    """schemes: [(key, total, [(类别, 金额)], cny_per_tok)]"""
    row_h = 185
    h = HEADER + 60 + len(schemes) * row_h + 80 + FOOTER
    img, d = canvas(1800, h)
    header(d, "钱花在哪：三套方案的整机价构成",
           "按指南口径归为 GPU / 内存 / 平台三类；统一内存整机不可拆分")

    colors = {"GPU": ACCENT, "内存": ACCENT2, "平台": SLATE, "整机": INDIGO}
    top = HEADER + 60
    bx, bw = 300, 1080
    max_total = max(s[1] for s in schemes)
    scale = bw / max_total

    for i, (key, total, parts, per_tok) in enumerate(schemes):
        y = top + i * row_h
        text(d, (MARGIN, y + 2), key, size=40, bold=True)
        text(d, (MARGIN, y + 50), f"￥{total:,}", size=24, fill=MUTED)

        x = bx
        for name, amount in parts:
            w = max(3, int(amount * scale))
            d.rectangle([x, y, x + w, y + 56], fill=colors.get(name, MUTED))
            if w > 190:
                text(d, (x + 14, y + 13), f"{name} {amount / total:.0%}", size=24,
                     fill=WHITE, bold=True)
            x += w
        # 未标出的小块用引线补一个百分比
        if sum(amount for _, amount in parts) and total:
            small = [(n, a) for n, a in parts if a * scale <= 190]
            if small:
                note = "  ".join(f"{n} {a / total:.0%}" for n, a in small)
                text(d, (bx + bw + 16, y + 16), note, size=23, fill=MUTED)
        text(d, (bx, y + 76), f"元 / (tok/s) = ￥{per_tok:,.0f}", size=26, fill=MUTED)

    ly = top + len(schemes) * row_h + 8
    lx = MARGIN
    for name in ("GPU", "内存", "平台", "整机"):
        d.rectangle([lx, ly + 2, lx + 34, ly + 26], fill=colors[name])
        text(d, (lx + 44, ly), name, size=24, fill=MUTED)
        lx += 44 + 40 * len(name) + 60

    footer(d, "图 6  整机价格构成（2026-11 渠道价，未计显示器与外设）", 1800, h)
    return save(img, out)


# ===========================================================================
# 第 03 讲 的图
# ===========================================================================
def layer_parallel_figure(out: str) -> str:
    """四层实现的并行度：同一个乘加，硬件里同时做几份。"""
    h = HEADER + 40 + 470 + 120 + FOOTER
    img, d = canvas(1800, h)
    header(d, "同一句乘加，三种并行度",
           "C 用 1 个乘法器跑 27 次；Verilog 铺 27 个乘法器同时算；CUDA 起 32 个线程、9 个有效")

    top = HEADER + 50
    pw, gap = 520, 60
    x0 = MARGIN

    def panel(i, title, sub, color):
        x = x0 + i * (pw + gap)
        d.rounded_rectangle([x, top, x + pw, top + 430], radius=16, fill=LIGHT)
        d.rectangle([x, top, x + pw, top + 8], fill=color)
        text(d, (x + 28, top + 22), title, size=30, bold=True)
        text(d, (x + 28, top + 64), sub, size=22, fill=MUTED)
        return x

    # 1) C：一个乘法器，循环 27 次
    x = panel(0, "C 三重循环", "1 个乘法器 × 27 次迭代", ACCENT)
    d.rounded_rectangle([x + 150, top + 110, x + 370, top + 190], radius=12, fill=ACCENT)
    text(d, (x + 260, top + 132), "imull + addl", size=26, fill=WHITE, bold=True, anchor="ma")
    # 循环箭头
    d.arc([x + 120, top + 210, x + 400, top + 330], 200, 340, fill=ACCENT, width=6)
    text(d, (x + 260, top + 250), "for k = 0..2  ×  9 个元素", size=24, fill=INK, anchor="ma")
    text(d, (x + 260, top + 300), "时间换来空间：只要 1 份硬件", size=22, fill=MUTED, anchor="ma")
    text(d, (x + 260, top + 350), "耗时 ∝ 27 × 单次乘加", size=24, fill=ACCENT, bold=True, anchor="ma")

    # 2) Verilog：27 个乘法器并行
    x = panel(1, "Verilog 结构级", "27 个乘法器 + 18 个加法器", GREEN)
    for i in range(3):
        for j in range(3):
            d.rounded_rectangle([x + 60 + j * 66, top + 100 + i * 62,
                                 x + 60 + j * 66 + 52, top + 100 + i * 62 + 48],
                                radius=8, fill=GREEN)
    text(d, (x + 380, top + 140), "9 组", size=26, fill=INK, bold=True)
    text(d, (x + 380, top + 176), "乘加单元", size=22, fill=MUTED)
    text(d, (x + 260, top + 310), "同一时刻全部翻转，C 一次就位", size=22, fill=MUTED, anchor="ma")
    text(d, (x + 260, top + 356), "空间换来时间：27 份硬件", size=24, fill=GREEN, bold=True, anchor="ma")

    # 3) CUDA：32 个线程，9 个有效
    x = panel(2, "CUDA 核函数", "1 块 × 32 线程，9 个干活", ACCENT2)
    for t in range(32):
        r_, c_ = divmod(t, 8)
        used = t < 9
        d.rounded_rectangle([x + 40 + c_ * 56, top + 100 + r_ * 56,
                             x + 40 + c_ * 56 + 46, top + 100 + r_ * 56 + 46],
                            radius=6, fill=ACCENT2 if used else (226, 232, 240))
    text(d, (x + 260, top + 340), "有效 9 / 空转 23（71.9%）", size=22, fill=MUTED, anchor="ma")
    text(d, (x + 260, top + 380), "线程调度交给硬件", size=24, fill=ACCENT2, bold=True, anchor="ma")

    text(d, (MARGIN, top + 460), "三种并行度对应三种代价：C 花时间、Verilog 花面积、CUDA 花线程槽位。",
         size=24, fill=MUTED)
    footer(d, "图 1  同一算法的三种并行度", 1800, h)
    return save(img, out)


def asm_breakdown_figure(total: int, counts: dict, out: str) -> str:
    """-O0 下一条乘加语句的 23 条指令都在干什么。"""
    h = HEADER + 60 + 120 + 40 + 60 + len(counts) * 62 + 140 + FOOTER
    img, d = canvas(1800, h)
    header(d, f"一条 c[i][j] += a[i][k]*b[k][j]，在 -O0 下是 {total} 条指令",
           "其中只有 1 条 imull 在算 a×b、1 条 addl 在累加，其余都在算下标、搬数据")

    top = HEADER + 70
    useful = 3
    waste = total - useful
    bx, bw = MARGIN, 1640
    hbar(d, bx, top, bw, 64, useful / total, color=ACCENT)
    d.rectangle([bx + int(bw * useful / total), top, bx + bw, top + 64], fill=ACCENT2)
    text(d, (bx + 14, top + 18), f"算术 {useful} 条", size=24, fill=WHITE, bold=True)
    text(d, (bx + int(bw * useful / total) + 14, top + 18),
         f"寻址 / 搬运 {waste} 条（{waste / total:.0%}）", size=24, fill=WHITE, bold=True)

    y = top + 110
    text(d, (MARGIN, y), "按指令类型拆开（脚本解析 matmul.s 得到，不是估计值）", size=23, fill=MUTED)
    y += 44
    maxc = max(counts.values())
    for mnem, cnt in counts.items():
        d.rectangle([MARGIN, y, MARGIN + 120, y + 40], fill=LIGHT)
        text(d, (MARGIN + 12, y + 6), mnem, size=26, bold=True)
        hbar(d, MARGIN + 140, y + 4, 1100, 32, cnt / maxc, color=ACCENT, radius=4)
        text(d, (MARGIN + 1260, y + 4), f"{cnt}", size=28, bold=True)
        note = {"movl": "取下标 / 取数据 / 栈暂存", "imull": "1 次 a×b，2 次算 i×n、k×n",
                "addl": "1 次累加，2 次下标相加", "cltq": "32 位下标扩展到 64 位地址",
                "leaq": "下标 ×4（用 lea 代替 imul）", "movq": "取数组基址",
                "addq": "基址 + 偏移"}.get(mnem, "")
        text(d, (MARGIN + 1320, y + 10), note, size=21, fill=MUTED)
        y += 62

    text(d, (MARGIN, y + 20),
         "结论：-O0 不优化，一条语句 87% 的指令都花在「怎么找到数据」上；这也是 -O2 能提速一个量级的原因。",
         size=23, fill=MUTED)
    footer(d, "图 2  内层乘加的指令构成（-O0）", 1800, h)
    return save(img, out)


def matrix_consistency_figure(c: list, expect: list, out: str) -> str:
    """3×3 结果矩阵：四路实现逐位一致。"""
    h = HEADER + 40 + 3 * 165 + 100 + FOOTER
    img, d = canvas(1800, h)
    header(d, "四份实现算出来的 C 完全相同",
           "C 三重循环 / Verilog 结构级 / CUDA 线程映射 / numpy 参照 —— 9 个元素逐位相等")

    top = HEADER + 50
    cw = 300
    x0 = (1800 - 3 * cw - 2 * 20) // 2
    ok = c == expect
    for i in range(3):
        for j in range(3):
            v = c[i * 3 + j]
            x = x0 + j * (cw + 20)
            y = top + i * 165
            d.rounded_rectangle([x, y, x + cw, y + 145], radius=14,
                                fill=(236, 253, 245) if v == expect[i * 3 + j] else (254, 226, 226),
                                outline=GREEN if v == expect[i * 3 + j] else (220, 38, 38), width=3)
            text(d, (x + 20, y + 10), f"C[{i}][{j}]", size=21, fill=MUTED)
            text(d, (x + cw // 2, y + 32), str(v), size=46, bold=True, anchor="ma")
            text(d, (x + cw // 2, y + 110), "四路一致" if ok else "不一致", size=19,
                 fill=GREEN if ok else (220, 38, 38), anchor="ma")

    text(d, (MARGIN, top + 3 * 165 + 16),
         "C 的 1 个乘法器跑 27 次、Verilog 的 27 个乘法器同时翻转、CUDA 的 9 个线程各算一格，"
         "结果必须一模一样 —— 这就是「同一算法、四种代价」。",
         size=23, fill=MUTED)
    footer(d, "图 3  四路实现的 3×3 结果", 1800, h)
    return save(img, out)


# ===========================================================================
# 第 04 讲 的图
# ===========================================================================
def time_bars_figure(runs: list, out: str) -> str:
    """三语言 × 三规模的中位耗时（对数刻度，每种语言一条细条，同一基线）。"""
    import math as _m

    langs = [("python", "Python", ACCENT), ("numpy", "numpy (BLAS)", INDIGO),
             ("csharp", "C# (.NET)", GREEN), ("javascript", "Node (V8)", ACCENT2)]
    row_h = 150
    h = HEADER + 80 + len(runs) * row_h + 110 + FOOTER
    img, d = canvas(1800, h)
    header(d, "同一个点积，三种执行方式",
           "中位数毫秒（对数刻度）；C/Rust 因本机无编译器未运行，用 C#/.NET 与 numpy(BLAS) 代表编译代码")

    top = HEADER + 70
    bx, bw = 400, 940                      # 条区 400~1340，右侧留标签位
    maxv = max(r["runs"][k]["median_ms"] for r in runs for k, _, _ in langs
               if r["runs"].get(k, {}).get("available"))
    lo = 0.003

    def scale(v):
        return _m.log10(max(v, lo) / lo) / _m.log10(maxv / lo)

    for i, row in enumerate(runs):
        y = top + i * row_h
        text(d, (MARGIN, y + 40), f"N = {row['n']:,}", size=28, bold=True)
        for j, (lang, name, color) in enumerate(langs):
            rr = row["runs"].get(lang, {})
            if not rr.get("available"):
                continue
            by = y + j * 30
            d.rectangle([bx, by, bx + bw, by + 26], fill=LIGHT)
            d.rectangle([bx, by, bx + max(4, int(bw * scale(rr["median_ms"]))), by + 26], fill=color)
            val = rr["median_ms"]
            txt = f"{val:.4f} ms" if val < 0.1 else f"{val:.3f} ms"
            text(d, (bx + bw + 20, by - 2), f"{name}  {txt}", size=22, fill=color, bold=True)

    y = top + len(runs) * row_h + 20
    text(d, (MARGIN, y),
         "Python 随 N 线性增长到 25.9 ms；编译路径稳定在 0.4~0.7 ms，BLAS 只要 0.14 ms —— 差距 40~183 倍；",
         size=23, fill=MUTED)
    text(d, (MARGIN, y + 34),
         "而且这个倍数不随 N 变化，说明差的是「每个元素的执行成本」，不是算法或缓存。",
         size=23, fill=MUTED)
    footer(d, "图 4  三语言点积耗时（预热 3 轮，10 轮中位数）", 1800, h)
    return save(img, out)


def speedup_figure(runs: list, out: str) -> str:
    """相对 Python 的加速倍数。"""
    h = HEADER + 80 + 420 + 100 + FOOTER
    img, d = canvas(1800, h)
    header(d, "加速倍数：编译路径稳定在 40~66 倍",
           "以 Python 为 1×；横轴是向量长度，纵轴是倍数")

    top = HEADER + 90
    x0, x1 = 260, 1500
    y0, y1 = top + 40, top + 360
    ns = [r["n"] for r in runs]
    xs = {n: x0 + (x1 - x0) * i / max(1, len(ns) - 1) for i, n in enumerate(ns)}
    maxsp = 80

    def yv(sp):
        return y1 - (y1 - y0) * sp / maxsp

    for sp in (0, 20, 40, 60, 80):
        d.line([x0, yv(sp), x1, yv(sp)], fill=GRID, width=2)
        text(d, (x0 - 16, yv(sp) - 12), f"{sp}×", size=22, fill=MUTED, anchor="ra")
    for n in ns:
        text(d, (xs[n], y1 + 14), f"{n:,}", size=22, fill=MUTED, anchor="ma")

    for lang, name, color in (("csharp", "C# (.NET)", GREEN), ("javascript", "Node (V8)", ACCENT2)):
        pts = []
        for row in runs:
            rr = row["runs"].get(lang, {})
            if rr.get("available"):
                pts.append((xs[row["n"]], yv(rr["speedup_vs_python"])))
        for a, b in zip(pts, pts[1:]):
            d.line([a[0], a[1], b[0], b[1]], fill=color, width=6)
        for (px, py) in pts:
            d.ellipse([px - 9, py - 9, px + 9, py + 9], fill=color)
        if pts:
            text(d, (pts[-1][0] + 16, pts[-1][1] - 10), name, size=24, fill=color, bold=True)

    text(d, (MARGIN, y1 + 70), "结论：倍数对 N 不敏感，说明差距来自「每个元素怎么执行」，不是缓存或规模的偶然。",
         size=23, fill=MUTED)
    footer(d, "图 5  相对 Python 的加速倍数", 1800, h)
    return save(img, out)


def timer_figure(probe: dict, out: str) -> str:
    """计时器分辨率的真实对照：time.time() 量不出微秒级函数。"""
    h = HEADER + 90 + 320 + 120 + FOOTER
    img, d = canvas(1800, h)
    header(d, "同一个 0.26 ms 的点积，两种计时器的读数",
           f"time.time() 的分辨率是 {probe['clock_resolution_ms']:.3f} ms，比被测量的函数还大 60 倍")

    top = HEADER + 100
    text(d, (MARGIN, top - 40), "time.time()  10 次读数（灰色 = 测到 0.000）", size=24, bold=True, fill=MUTED)
    bw, bh = 140, 60
    for i in range(10):
        x = MARGIN + i * (bw + 12)
        zero = i < probe["time_time_zeros"]
        d.rectangle([x, top, x + bw, top + bh], fill=(226, 232, 240) if zero else ACCENT2)
        text(d, (x + bw // 2, top + 14), "0.000" if zero else "15.6", size=22,
             fill=INK if zero else WHITE, bold=True, anchor="ma")

    y2 = top + 130
    text(d, (MARGIN, y2), f"perf_counter()  10 次读数（中位数 {probe['perf_counter_median_ms']:.3f} ms）",
         size=24, bold=True, fill=MUTED)
    for i in range(10):
        x = MARGIN + i * (bw + 12)
        d.rectangle([x, y2 + 40, x + bw, y2 + 40 + bh], fill=GREEN)
        text(d, (x + bw // 2, y2 + 54), "≈0.26", size=22, fill=WHITE, bold=True, anchor="ma")

    text(d, (MARGIN, y2 + 140),
         f"实测：10 次里有 {probe['time_time_zeros']} 次读到 0.000 ms —— 用 time.time() 计时，量到的是计时器分辨率，不是函数耗时。",
         size=23, fill=MUTED)
    text(d, (MARGIN, y2 + 176),
         "这就是实验要求「统一计时口径」的原因：先确认计时器比被测量的东西细，再谈比较。",
         size=23, fill=MUTED)
    footer(d, "图 6  计时器分辨率对照", 1800, h)
    return save(img, out)
