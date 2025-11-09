# 数字媒体程序设计 · 实验作业（第 01、02 讲）

2026 秋《数字媒体程序设计》两讲实验的**全部代码 + 数据 + 报告**。
两个实验都是"先推导、再验证、最后落到一张配置单/一张结论"，所以每个实验目录里
都有**可运行的脚本**和**由脚本生成的报告**，报告里的每个数字都能在代码里找到出处。

## 目录结构

```
dm-prog-labs/
├─ lab01_number_storage/          第 01 讲：数制转换与存储容量估算
│  ├─ estimate.py                 计算 + 验证脚本（纯标准库，无第三方依赖）
│  ├─ results.md / results.json   脚本导出的计算过程表与机器可读结果
│  └─ report/
│     ├─ 第01讲-…-实验报告.docx    填好的报告（沿用老师给的模板版式）
│     ├─ 第01讲-…-实验报告.pdf     提交用 PDF
│     └─ figures/                 报告插图（由 results.json 绘制）
├─ lab02_ai_workstation/          第 02 讲：H3 与 Strata Qwen3.8 128B 主机配置单
│  ├─ sizing.py                   显存/带宽/价格推导脚本
│  ├─ results.md / results.csv    三方案对照表（Markdown / CSV）
│  └─ report/                     报告 docx + pdf + 插图
├─ tools/                         生成报告与插图的小工具
│  ├─ chart.py                    用 Pillow 画报告插图
│  ├─ make_figures.py             从 results.json 生成全部插图
│  ├─ docx_util.py                填模板用的 python-docx 封装
│  ├─ build_lab1.py / build_lab2.py  把模板填成完整报告
│  └─ export_pdf.py               docx → pdf（调用环境自带的 LibreOffice Kit）
├─ templates/                     老师给的两份空白报告模板（保留原版式）
└─ README.md
```

## 快速开始

```powershell
# 第 01 讲：算一遍，并导出计算过程表
python lab01_number_storage/estimate.py
python lab01_number_storage/estimate.py --md lab01_number_storage/results.md `
                                        --json lab01_number_storage/results.json

# 第 01 讲步骤 7：核对某张截图/照片的压缩比（路径|宽x高|标签）
python lab01_number_storage/estimate.py --measure "shot.png|1080x2400|手机截图"

# 第 02 讲：三套方案推导 + 导出对照表
python lab02_ai_workstation/sizing.py --md lab02_ai_workstation/results.md `
                                      --csv lab02_ai_workstation/results.csv `
                                      --json lab02_ai_workstation/results.json

# 重新生成插图、报告与 PDF
python tools/make_figures.py
python tools/build_lab1.py
python tools/build_lab2.py
python tools/export_pdf.py lab01_number_storage/report/第01讲-数制转换与存储容量估算-实验报告.docx `
                           lab01_number_storage/report/第01讲-数制转换与存储容量估算-实验报告.pdf
```

## 两个实验的核心结论

**第 01 讲（数制与容量）**

| 对象 | 公式 | 结果 |
| --- | --- | --- |
| 10110101₂ | 位权展开 128+32+16+4+1 | 181₁₀ |
| 255₁₀ / 1A₁₆ | 除 16 取余 / 一位拆四位 | 0xFF / 11010₂ |
| 1920×1080 24 位照片 | 宽×高×位深÷8 | 6.22 MB（5.93 MiB） |
| 4 分钟 CD 级音频 | 采样率×位深×声道×时长÷8 | 42.34 MB（40.37 MiB） |
| 2 小时 8 Mbps 视频 | 码率×时长÷8 | 7.20 GB（6.71 GiB） |

实测压缩比：课件页截图 28.3:1、4K 照片 20.0:1 —— 所以**估算存储必须用未压缩公式**，
压缩率只能当 10~30 倍的经验修正，不能反推分辨率。

**第 02 讲（AI 整机选型）**

128B INT4 权重 64 GB + 32K KV cache 3.76 GB + 框架开销 2 GB = **69.8 GB 才能跑起来**。

| 方案 | 显存/内存 | 出词 | H3 单条 | 整机价 | 元/(tok/s) |
| --- | --- | --- | --- | --- | --- |
| A 32GB 单卡 + 128GB DDR5（指南） | 32 / 128 GB | 2.05 tok/s | 7m16s | ￥84,300 | ￥41,022 |
| B 双卡 64GB | 64 / 64 GB | 9.57 tok/s | 7m16s | ￥134,100 | ￥14,010 |
| C 128GB 统一内存整机 | 96 / 128 GB | 3.91 tok/s | 25m24s | ￥26,600 | ￥6,797 |
| 参考 D Mac Studio 256GB | 224 / 256 GB | 17.2 tok/s | 18m09s | ￥68,400 | ￥3,976 |

出词速度由**带宽**决定（1792 / 80 / 273 / 1200 GB/s），不由算力决定：
A 方案把 37.8 GB 权重放在 80 GB/s 的 DDR5 上，单 token 就要 0.47 s，所以只有 2 tok/s。
结论：预算 3 万内选 C，7 万左右选 D；A、B 不划算。本地跑长文对话，出片上云。

## 数据与口径

- 价格取 **2026-11** 电商渠道价与公开报道（RTX 5090 32GB 约 5.4 万元、DDR5-6000 128GB 套条约 1.6 万元、
  128GB 统一内存迷你主机 3699 美元 ≈ 2.66 万元、Mac Studio M5 Ultra 256GB 9499 美元 ≈ 6.84 万元）。
- 容量单位一律 SI（1 MB = 10⁶ B），需要时并列给出 IEC（MiB/GiB），两者不混用。
- 出词速度用「保守带宽模型」：全部权重每 token 读一遍（MoE 稀疏激活实测会快 1.5~3 倍），
  所以给的是下限，用来做方案对比不会高估。
- H3 耗时从 RTX 5090 的社区实测锚点（864×480 / 10 秒 / 10 步 ≈ 175 秒、峰值 26.9 GB）
  按「像素数 × 帧数 × 步数」缩放，C/D 另乘生态系数（ROCm 3.5 倍、MPS 2.5 倍）。

## 说明

- 报告首页的**班级 / 姓名 / 学号 / 日期**已填好（数媒1班 / 刘纯 / 2025310570 / 2026.11.9）。要改的话改 `tools/build_lab1.py` 与 `tools/build_lab2.py` 顶部的 `STUDENT` 常量，两份报告一起更新。
- 老师给的模板保留在 `templates/`，报告是在模板副本上填的，版式没有被改动。
