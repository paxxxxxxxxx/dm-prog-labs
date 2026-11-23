# 数字媒体程序设计 · 实验作业（第 01–05 讲）

2026 秋《数字媒体程序设计》五讲实验的**全部代码 + 数据 + 报告**。
四个实验都是「先推导、再实现/验证、最后落到一张表或一段结论」，所以每个实验目录里
都有**可运行的脚本**；报告（docx/pdf）与插图只在本地生成、不进仓库，
用 	ools/ 里的脚本随时可以重新产出，报告里的每个数字都能在代码里找到出处。

## 目录结构

```
dm-prog-labs/
├─ lab01_number_storage/          第 01 讲：数制转换与存储容量估算
│  ├─ estimate.py                 计算 + 验证脚本（纯标准库）
│  ├─ results.md / results.json   计算过程表与机器可读结果
│  └─ results/                    脚本导出的结果
├─ lab02_ai_workstation/          第 02 讲：H3 与 Strata Qwen3.8 128B 主机配置单
│  ├─ sizing.py                   显存/带宽/价格推导脚本
│  └─ results.md / results.csv    三方案对照表
├─ lab03_matmul_layers/           第 03 讲：矩阵乘法四层实现（Verilog → 汇编 → C → CUDA）
│  ├─ src/                        matmul.c / .s / .v / _tb.v / .cu / .mu 六份源码
│  ├─ ref/ref_matmul.py           四路一致性核对 + 指令统计 + MUSA diff
│  └─ results/                    脚本导出的结果
├─ lab05_network_layers/          第 05 讲：网络场景分层与协议标注
│  ├─ scenarios.py                10 个场景的四层标注 + 六条规则自检
│  ├─ verify.py                   ipconfig/arp/ping/nslookup/netstat 真实采集与解析
│  ├─ packet.py                   构造并逐层解析一个 54 字节 TCP SYN
│  └─ results/                    三份 JSON（场景表 / 验证记录 / 报文解析）
├─ lab04_dot_bench/               第 04 讲：Scaled Dot-Product 与 Python/C/Rust 效率对比
│  ├─ bench/gen_data.py           三语言共用的二进制数据（同一种子、记 sha256）
│  ├─ bench/dot.py .c .rs         三份实现（统一接口与 RESULT 输出）
│  ├─ bench/dot_cs.cs .mjs        本机可跑的编译路径（C#/.NET、Node V8）
│  ├─ bench/bench.py              统一计时、正确性验收、结果汇总
│  ├─ bench/test_dot.py           6 条边界用例
│  └─ results/                    计时结果 json/md
├─ tools/                         生成报告与插图的小工具
│  ├─ chart.py                    用 Pillow 画报告插图
│  ├─ make_figures.py             第 01、02 讲的插图
│  ├─ make_figures_l34.py         第 03、04 讲的插图
│  ├─ docx_util.py                填模板用的 python-docx 封装
│  ├─ build_lab1..4.py            把模板填成完整报告
│  └─ export_pdf.py               docx → pdf（调用环境自带的 LibreOffice Kit）
├─ templates/                     老师给的五份空白报告模板（生成报告时要用）
└─ README.md
```

## 快速开始

```powershell
# 第 01 讲：算一遍并导出计算过程表
python lab01_number_storage/estimate.py --md lab01_number_storage/results.md `
                                        --json lab01_number_storage/results.json

# 第 02 讲：三套方案推导
python lab02_ai_workstation/sizing.py --md lab02_ai_workstation/results.md `
                                      --csv lab02_ai_workstation/results.csv `
                                      --json lab02_ai_workstation/results.json

# 第 03 讲：四路重算 + 指令统计 + MUSA 改动量（不需要编译器）
python lab03_matmul_layers/ref/ref_matmul.py --md lab03_matmul_layers/ref/results.md `
                                             --json lab03_matmul_layers/ref/results.json

# 第 04 讲：生成数据 → 跑三语言计时 → 边界用例
python lab04_dot_bench/bench/gen_data.py
python lab04_dot_bench/bench/bench.py --md lab04_dot_bench/results/results.md `
                                      --json lab04_dot_bench/results/results.json
python lab04_dot_bench/bench/test_dot.py

# 第 05 讲：场景标注自检 → 采集本机网络 → 解析报文
python lab05_network_layers/scenarios.py --md lab05_network_layers/results/scenarios.md `
                                         --csv lab05_network_layers/results/scenarios.csv `
                                         --json lab05_network_layers/results/scenarios.json
python lab05_network_layers/verify.py --md lab05_network_layers/results/verify.md `
                                      --json lab05_network_layers/results/verify.json
python lab05_network_layers/packet.py --json lab05_network_layers/results/packet.json

# 重新生成插图、报告与 PDF
python tools/make_figures.py
python tools/make_figures_l34.py
python tools/make_figures_l5.py
python tools/build_lab1.py   # 同理 build_lab2/3/4.py
python tools/export_pdf.py <输入.docx> <输出.pdf>
```

## 四个实验的核心结论

**第 01 讲（数制与容量）**

| 对象 | 公式 | 结果 |
| --- | --- | --- |
| 10110101₂ | 位权展开 128+32+16+4+1 | 181₁₀ |
| 255₁₀ / 1A₁₆ | 除 16 取余 / 一位拆四位 | 0xFF / 11010₂ |
| 1920×1080 24 位照片 | 宽×高×位深÷8 | 6.22 MB（5.93 MiB） |
| 4 分钟 CD 级音频 | 采样率×位深×声道×时长÷8 | 42.34 MB（40.37 MiB） |
| 2 小时 8 Mbps 视频 | 码率×时长÷8 | 7.20 GB（6.71 GiB） |

实测压缩比：课件页截图 28.3:1、4K 照片 20.0:1 —— **估算存储必须用未压缩公式**，
压缩率只能当 10~30 倍的经验修正，不能反推分辨率。

**第 02 讲（AI 整机选型）**

128B INT4 权重 64 GB + 32K KV cache 3.76 GB + 框架开销 2 GB = **69.8 GB 才能跑起来**。

| 方案 | 显存/内存 | 出词 | H3 单条 | 整机价 | 元/(tok/s) |
| --- | --- | --- | --- | --- | --- |
| A 32GB 单卡 + 128GB DDR5（指南） | 32 / 128 GB | 2.05 tok/s | 7m16s | ￥84,300 | ￥41,022 |
| B 双卡 64GB | 64 / 64 GB | 9.57 tok/s | 7m16s | ￥134,100 | ￥14,010 |
| C 128GB 统一内存整机 | 96 / 128 GB | 3.91 tok/s | 25m24s | ￥26,600 | ￥6,797 |
| 参考 D Mac Studio 256GB | 224 / 256 GB | 17.2 tok/s | 18m09s | ￥68,400 | ￥3,976 |

出词速度由**带宽**决定（1792 / 80 / 273 / 1200 GB/s）：A 把 37.8 GB 权重放在 80 GB/s 的
DDR5 上，单 token 就要 0.47 s，所以只有 2 tok/s。结论：预算 3 万选 C、7 万选 D，A/B 不划算。

**第 03 讲（矩阵乘法四层实现）**

同一句 `c[i][j] += a[i][k]*b[k][j]`，在四层里的代价完全不同：

| 实现层 | 并行粒度 | 一条乘加的代价 |
| --- | --- | --- |
| Verilog | 27 个乘法器 + 18 个加法器同时翻转 | 面积（约 27 个乘法器单元） |
| 汇编（-O0） | 无并行，一条指令一个动作 | **23 条指令**，其中只有 3 条在做算术 |
| C（三重循环） | 编译器向量化后才有指令级并行 | 1 次乘加 + 循环开销 |
| CUDA | 1 块 × 32 线程（3×3 时 9 个有效） | 1 个线程 + 71.9% 空转 |

四路算出的 C 必须逐位相同：`[30,24,18, 84,69,54, 138,114,90]`。

**第 04 讲（三语言点积效率）**

| 实现 | N=10⁴ | N=10⁵ | N=10⁶ | 10⁶ 时相对 Python |
| --- | --- | --- | --- | --- |
| Python（CPython） | 0.253 ms | 2.672 ms | 25.878 ms | 1.0×（基准） |
| numpy（BLAS） | 0.0017 ms | 0.108 ms | 0.142 ms | 182.9× |
| C#（.NET JIT） | 0.0042 ms | 0.0459 ms | 0.421 ms | 61.5× |
| Node（V8 JIT） | 0.0170 ms | 0.0631 ms | 0.657 ms | 39.4× |
| C（gcc -O2）/ Rust（rustc -O） | — | — | — | 本机缺工具链，未运行 |

**倍数几乎不随 N 变化**，说明差的是「每个元素花多少指令」，不是缓存或算法。

**第 05 讲（网络分层）**

10 个日常场景逐条落到四层（应用 / 传输 / 网络 / 链路），并用脚本按「常见问题」的六条规则自检：

| 检查项 | 结果 |
| --- | --- |
| 四层齐全、应用层不写 TCP/UDP | 10/10 通过 |
| 传输层写出协议 + 端口 | 10/10 通过 |
| 场景覆盖 | TCP 9 个、UDP 4 个、应用层协议 9 种 |

本机实测（真实执行 `ipconfig` / `arp` / `nslookup` / `netstat`）：
IPv4 `10.250.206.189/16`、网关 `10.250.0.1`、DNS `10.248.98.30`、网卡 MAC `DC-56-7B-6F-36-B1`，
网关 MAC `3C-15-FB-A9-72-2F` —— 而且网关的 IPv6 链路本地地址 `fe80::3e15:fbff:fea9:722f`
正好是它的 MAC 按 EUI-64 推出来的（脚本做了反推验证）。

一个真实的诊断结论：本机 `ping` 连 `127.0.0.1` 都 `transmit failed`（ICMP 出站被限制），
但 TCP 连 `223.5.5.5:443` 只要 40 ms —— **ping 不通 ≠ 网不通**。

## 数据与口径

- 第 02 讲价格取 **2026-11** 电商渠道价与公开报道；汇率按 1 美元 ≈ 7.2 元。
- 容量单位一律 SI（1 MB = 10⁶ B），需要时并列给出 IEC（MiB/GiB），两者不混用。
- 第 04 讲的点积数据由 `gen_data.py` 生成（种子 20261116，[-1,1) 均匀分布），
  三语言读**同一份字节**，sha256 记在 `data/manifest.json`；计时统一「预热 3 轮 + 10 轮中位数、
  只计点积不含读文件、结果必须参与输出」。
- 第 05 讲的报文是**用本机真实 MAC/IP/端口手工构造**的 54 字节 TCP SYN（校验和按 RFC 1071 计算并回验），
  不是抓包结果 —— 本机 Wireshark 未安装、`pktmon` 需要管理员权限（返回码 5），报告里已明确标注。
- 本机没有 gcc / rustc / iverilog / nvcc，且沙箱不通外网，所以：第 03 讲的 C/Verilog/CUDA
  交源码 + 编译命令，一致性用 Python 按各实现语义重算；第 04 讲的 C/Rust 同样只交源码，
  编译型路径的实测数据由 C#/.NET 与 numpy(BLAS) 代跑（报告里明确标注「代跑」）。

## 说明

- 报告首页的**班级 / 姓名 / 学号 / 日期**在 `tools/build_lab*.py` 顶部的 `STUDENT` 常量里设置，
  重新生成 docx 时会自动填进模板（这些信息不写进仓库）。
- 老师给的模板保留在 `templates/`，报告是在模板副本上填的，版式没有被改动。

- 仓库里只放**代码、tools 脚本、results 结果数据与报告模板**；*/report/*.docx、*/report/*.pdf、
  */report/figures/*.png 已在 .gitignore 里挡住，只在本地生成与保存。
