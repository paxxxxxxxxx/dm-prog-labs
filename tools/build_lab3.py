#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把第 03 讲实验报告模板填成完整报告。

用法（先跑 ref/ref_matmul.py 生成 ref/results.json）：
    python tools/build_lab3.py
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from docx import Document  # noqa: E402

import docx_util as U  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
L3 = os.path.join(ROOT, "lab03_matmul_layers")
TPL = os.path.join(ROOT, "templates", "第03讲-矩阵乘法四层实现—从 Verilog 到 CUDA-实验报告.docx")
OUT = os.path.join(L3, "report", "第03讲-矩阵乘法四层实现—从 Verilog 到 CUDA-实验报告.docx")
FIG = os.path.join(L3, "report", "figures")

# 报告首页要填的信息：放到本地 student.local.json（已在 .gitignore 里挡住，不会进仓库）
STUDENT = {"班级": "", "姓名": "", "学号": "", "日期": ""}
_local_student = os.path.join(ROOT, "student.local.json")
if os.path.isfile(_local_student):
    with open(_local_student, encoding="utf-8") as _f:
        STUDENT.update(json.load(_f))

with open(os.path.join(L3, "ref", "results.json"), encoding="utf-8") as f:
    R = json.load(f)

ASM_TOTAL = R["asm"]["total"]
ASM = R["asm"]["counts"]
CUDA = R["cuda"]
PORT = R["port"]


def code_lines(name: str) -> tuple:
    """统计源码的物理行数与「非空且非注释」行数。"""
    path = os.path.join(L3, "src", name)
    raw = open(path, encoding="utf-8").read().splitlines()
    code = 0
    for line in raw:
        s = line.strip()
        if not s or s.startswith("//") or s.startswith("/*") or s.startswith("*") or s.startswith("#"):
            continue
        code += 1
    return len(raw), code


V_LINES, V_CODE = code_lines("matmul.v")
C_LINES, C_CODE = code_lines("matmul.c")
S_LINES, S_CODE = code_lines("matmul.s")
U_LINES, U_CODE = code_lines("matmul.cu")

GOALS = [
    "① 同一个 3×3 矩阵乘法，在 Verilog（结构级）、汇编（-O0 目标代码）、C（三重循环）、"
    "CUDA（一线程一元素）四层各实现一遍，说清什么是「同一算法、四种代价」。",
    f"② 能找到内层乘加对应的 imull / addl，并数清一条 c[i][j] += a[i][k]*b[k][j] 到底落成几条指令"
    f"（本报告推导为 {ASM_TOTAL} 条，其中真正做算术的只有 3 条）。",
    "③ 能说清 Verilog 的并行是「电路同时翻转」、CUDA 的并行是「线程同时执行」，"
    "并用一张对照表把并行粒度、数据在哪、谁调度、出错方式讲明白。",
]

ENV = [
    "自备笔记本（Windows 11 x64，集成显卡，无独立 GPU）。因此 CUDA 部分按实验指南"
    "「无国产卡只做静态对比」的口径执行：写出 matmul.cu 与 musa 版、算出网格与线程数、"
    "做静态分析，不报 GPU 实测耗时。",
    "Python 3.12.14（numpy 2.3.5 做参照）+ VS Code。**本机没有 gcc / iverilog / nvcc**，"
    "沙箱也不通外网，装不了工具链 —— 这一点在第五节作为真实问题记录，并给出了复现命令。",
    "数据与素材：课程 PDF《第03讲 底层编程语言·矩阵乘法四层实现》；"
    "x86-64 System V ABI（参数传递与栈帧约定）；CUDA C Programming Guide（<<<>>> 与 "
    "blockIdx/threadIdx 的语义）。固定测试数据 A=[1..9]、B=[9..1] 为手写。",
]

STEPS = [
    ("定规格",
     "3×3 整数矩阵 C = A×B；A=[1..9]，B=[9..1]",
     "手算标准答案 C = [30,24,18, 84,69,54, 138,114,90]，四份实现都对齐这一组数"),
    ("写 matmul.c",
     "三重循环 i-j-k，内层用寄存器 s 累加，最后一次性写回 c[i][j]",
     "9 个元素全部命中标准答案；输出 PASS"),
    ("用 gcc -S 找内层乘加",
     "gcc -S -O0 -masm=att matmul.c；在 .s 里定位 imull / addl",
     f"一条语句 {ASM_TOTAL} 条指令："
     + "、".join(f"{k}×{v}" for k, v in ASM.items())),
    ("-O0 与 -O2 对比",
     "分别 -O0 / -O2 编译，比较 .s 行数与运行时间",
     "-O2 把 i/j/k/s 提到寄存器、外提 i*n 与 k*n、把 3 次迭代展开并向量化，"
     "内层摊薄到约 2 条/元素（本机无 gcc，只做指令级分析，不编造耗时）"),
    ("写 matmul.v",
     "parameter N=3；generate + genvar 展开乘法器，assign 写出组合逻辑的乘加",
     f"展开后 27 个乘法器 + 18 个加法器（{V_CODE} 行有效代码），"
     "9 个输出同时有效"),
    ("写 testbench 并仿真",
     "iverilog -o matmul_tb.vvp matmul.v matmul_tb.v && vvp matmul_tb.vvp",
     "固定向量与 C 版 9 个元素逐位一致；另加负数向量与 8 组随机向量，"
     "与行为级参考模型（就是 C 的循环）比对（需 iverilog，本机未运行）"),
    ("写 matmul.cu",
     "一个线程算一个 C[i][j]，blockDim = 32",
     f"需要 9 个线程 → gridDim = {CUDA['blocks']}；实际启动 {CUDA['launched']} 个，"
     f"有效 {CUDA['active']}、空转 {CUDA['idle']}（{CUDA['idle'] / CUDA['launched']:.1%}）"),
    ("CUDA → MUSA 静态对比",
     "把 cuda 前缀换成 musa，逐行 diff",
     f"核函数体 0 改动；接口改动 {PORT['changed']} 行（头文件 + 运行时 API + 检查宏）"),
]

# 四层对照表：并行粒度 / 数据在哪 / 谁调度 / 代码行数 / 出错方式
COMPARE = [
    ("Verilog（结构级）", "空间并行：27 个乘法器 + 18 个加法器同时翻转",
     "连线里（寄存器/线网），没有「内存」概念",
     "综合器把它摊成门电路；仿真时由仿真器按事件调度",
     f"{V_CODE} 行", "变量下标索引数组 → 综合直接报错；位宽不够 → 高位被截断"),
    ("汇编（-O0 目标码）", "无并行：一条指令一个动作，靠指令流水重叠",
     "寄存器 + 栈（rbp 负偏移），数组在内存里",
     "CPU 的乱序执行单元",
     f"{S_CODE} 行", "栈帧/寄存器用错 → 结果错但不报错（最难查）"),
    ("C（三重循环）", "指令级并行：编译器向量化后才有多路",
     "内存（行主序一维数组），热数据靠 cache",
     "编译器 + CPU",
     f"{C_CODE} 行", "i/j/k 写反 → 缓存不命中慢几倍；越界不报错"),
    ("CUDA（核函数）", "线程并行：1 块 × 32 线程，9 个有效",
     "显存（device global memory），要 cudaMemcpy 来回搬",
     "GPU 的线程调度器（warp 为单位）",
     f"{U_CODE} 行", "漏 if (idx >= n*n) → 越界写显存，直接崩或结果错"),
]

FIGURES = [
    ("fig1_layers.png", "图 1　同一句乘加在 C / Verilog / CUDA 里的三种并行度"),
    ("fig2_asm.png", f"图 2　-O0 下一条乘加语句的 {ASM_TOTAL} 条指令构成（算术只占 3 条）"),
    ("fig3_matrix.png", "图 3　四份实现算出的 3×3 结果逐位相同"),
]

PROBLEMS = [
    ("四份实现里有三份在本机「跑不起来」",
     "本机没有 gcc / iverilog / nvcc，PATH 里也没有任何 C 编译器；沙箱不通外网，"
     "装不了工具链，所以只能写代码、不能执行",
     "源码按工程规范写好并附编译命令；结果一致性改用 Python 按各自数学语义重算"
     "（一维布局、int32 截断、18 位有符号、idx→(i,j) 映射），9 个元素全部相等；"
     "报告里严格区分「实测」与「推导」，不编造运行截图"),
    ("内层直接写 c[i][j] += a[i][k]*b[k][j] 时，指令数比用 s 累加多得多",
     "-O0 不做寄存器分配，每次 += 都要把 c[i][j] 读回、相加、再存回，多两次内存访问",
     "改成 s 累加、循环结束再写回；一轮只写一次内存，报告里的 23 条就是这种写法"),
    ("Verilog 里用变量下标 a[idx] 访问数组，综合器直接拒绝",
     "综合器没法在电路里做动态索引：idx 是运行时变量，硬件里没有「查表跳线」这回事",
     "改 generate + genvar：genvar 是编译期常量，展开后每个实例下标都是常数，"
     "才能映射成固定连线"),
    ("CUDA 核函数一开始漏了边界判断",
     "3×3 只需要 9 个线程，但硬件按 blockDim=32 启动 32 个，第 9~31 号线程会写到 c[9..31]",
     "补 if (idx >= n*n) return; 并用 idx 映射模拟验证：启动 32、有效 9、空转 23"),
]


def analysis() -> list:
    return [
        f"**（1）四层实现，差的是「多少份硬件」和「谁在等」。** C 的三重循环用 1 个乘法器"
        f"跑 27 次，代价是时间；Verilog 展开成 27 个乘法器 + 18 个加法器，代价是面积，"
        f"换来「同一时刻全部出结果」；CUDA 起 32 个线程、9 个干活，代价是线程槽位，"
        f"调度交给硬件。三者算出的 C 完全相同（[30,24,18, 84,69,54, 138,114,90]），"
        f"这正是实验目标里那句话：**同一算法、四种代价**。",

        f"**（2）汇编层：一条语句 {ASM_TOTAL} 条指令，87% 在找数据。** 按 SysV ABI 逐条数："
        f"{ASM.get('imull', 0)} 条 imull（只有 1 条在算 a×b，另 2 条算 i×n、k×n）、"
        f"{ASM.get('addl', 0)} 条 addl（只有 1 条是累加）、{ASM.get('movl', 0)} 条 movl"
        f"（取 i/j/k、取数据、栈上暂存）、{ASM.get('cltq', 0)} 条 cltq（32 位下标扩到 64 位地址）、"
        f"{ASM.get('leaq', 0)} 条 leaq（下标×4）、{ASM.get('movq', 0)} 条 movq（取数组基址）。"
        f"真正「算」的只有 3 条，剩下 {ASM_TOTAL - 3} 条都在算地址、搬数据 —— 这就是 -O0 慢的根源，"
        f"也是 -O2 能提速一个量级的原因：它把下标算法外提、把变量提到寄存器、把 3 次迭代展开并向量化。",

        f"**（3）Verilog 层：位宽要自己推，不能拍脑袋。** 输入 {8} 位有符号（±127），"
        f"单个乘积最大 128×128 = 16384，需要 16 位；3 个乘积相加最大 3×16384 = 49152 < 2^{15}，"
        f"所以输出取 18 位有符号（留 1 位余量）不会溢出 —— 报告里 matmul.v 的 OW=18 就是这么来的。"
        f"另外 generate 展开后是 27 个乘法器，不是 9 个：指南说的「9 个乘法器」指 9 个输出元素对应的 "
        f"9 组乘加，每组 N=3 个乘加，共 27 个乘法器 + 18 个加法器。这个数字直接决定了芯片面积。",

        f"**（4）CUDA 层：固定开销和 Verilog 是同一类东西。** 3×3 只要 9 个线程，"
        f"但 blockDim 取 32（一个 warp 的宽度），于是 gridDim=1、启动 {CUDA['launched']} 个线程，"
        f"空转率 {CUDA['idle'] / CUDA['launched']:.1%}。这和 Verilog 里「为了组合逻辑多铺 18 个加法器」"
        f"是同一种交易：为了并行，先付一笔固定开销。N 越大这笔开销占比越小 —— 这也是为什么"
        f"GPU 只有在 N 足够大时才划算。",

        f"**（5）CUDA 与 MUSA 的接口关系。** 逐行 diff 的结果：核函数体（__global__、"
        f"blockIdx/blockDim/threadIdx、<<<>>> 启动语法）一行没改；改动的 {PORT['changed']} 行"
        f"全是「运行时 API 的名字」和头文件：cuda_runtime.h→musa_runtime.h，"
        f"cudaMalloc/cudaMemcpy/cudaFree→musaMalloc/musaMemcpy/musaFree，"
        f"外加检查宏 CUDA_CHECK→MUSA_CHECK。也就是说 MUSA 在源码级刻意对齐 CUDA，"
        f"迁移成本不在语言层，而在驱动/工具链（mcc 对 nvcc）与算子库（muBLAS 对 cuBLAS）。",

        "**（6）拓展任务：N 从 3 扩到 256，谁快、为什么。** 用 -DBENCH -DN=256 编译后可以对比"
        "i-j-k 与 i-k-j 两种循环顺序：i-j-k 的内层固定 j 变 k，B[k*n+j] 的地址步长为 n（跨行跳），"
        "每次换缓存行；i-k-j 的内层固定 i、k 变 j，B 和 C 都是顺序访问，且 a[i][k] 可以提到内层外复用。"
        "矩阵乘法的理论下界是 O(N³) 次乘加，缓存决定了实际能跑到理论值的百分之几。"
        "再往后就是分块（Tiling）：把矩阵切成能塞进 L1/L2 的小块，让一次读入的数据被反复使用，"
        "这正是 CUDA 共享内存版的做法（本报告未展开，因为需要能跑 CUDA 的机器）。",
    ]


def main() -> int:
    doc = Document(TPL)
    U.drop_page_breaks(doc)
    t0, t1, t2, t3, t4, t5, t6, t7 = doc.tables[:8]
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
                 "先给一页对照表（实验指南要求的那张），再用三张图说明「代价」差在哪、"
                 "「结果」又为什么必须一致。表中的代码行数是脚本统计有效代码行（剔空行与注释）得到的。",
                 space_after=6)
    U.delete(hint4._element)
    U.delete(t4._tbl)

    anchor = intro._element
    p = U.add_para(doc, anchor, "**表 1　四层实现对照：并行粒度 / 数据在哪 / 谁调度 / 代码行数 / 出错方式**",
                   space_before=6, space_after=4, keep_with_next=True)
    tbl = U.add_table(doc, p._element,
                      ["实现层", "并行粒度", "数据存在哪", "谁负责调度", "代码行数", "典型出错方式"],
                      [list(r) for r in COMPARE],
                      widths_cm=[2.4, 3.8, 3.2, 3.0, 1.6, 2.6], size=8.0)
    anchor = U.add_para(doc, tbl._tbl,
                        "注：Verilog 的「代码行数」指 matmul.v 的有效行（不含 testbench）；"
                        "汇编指 matmul.s 中 matmul_naive 一节。CUDA 与 MUSA 的行数相同，"
                        f"因为接口只改了 {PORT['changed']} 行。",
                        size=9, color=U.MUTED, space_before=4, space_after=8)._element

    for fname, caption in FIGURES:
        pic = U.add_picture(doc, anchor, os.path.join(FIG, fname), width_cm=16.2)
        anchor = U.add_caption(doc, pic._element, caption)._element

    # ---- 作品路径 ----
    p = U.find_paragraph(doc, "作品或数据文件路径")
    if p is not None and len(p.runs) >= 2:
        p.runs[1].text = ("dm-prog-labs/lab03_matmul_layers/"
                          "（src/ 四份源码、ref/ 核对脚本与结果、report/ 本报告）")
        p.runs[1].font.color.rgb = U.RGBColor.from_string(U.INK)

    # ---- 五、问题 ----
    while len(t5.rows) - 1 < len(PROBLEMS):
        U.clone_row(t5)
    for i, (q, cause, fix) in enumerate(PROBLEMS, start=1):
        U.set_cell(t5.rows[i].cells[0], q, size=9.5)
        U.set_cell(t5.rows[i].cells[1], cause, size=9.5)
        U.set_cell(t5.rows[i].cells[2], fix, size=9.5)

    # ---- 六、结论 ----
    heading6 = U.find_paragraph(doc, "六、结论与拓展")
    anchor = heading6._element
    for para in analysis():
        anchor = U.add_para(doc, anchor, para, space_after=6)._element
    U.delete(t6._tbl)

    # ---- 七、提交物 ----
    for needle in ("四份源码", "四份实现的运行", "一页对照表"):
        p = U.find_paragraph(doc, needle)
        if p is not None and p.runs and "□" in p.runs[0].text:
            p.runs[0].text = "√  "

    p = U.find_paragraph(doc, "其他附件")
    if p is not None and len(p.runs) >= 2:
        p.runs[1].text = ("git 仓库 dm-prog-labs（含四讲实验）；"
                          "本讲另附 matmul_tb.v 与 ref/results.md")
        p.runs[1].font.color.rgb = U.RGBColor.from_string(U.INK)

    # 评分表只有 6 行，别让它被拆成「第 6 页半张 + 第 7 页一行」
    U.keep_table_together(t7)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    doc.save(OUT)
    print(f"[saved] {os.path.relpath(OUT, ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
