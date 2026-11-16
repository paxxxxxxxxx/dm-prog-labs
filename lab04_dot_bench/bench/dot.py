#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第 04 讲 dot.py —— 点积的 Python 实现（三语言里的基准组）

验收规格（与 C / Rust 版共用，缺一不可）：
    1. 接口一致：dot(a, b) -> float64 标量；
    2. 读同一份二进制文件（data/a_f64_<N>.bin、b_f64_<N>.bin）；
    3. 正确性：与 numpy 的结果相对误差 ≤ 1e-9；
    4. 计时协议：先预热 WARMUP 轮，再正式计 TIMES 轮，取**中位数**；
       循环里必须把结果累加到全局变量并最后打印，防止被解释器/编译器「整段优化掉」；
    5. 计时只计 dot 调用本身，不含文件读取。

单独运行（不经过 bench.py）：
    python bench/dot.py 1000000
"""

from __future__ import annotations

import statistics
import struct
import sys
import time

WARMUP = 3
TIMES = 10

# 黑盒累加器：让每轮结果都「被用到」，避免整段计算被优化掉
_SINK = 0.0


def load(path: str) -> list:
    """按原生小端 float64 读入一整个文件。"""
    with open(path, "rb") as f:
        raw = f.read()
    n = len(raw) // 8
    return list(struct.unpack("<%dd" % n, raw))


def dot(a, b) -> float:
    """点积：纯 Python 循环，不调用任何第三方库。

    这里刻意用局部变量 s 累加、用 len(a) 做上界 —— CPython 里
    「局部变量 + 内建 len」比属性查找快得多，这是 Python 这层能做的唯一优化。
    """
    s = 0.0
    for i in range(len(a)):
        s += a[i] * b[i]
    return s


def bench(n: int, data_dir: str = "data") -> dict:
    global _SINK
    a = load(f"{data_dir}/a_f64_{n}.bin")
    b = load(f"{data_dir}/b_f64_{n}.bin")

    t_dot = dot(a, b)

    for _ in range(WARMUP):                 # 预热：让解释器缓存、CPU 预热
        _SINK += dot(a, b)
    samples = []
    for _ in range(TIMES):
        t0 = time.perf_counter()
        v = dot(a, b)
        t1 = time.perf_counter()
        _SINK += v
        samples.append((t1 - t0) * 1e3)     # 毫秒

    return {
        "lang": "python",
        "n": n,
        "median_ms": statistics.median(samples),
        "min_ms": min(samples),
        "max_ms": max(samples),
        "value": t_dot,
        "checksum": _SINK,
        "samples_ms": samples,
    }


def main() -> int:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 1_000_000
    r = bench(n)
    print(f"RESULT lang=python n={n} median_ms={r['median_ms']:.6f} "
          f"min_ms={r['min_ms']:.6f} value={r['value']:.17g} checksum={r['checksum']:.17g}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
