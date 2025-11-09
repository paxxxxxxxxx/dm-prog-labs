#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第 02 讲 外围系统与 AI 算力 —— H3 与 Strata Qwen3.8 128B 主机配置单计算器

对应实验指南：第 02 讲《外围系统与 AI 算力 · H3 与 Strata Qwen3.8 128B 主机配置单》
（实验步骤 1-8）

这个脚本不"编"结论，它只做四件事：
    1. 按公式推导模型体积（权重 / KV cache / 框架开销），判断"装不装得下"；
    2. 按「每 token 要搬多少字节 ÷ 该层带宽」推导出词速度，判断"跑不跑得快"；
    3. 用 2026-11 的真实渠道价把三套方案配出来，算整机价与「每万元买到多少 tok/s」；
    4. 核对 PCIe / 供电 / 长度 / 散热这些物理约束。

运行：
    python sizing.py                  # 打印完整推导
    python sizing.py --md out.md --csv out.csv --json out.json

所有价格都在 PRICES 里，改一行就能按最新行情重算。

带宽模型说明（重要）
--------------------
自回归解码每生成 1 个 token，至少要把「参与计算的那部分权重」从它所在的存储层读一遍，
所以单 token 耗时 ≈ Σ(该层权重大小 ÷ 该层带宽)。这就是显存不够、把层放到内存后
出词速度掉到个位数的原因：DDR5 双通道的带宽只有 RTX 5090 显存的 1/20 左右。

保守假设：按「全部权重每 token 读一遍」计算（MoE 稀疏激活实际只会读被路由到的专家，
实测通常比这里快 1.5-3 倍）。这样算出来的数字是下限，用来做方案对比不会高估。
"""

from __future__ import annotations

import argparse
import json
import math
import sys

# ---------------------------------------------------------------------------
# 一、口径与常数
# ---------------------------------------------------------------------------
GB = 1e9          # 十进制 GB（存储与显存容量都用它，避免 MB/MiB 混用）
GIB = 1024 ** 3

# 需求（实验指南 步骤 1）
CTX_TOKENS = 32_768          # 32K 上下文
H3_RES = (1344, 768)         # 768p 全画布（短边 768）
H3_SECONDS = 5               # 单条视频 5 秒
H3_STEPS = 20                # 全步数

# 模型（实验指南 步骤 2、3）
LLM_PARAMS = 128e9           # Strata Qwen3.8 Flash 128B（MoE）
LLM_LAYERS = 56              # 假设层数（MoE 常用 48-64 层）
LLM_KV_HEADS = 8             # GQA 的 KV 头数
LLM_HEAD_DIM = 128
KV_BYTES = 1                 # KV cache 用 FP8/INT8 存，1 B/元素

H3_PARAMS = 33e9             # MiniMax H3：33B 稠密单流 Transformer（含音频）
H3_WEIGHTS_GB = 12.0         # pruned INT8 扩散模型（实验指南给的 12GB）
H3_TEXT_ENCODER_GB = 14.6    # nvfp4 AWQ 文本编码器（每个提示词只跑一次，之后卸载）
H3_VAE_GB = 0.5

FRAMEWORK_OVERHEAD_GB = 2.0  # 激活、CUDA context、框架缓冲

# ---------------------------------------------------------------------------
# 二、2026-11 价格与规格（改这里就是改行情）
# ---------------------------------------------------------------------------
PRICES = {
    "gpu_5090": {
        "name": "RTX 5090 32GB GDDR7",
        "price": 54_000,
        "vram_gb": 32,
        "bandwidth_gbs": 1_792,
        "power_w": 575,
        "length_mm": 304,
        "source": "快科技 2026-10-27：电商 32GB 版已从 9 月前约 3.5 万元涨到约 5.4 万元",
    },
    "ddr5_128": {
        "name": "DDR5-6000 64GB×2（128GB）",
        "price": 16_000,
        "bandwidth_gbs": 80,          # 双通道理论 96 GB/s，按有效 80 计
        "source": "国内渠道 32GB 套条 2000-4000 元推算；日本零售 128GB 套装折合约 2.18 万元（2026-10）",
    },
    "ddr5_64": {
        "name": "DDR5-6000 32GB×2（64GB）",
        "price": 8_000,
        "bandwidth_gbs": 80,
        "source": "同上，按 32GB 套条中位价 ×2",
    },
    "cpu_9950x3d": {"name": "Ryzen 9 9950X3D", "price": 5_000, "power_w": 200},
    "mb_x870e": {"name": "X870E 主板（PCIe 5.0 x16）", "price": 3_500},
    "psu_1200": {"name": "1200W ATX 3.1 金牌", "price": 1_800},
    "psu_1600": {"name": "1600W ATX 3.1 白金", "price": 3_000},
    "case_cool": {"name": "机箱 + 360 水冷", "price": 1_500},
    "ssd_4t": {"name": "4TB PCIe 5.0 SSD", "price": 2_500},
    "mini_128g": {
        "name": "128GB 统一内存迷你主机（Ryzen AI Max+ Pro 495）",
        "price": 26_600,
        "vram_gb": 96,         # 可分配给 GPU 的统一内存上限（实际按 96GB 计）
        "bandwidth_gbs": 273,  # LPDDR5x-8533 × 256-bit
        "power_w": 140,
        "source": "Lenovo ThinkCentre X Ultra 起售价 3699 美元 × 7.2（2026-08 发布，11 月开售）",
    },
    "mac_studio_256g": {
        "name": "Mac Studio M5 Ultra 256GB",
        "price": 68_400,       # 9499 美元 × 7.2
        "vram_gb": 224,        # 统一内存可给 GPU 的实际上限
        "bandwidth_gbs": 1_200,
        "power_w": 270,
        "source": "Mac Studio M5 Ultra 96GB 起售 5499 美元，256GB 加 4000 美元（2026-08）",
    },
}

# H3 实测锚点：RTX 5090 跑 NVFP4，864×480 / 10 秒 / 10 步 ≈ 175 秒，峰值显存 26.9 GB
H3_ANCHOR = {
    "res": (864, 480),
    "seconds": 10,
    "steps": 10,
    "time_s": 175,
    "peak_vram_gb": 26.9,
}

# 相对 5090 的生成速度系数（同一 H3 工作流）
SPEED_FACTOR = {
    "gpu_5090": 1.0,
    "gpu_5090_x2": 1.0,   # 扩散是单流，双卡几乎不提速，只解决"装得下"
    "mini_128g": 1 / 3.5,  # iGPU 无 NVFP4 原生路径，按慢 3.5 倍估
    "mac_studio_256g": 1 / 2.5,   # Mac 走 MPS，视频生成生态弱，按慢 2.5 倍估
}


def money(x: float) -> str:
    return f"￥{x:,.0f}"


def gb(x: float) -> str:
    return f"{x:,.1f} GB"


# ---------------------------------------------------------------------------
# 三、模型体积推导
# ---------------------------------------------------------------------------
def weight_bytes(params: float, bits_per_param: float) -> float:
    """权重体积 = 参数量 × 每参数比特数 ÷ 8，返回字节。"""
    return params * bits_per_param / 8


def kv_cache_bytes(ctx: int = CTX_TOKENS, layers: int = LLM_LAYERS,
                   kv_heads: int = LLM_KV_HEADS, head_dim: int = LLM_HEAD_DIM,
                   bytes_per_elem: int = KV_BYTES) -> float:
    """KV cache = 2(K 和 V) × 层数 × KV 头数 × 头维度 × 上下文长度 × 每元素字节数。

    注意是「每层都有自己的一份 KV」，层数在乘号里面，这一项最容易被漏掉。
    """
    return 2 * layers * kv_heads * head_dim * ctx * bytes_per_elem


def model_sizing() -> dict:
    rows = []
    for name, bits in (("FP16", 16), ("INT8", 8), ("INT4", 4)):
        w = weight_bytes(LLM_PARAMS, bits)
        rows.append({"dtype": name, "bits": bits, "bytes": w, "gb": w / GB})

    kv = kv_cache_bytes()
    kv_fp16 = kv_cache_bytes(bytes_per_elem=2)
    return {
        "weights": rows,
        "kv_int8": {"bytes": kv, "gb": kv / GB},
        "kv_fp16": {"bytes": kv_fp16, "gb": kv_fp16 / GB},
        "overhead_gb": FRAMEWORK_OVERHEAD_GB,
        # 落地需要的总量：INT4 权重 + KV + 框架开销
        "total_int4_gb": rows[2]["gb"] + kv / GB + FRAMEWORK_OVERHEAD_GB,
    }


def kv_table() -> list:
    """不同上下文长度下的 KV cache，用来说明 32K 为什么要留 2-4GB。"""
    out = []
    for ctx, label in ((16_384, "16K"), (32_768, "32K"), (65_536, "64K"), (131_072, "128K")):
        out.append({
            "ctx": ctx,
            "label": label,
            "int8_gb": kv_cache_bytes(ctx=ctx) / GB,
            "fp16_gb": kv_cache_bytes(ctx=ctx, bytes_per_elem=2) / GB,
        })
    return out


def h3_sizing() -> dict:
    bf16 = weight_bytes(H3_PARAMS, 16) / GB
    int8 = weight_bytes(H3_PARAMS, 8) / GB
    int4 = weight_bytes(H3_PARAMS, 4) / GB
    peak = H3_WEIGHTS_GB + H3_VAE_GB + 2.0  # 扩散模型 + VAE + 激活
    peak_with_encoder = peak + H3_TEXT_ENCODER_GB
    return {
        "params": H3_PARAMS,
        "bf16_gb": bf16,
        "int8_gb": int8,
        "int4_gb": int4,
        "weights_int8_pruned_gb": H3_WEIGHTS_GB,
        "text_encoder_gb": H3_TEXT_ENCODER_GB,
        "vae_gb": H3_VAE_GB,
        "peak_gb": peak,
        "peak_with_encoder_gb": peak_with_encoder,
        # 实际要预留的显存：直接采用社区实测峰值，比"自己加"更可信
        "peak_effective_gb": H3_ANCHOR["peak_vram_gb"],
        "anchor": H3_ANCHOR,
    }


# ---------------------------------------------------------------------------
# 四、三套方案
# ---------------------------------------------------------------------------
def build_schemes() -> list:
    """三套方案：A 单卡+大内存（指南给定）、B 双卡、C 统一内存迷你主机。

    每套方案给出：部件清单、总价、显存/内存分层、出词速度、H3 单条耗时。
    """
    p = PRICES
    total_gb = model_sizing()["total_int4_gb"]        # INT4 权重 + KV + 开销
    kv = model_sizing()["kv_int8"]["gb"]

    def split(total: float, vram: float) -> tuple:
        """能放进显存的权重体积（要给 KV 和框架开销让位）。"""
        hot = max(0.0, min(vram - kv - FRAMEWORK_OVERHEAD_GB, total - kv - FRAMEWORK_OVERHEAD_GB))
        return hot, max(0.0, total - kv - FRAMEWORK_OVERHEAD_GB - hot)

    def tokens_per_sec(vram_weights: float, ram_weights: float,
                       vram_bw: float, ram_bw: float) -> float:
        """单 token 耗时 = 显存部分 ÷ 显存带宽 + 内存部分 ÷ 内存带宽。

        方案 C 的显存与内存是同一块物理内存（统一内存），所以 vram_weights 传 0、
        ram_weights 传全量，全部按统一内存带宽算。
        """
        t = 0.0
        if vram_weights > 0 and vram_bw > 0:
            t += vram_weights / vram_bw
        if ram_weights > 0:
            t += ram_weights / ram_bw
        return 1.0 / t if t > 0 else float("inf")

    def h3_seconds(factor: float, res=H3_RES, seconds=H3_SECONDS, steps=H3_STEPS) -> float:
        """按「像素数 × 帧数 × 步数」从实测锚点缩放。"""
        a = H3_ANCHOR
        k = (res[0] * res[1]) / (a["res"][0] * a["res"][1])
        k *= seconds / a["seconds"]
        k *= steps / a["steps"]
        return a["time_s"] * k / factor

    schemes = []

    # ---- 方案 A：32GB 单卡 + 128GB DDR5（指南给定方案）----
    parts_a = [
        ("GPU", p["gpu_5090"]["name"], 1, p["gpu_5090"]["price"]),
        ("内存", p["ddr5_128"]["name"], 1, p["ddr5_128"]["price"]),
        ("CPU", p["cpu_9950x3d"]["name"], 1, p["cpu_9950x3d"]["price"]),
        ("主板", p["mb_x870e"]["name"], 1, p["mb_x870e"]["price"]),
        ("电源", p["psu_1200"]["name"], 1, p["psu_1200"]["price"]),
        ("机箱散热", p["case_cool"]["name"], 1, p["case_cool"]["price"]),
        ("SSD", p["ssd_4t"]["name"], 1, p["ssd_4t"]["price"]),
    ]
    hot_a, cold_a = split(total_gb, p["gpu_5090"]["vram_gb"])
    tok_a = tokens_per_sec(hot_a, cold_a, p["gpu_5090"]["bandwidth_gbs"], p["ddr5_128"]["bandwidth_gbs"])
    schemes.append({
        "key": "A",
        "name": "方案 A：32GB 单卡 + 128GB DDR5（指南给定）",
        "parts": parts_a,
        "total": sum(q * u for _, _, q, u in parts_a),
        "vram_gb": p["gpu_5090"]["vram_gb"],
        "ram_gb": 128,
        "vram_weights_gb": hot_a,
        "ram_weights_gb": cold_a,
        "vram_bw": p["gpu_5090"]["bandwidth_gbs"],
        "ram_bw": p["ddr5_128"]["bandwidth_gbs"],
        "tok_s": tok_a,
        "h3_s": h3_seconds(SPEED_FACTOR["gpu_5090"]),
        "h3_ok": True,
        "power_w": p["gpu_5090"]["power_w"] + p["cpu_9950x3d"]["power_w"],
        "note": "32GB 显存装不下 64GB 权重，必须靠 llama.cpp 分层：热层进显存、其余走 DDR5",
    })

    # ---- 方案 B：双卡 64GB ----
    parts_b = [
        ("GPU", p["gpu_5090"]["name"], 2, p["gpu_5090"]["price"]),
        ("内存", p["ddr5_64"]["name"], 1, p["ddr5_64"]["price"]),
        ("CPU", p["cpu_9950x3d"]["name"], 1, p["cpu_9950x3d"]["price"]),
        ("主板", "X870E 双卡主板（x8/x8 拆分）", 1, 5_000),
        ("电源", p["psu_1600"]["name"], 1, p["psu_1600"]["price"]),
        ("机箱散热", "全塔机箱 + 双 360 水冷", 1, 2_600),
        ("SSD", p["ssd_4t"]["name"], 1, p["ssd_4t"]["price"]),
    ]
    hot_b, cold_b = split(total_gb, 2 * p["gpu_5090"]["vram_gb"])
    tok_b = tokens_per_sec(hot_b, cold_b, p["gpu_5090"]["bandwidth_gbs"], p["ddr5_64"]["bandwidth_gbs"])
    schemes.append({
        "key": "B",
        "name": "方案 B：双卡 64GB + 64GB DDR5",
        "parts": parts_b,
        "total": sum(q * u for _, _, q, u in parts_b),
        "vram_gb": 2 * p["gpu_5090"]["vram_gb"],
        "ram_gb": 64,
        "vram_weights_gb": hot_b,
        "ram_weights_gb": cold_b,
        "vram_bw": p["gpu_5090"]["bandwidth_gbs"],
        "ram_bw": p["ddr5_64"]["bandwidth_gbs"],
        "tok_s": tok_b,
        "h3_s": h3_seconds(SPEED_FACTOR["gpu_5090_x2"]),
        "h3_ok": True,
        "power_w": 2 * p["gpu_5090"]["power_w"] + p["cpu_9950x3d"]["power_w"],
        "note": "64GB 显存刚好卡在临界点：权重+KV+开销约 70GB，仍有 6GB 要落到内存",
    })

    # ---- 方案 C：128GB 统一内存迷你主机 ----
    mini = p["mini_128g"]
    tok_c = tokens_per_sec(0, total_gb, 0, mini["bandwidth_gbs"])
    schemes.append({
        "key": "C",
        "name": "方案 C：128GB 统一内存迷你主机（Ryzen AI Max+ Pro 495）",
        "parts": [("整机", mini["name"], 1, mini["price"])],
        "total": mini["price"],
        "vram_gb": mini["vram_gb"],
        "ram_gb": 128,
        "vram_weights_gb": 0.0,
        "ram_weights_gb": total_gb,
        "vram_bw": mini["bandwidth_gbs"],
        "ram_bw": mini["bandwidth_gbs"],
        "tok_s": tok_c,
        "h3_s": h3_seconds(SPEED_FACTOR["mini_128g"]),
        "h3_ok": True,
        "power_w": mini["power_w"],
        "note": "统一内存没有「分层」这一步，但所有访存都按 LPDDR5x 带宽算",
    })
    return schemes


def upgrade_path() -> dict:
    """半年后的升级路径：Mac Studio 256GB 作为"完全不分层"的参照。"""
    total = model_sizing()["total_int4_gb"]
    mac = PRICES["mac_studio_256g"]
    tok = 1.0 / (total / mac["bandwidth_gbs"])
    factor = SPEED_FACTOR["mac_studio_256g"]
    a = H3_ANCHOR
    k = (H3_RES[0] * H3_RES[1]) / (a["res"][0] * a["res"][1]) * (H3_SECONDS / a["seconds"]) * (H3_STEPS / a["steps"])
    return {
        "name": mac["name"],
        "price": mac["price"],
        "bandwidth_gbs": mac["bandwidth_gbs"],
        "tok_s": tok,
        "h3_s": a["time_s"] * k / factor,
        "source": mac["source"],
    }


# ---------------------------------------------------------------------------
# 五、预算占比与兼容性
# ---------------------------------------------------------------------------
def budget_split(scheme: dict) -> dict:
    """按 GPU / 内存 / 平台(CPU+主板+电源+机箱+SSD) 归类，和指南的 55-60% / 10% / 25% 对照。

    整机（SoC 一体）无法按部件拆分，单独列一档，避免算成「GPU 占 0%」这种假结论。
    """
    buckets = {"GPU": 0.0, "内存": 0.0, "平台": 0.0, "整机": 0.0}
    for kind, _name, qty, unit in scheme["parts"]:
        if kind == "GPU":
            buckets["GPU"] += qty * unit
        elif kind == "内存":
            buckets["内存"] += qty * unit
        elif kind == "整机":
            buckets["整机"] += qty * unit
        else:
            buckets["平台"] += qty * unit
    total = scheme["total"]
    return {k: (v, v / total * 100) for k, v in buckets.items() if v > 0}


def compatibility(scheme: dict) -> list:
    """逐项核对物理/接口约束，返回 (项目, 需求, 实际, 结论)。"""
    p = PRICES
    rows = []
    key = scheme["key"]
    if key in ("A", "B"):
        rows.append(("PCIe", "PCIe 5.0 x16（单卡）",
                     "x16 单卡" if key == "A" else "x8/x8 拆分（Gen5 x8 = 256 GB/s，够用）",
                     "满足"))
        need = 1.6 * scheme["power_w"]     # 留 60% 余量给瞬时功耗
        psu = p["psu_1200"]["price"] if key == "A" else p["psu_1600"]["price"]
        rows.append(("供电", f"峰值 {scheme['power_w']}W × 1.6",
                     f"{'1200W' if key == 'A' else '1600W'} 电源（{money(psu)}）",
                     "满足" if (1200 if key == "A" else 1600) >= need else "不足"))
        rows.append(("长度", "机箱限长 ≥ 显卡长度 + 供电线弯折空间",
                     "5090 公版 304mm，非公 330-360mm；需 ≥ 400mm 全塔" if key == "B" else "5090 约 304-360mm；需 ≥ 380mm 中塔",
                     "满足（选全塔）"))
        rows.append(("散热", "575W 级显卡热量直接排进机箱",
                     "机箱 3×140 进风 + 顶部排风" + ("；双卡之间至少留 1 槽间距" if key == "B" else ""),
                     "满足"))
        rows.append(("内存", "128GB 要 4 条 DDR5-6000 会掉频",
                     "用 64GB×2 双条，保留 2 个空槽" if key == "A" else "32GB×2 双条",
                     "满足"))
        rows.append(("驱动", "llama.cpp 分层要能指定每层放哪",
                     "--n-gpu-layers / --override-tensor 指定专家层；H3 跑时 LLM 先卸载",
                     "满足"))
    else:
        rows.append(("统一内存", "显存与内存共享 128GB",
                     "可分配约 96GB 给 GPU，权重 70GB 装得下", "满足"))
        rows.append(("带宽", "决定出词速度", "LPDDR5x-8533 × 256-bit = 273 GB/s", "够用但慢"))
        rows.append(("H3", "需要 CUDA/NVFP4 生态", "ROCm/ Vulkan 路径，无 NVFP4，按慢 3.5 倍估", "可跑，慢"))
        rows.append(("扩展", "后续能否加卡", "无 PCIe 插槽，只能整机替换", "受限"))
    return rows


# ---------------------------------------------------------------------------
# 六、输出
# ---------------------------------------------------------------------------
def build_results() -> dict:
    ms = model_sizing()
    schemes = build_schemes()
    h3 = h3_sizing()
    for s in schemes:
        s["cost_per_tok_s"] = s["total"] / s["tok_s"] if s["tok_s"] else float("inf")
        s["tok_s_per_wan"] = s["tok_s"] / (s["total"] / 10_000)
        s["budget"] = {k: {"amount": v[0], "percent": v[1]} for k, v in budget_split(s).items()}
        s["compat"] = compatibility(s)
        # 跑 H3 时，显存里还能剩多少给 LLM（决定能不能边聊边出片）
        s["llm_vram_during_h3_gb"] = max(0.0, s["vram_gb"] - h3["peak_effective_gb"])
        if s["key"] == "A":
            s["concurrent"] = (
                f"不能：H3 峰值 {h3['peak_effective_gb']:.0f}GB 时只剩 "
                f"{s['llm_vram_during_h3_gb']:.0f}GB，LLM 必须全部退出显存"
            )
        elif s["key"] == "B":
            s["concurrent"] = "可以：一张卡跑 H3、另一张卡驻留 LLM"
        else:
            s["concurrent"] = "可以：同一块统一内存，但两个任务同时跑会互相抢带宽"
    return {
        "model": ms,
        "kv": kv_table(),
        "h3": h3_sizing(),
        "schemes": schemes,
        "upgrade": upgrade_path(),
        "prices": PRICES,
    }


def fmt_hms(seconds: float) -> str:
    m, s = divmod(int(round(seconds)), 60)
    if m >= 60:
        h, m = divmod(m, 60)
        return f"{h}h{m:02d}m{s:02d}s"
    return f"{m}m{s:02d}s"


def print_report(r: dict) -> None:
    line = "=" * 82
    m, h3 = r["model"], r["h3"]

    print(line)
    print("第 02 讲 H3 与 Strata Qwen3.8 128B 主机配置单 —— 推导与三方案对照")
    print(line)

    print("\n[1] 模型体积：128B 参数在不同精度下的权重")
    print("    公式：权重 = 参数量 × 每参数比特数 ÷ 8")
    for row in m["weights"]:
        print(f"    {row['dtype']:<5} {row['bits']:>2} bit/参数  ->  {row['gb']:>7.1f} GB   "
              f"({row['bytes'] / GIB:.1f} GiB)")
    print(f"    -> 所以只考虑 INT4：64GB 权重是 32GB 单卡的 2 倍，单卡必装不下")

    print("\n[2] KV cache：32K 上下文要留多少显存")
    print("    公式：2(K,V) × 层数 × KV头数 × 头维度 × 上下文 × 每元素字节")
    print(f"    本机口径：{LLM_LAYERS} 层 × {LLM_KV_HEADS} KV头 × {LLM_HEAD_DIM} 维 × {CTX_TOKENS} token")
    print(f"    INT8/FP8 KV：{m['kv_int8']['gb']:.2f} GB     FP16 KV：{m['kv_fp16']['gb']:.2f} GB")
    print("    不同上下文下的 KV（INT8）：")
    for row in r["kv"]:
        print(f"      {row['label']:<5} {row['int8_gb']:>6.2f} GB（FP16 {row['fp16_gb']:>6.2f} GB）")
    print(f"    -> 与指南给的「32K 约 2-4GB」一致；再加框架开销 {m['overhead_gb']:.1f} GB")

    print(f"\n[3] 落地总量：INT4 权重 {m['weights'][2]['gb']:.1f} GB + KV {m['kv_int8']['gb']:.2f} GB "
          f"+ 开销 {m['overhead_gb']:.1f} GB = {m['total_int4_gb']:.1f} GB")
    print("    -> 关键结论：不是「64GB 权重」，而是「70GB 才能跑起来」。32GB 单卡差得远，")
    print("       双卡 64GB 也只是刚刚不够，仍然有 6GB 要落到内存。")

    print("\n[4] H3 体积：33B 稠密 Transformer（视频 + 音频同一路前向）")
    print(f"    BF16 全量 {h3['bf16_gb']:.1f} GB / INT8 {h3['int8_gb']:.1f} GB / INT4 {h3['int4_gb']:.1f} GB")
    print(f"    实际用 pruned INT8：{h3['weights_int8_pruned_gb']:.1f} GB（剪掉约 40% modulation 权重）")
    print(f"    扩散模型常驻：{h3['weights_int8_pruned_gb']:.1f} + VAE {h3['vae_gb']:.1f} + 激活 2.0 "
          f"= {h3['peak_gb']:.1f} GB")
    print(f"    文本编码器 {h3['text_encoder_gb']:.1f} GB 按需分块，与扩散模型叠加后上限约 "
          f"{h3['peak_with_encoder_gb']:.1f} GB")
    print(f"    社区实测峰值 {h3['anchor']['peak_vram_gb']} GB（5090 / NVFP4 / 864×480 / 10 秒 10 步）")
    print(f"    -> 规划时按实测峰值 {h3['peak_effective_gb']:.1f} GB 留显存：32GB 卡装得下，"
          f"但跑 H3 时只剩 5GB 给 LLM")

    print("\n[5] 出词速度模型")
    print("    单 token 耗时 = 显存里的权重量 ÷ 显存带宽 + 内存里的权重量 ÷ 内存带宽")
    print("    （保守假设：全部权重每 token 读一遍；MoE 稀疏激活实测会更快）")

    print("\n[6] 三方案对照")
    head = f"    {'方案':<6}{'显存/内存':<16}{'显存内权重':>10}{'内存内权重':>10}{'出词 tok/s':>12}{'H3 单条':>12}{'整机价':>12}{'元/(tok/s)':>12}"
    print(head)
    for s in r["schemes"]:
        print(f"    {s['key']:<6}{str(s['vram_gb']) + 'GB / ' + str(s['ram_gb']) + 'GB':<16}"
              f"{s['vram_weights_gb']:>9.1f}G{s['ram_weights_gb']:>9.1f}G"
              f"{s['tok_s']:>12.2f}{fmt_hms(s['h3_s']):>12}{money(s['total']):>12}"
              f"{money(s['cost_per_tok_s']):>12}")
    print(f"\n    每万元买到的 tok/s（越高越划算）：")
    for s in r["schemes"]:
        print(f"      {s['key']}  {s['tok_s_per_wan']:>5.2f} tok/s / 万元   —— {s['note']}")

    print("\n[7] 预算占比 vs 指南口径（GPU 55-60% / 内存 10% / 平台 25%）")
    for s in r["schemes"]:
        b = s["budget"]
        parts = "  ".join(f"{k} {v['percent']:>5.1f}%" for k, v in b.items())
        print(f"    {s['key']}: {parts}   合计 {money(s['total'])}")
    print("    -> 2026-11 的行情把内存从 10% 推到 15-20%，GPU 占比被挤到 60% 以上，")
    print("       指南给的 55-60/10/25 在当前价位已经配不出来，报告里要说明这一偏差。")

    print("\n[8] 兼容性核对")
    for s in r["schemes"]:
        print(f"    -- {s['name']}")
        for item, need, actual, verdict in s["compat"]:
            print(f"       {item:<8} 需求: {need}")
            print(f"       {'':<8} 实际: {actual} -> {verdict}")

    up = r["upgrade"]
    print("\n[9] 半年后的升级路径（完全不分层的参照）")
    print(f"    {up['name']}：{money(up['price'])}，带宽 {up['bandwidth_gbs']:.0f} GB/s，"
          f"出词 {up['tok_s']:.1f} tok/s，H3 单条 {fmt_hms(up['h3_s'])}")
    print("    -> 统一内存带宽一旦过 1 TB/s，「分层」这件事就消失了，这是真正的换代点。")

    print("\n" + line)
    print("数据来源：价格见 PRICES 里的 source 字段；H3 锚点见 H3_ANCHOR。")
    print(line)


def to_markdown(r: dict) -> str:
    m, h3 = r["model"], r["h3"]
    md = ["# 第 02 讲 配置单推导（脚本生成）", ""]

    md += ["## 1  模型体积", "", "| 精度 | 比特/参数 | 权重体积 |", "| --- | --- | --- |"]
    for row in m["weights"]:
        md.append(f"| {row['dtype']} | {row['bits']} | {row['gb']:.1f} GB（{row['bytes'] / GIB:.1f} GiB） |")
    md += ["", f"落地总量 = INT4 权重 {m['weights'][2]['gb']:.1f} GB + KV {m['kv_int8']['gb']:.2f} GB "
               f"+ 框架开销 {m['overhead_gb']:.1f} GB = **{m['total_int4_gb']:.1f} GB**", ""]

    md += ["## 2  KV cache", "", "| 上下文 | INT8/FP8 KV | FP16 KV |", "| --- | --- | --- |"]
    for row in r["kv"]:
        md.append(f"| {row['label']} | {row['int8_gb']:.2f} GB | {row['fp16_gb']:.2f} GB |")
    md.append("")

    md += ["## 3  H3 体积与峰值", "",
           f"- 33B：BF16 {h3['bf16_gb']:.1f} GB / INT8 {h3['int8_gb']:.1f} GB / INT4 {h3['int4_gb']:.1f} GB",
           f"- 实跑 pruned INT8：{h3['weights_int8_pruned_gb']:.1f} GB",
           f"- 峰值（含 VAE 与激活）：{h3['peak_gb']:.1f} GB；另有文本编码器 {h3['text_encoder_gb']:.1f} GB 编码后卸载",
           f"- 社区实测峰值：{h3['anchor']['peak_vram_gb']} GB（RTX 5090 / NVFP4）", ""]

    md += ["## 4  三方案对照", "",
           "| 方案 | 显存/内存 | 显存内权重 | 内存内权重 | 出词 tok/s | H3 单条 | 整机价 | 元/(tok/s) | 每万元 tok/s |",
           "| --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for s in r["schemes"]:
        md.append(f"| {s['key']} | {s['vram_gb']}GB / {s['ram_gb']}GB | {s['vram_weights_gb']:.1f} GB | "
                  f"{s['ram_weights_gb']:.1f} GB | {s['tok_s']:.2f} | {fmt_hms(s['h3_s'])} | "
                  f"{money(s['total'])} | {money(s['cost_per_tok_s'])} | {s['tok_s_per_wan']:.2f} |")
    md.append("")

    md += ["## 5  预算占比", "", "| 方案 | GPU | 内存 | 平台 | 整机 | 合计 |",
           "| --- | --- | --- | --- | --- | --- |"]
    for s in r["schemes"]:
        b = s["budget"]

        def pct(key):
            return f"{b[key]['percent']:.1f}%" if key in b else "—"

        md.append(f"| {s['key']} | {pct('GPU')} | {pct('内存')} | {pct('平台')} | {pct('整机')} | {money(s['total'])} |")
    md.append("")

    md += ["## 6  配置单明细", ""]
    for s in r["schemes"]:
        md.append(f"### {s['name']}")
        md.append("")
        md.append("| 类别 | 型号 | 数量 | 单价 | 小计 |")
        md.append("| --- | --- | --- | --- | --- |")
        for kind, name, qty, unit in s["parts"]:
            md.append(f"| {kind} | {name} | {qty} | {money(unit)} | {money(qty * unit)} |")
        md.append(f"| **合计** |  |  |  | **{money(s['total'])}** |")
        md.append("")
    return "\n".join(md)


def to_csv(r: dict) -> str:
    lines = ["scheme,name,vram_gb,ram_gb,vram_weights_gb,ram_weights_gb,tok_s,h3_seconds,total_cny,cny_per_tok_s,tok_s_per_wan"]
    for s in r["schemes"]:
        lines.append(
            f"{s['key']},\"{s['name']}\",{s['vram_gb']},{s['ram_gb']},"
            f"{s['vram_weights_gb']:.2f},{s['ram_weights_gb']:.2f},{s['tok_s']:.3f},"
            f"{s['h3_s']:.0f},{s['total']:.0f},{s['cost_per_tok_s']:.0f},{s['tok_s_per_wan']:.3f}"
        )
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="第 02 讲 主机配置单计算器")
    ap.add_argument("--md")
    ap.add_argument("--csv")
    ap.add_argument("--json")
    args = ap.parse_args(argv)

    r = build_results()
    print_report(r)

    if args.md:
        with open(args.md, "w", encoding="utf-8") as f:
            f.write(to_markdown(r))
        print(f"\n[已写出] {args.md}")
    if args.csv:
        with open(args.csv, "w", encoding="utf-8-sig") as f:
            f.write(to_csv(r))
        print(f"[已写出] {args.csv}")
    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(r, f, ensure_ascii=False, indent=2, default=str)
        print(f"[已写出] {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
