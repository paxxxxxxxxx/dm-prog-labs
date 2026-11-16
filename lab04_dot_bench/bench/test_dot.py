#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第 04 讲 dot.py 的边界用例测试（实验提交物里要求的那 5 条）

为什么单独写测试：
    性能测试只能证明「快」，证明不了「对」。点积有几个经典边界：
    空向量、单元素、正负抵消、上溢、NaN 传播 —— 这几条在 C / Rust 里
    行为还不完全一样（C 是 IEEE 754 静默溢出，Rust 的 debug 模式会 panic），
    所以必须逐条钉死预期行为。

运行：
    python bench/test_dot.py
"""

from __future__ import annotations

import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from dot import dot  # noqa: E402

CASES = []


def case(name, expect_note):
    def deco(fn):
        CASES.append((name, expect_note, fn))
        return fn
    return deco


@case("n = 0（空向量）", "点积定义为 0.0，不能抛异常")
def t_empty():
    return dot([], []) == 0.0


@case("n = 1（单元素）", "a[0]*b[0]")
def t_single():
    return abs(dot([2.5], [-4.0]) - (-10.0)) < 1e-15


@case("正负抵消", "1*1 + (-1)*1 + 1*1 + (-1)*1 = 0，且必须是精确 0")
def t_cancel():
    return dot([1.0, -1.0, 1.0, -1.0], [1.0, 1.0, 1.0, 1.0]) == 0.0


@case("上溢（1e308 × 1e308）", "IEEE 754 静默溢出为 inf，不抛异常")
def t_overflow():
    v = dot([1e308, 0.0], [1e308, 0.0])
    return math.isinf(v) and v > 0


@case("NaN 传播", "任一元素是 NaN，结果必须是 NaN")
def t_nan():
    v = dot([1.0, float("nan")], [1.0, 2.0])
    return math.isnan(v)


@case("与 numpy 逐项一致（随机 1000 维）", "相对误差 ≤ 1e-12")
def t_numpy():
    try:
        import numpy as np
    except ImportError:
        return True          # 没装 numpy 就跳过
    rng = np.random.default_rng(7)
    a = rng.random(1000) * 2 - 1
    b = rng.random(1000) * 2 - 1
    want = float(np.dot(a, b))
    got = dot(list(a), list(b))
    return abs(got - want) <= 1e-12 * max(1.0, abs(want))


def main() -> int:
    print("=" * 70)
    print("dot.py 边界用例")
    print("=" * 70)
    bad = 0
    for name, note, fn in CASES:
        try:
            ok = bool(fn())
        except Exception as e:      # 抛异常也算不通过
            ok = False
            note = f"{note}（抛了 {type(e).__name__}: {e}）"
        bad += 0 if ok else 1
        print(f"  [{'PASS' if ok else 'FAIL'}] {name:<28} {note}")
    print("-" * 70)
    print(f"结果：{'全部通过' if bad == 0 else f'{bad} 项未通过'}（共 {len(CASES)} 项）")
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
