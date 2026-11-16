#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第 04 讲 实验步骤 1：生成三语言共用的随机向量

为什么要先生成文件、再三语言读同一份？
    如果每个语言各自调用自己的随机数发生器，那比较的就不是「同一个点积」了 ——
    数据不同、和不同、结果不同，计时也没法互相印证。
    所以这里一次性生成 a_f64.bin / b_f64.bin（原生小端 float64，无头部），
    三种语言都用二进制方式读入，并把 sha256 记进 manifest.json，
    报告里可以核对「三份读数确实是同一批字节」。

用法：
    python bench/gen_data.py                 # 生成 N=1e4 / 1e5 / 1e6 三组
    python bench/gen_data.py --sizes 1000 2000
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(os.path.dirname(HERE), "data")

SIZES = [10_000, 100_000, 1_000_000]
SEED = 20261116


def gen(n: int, seed: int) -> tuple:
    """生成 [-1, 1) 上均匀分布的两组 float64，固定种子保证可复现。"""
    rng = np.random.default_rng(seed + n)
    a = (rng.random(n) * 2.0 - 1.0).astype(np.float64)
    b = (rng.random(n) * 2.0 - 1.0).astype(np.float64)
    return a, b


def sha256_of(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sizes", nargs="*", type=int, default=SIZES)
    args = ap.parse_args(argv)

    os.makedirs(DATA, exist_ok=True)
    manifest = {"seed": SEED, "dtype": "float64", "endian": "little", "items": []}

    for n in args.sizes:
        a, b = gen(n, SEED)
        pa = os.path.join(DATA, f"a_f64_{n}.bin")
        pb = os.path.join(DATA, f"b_f64_{n}.bin")
        a.tofile(pa)
        b.tofile(pb)
        manifest["items"].append({
            "n": n,
            "a": os.path.relpath(pa, os.path.dirname(HERE)),
            "b": os.path.relpath(pb, os.path.dirname(HERE)),
            "bytes_each": n * 8,
            "sha256_a": sha256_of(pa),
            "sha256_b": sha256_of(pb),
            "python_dot": float(np.dot(a, b)),
        })
        print(f"[gen] N={n:>9,}  {pa}  {n * 8 / 1024:,.0f} KB  "
              f"numpy 点积 = {float(np.dot(a, b)):+.12f}")

    with open(os.path.join(DATA, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print(f"[gen] 清单写入 {os.path.join(DATA, 'manifest.json')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
