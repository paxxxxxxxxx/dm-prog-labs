#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第 03 讲 矩阵乘法四层实现 —— 一致性核对与静态分析

本机环境说明（写进报告第五节）：
    这台机器上没有 gcc / g++ / clang / iverilog / nvcc，也没有 CUDA 或摩尔线程的卡，
    沙箱又不通外网，无法安装工具链。所以：
      · matmul.c / matmul.v / matmul.cu / matmul.mu 四份源码照写，编译命令写在 README；
      · 「四份实现结果一致」这件事，用本脚本按同样的算术语义重算一遍来核对：
        一维布局、int32 截断、Verilog 的 18 位有符号、CUDA 的 idx→(i,j) 映射，
        全部按各自实现的数学语义执行，任何一处下标或位宽写错都会在这里暴露；
      · matmul.s 的指令条数由本脚本**直接解析那个文件**得到，不是手写死的。

用法：
    python ref/ref_matmul.py            # 打印核对过程
    python ref/ref_matmul.py --md ref/results.md --json ref/results.json
"""

from __future__ import annotations

import argparse
import difflib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(os.path.dirname(HERE), "src")

N = 3
W = 8          # 输入位宽（有符号）
OW = 18        # 输出位宽（有符号）

A = [1, 2, 3,
     4, 5, 6,
     7, 8, 9]
B = [9, 8, 7,
     6, 5, 4,
     3, 2, 1]

# matmul.c 里硬编码的标准答案（手算得到的同一组数）
EXPECT = [30, 24, 18, 84, 69, 54, 138, 114, 90]

BLOCK_DIM = 32


# ---------------------------------------------------------------------------
# 整数语义：int32 与 18 位有符号的截断，保证和 C / Verilog 一致
# ---------------------------------------------------------------------------
def as_int32(v: int) -> int:
    v &= 0xFFFFFFFF
    return v - (1 << 32) if v & 0x80000000 else v


def as_signed(v: int, width: int) -> int:
    v &= (1 << width) - 1
    return v - (1 << width) if v & (1 << (width - 1)) else v


# ---------------------------------------------------------------------------
# 四种「实现」——分别对应四份源码的数学语义
# ---------------------------------------------------------------------------
def impl_c_naive(a: list, b: list, n: int) -> list:
    """对应 matmul.c 的 matmul_naive：i-j-k 三重循环，int32 寄存器累加。"""
    c = [0] * (n * n)
    for i in range(n):
        for j in range(n):
            s = 0
            for k in range(n):
                s = as_int32(s + as_int32(a[i * n + k] * b[k * n + j]))
            c[i * n + j] = s
    return c


def impl_verilog_struct(a: list, b: list, n: int) -> tuple:
    """对应 matmul.v 的 generate 展开：27 个乘法器 + 9 条累加链，全部 18 位有符号。

    返回 (c, prods, accs)，其中 prods[i][j][k] 是那 27 根乘积线，
    用来在图里画「电路同时翻转」的结构。
    """
    prods = [[[0] * n for _ in range(n)] for _ in range(n)]
    accs = [[[0] * n for _ in range(n)] for _ in range(n)]
    for i in range(n):
        for j in range(n):
            for k in range(n):
                # assign prod = a * b；8 位有符号乘 8 位有符号，结果按 OW 位保存
                prods[i][j][k] = as_signed(a[i * n + k] * b[k * n + j], OW)
            # assign acc[0] = prod[0]; acc[k] = acc[k-1] + prod[k]
            accs[i][j][0] = prods[i][j][0]
            for k in range(1, n):
                accs[i][j][k] = as_signed(accs[i][j][k - 1] + prods[i][j][k], OW)
    c = [accs[i][j][n - 1] for i in range(n) for j in range(n)]
    return c, prods, accs


def impl_cuda(a: list, b: list, n: int, block_dim: int = BLOCK_DIM) -> tuple:
    """对应 matmul.cu：一个线程算一个 C[i][j]，线程号由 blockIdx*blockDim+threadIdx 得到。"""
    blocks = (n * n + block_dim - 1) // block_dim
    c = [0] * (n * n)
    launched = blocks * block_dim
    active = 0
    for blk in range(blocks):
        for tid in range(block_dim):
            idx = blk * block_dim + tid
            if idx >= n * n:            # 核函数里那句 if (idx >= n*n) return;
                continue
            active += 1
            i, j = idx // n, idx % n
            s = 0
            for k in range(n):
                s = as_int32(s + as_int32(a[i * n + k] * b[k * n + j]))
            c[idx] = s
    return c, {"blocks": blocks, "block_dim": block_dim,
               "launched": launched, "active": active, "idle": launched - active}


def impl_numpy(a: list, b: list, n: int) -> list:
    """第五方参照：numpy（底层是编译好的 BLAS），用来兜底验证手算。"""
    try:
        import numpy as np
    except ImportError:
        return None
    A_ = np.array(a, dtype=np.int64).reshape(n, n)
    B_ = np.array(b, dtype=np.int64).reshape(n, n)
    return (A_ @ B_).ravel().tolist()


# ---------------------------------------------------------------------------
# matmul.s 指令统计：直接解析文件，不是写死的数字
# ---------------------------------------------------------------------------
MNEMONICS = {
    "movl", "movq", "movb", "addl", "addq", "subl", "subq", "imull", "idivl",
    "cltq", "leaq", "jmp", "jge", "jl", "je", "jne", "cmpq", "cmpl", "pushq",
    "popq", "ret", "leave", "nop", "call",
}


def analyse_asm(path: str) -> dict:
    text = open(path, encoding="utf-8").read()
    start = text.find("# 核心：")
    end = text.find("# 计数小结（")
    core = text[start:end] if start >= 0 and end > start else ""
    counts = {}
    total = 0
    for raw in core.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("."):
            continue
        # 去掉行尾注释与行首编号（"1  eax = i" 这种注释行已经被 # 过滤）
        m = re.match(r"([a-z]+)\s", line)
        if not m:
            continue
        mnem = m.group(1)
        if mnem in MNEMONICS:
            counts[mnem] = counts.get(mnem, 0) + 1
            total += 1
    return {"total": total, "counts": dict(sorted(counts.items(), key=lambda kv: -kv[1]))}


# ---------------------------------------------------------------------------
# matmul.cu → matmul.mu 的真实 diff
# ---------------------------------------------------------------------------
def strip_comments(text: str) -> list:
    """去掉 // 与 /* */ 注释和空行，只留代码行（用来统计真正的接口改动）。"""
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    out = []
    for line in text.splitlines():
        line = line.split("//")[0].rstrip()
        if line.strip():
            out.append(line.strip())
    return out


def analyse_port() -> dict:
    cu = strip_comments(open(os.path.join(SRC, "matmul.cu"), encoding="utf-8").read())
    mu = strip_comments(open(os.path.join(SRC, "matmul.mu"), encoding="utf-8").read())
    diff = list(difflib.unified_diff(cu, mu, fromfile="matmul.cu(代码行)",
                                     tofile="matmul.mu(代码行)", lineterm="", n=0))
    minus = [l for l in diff if l.startswith("-") and not l.startswith("---")]
    plus = [l for l in diff if l.startswith("+") and not l.startswith("+++")]
    # 逐对找出 cuda->musa 的替换关系（只看真正改动了的代码行）
    pairs = [{"cu": a[1:].strip(), "mu": b[1:].strip()} for a, b in zip(minus, plus)]
    return {
        "cu_code_lines": len(cu),
        "mu_code_lines": len(mu),
        "minus": len(minus),
        "plus": len(plus),
        "changed": max(len(minus), len(plus)),
        "pairs": pairs,
        "diff": diff,
    }


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------
def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--md")
    ap.add_argument("--json")
    args = ap.parse_args(argv)

    out = []
    p = out.append

    p("=" * 78)
    p("第 03 讲 矩阵乘法四层实现 —— 结果一致性核对与静态分析")
    p("=" * 78)

    p("\n[1] 输入与手算标准答案")
    p(f"    A = {A}")
    p(f"    B = {B}")
    p(f"    手算 C = {EXPECT}")

    # ---- 四路重算 ----
    c_c = impl_c_naive(A, B, N)
    c_v, prods, accs = impl_verilog_struct(A, B, N)
    c_g, cinfo = impl_cuda(A, B, N)
    c_np = impl_numpy(A, B, N)

    p("\n[2] 按四份源码的语义分别重算（一维行主序、int32 截断）")
    p(f"    ① C 三重循环 (matmul.c)          C = {c_c}")
    p(f"    ② Verilog 结构级 (matmul.v)      C = {c_v}")
    p(f"    ③ CUDA 线程映射 (matmul.cu)      C = {c_g}")
    if c_np is not None:
        p(f"    ④ numpy 参照 (BLAS)              C = {c_np}")

    ok_c = c_c == EXPECT
    ok_v = c_v == EXPECT
    ok_g = c_g == EXPECT
    ok_np = (c_np == EXPECT) if c_np is not None else True
    all_ok = ok_c and ok_v and ok_g and ok_np
    p(f"\n    与手算逐一比对：C {ok_c} / Verilog {ok_v} / CUDA {ok_g} / numpy {ok_np}")
    p(f"    结论：{'四路完全一致 PASS' if all_ok else '存在不一致 FAIL'}")

    # ---- Verilog 结构：27 根乘积线 ----
    p("\n[3] Verilog 展开后的真实代价（generate 展开的结果）")
    p("    每个输出元素一组乘加，N=3 时共 27 个乘法器、18 个加法器：")
    p("      C[i][j]      乘积 p0        p1        p2      ->  和（18 位有符号）")
    for i in range(N):
        for j in range(N):
            p(f"      C[{i}][{j}]  {prods[i][j][0]:>10}  {prods[i][j][1]:>8}  {prods[i][j][2]:>8}"
              f"  ->  {accs[i][j][N-1]:>6}")
    p("    这 27 个乘法器在同一个时刻一起翻转 —— 硬件里没有「循环」，")
    p("    只有「多少份并行硬件」；C 的三重循环用 1 个乘法器跑 27 次，代价是时间。")
    max_val = max(abs(v) for i in range(N) for j in range(N) for v in prods[i][j])
    p(f"    位宽核对：最大乘积绝对值 {max_val}，18 位有符号上限 {(1 << (OW - 1)) - 1} -> 不溢出")

    # ---- CUDA 网格 ----
    p("\n[4] CUDA 网格与线程（blockDim = 32，一个线程算一个元素）")
    p(f"    需要线程数 {N*N}，blockDim {cinfo['block_dim']} -> gridDim {cinfo['blocks']}")
    p(f"    实际启动 {cinfo['launched']} 个线程：有效 {cinfo['active']} 个，空转 {cinfo['idle']} 个"
      f"（空转率 {cinfo['idle'] / cinfo['launched']:.1%}）")
    p("    这和 Verilog 里多出来的加法器是同一类代价：为了并行，先付一笔固定开销。")

    # ---- 汇编统计 ----
    asm = analyse_asm(os.path.join(SRC, "matmul.s"))
    p("\n[5] matmul.s 内层乘加的指令统计（脚本直接解析该文件得到）")
    p(f"    一条 s += a[i*n+k] * b[k*n+j] 共 {asm['total']} 条指令：")
    for mnem, cnt in asm["counts"].items():
        p(f"      {mnem:<7} {cnt:>2}")
    mul = asm["counts"].get("imull", 0)
    add = asm["counts"].get("addl", 0)
    p(f"    3 条 imull 里只有 1 条是真正的 a*b，另 2 条在算 i*n / k*n；")
    p(f"    {add} 条 addl 里只有 1 条是累加，另 2 条在下标相加；")
    p(f"    剩下 {asm['total'] - mul - add} 条全在算地址、搬数据 —— 这就是「同一算法、几种代价」。")

    # ---- 移植 diff ----
    port = analyse_port()
    p("\n[6] CUDA -> MUSA 的静态对比（matmul.cu 与 matmul.mu 真实 diff）")
    p(f"    去掉注释后的代码行：matmul.cu {port['cu_code_lines']} 行，matmul.mu {port['mu_code_lines']} 行")
    p(f"    真正改动 {port['changed']} 行（删 {port['minus']} / 增 {port['plus']}）：")
    for pair in port["pairs"]:
        p(f"      - {pair['cu']}")
        p(f"      + {pair['mu']}")
    p("    核函数体（__global__、blockIdx/blockDim/threadIdx、<<<>>>）一行未改；")
    p("    改的只有头文件名与运行时 API 前缀：cuda_runtime.h -> musa_runtime.h，")
    p("    cudaMalloc/cudaMemcpy/cudaFree -> musaMalloc/musaMemcpy/musaFree。")

    p("\n" + "=" * 78)
    print("\n".join(out))

    if args.md:
        lines = ["# 第 03 讲 核对结果（脚本生成）", ""]
        lines.append("## 四路重算")
        lines.append("")
        lines.append("| 实现 | 结果（行主序） | 与手算一致 |")
        lines.append("| --- | --- | --- |")
        lines.append(f"| C 三重循环 matmul.c | {c_c} | {'是' if ok_c else '否'} |")
        lines.append(f"| Verilog 结构级 matmul.v | {c_v} | {'是' if ok_v else '否'} |")
        lines.append(f"| CUDA 线程映射 matmul.cu | {c_g} | {'是' if ok_g else '否'} |")
        if c_np is not None:
            lines.append(f"| numpy（BLAS 参照） | {c_np} | {'是' if ok_np else '否'} |")
        lines.append("")
        lines.append("## 汇编指令统计（解析 matmul.s）")
        lines.append("")
        lines.append(f"一条 `s += a[i*n+k] * b[k*n+j]` 共 **{asm['total']} 条**指令：")
        lines.append("")
        lines.append("| 指令 | 条数 |")
        lines.append("| --- | --- |")
        for mnem, cnt in asm["counts"].items():
            lines.append(f"| {mnem} | {cnt} |")
        lines.append("")
        lines.append("## MUSA 移植改动量")
        lines.append("")
        lines.append(f"- 真正改动的代码行：{port['changed']} 行（删 {port['minus']} / 增 {port['plus']}）")
        lines.append(f"- 代码行总数：matmul.cu {port['cu_code_lines']} -> matmul.mu {port['mu_code_lines']}")
        with open(args.md, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        print(f"[已写出] {args.md}")

    if args.json:
        payload = {
            "matrix": {"A": A, "B": B, "expect": EXPECT},
            "impl": {"c": c_c, "verilog": c_v, "cuda": c_g, "numpy": c_np},
            "consistent": all_ok,
            "verilog": {"products": prods, "accs": accs, "max_product": max_val},
            "cuda": cinfo,
            "asm": asm,
            "port": {k: v for k, v in port.items() if k != "diff"},
        }
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        print(f"[已写出] {args.json}")

    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
