#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第 01 讲 数制转换与存储容量估算 —— 验证 + 估算脚本

对应实验指南：第 01 讲《计算机核心结构 · 数制转换与存储容量估算》
（实验步骤 1–7 + 拓展任务）

运行方式：
    python estimate.py                 # 打印完整计算过程
    python estimate.py --md out.md     # 同时导出 Markdown 版计算过程表
    python estimate.py --json out.json # 导出机器可读结果（供报告/图表复用）
    python estimate.py --image 截图.png --width 1080 --height 2400
                                       # 步骤 7：核对截图分辨率与实际文件大小

设计原则
--------
1. 所有结果都由「显式公式 + 显式单位」算出来，不写死常数，
   这样报告里的每一个数字都能在代码里找到出处；
2. 容量同时给出 SI 十进制单位（MB/GB, 10^3）与 IEC 二进制单位（MiB/GiB, 2^10），
   避免实验指南「常见问题」里点名的 MB/MiB 混用；
3. 压缩后的文件大小用于对照，绝不用它冒充未压缩估算值。
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from typing import Iterable

# ---------------------------------------------------------------------------
# 单位换算常数（只在这里定义一次，全脚本复用）
# ---------------------------------------------------------------------------
KB = 1000          # 十进制（SI）
MB = 1000 ** 2
GB = 1000 ** 3
KiB = 1024         # 二进制（IEC）
MiB = 1024 ** 2
GiB = 1024 ** 3


def to_units(n_bytes: float) -> dict:
    """把一个字节数换算成两套单位，便于同时展示、避免单位混用。"""
    return {
        "byte": n_bytes,
        "MB": n_bytes / MB,
        "MiB": n_bytes / MiB,
        "GB": n_bytes / GB,
        "GiB": n_bytes / GiB,
    }


def human(n_bytes: float) -> str:
    """MB / MiB 双写，保留两位小数。"""
    u = to_units(n_bytes)
    if u["GB"] >= 1:
        return f"{u['GB']:.2f} GB（{u['GiB']:.2f} GiB）"
    return f"{u['MB']:.2f} MB（{u['MiB']:.2f} MiB）"


# ---------------------------------------------------------------------------
# 步骤 1：二进制 → 十进制，写出每一位的位权
# ---------------------------------------------------------------------------
def bits_to_decimal(binary: str) -> dict:
    """按位权展开法把二进制串转成十进制，并返回展开明细。

    位权：从右往左依次是 2^0、2^1、2^2 ……；第 k 位（从右数，k 从 0 起）的权值是 2^k。
    值 = Σ(该位数字 × 2^k)
    """
    binary = binary.replace(" ", "")
    if not binary or set(binary) - {"0", "1"}:
        raise ValueError(f"不是合法的二进制串: {binary!r}")

    n = len(binary)
    rows = []           # 每一位的明细
    total = 0
    for pos, ch in enumerate(binary):
        bit = int(ch)
        power = n - 1 - pos          # 该位的指数
        weight = 1 << power          # 2^power，用移位保证是整数
        product = bit * weight       # 该位的贡献
        total += product
        rows.append(
            {
                "bit": bit,
                "power": power,
                "weight": weight,
                "product": product,
            }
        )
    assert total == int(binary, 2)   # 自己算的结果要和 Python 内置转换一致
    return {"binary": binary, "decimal": total, "rows": rows}


# ---------------------------------------------------------------------------
# 步骤 2：十进制 <-> 十六进制（除 16 取余）与十六进制 → 二进制（1 位拆 4 位）
# ---------------------------------------------------------------------------
def decimal_to_hex(n: int) -> dict:
    """除 16 取余，余数倒序排列。返回每一步的余数，方便写过程。"""
    if n < 0:
        raise ValueError("本实验只处理非负整数")
    steps = []
    q = n
    while True:
        q, r = divmod(q, 16)
        steps.append({"dividend": q * 16 + r, "quotient": q, "remainder": r})
        if q == 0:
            break
    digits = "".join("0123456789ABCDEF"[s["remainder"]] for s in reversed(steps))
    return {"decimal": n, "hex": digits, "steps": steps}


def hex_to_binary(h: str) -> dict:
    """十六进制每一位拆成 4 位二进制（一位十六进制 = 4 个二进制位）。"""
    h = h.upper().replace("0X", "")
    table = []
    out = []
    for ch in h:
        v = int(ch, 16)
        four = format(v, "04b")
        out.append(four)
        table.append({"hex_digit": ch, "decimal": v, "binary4": four})
    return {"hex": h, "binary": "".join(out), "table": table}


# ---------------------------------------------------------------------------
# 步骤 4–6：按位深 / 采样率 / 码率估算存储体积
# ---------------------------------------------------------------------------
def image_size(width: int, height: int, bit_depth: int = 24) -> dict:
    """未压缩位图 = 宽 × 高 × 每像素位数 ÷ 8。

    每像素位数：24 位 = RGB 各 8 位；32 位 = RGBA；48 位 = 每通道 16 位。
    """
    pixels = width * height
    total_bits = pixels * bit_depth
    n_bytes = total_bits / 8
    return {
        "kind": "photo",
        "width": width,
        "height": height,
        "bit_depth": bit_depth,
        "pixels": pixels,
        "bits": total_bits,
        "bytes": n_bytes,
        "formula": f"{width}×{height} px × {bit_depth} bit ÷ 8 = {n_bytes:,.0f} B",
    }


def audio_size(minutes: float, sample_rate: int = 44100, bit_depth: int = 16, channels: int = 2) -> dict:
    """未压缩 PCM = 采样率 × 位深 × 声道数 × 时长（秒）÷ 8。

    单位链：44,100 次/秒 × 16 bit × 2 声道 = 1,411,200 bit/s = 176,400 B/s
    """
    seconds = minutes * 60
    bitrate = sample_rate * bit_depth * channels          # bit/s
    n_bytes = bitrate * seconds / 8
    return {
        "kind": "audio",
        "minutes": minutes,
        "seconds": seconds,
        "sample_rate": sample_rate,
        "bit_depth": bit_depth,
        "channels": channels,
        "bitrate_bps": bitrate,
        "bytes": n_bytes,
        "formula": (
            f"{sample_rate:,} Hz × {bit_depth} bit × {channels} 声道 × {seconds:.0f} s ÷ 8 "
            f"= {n_bytes:,.0f} B"
        ),
    }


def video_size(hours: float, bitrate_mbps: float = 8.0) -> dict:
    """按码率估算 = 码率(Mbit/s) × 时长(s) ÷ 8。

    注意 8 Mbps 里的 M 是 10^6（网络/视频码率的惯例），不是 2^20。
    """
    seconds = hours * 3600
    n_bytes = bitrate_mbps * 1_000_000 * seconds / 8
    return {
        "kind": "video",
        "hours": hours,
        "seconds": seconds,
        "bitrate_mbps": bitrate_mbps,
        "bytes": n_bytes,
        "formula": f"{bitrate_mbps} Mbit/s × 10^6 × {seconds:.0f} s ÷ 8 = {n_bytes:,.0f} B",
    }


# ---------------------------------------------------------------------------
# 步骤 7：截图 / 照片的「理论未压缩大小 vs 实际文件大小」
# ---------------------------------------------------------------------------
def compression_report(path: str, width: int, height: int, bit_depth: int = 24, label: str = "") -> dict:
    """对比：理论未压缩大小、实际文件大小、压缩比、每像素平均字节数。"""
    raw = width * height * bit_depth / 8
    actual = os.path.getsize(path)
    ratio = raw / actual
    return {
        "path": os.path.abspath(path),
        "filename": os.path.basename(path),
        "label": label,
        "width": width,
        "height": height,
        "bit_depth": bit_depth,
        "pixels": width * height,
        "raw_bytes": raw,
        "actual_bytes": actual,
        "compressed_ratio": ratio,          # 压缩比 = 原始 / 实际
        "saving_percent": (1 - actual / raw) * 100,
        "bytes_per_pixel": actual / (width * height),
    }


def parse_measure_arg(spec: str) -> tuple:
    """解析 --measure 的取值：路径|宽x高|标签（用竖线分隔，避免和 Windows 盘符冲突）。"""
    parts = [p.strip() for p in spec.split("|")]
    if len(parts) < 2:
        raise SystemExit("--measure 需要写成 路径|宽x高[|标签]，例如 \"shot.png|1080x2400|手机截图\"")
    path, size = parts[0], parts[1]
    label = parts[2] if len(parts) > 2 else ""
    try:
        w, h = (int(v) for v in size.lower().split("x"))
    except ValueError:
        raise SystemExit(f"无法解析尺寸 {size!r}，应写成 1080x2400")
    if not os.path.isfile(path):
        raise SystemExit(f"找不到文件：{path}")
    return path, w, h, label


# ---------------------------------------------------------------------------
# 拓展任务：256 GB 手机能存多少张自己拍的照片
# ---------------------------------------------------------------------------
PHOTO_CASES = [
    # (档位名称, 单张体积 MB, 说明)
    ("12MP HEIC（默认高效格式）", 3.2, "iPhone/多数安卓默认，压缩率高"),
    ("12MP JPEG（兼容格式）", 4.8, "同分辨率，JPEG 比 HEIC 大约 50%"),
    ("48MP 高像素 JPEG", 9.5, "高像素模式，细节多、体积翻倍"),
    ("48MP ProRAW / RAW", 26.0, "保留原始传感器数据，几乎不压缩"),
]

PHONE_CAPACITY_GB = 256.0
USABLE_RATIO = 0.90        # 系统、App、缓存大约吃掉 10%


def phone_photo_capacity(capacity_gb: float = PHONE_CAPACITY_GB,
                         usable_ratio: float = USABLE_RATIO,
                         cases: Iterable = PHOTO_CASES) -> list:
    usable_bytes = capacity_gb * GB * usable_ratio
    rows = []
    for name, mb, note in cases:
        per_photo = mb * MB
        rows.append(
            {
                "case": name,
                "mb": mb,
                "note": note,
                "count": math.floor(usable_bytes / per_photo),
                "usable_gb": usable_bytes / GB,
            }
        )
    return rows


# ---------------------------------------------------------------------------
# 结果输出
# ---------------------------------------------------------------------------
def build_results(measurements: list | None = None) -> dict:
    results: dict = {}

    # 1) 位权展开
    results["task1"] = bits_to_decimal("10110101")

    # 2) 数制互转
    to_hex = decimal_to_hex(255)
    to_bin = hex_to_binary("1A")
    results["task2"] = {
        "255_to_hex": to_hex,
        "1A_to_bin": to_bin,
    }

    # 3) Python 内置函数交叉验证
    results["task3"] = {
        "python": {
            "int_10110101_base2": int("10110101", 2),
            "hex_255": hex(255),
            "bin_0x1A": bin(0x1A),
            "int_1A_base16": int("1A", 16),
        },
        "self_check": {
            "binary_match": int("10110101", 2) == results["task1"]["decimal"],
            "hex_match": hex(255).upper() == "0XFF",
            "bin_match": bin(0x1A) == "0b11010",
        },
    }

    # 4–6) 三类媒体容量
    results["task4"] = image_size(1920, 1080, 24)
    results["task5"] = audio_size(4, 44100, 16, 2)
    results["task6"] = video_size(2, 8.0)

    # 7) 截图实测（可选，可给多组）
    if measurements:
        results["task7"] = [compression_report(p, w, h, 24, label) for (p, w, h, label) in measurements]

    # 拓展任务
    results["extension"] = {
        "capacity_gb": PHONE_CAPACITY_GB,
        "usable_ratio": USABLE_RATIO,
        "rows": phone_photo_capacity(),
    }
    return results


def print_report(r: dict) -> None:
    line = "=" * 78

    print(line)
    print("第 01 讲 数制转换与存储容量估算 —— 计算过程与验证结果")
    print(line)

    # ---- 步骤 1 ----
    t1 = r["task1"]
    print("\n【步骤 1】二进制 → 十进制：按位权展开")
    print(f"  被转换数：{t1['binary']}_2（共 {len(t1['binary'])} 位）\n")
    print("  位数(从右数)  该位数字   位权 2^k      该位贡献 = 数字 × 位权")
    for i, row in enumerate(reversed(t1["rows"]), start=0):
        print(f"      第 {i} 位         {row['bit']}        2^{row['power']:<2} = {row['weight']:<5}   {row['bit']} × {row['weight']:<5} = {row['product']:<5}")
    print("\n  展开式：", end="")
    print(" + ".join(str(x["product"]) for x in t1["rows"] if x["product"]) , end="")
    print(f" = {t1['decimal']}")
    print(f"  结论：{t1['binary']}_2 = {t1['decimal']}_10")

    # ---- 步骤 2 ----
    t2 = r["task2"]
    h = t2["255_to_hex"]
    print("\n【步骤 2a】十进制 → 十六进制：除 16 取余，余数倒序")
    for s in h["steps"]:
        print(f"    {s['dividend']:>4} ÷ 16 = {s['quotient']:>3} …… 余 {s['remainder']:>2} "
              f"→ 十六进制位 {'0123456789ABCDEF'[s['remainder']]}")
    print(f"  结论：255_10 = 0x{h['hex']}")

    b = t2["1A_to_bin"]
    print("\n【步骤 2b】十六进制 → 二进制：一位十六进制拆成四位二进制")
    for row in b["table"]:
        print(f"    {row['hex_digit']} → {row['decimal']:>2} → {row['binary4']}")
    print(f"  结论：0x{b['hex']} = {b['binary']}_2 = {int(b['binary'], 2)}_10")

    # ---- 步骤 3 ----
    t3 = r["task3"]
    py = t3["python"]
    print("\n【步骤 3】用 Python 内置函数交叉验证（三方结果必须一致）")
    print(f"    int('10110101', 2) = {py['int_10110101_base2']}")
    print(f"    hex(255)           = {py['hex_255']}")
    print(f"    bin(0x1A)          = {py['bin_0x1A']}")
    print(f"    int('1A', 16)      = {py['int_1A_base16']}")
    ok = all(t3["self_check"].values())
    print(f"    自检：{'全部一致 [OK]' if ok else '存在不一致 [X]'}  {t3['self_check']}")

    # ---- 步骤 4–6 ----
    print("\n【步骤 4–6】按位深 / 采样率 / 码率估算存储体积")
    print("  单位约定：1 MB = 10^6 B，1 MiB = 2^20 B；报告里两套单位同时写，绝不混用。")
    for key, label in (("task4", "照片"), ("task5", "音频"), ("task6", "视频")):
        d = r[key]
        print(f"\n  - {label}")
        print(f"    公式：{d['formula']}")
        print(f"    结果：{human(d['bytes'])}")

    # ---- 步骤 7 ----
    if "task7" in r:
        print("\n【步骤 7】截图 / 照片：理论未压缩大小 vs 实际文件大小")
        print("    同一张图，位深固定 24 位：未压缩 = 宽 × 高 × 3 B；实际大小看文件系统里的大小。")
        print("    名称                  分辨率        理论未压缩        实际文件        压缩比   每像素")
        for t7 in r["task7"]:
            name = (t7["label"] or t7["filename"])[:20]
            print(f"    {name:<20} {t7['width']}×{t7['height']:<6} "
                  f"{t7['raw_bytes'] / MB:>8.2f} MB  {t7['actual_bytes'] / MB:>8.2f} MB  "
                  f"{t7['compressed_ratio']:>7.1f}:1  {t7['bytes_per_pixel']:.2f} B")

    # ---- 拓展 ----
    ext = r["extension"]
    print("\n【拓展任务】256 GB 手机能存多少张自己拍的照片")
    print(f"    可用容量 = {ext['capacity_gb']:.0f} GB × {ext['usable_ratio']:.0%} = {ext['capacity_gb'] * ext['usable_ratio']:.0f} GB")
    print("    拍摄格式                 单张体积      可存张数      备注")
    for row in ext["rows"]:
        print(f"    {row['case']:<22} {row['mb']:>6.1f} MB  {row['count']:>9,} 张   {row['note']}")

    print("\n" + line)
    print("说明：以上每个数字都由脚本按公式算出，--json 导出的同一份数据用于生成报告表格。")
    print(line)


def to_markdown(r: dict) -> str:
    """导出 Markdown 计算过程表，可直接粘进报告或 README。"""
    md = ["# 第 01 讲 计算过程表（脚本生成）", ""]

    t1 = r["task1"]
    md.append("## 步骤 1  10110101_2 → 十进制（按位权展开）")
    md.append("")
    md.append("| 位数（从右数） | 该位数字 | 位权 2^k | 该位贡献 |")
    md.append("| --- | --- | --- | --- |")
    for i, row in enumerate(reversed(t1["rows"])):
        md.append(f"| 第 {i} 位 | {row['bit']} | 2^{row['power']} = {row['weight']} | {row['product']} |")
    md.append("")
    md.append("展开式：" + " + ".join(str(x["product"]) for x in t1["rows"] if x["product"]) + f" = **{t1['decimal']}**")
    md.append("")

    t2 = r["task2"]
    md.append("## 步骤 2  十进制 <-> 十六进制、十六进制 → 二进制")
    md.append("")
    md.append("| 被除数 | ÷16 商 | 余数 | 十六进制位 |")
    md.append("| --- | --- | --- | --- |")
    for s in t2["255_to_hex"]["steps"]:
        md.append(f"| {s['dividend']} | {s['quotient']} | {s['remainder']} | {'0123456789ABCDEF'[s['remainder']]} |")
    md.append("")
    md.append("余数倒序 → **255_10 = 0xFF**")
    md.append("")
    md.append("| 十六进制位 | 十进制 | 四位二进制 |")
    md.append("| --- | --- | --- |")
    for row in t2["1A_to_bin"]["table"]:
        md.append(f"| {row['hex_digit']} | {row['decimal']} | {row['binary4']} |")
    md.append("")
    md.append(f"→ **0x1A = {t2['1A_to_bin']['binary']}_2 = {int(t2['1A_to_bin']['binary'], 2)}_10**")
    md.append("")

    md.append("## 步骤 4–6  存储容量估算")
    md.append("")
    md.append("| 对象 | 公式 | 结果 |")
    md.append("| --- | --- | --- |")
    for key, label in (("task4", "1920×1080 24 位照片"), ("task5", "4 分钟 44.1kHz/16bit 立体声"), ("task6", "2 小时 8Mbps 视频")):
        d = r[key]
        md.append(f"| {label} | {d['formula']} | {human(d['bytes'])} |")
    md.append("")

    if "task7" in r:
        md.append("## 步骤 7  压缩前后对照")
        md.append("")
        md.append("| 对象 | 分辨率 | 理论未压缩 | 实际文件 | 压缩比 | 平均每像素 |")
        md.append("| --- | --- | --- | --- | --- | --- |")
        for t7 in r["task7"]:
            md.append(
                f"| {t7['label'] or t7['filename']} | {t7['width']}×{t7['height']} | "
                f"{t7['raw_bytes']:,.0f} B（{t7['raw_bytes'] / MB:.2f} MB） | "
                f"{t7['actual_bytes']:,.0f} B（{t7['actual_bytes'] / MB:.2f} MB） | "
                f"{t7['compressed_ratio']:.1f} : 1 | {t7['bytes_per_pixel']:.2f} B |"
            )
        md.append("")

    ext = r["extension"]
    md.append("## 拓展  256 GB 手机可存照片张数")
    md.append("")
    md.append("| 拍摄格式 | 单张体积 | 可存张数 | 备注 |")
    md.append("| --- | --- | --- | --- |")
    for row in ext["rows"]:
        md.append(f"| {row['case']} | {row['mb']:.1f} MB | {row['count']:,} | {row['note']} |")
    md.append("")
    return "\n".join(md)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="第 01 讲 数制转换与存储容量估算")
    p.add_argument("--md", help="导出 Markdown 计算过程表")
    p.add_argument("--json", help="导出 JSON 结果")
    p.add_argument(
        "--measure",
        action="append",
        default=[],
        metavar="路径|宽x高|标签",
        help="步骤 7：核对某个图片的理论未压缩大小与实际文件大小，可给多次",
    )
    args = p.parse_args(argv)

    measurements = [parse_measure_arg(s) for s in args.measure]
    r = build_results(measurements)
    print_report(r)

    if args.md:
        with open(args.md, "w", encoding="utf-8") as f:
            f.write(to_markdown(r))
        print(f"\n[已写出] {args.md}")
    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(r, f, ensure_ascii=False, indent=2)
        print(f"[已写出] {args.json}")

    ok = all(r["task3"]["self_check"].values())
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
