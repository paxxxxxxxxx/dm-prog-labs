#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成第 03、04 讲报告的插图（数据来自两讲各自的 results.json）。

用法：
    python tools/make_figures_l34.py
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import chart  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
L3 = os.path.join(ROOT, "lab03_matmul_layers")
L4 = os.path.join(ROOT, "lab04_dot_bench")


def load(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def fig_lab3() -> list:
    r = load(os.path.join(L3, "ref", "results.json"))
    out = os.path.join(L3, "report", "figures")
    made = []
    made.append(chart.layer_parallel_figure(os.path.join(out, "fig1_layers.png")))
    made.append(chart.asm_breakdown_figure(r["asm"]["total"], r["asm"]["counts"],
                                           os.path.join(out, "fig2_asm.png")))
    made.append(chart.matrix_consistency_figure(r["impl"]["c"], r["matrix"]["expect"],
                                                os.path.join(out, "fig3_matrix.png")))
    return made


def fig_lab4() -> list:
    r = load(os.path.join(L4, "results", "results.json"))
    out = os.path.join(L4, "report", "figures")
    made = []
    made.append(chart.time_bars_figure(r["runs"], os.path.join(out, "fig1_time.png")))
    made.append(chart.speedup_figure(r["runs"], os.path.join(out, "fig2_speedup.png")))
    made.append(chart.timer_figure(r["timer_probe"], os.path.join(out, "fig3_timer.png")))
    return made


def main() -> int:
    for f in fig_lab3() + fig_lab4():
        print(f"[figure] {os.path.relpath(f, ROOT)}  {os.path.getsize(f) // 1024} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
