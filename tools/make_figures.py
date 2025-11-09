#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从两个实验脚本导出的 results.json 生成报告插图。

用法（在仓库根目录）：
    python tools/make_figures.py
输出：
    lab01_number_storage/report/figures/*.png
    lab02_ai_workstation/report/figures/*.png

注意：图里的数字全部来自 results.json，不在这里手写死数据，
保证「报告表格 / 插图 / 脚本输出」三者永远一致。
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import chart  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
L1 = os.path.join(ROOT, "lab01_number_storage")
L2 = os.path.join(ROOT, "lab02_ai_workstation")


def load(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def fig_lab1() -> list:
    r = load(os.path.join(L1, "results.json"))
    out_dir = os.path.join(L1, "report", "figures")
    made = []

    # 图 1：位权展开
    made.append(chart.bit_weight_figure(r["task1"]["binary"],
                                        os.path.join(out_dir, "fig1_bit_weights.png")))

    # 图 2：三类媒体体积
    d4, d5, d6 = r["task4"], r["task5"], r["task6"]
    items = [
        ("1920×1080 · 24 位照片", f"{d4['bytes'] / 1e6:.2f} MB",
         f"≈ {d4['bytes'] / 2 ** 20:.2f} MiB\n宽×高×位深÷8", chart.ACCENT),
        ("4 分钟 · 44.1kHz/16bit 立体声", f"{d5['bytes'] / 1e6:.1f} MB",
         f"≈ {d5['bytes'] / 2 ** 20:.1f} MiB\nCD 码率 1411 kbps", chart.ACCENT2),
        ("2 小时 · 8 Mbps 视频", f"{d6['bytes'] / 1e9:.2f} GB",
         f"≈ {d6['bytes'] / 2 ** 30:.2f} GiB\n码率×时长÷8", chart.GREEN),
    ]
    made.append(chart.media_size_figure(items, os.path.join(out_dir, "fig2_media_sizes.png")))

    # 图 3：压缩前后
    rows = []
    for t7 in r["task7"]:
        rows.append((t7["label"] or t7["filename"],
                     f"{t7['width']}×{t7['height']} px，24 位色",
                     t7["raw_bytes"] / 1e6, t7["actual_bytes"] / 1e6,
                     t7["compressed_ratio"], t7["bytes_per_pixel"]))
    made.append(chart.compression_figure(rows, os.path.join(out_dir, "fig3_compression.png")))
    return made


def fig_lab2() -> list:
    r = load(os.path.join(L2, "results.json"))
    out_dir = os.path.join(L2, "report", "figures")
    made = []
    schemes = r["schemes"]

    split = []
    for s in schemes:
        if s["key"] == "C":
            cap = "统一内存 128GB（可分配约 96GB 给 GPU，没有 PCIe 插槽）"
        else:
            cap = f"显存 {s['vram_gb']}GB / 系统内存 {s['ram_gb']}GB"
        split.append({"key": s["key"], "cap": cap,
                      "vw": s["vram_weights_gb"], "rw": s["ram_weights_gb"],
                      "tok": s["tok_s"]})
    made.append(chart.memory_split_figure(split, r["model"]["total_int4_gb"],
                                          os.path.join(out_dir, "fig1_memory_split.png")))

    vals = [(s["key"], s["name"], s["tok_s"], s["tok_s_per_wan"], s["total"]) for s in schemes]
    made.append(chart.value_figure(vals, os.path.join(out_dir, "fig2_speed_value.png")))

    costs = []
    for s in schemes:
        parts = [(k, v["amount"]) for k, v in s["budget"].items()]
        costs.append((s["key"], s["total"], parts, s["cost_per_tok_s"]))
    made.append(chart.cost_figure(costs, os.path.join(out_dir, "fig3_cost_split.png")))
    return made


def main() -> int:
    files = fig_lab1() + fig_lab2()
    for f in files:
        print(f"[figure] {os.path.relpath(f, ROOT)}  {os.path.getsize(f) // 1024} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
