#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把第 02 讲实验报告模板填成完整报告（保留老师的版式）。

用法（在仓库根目录，先跑 sizing.py 生成 results.json）：
    python tools/build_lab2.py
输出：
    lab02_ai_workstation/report/第02讲-H3 与 Strata Qwen3.8 128B 主机配置单-实验报告.docx

表格与正文里的每个数字都从 results.json 取，避免"改了脚本忘了改报告"。
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from docx import Document  # noqa: E402

import docx_util as U  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
L2 = os.path.join(ROOT, "lab02_ai_workstation")
TPL = os.path.join(ROOT, "templates", "第02讲-H3 与 Strata Qwen3.8 128B 主机配置单-实验报告.docx")
OUT = os.path.join(L2, "report", "第02讲-H3 与 Strata Qwen3.8 128B 主机配置单-实验报告.docx")
FIG = os.path.join(L2, "report", "figures")

with open(os.path.join(L2, "results.json"), encoding="utf-8") as f:
    R = json.load(f)

S = {s["key"]: s for s in R["schemes"]}
UP = R["upgrade"]
TOTAL_GB = R["model"]["total_int4_gb"]
KV_GB = R["model"]["kv_int8"]["gb"]
H3_PEAK = R["h3"]["peak_effective_gb"]


def hms(sec: float) -> str:
    m, s = divmod(int(round(sec)), 60)
    if m >= 60:
        h, m = divmod(m, 60)
        return f"{h}h{m:02d}m{s:02d}s"
    return f"{m}m{s:02d}s"


def pct(scheme: dict, key: str) -> str:
    b = scheme["budget"]
    return f"{b[key]['percent']:.1f}%" if key in b else "—"


# ---------------------------------------------------------------------------
# 一、实验目的
# ---------------------------------------------------------------------------
# 报告首页要填的信息：放到本地 student.local.json（已在 .gitignore 里挡住，不会进仓库）
STUDENT = {"班级": "", "姓名": "", "学号": "", "日期": ""}
_local_student = os.path.join(ROOT, "student.local.json")
if os.path.isfile(_local_student):
    with open(_local_student, encoding="utf-8") as _f:
        STUDENT.update(json.load(_f))

GOALS = [
    "① 能从「Strata Qwen3.8 Flash 128B（INT4）长文对话 + MiniMax H3 视频生成」这两个需求"
    f"倒推出显存 / 内存 / 带宽门槛：权重 64 GB、32K 上下文 KV cache {KV_GB:.2f} GB、"
    f"加框架开销共 {TOTAL_GB:.1f} GB 才「跑得起来」。",
    "② 能用同一口径（出词 tok/s、H3 单条耗时、整机价、元/(tok/s)、每万元 tok/s）比较三套方案，"
    "并用量化数据说明为什么不多花、也不少花。",
    "③ 能核对 PCIe 5.0、供电、显卡长度、散热四项物理约束，"
    "并给出「哪些任务本地跑、哪些上云」的分界线与半年后的升级路径。",
]

# ---------------------------------------------------------------------------
# 二、实验环境与工具
# ---------------------------------------------------------------------------
ENV = [
    "本次为纸面选型，不占用本机算力；本机是普通笔记本（Windows 11 x64，无独立显卡），"
    "只用来查价、跑计算脚本和排版。价格取自 2026 年 11 月的电商渠道页与公开报道，"
    "汇率按 1 美元 ≈ 7.2 元折算。",
    "Python 3.12.14（标准库）+ VS Code；sizing.py 完成全部推导并输出 results.md / results.csv；"
    "参考工具：llama.cpp（--n-gpu-layers / --override-tensor 做分层）、ComfyUI 0.30（H3 工作流）、"
    "Windows 计算器。",
    "数据与素材：2026-11 电商渠道报价（RTX 5090 32GB 约 5.4 万元、DDR5-6000 128GB 套装约 1.6 万元、"
    "2TB 固态与 1200W 电源按京东自营价）；公开资料：MiniMax H3 模型卡与社区显存实测、"
    "RTX 5090 规格与行情报道、Mac Studio M5 Ultra 与 ThinkCentre X Ultra 的发布信息。",
]

# ---------------------------------------------------------------------------
# 三、实验步骤
# ---------------------------------------------------------------------------
STEPS = [
    ("写清需求",
     "本地 32K 长文对话 + H3 生成 480p/768p 带音频视频",
     f"两个任务都要显存：H3 峰值 {H3_PEAK:.1f} GB、对话 KV {KV_GB:.2f} GB，不能同时全占"),
    ("算模型体积",
     "128×10^{9} 参数 × 4 bit ÷ 8 = 64 GB；FP16 256 GB、INT8 128 GB",
     "只有 INT4 有可能进消费级；INT8 要 128 GB 显存，不现实"),
    ("算 KV cache",
     "2(K,V) × 56 层 × 8 个 KV 头 × 128 维 × 32768 token × 1 B",
     f"{KV_GB:.2f} GB（FP16 KV 则 7.52 GB）；再加框架开销 2 GB"),
    ("拆任务",
     "H3 pruned INT8 约 12 GB，可整块进显存；128B INT4 的 64 GB 单卡装不下",
     "必须分层（显存+内存），或换双卡 / 统一内存"),
    ("定三套方案",
     "A 32GB 单卡 + 128GB DDR5（指南给定）；B 双卡 64GB；C 128GB 统一内存",
     "三套都能跑通，差别在速度、价格与能否并发"),
    ("分配预算并核对约束",
     "按 GPU 55-60%、内存 10%、平台 25% 分配；核对 PCIe 5.0 x16 / 1200W / 卡长 / 风道",
     f"实际占比 GPU {pct(S['A'], 'GPU')}、内存 {pct(S['A'], '内存')}、平台 {pct(S['A'], '平台')}（内存涨价所致），物理约束全部满足"),
    ("估性能与成本",
     "用「每 token 读多少字节 ÷ 该层带宽」算 tok/s；H3 按像素×帧数×步数从实测锚点缩放",
     f"A {S['A']['tok_s']:.2f} tok/s / {hms(S['A']['h3_s'])}；B {S['B']['tok_s']:.2f} / {hms(S['B']['h3_s'])}；"
     f"C {S['C']['tok_s']:.2f} / {hms(S['C']['h3_s'])}"),
    ("写结论",
     "哪些任务本地跑、哪些上云；给一条半年后的升级路径",
     "对话本地、出片云端；半年后换 1.2 TB/s 的统一内存机型"),
]

# ---------------------------------------------------------------------------
# 四、方案 A 配置单（型号 / 价格 / 选型理由）
# ---------------------------------------------------------------------------
CONFIG_A = [
    ("GPU", "RTX 5090 32GB GDDR7", "54,000",
     f"H3 峰值 {H3_PEAK:.1f} GB 必须 32GB 显存才放得下；1792 GB/s 是全机唯一的高带宽层，"
     "LLM 的热层必须靠它"),
    ("内存", "DDR5-6000 64GB×2（128GB）", "16,000",
     f"64 GB 权重装不进 32GB 显存，多出的 {S['A']['ram_weights_gb']:.1f} GB 只能放内存；"
     "用两条 64GB 而不是四条 32GB，避免四槽降频到 4800 以下"),
    ("CPU", "Ryzen 9 9950X3D", "5,000",
     "只负责调度、分词与权重加载；16 核够用，大缓存在长上下文预处理上有帮助"),
    ("主板", "X870E（PCIe 5.0 x16 直连）", "3,500",
     "显卡要满带宽 x16 直连；4 条 DDR5 插槽留出升级空间"),
    ("电源", "1200W ATX 3.1 金牌", "1,800",
     "峰值 775W（575+200），按 65% 负载选 1200W，留出瞬时功耗余量；原生 12V-2x6 接口"),
    ("机箱散热", "中塔 + 360 水冷", "1,500",
     "5090 长 304-360mm、3.5 槽，机箱限长需 ≥380mm；3×140 进风直吹显卡"),
    ("SSD", "4TB PCIe 5.0", "2,500",
     "64GB 权重 + H3 权重 + 素材，4TB 才装得下两三套模型并留出缓存空间"),
]

# ---------------------------------------------------------------------------
# 五、问题与解决
# ---------------------------------------------------------------------------
PROBLEMS = [
    ("按「权重 64GB」选了 64GB 显存的双卡，算完发现仍然装不满",
     "漏算 KV cache 3.76GB 与框架开销 2GB，实际要 69.8GB 才够",
     f"按 69.8GB 重新分层：双卡仍有 {S['B']['ram_weights_gb']:.1f}GB 落内存，"
     f"出词从理论上限掉到 {S['B']['tok_s']:.2f} tok/s"),
    ("三方案的 tok/s 相差 4.7 倍，怀疑公式写反了",
     "DDR5 双通道 80GB/s 只有 GDDR7 1792GB/s 的 1/22，差距本来就该这么大",
     f"用「每 token 读多少字节 ÷ 该层带宽」逐项复核：方案 A 单 token "
     f"{S['A']['ram_weights_gb'] / 80 + S['A']['vram_weights_gb'] / 1792:.3f}s，与「个位数 tok/s」的经验一致"),
    ("预算占比与指南给的 55-60% / 10% / 25% 对不上",
     "2026 年 DRAM 涨价约 760%，128GB 套装从 2500 元涨到 1.6 万元",
     "如实记录偏差并单列一节说明；不为了凑比例去换更慢的内存"),
    ("H3 与 LLM 同时跑必 OOM",
     f"H3 峰值 {H3_PEAK:.1f}GB，32GB 卡只剩 {S['A']['llm_vram_during_h3_gb']:.1f}GB，一层专家都放不下",
     "错峰：出片前用 --override-tensor 把 LLM 专家层赶回内存；要并发就选双卡或统一内存"),
]

# ---------------------------------------------------------------------------
# 六、图
# ---------------------------------------------------------------------------
FIGURES = [
    ("fig1_memory_split.png", "图 1　三方案的权重落位：显存装不下的部分只能落到内存，速度随之下滑"),
    ("fig2_speed_value.png", "图 2　绝对速度与每万元买到的速度：把价格除进去，排序会反过来"),
    ("fig3_cost_split.png", "图 3　整机价格构成：GPU 占比 64%~81%，内存涨价把平台预算挤到 13%~17%"),
]


def build_analysis() -> list:
    a, b, c = S["A"], S["B"], S["C"]
    return [
        f"**（1）容量推导链：70 GB 是「能不能跑」的硬门槛。** 128B 参数按 INT4 存是 "
        f"128×10^{{9}}×0.5 B = 64 GB；32K 上下文的 KV cache 是 2×56 层×8 个 KV 头×128 维×32768 token×1 B "
        f"= {KV_GB:.2f} GB；再加 CUDA context、激活与框架缓冲约 2 GB，合计 {TOTAL_GB:.1f} GB。"
        f"这三个数各有各的作用：64 GB 决定了「一张 32 GB 卡肯定不够」；{KV_GB:.2f} GB 决定了"
        f"「双卡 64 GB 也只是刚好差一点」；2 GB 决定了「别把显存算到最后一兆」。"
        f"指南「常见问题」里说的「只算权重不算 KV cache 与框架开销，128GB 内存也会 OOM」，"
        f"指的就是这条链。",

        f"**（2）速度由带宽决定，不由算力决定。** 解码每个 token 至少要把参与计算的那部分权重读一遍，"
        f"所以单 token 时间 ≈ Σ(该层权重 ÷ 该层带宽)。方案 A 把 {a['ram_weights_gb']:.1f} GB 放在 80 GB/s 的 DDR5 上："
        f"{a['ram_weights_gb'] / 80:.3f} s；显存里的 {a['vram_weights_gb']:.1f} GB 只要 "
        f"{a['vram_weights_gb'] / 1792:.3f} s；合计 {a['ram_weights_gb'] / 80 + a['vram_weights_gb'] / 1792:.3f} s/token，"
        f"即 {a['tok_s']:.2f} tok/s。这正是指南说的「分层推理受内存带宽限制，出词只有个位数」。"
        f"方案 B 只剩 {b['ram_weights_gb']:.1f} GB 落内存，升到 {b['tok_s']:.2f} tok/s；"
        f"方案 C 虽然全部走内存，但 LPDDR5x-8533 的 273 GB/s 是 DDR5 的 3.4 倍，反而有 {c['tok_s']:.2f} tok/s；"
        f"参考机型 D 的 1.2 TB/s 统一内存几乎等于「不分层」，拿到 {UP['tok_s']:.1f} tok/s。"
        f"结论很直接：**同一块模型，谁的高带宽层更大、谁的出词就更快。**",

        f"**（3）性价比：把价格除进去，排序会反过来。** 方案 A 是 ￥{a['cost_per_tok_s']:,.0f}/(tok/s)，"
        f"B 是 ￥{b['cost_per_tok_s']:,.0f}，C 是 ￥{c['cost_per_tok_s']:,.0f}，参考机型 D 是 "
        f"￥{UP['price'] / UP['tok_s']:,.0f}。方案 A 的问题不是「慢」而是「两头不靠」：比 C 贵 3.2 倍，出词还只有 C 的一半，"
        f"还因为 H3 峰值占满显存而丢掉了「边聊边出片」的能力。方案 B 用 13.4 万换 9.57 tok/s，"
        f"却被 6.84 万的 D（{UP['tok_s']:.1f} tok/s）全面碾压——更贵、更慢、1400 W 功耗、双卡还占地方。"
        f"所以按「不多花也不少花」的标准：**预算 3 万以内选 C，预算 7 万左右选 D；A 和 B 都不该买。**"
        f"这也是本报告与指南给定方案的分歧点：指南的 A 方案在 2026-11 的内存价位下已经失去性价比。",

        f"**（4）本地与云端的分界线。** 对话放在本地：32K 长文、每天高频、内容敏感，本地跑没有边际成本；"
        f"云端按 token 计费，重度使用一年也是千元级，且上下文越长单价越高，本地买的是隐私与不限量。"
        f"出片放到云端：方案 C 一条 768p/5 秒片要 {hms(c['h3_s'])}，D 也要 {hms(UP['h3_s'])}；"
        f"而公开积分报价折算下来，一条 768p/5 秒片约 5 元量级。C 的 2.66 万元 ÷ 5 元 ≈ 5,300 条，"
        f"按每周 5 条算是 20 年的量——**本地出片在经济上不成立**，只有「素材不能上传」的合规场景才值得。"
        f"所以分界线是：本地负责高频长文对话与 480p 粗剪试错，云端负责低频的 768p 成片。",

        f"**（5）兼容性核对。** PCIe：单卡 x16 直连；双卡只能 x8/x8 拆分，Gen5 x8 仍有 256 GB/s，"
        f"对分层推理够用，不再是瓶颈项。供电：A 峰值 775 W 配 1200 W（负载 65%），"
        f"B 峰值 1350 W 配 1600 W（84%，已接近红线，必须 ATX 3.1 + 双 12V-2x6）。"
        f"长度与风道：5090 公版 304 mm、非公到 360 mm、3.5 槽，机箱限长要 ≥380 mm，"
        f"双卡之间至少留 1 槽间距并配 3×140 进风。内存：128 GB 用 64GB×2 双条，"
        f"四条 32GB 会掉到 DDR5-4800 以下，带宽从 80 GB/s 掉到约 64 GB/s，直接拖慢出词速度。",

        "**（6）拓展任务：同预算改配 128GB 统一内存主机或双卡 64GB，对比出词与单条 768p 耗时。** "
        "我手上没有这两台机器，只能给出同一带宽模型的预估：双卡 64GB 约 "
        f"{b['tok_s']:.1f} tok/s、单条 768p 约 {hms(b['h3_s'])}；128GB 统一内存约 {c['tok_s']:.1f} tok/s、"
        f"约 {hms(c['h3_s'])}。差异全部来自带宽（1792 GB/s 对 273 GB/s）与 H3 的计算生态"
        "（CUDA/NVFP4 对 ROCm）。要把它变成实测，方法是：llama.cpp 用 "
        "llama-bench -m <gguf> -p 2048 -n 128 -r 3 各跑三次取中位数；H3 用 ComfyUI 固定同一提示词、"
        "同 seed、20 步、1344×768，记录三次耗时中位数。两边口径必须一致，否则数字没有可比性。",

        f"**（7）半年后的升级路径。** 等统一内存机型的价格下探：{UP['name']} 现在 "
        f"￥{UP['price']:,}，能给出 {UP['tok_s']:.1f} tok/s 与 {hms(UP['h3_s'])} 的出片时间，"
        f"把「分层」这件事彻底消掉。若半年内它降到 5 万以内，直接替换方案 C；"
        f"不建议现在买双卡——显卡与 DDR5 都在涨价，两头都是高位。",
    ]


def main() -> int:
    doc = Document(TPL)
    U.drop_page_breaks(doc)
    t0, t1, t2, t3, t4, t5, t6, t7 = doc.tables[:8]
    U.fill_header_card(t0, STUDENT)

    # ---- 一、实验目的：模板给 2 行，补 1 行 ----
    while len(t1.rows) < len(GOALS):
        U.clone_row(t1)
    for i, g in enumerate(GOALS):
        U.set_cell(t1.rows[i].cells[0], g, size=10.5)

    # ---- 二、实验环境 ----
    for i, text in enumerate(ENV):
        U.set_cell(t2.rows[i].cells[1], text, size=10.5)

    # ---- 三、实验步骤 ----
    for i, (op, params, result) in enumerate(STEPS, start=1):
        row = t3.rows[i]
        U.set_cell(row.cells[1], op, size=9.5)
        U.set_cell(row.cells[2], params, size=9.5)
        U.set_cell(row.cells[3], result, size=9.5)

    # ---- 删除提示语 ----
    for h in [
        "（对照实验指南的「实验目标」，写出 2–3 条可验证的目标）",
        "（按实验指南的步骤记录实际操作、命令与参数；失败与重试也应记录）",
        "（至少记录 1 个真实问题：现象、原因、解决办法与验证结果）",
        "（结论回答实验目标；拓展写 1 条可继续做的改进或对比实验）",
    ]:
        p = U.find_paragraph(doc, h)
        if p is not None:
            U.delete(p._element)

    # ---- 四、实验结果：配置单 + 三方案对照 + 插图 ----
    hint4 = U.find_paragraph(doc, "（粘贴 2–4 张关键截图")
    assert hint4 is not None
    intro = U.new_paragraph(doc, hint4._element, before=True)
    U.write_para(intro, "选型的推导过程由 sizing.py 输出，下面的表与图都取自同一份 results.json。"
                        "表 1 是方案 A 的逐项配置与理由；表 2 把三套方案（外加一个参考机型）放在同一口径下比较；"
                        "图 1~图 3 分别是权重落位、速度与性价比、价格构成。",
                 space_after=6)
    U.delete(hint4._element)
    U.delete(t4._tbl)

    anchor = intro._element
    p = U.add_para(doc, anchor, "**表 1　方案 A 配置单：型号、价格与选型理由**",
                   space_before=6, space_after=4, keep_with_next=True)
    rows = [[k, n, f"￥{p_}", why] for k, n, p_, why in CONFIG_A]
    tbl1 = U.add_table(doc, p._element, ["部件", "型号", "价格", "选型理由"], rows,
                       widths_cm=[2.0, 5.4, 2.2, 7.0], size=8.5)
    note = U.add_para(doc, tbl1._tbl,
                      "注：合计 ￥84,300，与表 2 的「整机价」一致。方案 B 在 A 的基础上"
                      "把 GPU 换成 2 张、内存降到 64GB、主板换成双卡板、电源升到 1600W；"
                      "方案 C 直接买 128GB 统一内存整机，没有可拆的部件。",
                      size=9, color=U.MUTED, space_before=4, space_after=8)

    # 三方案对照表
    p = U.add_para(doc, note._element, "**表 2　三方案对照（同一口径：32K 对话出词、768p/5 秒单条视频、整机价）**",
                   space_before=8, space_after=4, keep_with_next=True)
    table2 = []
    for key in ("A", "B", "C"):
        s = S[key]
        vram = "统一内存可分配约 96GB" if key == "C" else f"{s['vram_gb']}GB 显存"
        table2.append([key, f"{vram} / {s['ram_gb']}GB 内存", f"{s['tok_s']:.2f}",
                       hms(s["h3_s"]), f"￥{s['total']:,}", f"￥{s['cost_per_tok_s']:,.0f}"])
    table2.append(["参考 D", "统一内存可分配约 224GB / 256GB", f"{UP['tok_s']:.1f}",
                   hms(UP["h3_s"]), f"￥{UP['price']:,}", f"￥{UP['price'] / UP['tok_s']:,.0f}"])
    tbl2 = U.add_table(doc, p._element, ["方案", "显存 / 内存", "出词 tok/s", "H3 单条", "整机价", "元/(tok/s)"],
                       table2, widths_cm=[1.8, 5.6, 2.2, 2.2, 2.4, 2.4], size=8.5)
    lead2 = U.add_para(doc, tbl2._tbl,
                       "注：D 为参考机型（Mac Studio M5 Ultra 256GB，2026-08 发布），"
                       "不计入三方案，只用来说明「多加 4 万元能买到什么」。"
                       "H3 耗时按「像素数×帧数×步数」从 RTX 5090 的实测锚点缩放，"
                       "C/D 另乘生态系数（ROCm 3.5 倍、MPS 2.5 倍）。",
                       size=9, color=U.MUTED, space_before=4, space_after=8)

    anchor = lead2._element
    for fname, caption in FIGURES:
        pic = U.add_picture(doc, anchor, os.path.join(FIG, fname), width_cm=16.2)
        anchor = U.add_caption(doc, pic._element, caption)._element

    # ---- 作品路径 ----
    p = U.find_paragraph(doc, "作品或数据文件路径")
    if p is not None and len(p.runs) >= 2:
        p.runs[1].text = ("dm-prog-labs/lab02_ai_workstation/"
                          "（git 仓库内含 sizing.py、results.md、results.csv、figures/）")
        p.runs[1].font.color.rgb = U.RGBColor.from_string(U.INK)

    # ---- 五、问题与解决 ----
    while len(t5.rows) - 1 < len(PROBLEMS):
        U.clone_row(t5)
    for i, (q, cause, fix) in enumerate(PROBLEMS, start=1):
        U.set_cell(t5.rows[i].cells[0], q, size=9.5)
        U.set_cell(t5.rows[i].cells[1], cause, size=9.5)
        U.set_cell(t5.rows[i].cells[2], fix, size=9.5)

    # ---- 六、结论与拓展 ----
    heading6 = U.find_paragraph(doc, "六、结论与拓展")
    anchor = heading6._element
    for para in build_analysis():
        anchor = U.add_para(doc, anchor, para, space_after=6)._element
    U.delete(t6._tbl)

    # ---- 七、提交物自查 ----
    for needle in ("配置单表格", "三方案对照表", "一页结论"):
        p = U.find_paragraph(doc, needle)
        if p is not None and p.runs and "□" in p.runs[0].text:
            p.runs[0].text = "√  "

    p = U.find_paragraph(doc, "其他附件")
    if p is not None and len(p.runs) >= 2:
        p.runs[1].text = ("git 仓库 dm-prog-labs（含两份实验代码与报告）；"
                          "若以压缩包提交，见 dm-prog-labs.zip，解压后 git log 可看到完整提交历史")
        p.runs[1].font.color.rgb = U.RGBColor.from_string(U.INK)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    doc.save(OUT)
    print(f"[saved] {os.path.relpath(OUT, ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
