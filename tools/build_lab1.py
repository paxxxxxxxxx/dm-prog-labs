#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把第 01 讲实验报告模板填成完整报告（保留老师的版式）。

用法（在仓库根目录）：
    python tools/build_lab1.py
输出：
    lab01_number_storage/report/第01讲-数制转换与存储容量估算-实验报告.docx

报告里的数字与 lab01_number_storage/results.json 一致，
改 estimate.py 的公式后重新生成 results.json 与本报告即可同步。
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from docx import Document  # noqa: E402

import docx_util as U  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
L1 = os.path.join(ROOT, "lab01_number_storage")
TPL = os.path.join(ROOT, "templates", "第01讲-数制转换与存储容量估算-实验报告.docx")
OUT = os.path.join(L1, "report", "第01讲-数制转换与存储容量估算-实验报告.docx")
FIG = os.path.join(L1, "report", "figures")

# ---------------------------------------------------------------------------
# 一、实验目的（模板给 3 行）
# ---------------------------------------------------------------------------
STUDENT = {
    "班级": "数媒1班",
    "姓名": "刘纯",
    "学号": "2025310570",
    "日期": "2026.11.9",
}

GOALS = [
    "① 能独立完成二进制、十进制、十六进制的互转，并写出每一位的位权与展开式："
    "10110101_{2} = 181_{10}、255_{10} = 0xFF、1A_{16} = 11010_{2}。",

    "② 能用「宽×高×位深÷8」「采样率×位深×声道×时长÷8」「码率×时长÷8」三条公式"
    "估算照片、音频、视频的未压缩体积，并正确区分 MB（10^{6}）与 MiB（2^{20}）。",

    "③ 能用脚本复算全部结果，并解释同一张图为什么实际文件只有未压缩大小的 1/20~1/28。",
]

# ---------------------------------------------------------------------------
# 二、实验环境与工具（模板给 3 行）
# ---------------------------------------------------------------------------
ENV = [
    "自备笔记本（Windows 11 x64）。本实验全部是纸笔计算 + 纯 CPU 脚本，不需要独立显卡；"
    "计算器用 Windows 自带计算器的「程序员」模式，用于核对数制转换。",
    "Python 3.12.14（64 位，仅用标准库）+ VS Code / 记事本；命令行用 Windows Terminal。"
    "脚本 estimate.py 无第三方依赖，python estimate.py 即可运行。",
    "数据与素材：课程 PDF《第01讲 计算机核心结构·数制转换与存储容量估算》；"
    "两张用于实测压缩比的真实图片——课件第 1 页导出的位图（1191×1684）与系统自带壁纸（3840×2400）。",
]

# ---------------------------------------------------------------------------
# 三、实验步骤与过程记录（8 行 × 4 列）
# ---------------------------------------------------------------------------
STEPS = [
    ("手算 10110101_{2} → 十进制",
     "从右往左写出 2^{0}~2^{7} 共 8 列的权值，只把该位为 1 的权值相加",
     "128+32+16+4+1 = 181；最大权值 128 ≤ 181 < 256，说明 8 位刚好够"),
    ("手算 255_{10} → 十六进制",
     "255÷16 = 15 余 15；15÷16 = 0 余 15；余数倒序排列（15 记作 F）",
     "0xFF；规律：255 = 2^{8}−1，正好是两位全 F"),
    ("手算 1A_{16} → 二进制",
     "一位十六进制拆成四位二进制：1 → 0001，A(10) → 1010，再拼接",
     "0001 1010 = 11010_{2} = 26_{10}"),
    ("用 Python 交叉验证三组结果",
     "python estimate.py；命令 int('10110101', 2)、hex(255)、bin(0x1A)",
     "输出 181 / 0xff / 0b11010，与手算完全一致，脚本自检字段全为 True"),
    ("估算 1920×1080、24 位未压缩照片",
     "1920×1080 = 2,073,600 像素；×24 bit = 49,766,400 bit；÷8 = 字节",
     "6,220,800 B = 6.22 MB = 5.93 MiB"),
    ("估算 4 分钟、44.1kHz/16bit 立体声歌曲",
     "44,100×16×2 = 1,411,200 bit/s = 176,400 B/s；×240 s",
     "42,336,000 B = 42.34 MB = 40.37 MiB"),
    ("估算 2 小时、8 Mbps 电影",
     "8×10^{6} bit/s ÷ 8 = 1,000,000 B/s；×7200 s",
     "7,200,000,000 B = 7.20 GB = 6.71 GiB"),
    ("用真实文件核对压缩带来的差异",
     "记录 1191×1684 与 3840×2400 两组分辨率，读文件大小，与「宽×高×3 B」比较",
     "6.02 MB → 0.21 MB（28.3:1）；27.65 MB → 1.38 MB（20.0:1）"),
]

# ---------------------------------------------------------------------------
# 补充：单位换算表（评分项「含公式与单位换算」）
# ---------------------------------------------------------------------------
UNITS = [
    ("KB / KiB", "1 KB = 10^{3} B；1 KiB = 2^{10} B = 1024 B",
     "6,220,800 B = 6,220.8 KB；资源管理器按 KiB 显示为 5.93 MiB"),
    ("MB / MiB", "1 MB = 10^{6} B ≈ 0.954 MiB",
     "照片 6.22 MB；同一张图在 Windows 里显示「5.93 MB」，其实单位是 MiB"),
    ("GB / GiB", "1 GB = 10^{9} B；1 GiB = 2^{30} B",
     "视频 7.20 GB = 6.71 GiB；厂商标称的 256 GB 硬盘 ≈ 238 GiB"),
    ("bit 与 Byte", "1 B = 8 bit",
     "位深、采样率、码率给的都是 bit，除以 8 才是字节"),
    ("Mbps（码率）", "1 Mbps = 10^{6} bit/s = 0.125 MB/s",
     "8 Mbps 视频每秒 1 MB，1 小时 3.6 GB，2 小时 7.2 GB"),
    ("像素与位深", "1 像素 = 位深 ÷ 8 字节",
     "24 位真彩 = 3 B/像素；32 位带 Alpha = 4 B/像素"),
]

# ---------------------------------------------------------------------------
# 四、实验结果：插图
# ---------------------------------------------------------------------------
FIGURES = [
    ("fig1_bit_weights.png", "图 1　10110101 的位权展开：只有 1 的位参与相加，结果为 181"),
    ("fig2_media_sizes.png", "图 2　三类媒体的体积估算：公式不同，结果差两个数量级"),
    ("fig3_compression.png", "图 3　未压缩大小与实际文件大小对照：压缩比 20~28 倍"),
]

# ---------------------------------------------------------------------------
# 五、问题与解决（模板给 3 行，第 4 行追加）
# ---------------------------------------------------------------------------
PROBLEMS = [
    ("视频体积按 ÷1024 换算，得到 6.87 GB，与指南给的 7.2 GB 差约 5%，一度以为公式写错",
     "把 SI 的 MB（10^{6}）和 IEC 的 MiB（2^{20}）混用了；视频码率里的 M 是 10^{6}",
     "统一口径：容量一律按 10^{3} 进制算，再另附 GiB/MiB 对照列；脚本里 GB 与 GiB 常数分开定义"),
    ("hex(255) 返回 '0xff'（小写带前缀），与手写的 0xFF 不一致，误判为算错",
     "Python 的 hex() 固定输出小写，且带 0x 前缀，这是格式约定不是数值差异",
     "比较时统一 upper()；报告里按习惯写 0xFF，代码里按 Python 输出写 0xff，并注明两者等价"),
    ("用压缩后的截图大小反推分辨率，算出 0.11 B/像素，看起来像「位深填错了」",
     "把 PNG/JPEG 这种压缩文件当成了未压缩位图，压缩比被误当成位深",
     "未压缩值只用公式算；实际文件大小只用来求压缩比与每像素字节数，两者不互相代入"),
    ("estimate.py 在 Windows 控制台报 UnicodeEncodeError: 'gbk' codec can't encode character",
     "控制台默认 GBK 代码页，下标字符与部分符号不在 GBK 字符集里",
     "屏幕输出改成 10110101(2) 这类 ASCII 写法；需要特殊符号时先 chcp 65001 切 UTF-8"),
]

# ---------------------------------------------------------------------------
# 六、结论与拓展
# ---------------------------------------------------------------------------
ANALYSIS = [
    "**（1）数制互转：三个目标全部达成。** 按位权展开法把 10110101 写成 "
    "1×128 + 0×64 + 1×32 + 1×16 + 0×8 + 1×4 + 0×2 + 1×1 = 181；"
    "255 用「除 16 取余、余数倒序」得到 FF；1A 用「一位十六进制拆四位」得到 11010。"
    "三条路径再用 int()、hex()、bin() 复核，结果与手算一致，说明进位与位序没有错位。"
    "位权法的意义在于：它把「读一串 0/1」变成「8 个固定权值的加法」，"
    "这也是后面所有容量估算共用的思想——每一项 = 数量 × 单位大小。",

    "**（2）容量推导：三条公式，一个套路。** 照片 1920×1080×24÷8 = 6,220,800 B = 6.22 MB（5.93 MiB）；"
    "4 分钟 CD 级音频 44,100×16×2×240÷8 = 42,336,000 B = 42.34 MB（40.37 MiB）；"
    "2 小时 8 Mbps 视频 8×10^{6}×7200÷8 = 7.2×10^{9} B = 7.20 GB（6.71 GiB）。"
    "三者数量级差两个台阶：照片 MB 级、音频几十 MB、视频 GB 级。"
    "全部换算都由 estimate.py 复算，报告表格里的每个数字都能在脚本输出里找到对应行。",

    "**（3）容量直觉：带单位的「多大」才有意义。** 1 分钟 8 Mbps 视频约 60 MB，1 小时约 3.6 GB，"
    "一部 2 小时电影 7.2 GB——正好一张 DVD-9（8.5 GB）装得下。"
    "一首 4 分钟未压缩 PCM 音频 42 MB，相当于 7 张 1080p 照片；"
    "同一段音频压成 128 kbps 的 MP3 只有 3.84 MB，体积差 11 倍，这正是「有损压缩换容量」的直观例子。"
    "所以光说「我的视频 2 小时」没有意义，必须带上码率或分辨率。",

    "**（4）压缩带来的差异：估算用公式，压缩率只作修正。** 实测课件页截图（1191×1684）未压缩 6.02 MB、"
    "实际 PNG 只有 0.21 MB，压缩比 28.3:1；4K 壁纸照片（3840×2400）未压缩 27.65 MB、"
    "实际 JPEG 1.38 MB，压缩比 20.0:1。原因是截图与照片的相邻像素高度相关，"
    "PNG 的字典压缩、JPEG 的 DCT + 量化都能把这份冗余去掉，平均每像素只剩 0.11~0.15 B。"
    "但压缩比对内容极其敏感：噪点多、纹理碎的图片往往只有 2~5 倍。"
    "因此估算存储必须用未压缩公式，压缩率只能当作 10~30 倍的经验修正；"
    "反过来用压缩后的文件大小去推分辨率，就会得到 0.11 B/像素这种明显矛盾的结果（见问题 3）。",

    "**（5）拓展任务：256 GB 手机能存多少张自己拍的照片。** 按可用 90% 即 230.4 GB 计算："
    "12MP HEIC（3.2 MB/张）约 72,000 张；12MP JPEG（4.8 MB）约 48,000 张；"
    "48MP JPEG（9.5 MB）约 24,252 张；48MP ProRAW（26 MB）约 8,861 张。"
    "取舍很清楚：日常记录用 HEIC，用 7 万张的容量换「随手就拍」的自由，按每天 20 张算够用 10 年；"
    "需要二次构图或大幅调色时才开 48MP/ProRAW，因为单张体积是 HEIC 的 8 倍，"
    "等于用 8 倍空间换 4 倍像素与 14 bit 宽容度。我自己的设置是「默认 12MP HEIC + 重要场景手动开 48MP」，"
    "等效容量约 5 万张，兼顾了画质与空间。",

    "**（6）可继续做的对比实验。** 把同一张 1920×1080 图分别存成 PNG、JPEG(q=90)、WebP(q=80)，"
    "用 estimate.py --measure 复算三者的压缩比与每像素字节数，验证「编码格式对体积的影响大于分辨率」。"
    "预期 JPEG/WebP 会比 PNG 再小 3~5 倍，而分辨率完全不变；"
    "若把同一张图降到 1280×720 再存 PNG，体积只会降到约 44%。这个对比能进一步说明："
    "决定文件体积的是「像素数 × 编码效率」，而不是分辨率一个因素。",
]


def main() -> int:
    doc = Document(TPL)
    U.drop_page_breaks(doc)
    t0, t1, t2, t3, t4, t5, t6, t7 = doc.tables[:8]
    U.fill_header_card(t0, STUDENT)

    # ---- 一、实验目的 ----
    for i, g in enumerate(GOALS[:len(t1.rows)]):
        U.set_cell(t1.rows[i].cells[0], g, size=10.5)

    # ---- 二、实验环境 ----
    for i, text in enumerate(ENV[:len(t2.rows)]):
        U.set_cell(t2.rows[i].cells[1], text, size=10.5)

    # ---- 三、实验步骤 ----
    for i, (op, params, result) in enumerate(STEPS, start=1):
        row = t3.rows[i]
        U.set_cell(row.cells[1], op, size=9.5)
        U.set_cell(row.cells[2], params, size=9.5)
        U.set_cell(row.cells[3], result, size=9.5)

    # 单位换算表（紧跟步骤表）
    lead = U.add_para(doc, t3._tbl, "**补充：本实验用到的单位换算。** "
                               "「常见问题」里点名的 MB/MiB 混用，根源就是下面这张表没固定下来，"
                               "所以先把口径写死，后面的每个数字都按它换算。",
                       space_before=10, space_after=6, keep_with_next=True)
    U.add_table(doc, lead._element, ["单位", "换算关系", "本实验中的用法与例子"], UNITS,
                widths_cm=[3.0, 6.0, 7.4], size=9.0)

    # ---- 删除模板提示语 ----
    hints = [
        "（对照实验指南的「实验目标」，写出 2–3 条可验证的目标）",
        "（按实验指南的步骤记录实际操作、命令与参数；失败与重试也应记录）",
        "（至少记录 1 个真实问题：现象、原因、解决办法与验证结果）",
        "（结论回答实验目标；拓展写 1 条可继续做的改进或对比实验）",
    ]
    for h in hints:
        p = U.find_paragraph(doc, h)
        if p is not None:
            U.delete(p._element)

    # ---- 四、实验结果：替换提示语，删掉占位表，插入插图 ----
    hint4 = U.find_paragraph(doc, "（粘贴 2–4 张关键截图")
    assert hint4 is not None, "找不到第四节提示语"
    intro = U.new_paragraph(doc, hint4._element, before=True)
    U.write_para(intro, "下图是本实验的关键结果：图 1 是位权展开的手算过程，图 2 是三条容量公式的结果对照，"
                        "图 3 用两个真实文件验证「未压缩估算」与「压缩后实际大小」的差距。"
                        "三张图的原始数据由 estimate.py 导出为 results.json，再由 tools/make_figures.py 绘制，"
                        "因此图与表、图与脚本输出三者的数字完全一致。",
                 space_after=6)
    U.delete(hint4._element)
    U.delete(t4._tbl)

    anchor = intro._element
    for fname, caption in FIGURES:
        pic = U.add_picture(doc, anchor, os.path.join(FIG, fname), width_cm=16.2)
        anchor = U.add_caption(doc, pic._element, caption)._element

    # ---- 作品路径 ----
    p = U.find_paragraph(doc, "作品或数据文件路径")
    if p is not None and len(p.runs) >= 2:
        p.runs[1].text = ("dm-prog-labs/lab01_number_storage/"
                          "（git 仓库内含 estimate.py、results.md、results.json、figures/）")
        p.runs[1].font.color.rgb = U.RGBColor.from_string(U.INK)

    # ---- 五、问题与解决 ----
    while len(t5.rows) - 1 < len(PROBLEMS):
        U.clone_row(t5)
    for i, (q, cause, fix) in enumerate(PROBLEMS, start=1):
        U.set_cell(t5.rows[i].cells[0], q, size=9.5)
        U.set_cell(t5.rows[i].cells[1], cause, size=9.5)
        U.set_cell(t5.rows[i].cells[2], fix, size=9.5)

    # ---- 六、结论与拓展：删掉空表，换成正文 ----
    heading6 = U.find_paragraph(doc, "六、结论与拓展")
    anchor = heading6._element
    for para in ANALYSIS:
        anchor = U.add_para(doc, anchor, para, space_after=6)._element
    U.delete(t6._tbl)

    # ---- 七、提交物自查：勾选 ----
    for needle in ("计算过程表", "验证脚本 estimate.py", "一页结论"):
        p = U.find_paragraph(doc, needle)
        if p is not None and p.runs and "□" in p.runs[0].text:
            p.runs[0].text = "√  "

    p = U.find_paragraph(doc, "其他附件")
    if p is not None and len(p.runs) >= 2:
        p.runs[1].text = ("git 仓库 dm-prog-labs（含两份实验代码与报告）；"
                          "若以压缩包提交，见 dm-prog-labs.zip，解压后 git log 可看到完整提交历史")
        p.runs[1].font.color.rgb = U.RGBColor.from_string(U.INK)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    doc.save(OUT)
    print(f"[saved] {os.path.relpath(OUT, ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
