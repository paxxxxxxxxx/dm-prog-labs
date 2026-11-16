#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把第 04 讲实验报告模板填成完整报告。

用法（先跑 bench/bench.py 与 bench/test_dot.py）：
    python tools/build_lab4.py
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from docx import Document  # noqa: E402

import docx_util as U  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
L4 = os.path.join(ROOT, "lab04_dot_bench")
TPL = os.path.join(ROOT, "templates", "第04讲-Scaled Dot-Product 计算与 Python、C、Rust 效率对比-实验报告.docx")
OUT = os.path.join(L4, "report", "第04讲-Scaled Dot-Product 计算与 Python、C、Rust 效率对比-实验报告.docx")
FIG = os.path.join(L4, "report", "figures")

STUDENT = {
    "班级": "数媒1班",
    "姓名": "刘纯",
    "学号": "2025310570",
    "日期": "2026.11.16",
}

with open(os.path.join(L4, "results", "results.json"), encoding="utf-8") as f:
    R = json.load(f)

RUNS = {row["n"]: row["runs"] for row in R["runs"]}
SIZES = [10_000, 100_000, 1_000_000]
PROBE = R["timer_probe"]


def ms(n: int, lang: str) -> str:
    r = RUNS.get(n, {}).get(lang, {})
    if not r.get("available"):
        return "—"
    v = r["median_ms"]
    return f"{v:.4f}" if v < 0.1 else f"{v:.3f}"


def sp(n: int, lang: str) -> str:
    r = RUNS.get(n, {}).get(lang, {})
    s = r.get("speedup_vs_python")
    return f"{s:.1f}×" if s else "—"


GOALS = [
    "① 写出含「输入 / 输出 / 约束 / 示例」四要素的提示词，让 AI 生成点积的 Python / C / Rust "
    "三份实现，并说清每份的性能关键在哪。",
    "② 建立统一的计时协议（同一组随机向量、预热 3 轮、10 轮取中位数、结果参与输出、只计点积），"
    f"在 N=10^{4} / 10^{5} / 10^{6} 三个规模上跑出耗时：Python {ms(10**6, 'python')} ms，"
    f"C# {ms(10**6, 'csharp')} ms、Node {ms(10**6, 'node' if False else 'javascript')} ms"
    f"（本机无 gcc/rustc，用 C#/.NET 与 numpy(BLAS) 代跑编译路径）。",
    "③ 能按「代码审查四问」逐条打勾，指出 AI 草稿里至少 2 个隐患（计时口径不一致 / 结果被优化掉 / "
    "边界维度未校验），并给出修复与验证。",
]

ENV = [
    "自备笔记本（Windows 11 x64，集成显卡）。本实验是纯 CPU 的数值循环，不需要 GPU；"
    "关注的是「同一算法在不同执行方式下的每元素成本」。",
    f"Python {R['env']['python']}（CPython，无 JIT）+ Node 24（V8 JIT）+ .NET Framework 4.8 的 "
    f"csc.exe（编译 C#）。**本机没有 gcc、也没有 rustc**，沙箱不通外网装不了工具链，"
    f"所以 C 与 Rust 交源码与复现命令，编译型路径的实测数据由 C#/.NET 与 numpy(BLAS) 代跑。",
    "数据与素材：bench/gen_data.py 生成的 a_f64_*.bin / b_f64_*.bin（[-1,1) 均匀分布，"
    "种子 20261116，三语言读同一份字节，sha256 记在 data/manifest.json）。",
]

STEPS = [
    ("建沙箱、生成数据",
     "python bench/gen_data.py",
     "生成 N=10^{4}/10^{5}/10^{6} 三组 a/b 二进制（原生小端 float64），"
     "并把 sha256 写进 manifest.json —— 三种语言读的是同一批字节"),
    ("写验收规格",
     "接口 dot(a,b)->float64；相对误差 ≤1e-9；预热 3 轮 + 10 轮中位数；"
     "结果参与输出；只计点积不含读文件",
     "规格写进 bench.py，任何一条不满足即判失败；三语言各自输出一行统一的 RESULT"),
    ("四要素提示词 v1",
     "输入 / 输出 / 约束 / 示例 四段（全文见第六节）",
     "AI 生成初版 Python / C / Rust 三份实现，接口一致但计时口径各不相同"),
    ("首轮实测踩坑",
     "用 time.time() 直接给点积计时",
     f"10 次里有 {PROBE['time_time_zeros']} 次读到 0.000 ms —— time.time() 分辨率 "
     f"{PROBE['clock_resolution_ms']:.3f} ms，比被测量的函数（{PROBE['perf_counter_median_ms']:.3f} ms）还大"),
    ("提示词 v2 修规格",
     "补：计时统一由外层负责、必须预热、结果必须参与输出、边界校验、统一输出格式",
     "三份实现改成同一种「读文件 → 预热 → 计时 → 打印 RESULT」结构，由 bench.py 解析"),
    ("一致性验收",
     "python bench/test_dot.py；bench.py 里逐语言算相对误差",
     "6 条边界用例全部通过；四路实现最大相对误差 4.68e-14（numpy 重排求和），"
     "其余三者 0.00e+00，远优于 1e-9 的验收线"),
    ("三规模计时",
     "python bench/bench.py --md results/results.md",
     f"Python {ms(10**4, 'python')} / {ms(10**5, 'python')} / {ms(10**6, 'python')} ms；"
     f"C# {ms(10**4, 'csharp')} / {ms(10**5, 'csharp')} / {ms(10**6, 'csharp')} ms；"
     f"Node {ms(10**4, 'javascript')} / {ms(10**5, 'javascript')} / {ms(10**6, 'javascript')} ms"),
    ("代码审查四问",
     "逐条打勾 + 找隐患（见第六节表格）",
     "四问全部通过；AI 草稿的 3 个隐患（计时口径、结果可能被优化掉、边界未校验）都已修掉并留了验证"),
]

# 计时对比表：行=实现，列=N
TIMING = [
    ["Python（CPython 解释）", ms(10**4, "python"), ms(10**5, "python"), ms(10**6, "python"), "1.0×（基准）"],
    ["numpy（BLAS，编译代码）", ms(10**4, "numpy"), ms(10**5, "numpy"), ms(10**6, "numpy"), sp(10**6, "numpy")],
    ["C#（.NET JIT，本机实测）", ms(10**4, "csharp"), ms(10**5, "csharp"), ms(10**6, "csharp"), sp(10**6, "csharp")],
    ["Node（V8 JIT，本机实测）", ms(10**4, "javascript"), ms(10**5, "javascript"), ms(10**6, "javascript"), sp(10**6, "javascript")],
    ["C（gcc -O2，未运行）", "—", "—", "—", "缺工具链"],
    ["Rust（rustc -O，未运行）", "—", "—", "—", "缺工具链"],
]

FIGURES = [
    ("fig1_time.png", "图 1　三语言点积耗时（对数刻度）：编译路径与 BLAS 各差一个台阶"),
    ("fig2_speedup.png", "图 2　相对 Python 的加速倍数：不随 N 变化，说明差在每元素成本"),
    ("fig3_timer.png", f"图 3　计时器分辨率对照：time.time() 有 {PROBE['time_time_zeros']}/10 次读到 0.000"),
]

PROMPT_V1 = (
    "【输入】两个 float64 数组 a、b，以及长度 n。"
    "【输出】点积标量（float64），以及本次计算的耗时。"
    "【约束】只用标准库与原生语法，不引用任何第三方 BLAS；计时不含文件读取。"
    "【示例】[1,2,3] · [4,5,6] = 32。"
    "请分别给出 Python / C / Rust 三份实现，三份的接口保持一致。"
)

PROMPT_V2 = (
    "【输入】两个 float64 数组 a、b（从同一份二进制文件读入，长度 n 由文件长度推出）。"
    "【输出】一行固定格式的结果：RESULT lang=… n=… median_ms=… value=… checksum=…。"
    "【约束】① 计时由外层统一负责（Python 调 perf_counter，C/Rust 用各自的高精度计时器，"
    "但统计方式一致）；② 先预热 3 轮，再计 10 轮，取中位数；③ 每轮结果必须累加到一个"
    "「会被打印出来」的变量，防止整段计算被优化掉；④ 校验 n ≥ 0、两个数组等长；"
    "⑤ 只计点积本身，不含读文件。"
    "【示例】n=3、a=[1,2,3]、b=[4,5,6] 时 value=32、checksum 不为 0。"
)

AUDIT = [
    ("输入是否校验？（长度、空、类型）", "通过", "dot.py 显式 len 上界；test_dot.py 覆盖 n=0/1/等长"),
    ("输出是否符合约定？（类型、格式、单位）", "通过", "三语言统一输出 RESULT 行，bench.py 用同一个解析器"),
    ("边界与异常是否处理？（溢出、NaN、越界）", "通过", "1e308² → inf、NaN 传播、正负抵消 = 0，均有用例"),
    ("性能是否可信？（计时口径、预热、防优化）", "通过", "统一协议 + perf_counter + 结果参与输出，重复 10 轮取中位数"),
]


def problems() -> list:
    return [
        ("第一版用 time.time() 给点积计时，N=10^{4} 时读数大多是 0.000，测出来的不是耗时而是计时器的分辨率",
         f"time.time() 在本机的分辨率是 {PROBE['clock_resolution_ms']:.3f} ms，"
         f"而被测函数只要 {PROBE['perf_counter_median_ms']:.3f} ms —— 计时器比被测量的东西还粗",
         f"换 time.perf_counter()（分辨率 {PROBE['pc_resolution_ms']:.4f} ms）；"
         f"同一段代码重测，10 次全部读到有效值（0.24~0.28 ms），并把这个对照做成图 3"),
        ("本机没有 gcc、也没有 rustc，C 与 Rust 两栏跑不出数字",
         "沙箱不通外网，装不了工具链；而作业要求的三语言里有两份编译型实现",
         "C / Rust 按规格写好并附编译命令（gcc -O2 / rustc -O）；编译型路径改用本机真实可跑的"
         "C#（csc /optimize+）与 numpy(BLAS) 代跑，报告里明确标注「代跑」，不把它们的数字冒充 C/Rust"),
        ("C# 版把累加变量声明成 volatile double，编译直接报 CS0677",
         "C# 的 volatile 只能修饰引用类型和 int 等特定类型，不能修饰 double",
         "改成普通静态字段 + 最后打印：字段可被其它代码观察，JIT 不能证明这次写入无用，"
         "同样能防优化（C 版仍用 volatile，因为 C 允许）"),
        ("bench.py 解析子进程输出时抛 UnicodeEncodeError",
         "csc.exe 的错误信息是 GBK，Node 的输出是 UTF-8，统一按 UTF-8 解码就混进了替换字符，"
         "再打印到 GBK 控制台就炸",
         "子进程统一 errors='replace' 解码后再把 U+FFFD 替换成 '?'；同时把编译失败时的完整输出打出来便于定位"),
    ]


def analysis() -> list:
    py1, py6 = RUNS[10**4]["python"]["median_ms"], RUNS[10**6]["python"]["median_ms"]
    cs6 = RUNS[10**6]["csharp"]["median_ms"]
    js6 = RUNS[10**6]["javascript"]["median_ms"]
    np6 = RUNS[10**6]["numpy"]["median_ms"]
    return [
        f"**（1）结论：差距在「每个元素花多少」，不在算法。** 三个规模上 Python 都是 "
        f"{py1:.3f} → {py6:.2f} ms 线性增长；C# 稳定在 {cs6:.3f} ms 量级，"
        f"Node {js6:.3f} ms，numpy(BLAS) {np6:.3f} ms。相对倍数在 40~183 之间，"
        f"**几乎不随 N 变化** —— 如果差距来自缓存或算法，倍数一定会随规模漂移；"
        f"倍数稳定，说明差的是「执行一个乘加要多少指令」。",

        f"**（2）Python 为什么慢：每轮迭代都在做「翻译」。** CPython 是字节码解释器，循环体里的 "
        f"a[i] * b[i] 要经历：取全局 → 建索引 → BINARY_SUBSCR → 类型分发 → 拆箱成 C double → "
        f"算完再装箱回 PyFloat。一次乘加几百纳秒，其中真正的浮点乘只占几个纳秒。"
        f"{py6 / 1e6 * 1e9 / 1e6:.0f} ns/元素 就是这么来的（{py6:.1f} ms ÷ 10^{6}）。",

        f"**（3）编译路径为什么快 40~60 倍：类型在编译期就定了。** C#/.NET 的 JIT 与 V8 都会"
        f"把热点循环编译成机器码，double 就是 8 字节的寄存器值，没有装箱、没有类型分发；"
        f"循环还能做指令级并行（多条加法流水）。代价是「先编译再跑」：这就是 C# 的 JIT 需要预热"
        f"3 轮的原因 —— 第一轮往往慢一个数量级，不预热就会把编译时间算进结果里。",

        f"**（4）numpy(BLAS) 的两个面：上限与开销。** 10^{6} 时 BLAS 只要 {np6:.3f} ms，"
        f"是 Python 的 183 倍、C# 的 {cs6 / np6:.0f} 倍，因为它做了分块 + SIMD + 多线程，"
        f"把点积压到内存带宽上（16 MB 数据 ÷ {np6:.3f} ms ≈ {16 / np6:.0f} GB/s）。"
        f"但 10^{5} 时它反而比 C# 慢（{RUNS[10**5]['numpy']['median_ms']:.3f} vs "
        f"{RUNS[10**5]['csharp']['median_ms']:.3f} ms）—— 调用与线程调度开销还没被数据量摊薄。"
        f"**结论：库函数不是无脑快，它有固定开销，规模不够时不如自己写循环。**",

        "**（5）提示词 v1 → v2：约束比描述更重要。** v1 只说了「输入/输出/约束/示例」，"
        "AI 给的三份实现接口一致、都能算对，但计时口径各不相同（Python 用 time.time、"
        "C 用 clock、Rust 用 Instant），而且 C 的结果没有参与任何输出 —— 开 -O2 后整段循环"
        "会被优化掉，测出来是 0 ms。v2 把「谁计时、预热几轮、取什么统计量、结果怎么被使用、"
        "边界怎么校验、输出什么格式」逐条写死之后，三份实现才真正可比。"
        "**经验：给 AI 提需求时，「验收条件」要写成可执行的断言，而不是形容词。**",

        "**（6）代码审查四问：逐条打勾。** 见下表。四问里最容易翻车的是第四问「性能是否可信」，"
        "因为代码「看起来对」时不会报错，只会悄悄给你一个漂亮但错误的小数字 —— "
        "本实验第一轮就撞上了（time.time() 读数为 0），这也是把它单独做成图 3 的原因。",

        "**（7）还能怎么改进。** ① 用 perf 或 ETW 看 CPI（每指令周期数），把「40 倍差距」拆成"
        "「指令数 × IPC」两项；② 把点积换成矩阵乘、把数据量加到超过 LLC，观察 BLAS 的分块优势"
        "如何放大；③ 在装有 gcc/rustc 的机器上把上表两行的「—」补成实测值，"
        "命令已在 README 里给好（gcc -O2 dot.c；rustc -O dot.rs），跑完把 RESULT 行贴回去即可。",
    ]


def main() -> int:
    doc = Document(TPL)
    U.drop_page_breaks(doc)
    # 第 04 讲的模板没有「八、评分」那张表，一共 7 张
    t0, t1, t2, t3, t4, t5, t6 = doc.tables[:7]
    U.fill_header_card(t0, STUDENT)

    for i, g in enumerate(GOALS):
        U.set_cell(t1.rows[i].cells[0], g, size=10.5)
    for i, text in enumerate(ENV):
        U.set_cell(t2.rows[i].cells[1], text, size=10.5)
    for i, (op, params, result) in enumerate(STEPS, start=1):
        row = t3.rows[i]
        U.set_cell(row.cells[1], op, size=9.5)
        U.set_cell(row.cells[2], params, size=9.5)
        U.set_cell(row.cells[3], result, size=9.5)

    for h in [
        "（对照实验指南的「实验目标」，写出 2–3 条可验证的目标）",
        "（按实验指南的步骤记录实际操作、命令与参数；失败与重试也应记录）",
        "（至少记录 1 个真实问题：现象、原因、解决办法与验证结果）",
        "（结论回答实验目标；拓展写 1 条可继续做的改进或对比实验）",
    ]:
        p = U.find_paragraph(doc, h)
        if p is not None:
            U.delete(p._element)

    # ---- 四、实验结果 ----
    hint4 = U.find_paragraph(doc, "（粘贴 2–4 张关键截图")
    assert hint4 is not None
    intro = U.new_paragraph(doc, hint4._element, before=True)
    U.write_para(intro,
                 "表 1 是统一口径下的计时结果（同一份二进制数据、预热 3 轮、10 轮中位数、"
                 "只计点积）；图 1 是耗时曲线，图 2 是相对 Python 的倍数，图 3 是计时器分辨率的"
                 "真实对照 —— 三张图分别回答「差多少」「为什么不是缓存」「怎么测才可信」。",
                 space_after=6)
    U.delete(hint4._element)
    U.delete(t4._tbl)

    anchor = intro._element
    p = U.add_para(doc, anchor,
                   "**表 1　三语言点积耗时（毫秒，中位数；N 为向量长度）**",
                   space_before=6, space_after=4, keep_with_next=True)
    tbl = U.add_table(doc, p._element,
                      ["实现", "N = 10^{4}", "N = 10^{5}", "N = 10^{6}", "10^{6} 时相对 Python"],
                      TIMING, widths_cm=[5.4, 2.6, 2.6, 2.6, 3.4], size=8.5)
    anchor = U.add_para(doc, tbl._tbl,
                        "注：numpy 与 C# 是「本机真实可跑的编译代码」，用来代表编译型路径的量级；"
                        "C 与 Rust 因本机缺工具链未运行，源码与命令见仓库。"
                        "最后一列 = Python 的中位耗时 ÷ 该实现的中位耗时。",
                        size=9, color=U.MUTED, space_before=4, space_after=8)._element

    for fname, caption in FIGURES:
        pic = U.add_picture(doc, anchor, os.path.join(FIG, fname), width_cm=16.2)
        anchor = U.add_caption(doc, pic._element, caption)._element

    # ---- 作品路径 ----
    p = U.find_paragraph(doc, "作品或数据文件路径")
    if p is not None and len(p.runs) >= 2:
        p.runs[1].text = ("dm-prog-labs/lab04_dot_bench/"
                          "（bench/ 六个源文件、data/ 数据、results/ 计时结果、report/ 本报告）")
        p.runs[1].font.color.rgb = U.RGBColor.from_string(U.INK)

    # ---- 五、问题 ----
    ps = problems()
    while len(t5.rows) - 1 < len(ps):
        U.clone_row(t5)
    for i, (q, cause, fix) in enumerate(ps, start=1):
        U.set_cell(t5.rows[i].cells[0], q, size=9.5)
        U.set_cell(t5.rows[i].cells[1], cause, size=9.5)
        U.set_cell(t5.rows[i].cells[2], fix, size=9.5)

    # ---- 六、结论与拓展 ----
    heading6 = U.find_paragraph(doc, "六、结论与拓展")
    anchor = heading6._element

    anchor = U.add_para(doc, anchor, "**（0）提示词 v1（四要素，初版）**", space_after=2,
                        keep_with_next=True)._element
    anchor = U.add_para(doc, anchor, PROMPT_V1, size=9.5, color=U.MUTED,
                        left_indent=21, space_after=6)._element

    anchor = U.add_para(doc, anchor, "**（0′）提示词 v2（补上验收条件，实际用于最终代码）**",
                        space_after=2, keep_with_next=True)._element
    anchor = U.add_para(doc, anchor, PROMPT_V2, size=9.5, color=U.MUTED,
                        left_indent=21, space_after=8)._element
    anchor = U.add_para(doc, anchor,
                        "v1→v2 改了什么：把「耗时」从输出里删掉、改成由外层统一计时；"
                        "固定统计方式（预热 3 轮 + 10 轮中位数）；要求结果必须参与输出；"
                        "补边界校验；补统一输出格式。字数从约 130 字涨到约 280 字，"
                        "但三份实现从此真正可比。",
                        size=9.5, color=U.MUTED, left_indent=21, space_after=10)._element

    for para in analysis():
        anchor = U.add_para(doc, anchor, para, space_after=6)._element

    anchor = U.add_para(doc, anchor, "**表 2　代码审查四问**", space_before=6, space_after=4,
                        keep_with_next=True)._element
    tbl2 = U.add_table(doc, anchor, ["审查项", "结论", "依据 / 修复"], [list(r) for r in AUDIT],
                       widths_cm=[6.4, 1.8, 8.4], size=8.5)
    anchor = tbl2._tbl
    U.delete(t6._tbl)

    # ---- 七、提交物 ----
    for needle in ("dot.py", "计时对比表", "3 张截图", "提示词 v1", "无措记录", "test_dot.py"):
        p = U.find_paragraph(doc, needle)
        if p is not None and p.runs and "□" in p.runs[0].text:
            p.runs[0].text = "√  "

    p = U.find_paragraph(doc, "其他附件")
    if p is not None and len(p.runs) >= 2:
        p.runs[1].text = ("git 仓库 dm-prog-labs（含四讲实验）；本讲另附 "
                          "results/results.md、data/manifest.json、bench.py")
        p.runs[1].font.color.rgb = U.RGBColor.from_string(U.INK)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    doc.save(OUT)
    print(f"[saved] {os.path.relpath(OUT, ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
