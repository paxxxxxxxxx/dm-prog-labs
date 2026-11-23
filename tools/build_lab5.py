#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把第 05 讲实验报告模板填成完整报告。

用法（先跑 scenarios.py / verify.py / packet.py）：
    python tools/build_lab5.py
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from docx import Document  # noqa: E402

import docx_util as U  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
L5 = os.path.join(ROOT, "lab05_network_layers")
TPL = os.path.join(ROOT, "templates", "第05讲-网络场景分层与协议标注-实验报告.docx")
OUT = os.path.join(L5, "report", "第05讲-网络场景分层与协议标注-实验报告.docx")
FIG = os.path.join(L5, "report", "figures")

# 报告首页要填的信息：放到本地 student.local.json（已在 .gitignore 里挡住，不会进仓库）
STUDENT = {"班级": "", "姓名": "", "学号": "", "日期": ""}
_local_student = os.path.join(ROOT, "student.local.json")
if os.path.isfile(_local_student):
    with open(_local_student, encoding="utf-8") as _f:
        STUDENT.update(json.load(_f))

with open(os.path.join(L5, "results", "scenarios.json"), encoding="utf-8") as f:
    SC = json.load(f)
with open(os.path.join(L5, "results", "verify.json"), encoding="utf-8") as f:
    VF = json.load(f)
with open(os.path.join(L5, "results", "packet.json"), encoding="utf-8") as f:
    PK = json.load(f)

CFG = VF["ipconfig"]
GW_MAC = VF["gateway_mac"]
EUI = VF["eui64"]
PING = VF["ping"]
TCP = VF["tcp_probe"]
NS = VF["nslookup"]
NET = VF["netstat"]

GOALS = [
    "① 建立「一层负责一件事」的分层直觉：能说清应用 / 传输 / 网络 / 链路各自解决什么问题、"
    "各自用什么地址（端口 / IP / MAC），以及每层的 PDU 叫什么。",
    f"② 能把 10 个日常网络行为逐条标注到四层，并用脚本按「常见问题」里的六条规则自检"
    f"（10 个场景全部通过，覆盖 TCP {SC['coverage']['tcp']} 个、UDP {SC['coverage']['udp']} 个、"
    f"应用层协议 {SC['coverage']['app_kinds']} 种）。",
    "③ 能用 ipconfig / arp / ping / nslookup / netstat 验证本机配置与连通性、解释每条输出的含义，"
    "并能逐层展开一个 TCP 报文的头部字段。",
]

ENV = [
    f"自备笔记本（Windows 11 x64，主机名 {CFG.get('host')}），无线网卡 "
    f"{CFG.get('desc')}，MAC {CFG.get('mac')}；本机 IPv4 {CFG.get('ipv4')}/"
    f"{CFG.get('mask')}，网关 {CFG.get('gateway_v4')}，DNS {', '.join(CFG.get('dns') or [])}。",
    "Windows 自带命令（ipconfig / arp / ping / nslookup / netstat / pktmon / tracert）"
    "+ Python 3.12（用 socket 做 TCP 连通性计时、用 struct 手工构造报文）+ Pillow（画图）。"
    "Wireshark 未安装，pktmon 需要管理员权限，抓包一项按指南允许的方式处理。",
    "数据与素材：本机真实配置与命令输出（verify.py 自动采集）；报文用本机真实的 MAC / IP / 端口"
    "手工构造，校验和按 RFC 1071 计算并回验；场景表与解析结果都导出了 JSON 存档。",
]


STEPS = [
    ("列 10 个场景",
     "覆盖网页、IM、邮件、音视频、DNS、流媒体、下载、游戏、支付、远程登录",
     f"写进 scenarios.py：TCP {SC['coverage']['tcp']} 个、UDP {SC['coverage']['udp']} 个、"
     f"应用层协议 {SC['coverage']['app_kinds']} 种，避免「全是网页」"),
    ("逐条标注四层",
     "应用层写协议名；传输层写 TCP/UDP + 端口；网络层写 IP 版本；链路层写介质",
     "10 行全部通过六条规则（见第三节第 2 步），无缺项、无端口遗漏"),
    ("画封装 / 解封装示意",
     "发送端自上而下加头，接收端自下而上剥头，中间过交换机与路由器",
     "见图 2：四层 PDU 为 报文 → 段 → 数据报 → 帧，加头顺序与剥头顺序相反"),
    ("ipconfig / arp 验证",
     "ipconfig /all；arp -a 查网关 MAC",
     f"IPv4 {CFG.get('ipv4')}/{CFG.get('mask')}，网关 {CFG.get('gateway_v4')}，"
     f"DNS {', '.join(CFG.get('dns') or [])}；网关 MAC {GW_MAC}"),
    ("ping 测连通性",
     "ping 127.0.0.1 / 网关 / 223.5.5.5",
     f"三项全部 transmit failed（连回环都不通）→ 本机 ICMP 出站被拦，不是网络故障"),
    ("改用 TCP 连接测试",
     "socket 连 443 / 53 并计时（ICMP 不可用时的替代方案）",
     f"223.5.5.5:443 {TCP[0]['ms']} ms 通；www.baidu.com:443 {TCP[1]['ms']} ms 通 → "
     f"网络是通的，只是 ICMP 不通"),
    ("nslookup 解析",
     "nslookup www.baidu.com；nslookup github.com",
     f"baidu → CNAME www.a.shifen.com → {', '.join(NS['www.baidu.com']['ipv4'])}（另有 IPv6）；"
     f"github → {', '.join(NS['github.com']['ipv4'])}"),
    ("逐层展开一个 TCP 报文",
     "Wireshark 未装、pktmon 拒绝访问（rc=5）→ 用真实 MAC/IP/端口手工构造 54 字节帧再解析",
     f"以太网 14 + IP 20 + TCP 20 = {PK['frame_len']} 字节；IP 校验和 0x2184、TCP 0xC995 均可回验（见图 3）"),
]

# 验证记录表
VERIFY_ROWS = [
    ["本机地址", "ipconfig /all",
     f"IPv4 {CFG.get('ipv4')} / 掩码 {CFG.get('mask')}",
     "掩码 255.255.0.0 → 同一网段是 10.250.0.0/16，可直接通信"],
    ["默认网关", "ipconfig /all",
     f"{CFG.get('gateway_v4')}（IPv6 {CFG.get('gateway_v6')}）",
     "跨网段的包都先发给网关；网关的 IPv6 地址由 MAC 按 EUI-64 推出"],
    ["DNS 服务器", "ipconfig /all + nslookup",
     f"{', '.join(CFG.get('dns') or [])}",
     "域名解析问它；nslookup 的输出里 Server 就是它"],
    ["网卡与网关 MAC", "arp -a",
     f"本机 {CFG.get('mac')}；网关 {GW_MAC}",
     "MAC 只在同一个二层网络内有效，出了网关就换成下一跳的 MAC"],
    ["ping 回环 / 网关 / 公网", "ping -n 2 <目标>",
     "三项均 transmit failed（收 0/2）",
     "连 127.0.0.1 都不通 → 是本机 ICMP 出站被限制，不是网线问题"],
    ["TCP 连通性（替代）", "socket.create_connection 计时",
     f"223.5.5.5:443 {TCP[0]['ms']} ms；www.baidu.com:443 {TCP[1]['ms']} ms",
     "ICMP 不通但 TCP 通 —— 正好说明「ping 不通 ≠ 网不通」"],
    ["域名解析", "nslookup",
     f"baidu → {', '.join(NS['www.baidu.com']['ipv4'])}；github → {', '.join(NS['github.com']['ipv4'])}",
     "先问 DNS，拿到 IP 才发 HTTP 请求；解析结果会按 TTL 缓存"],
    ["活动连接", "netstat -ano",
     f"TCP {NET['tcp_total']} 条，ESTABLISHED {NET['established_count']}、LISTENING {NET['listening_count']}",
     "每行就是一个五元组：协议 + 源 IP:端口 + 目的 IP:端口 + 状态 + 进程号"],
]

FIGURES = [
    ("fig2_matrix.png", "图 1　10 个场景在四层上的分布（完整文字见上表）"),
    ("fig1_encap.png", "图 2　封装与解封装：发送端逐层加头，接收端逐层剥头"),
    ("fig3_packet.png", "图 3　54 字节 TCP SYN 的逐层展开：三层头的边界与关键字段"),
]

PROBLEMS = [
    ("ping 连 127.0.0.1 都返回 transmit failed，一开始以为是网卡坏了",
     "本机对 ICMP 出站有限制（安全软件/沙箱），回环都不通说明问题在本机协议栈之外，"
     "不是线路或网关",
     "改用 TCP 连接测试：223.5.5.5:443 通、www.baidu.com:443 通，证明网络本身正常；"
     "把「ping 不通不等于网不通」写进结论，并保留三种测试的原始输出"),
    ("解析 ipconfig 时网关只抓到一个 IPv6 地址，导致 arp 查不到网关 MAC",
     "ipconfig 的「Default Gateway」有两行：IPv6 在前、IPv4 是缩进的续行，"
     "按「键: 值」一行行读会丢掉续行",
     "改成「标签行 + 续行」两段式解析，才拿到 10.250.0.1；顺带发现网关 IPv6 地址"
     "正好等于 MAC 按 EUI-64 推导的结果（3C:15:FB → 3e15:fbff:fea9:722f）"),
    ("第 2 个场景一开始写成「应用层 HTTP，传输层 TCP 443」，把微信当成网页",
     "看到 443 就默认是 HTTP —— 端口只能说明「谁在监听」，不能说明「跑的是什么协议」",
     "改成「私有协议（长连接 + MMTLS 加密）+ TCP 443」；并在脚本里加了断言："
     "应用层字段不允许出现 TCP/UDP"),
    ("Wireshark 未安装，pktmon 启动被拒绝（返回码 5），抓不到包",
     "pktmon 是内核驱动，需要管理员权限；沙箱里也拿不到网卡原始数据",
     "用本机真实的 MAC / IP / 端口手工构造一个合法的 54 字节 TCP SYN，"
     "校验和按 RFC 1071 计算并回验，再逐层解析字段 —— 字段偏移与含义和抓包完全一致，"
     "报告里明确标注「非抓包结果」"),
]


def analysis() -> list:
    return [
        "**（1）分层直觉：每层只管一件事，每层有自己的地址和 PDU 名。** "
        "应用层解决「说什么」（HTTP / DNS / SSH…），它的 PDU 叫报文；传输层解决「谁收、可靠不可靠」"
        "（TCP / UDP + 端口），PDU 叫段 / 数据报；网络层解决「怎么从这栋楼走到那栋楼」"
        "（IP 地址 + 路由），PDU 叫包；链路层解决「这一跳怎么送出去」（MAC 地址 + 介质），PDU 叫帧。"
        "记住这三套地址的适用范围，就不会再混淆 IP / MAC / 端口：端口只在主机内有效，"
        "IP 在整个互联网有效，MAC 只在一个二层网络内有效、每过一台路由器就换一次。",

        f"**（2）10 个场景的标注逻辑：先问「实时还是要完整」，再问「谁在管」。** "
        f"同样是音视频，微信视频通话走 UDP（丢一个包不重传，宁可糊一下也不卡），"
        f"在线看视频走 TCP（要完整、可卡缓冲）；同样是传文件，下载走 TCP（丢了必须重传），"
        f"游戏状态同步走 UDP（下一帧就覆盖了，重传没意义）。"
        f"10 个场景覆盖了 TCP {SC['coverage']['tcp']} 个、UDP {SC['coverage']['udp']} 个、"
        f"应用层协议 {SC['coverage']['app_kinds']} 种，避免了「十条全是网页」这种只练一个协议的偏差。",

        "**（3）封装与解封装：加头自上而下，剥头自下而上，中间设备只剥到自己那层。** "
        "发送端每往下一层就多套一个头：数据 → 加 TCP 头成段 → 加 IP 头成包 → 加帧头帧尾成帧；"
        "接收端反过来，每往上一层撕掉一个头。中间设备停在自己能处理的那层："
        "交换机只看到帧头（目的是 MAC），路由器剥到 IP 头（目的是 IP）、把 TTL 减 1、"
        "再套上新的帧头转发出去 —— 所以「MAC 每跳都变、IP 全程不变」，这一条能解释很多抓包时的困惑。",

        f"**（4）验证：三个数值 + 一个巧合。** 本机 IPv4 {CFG.get('ipv4')}、掩码 "
        f"{CFG.get('mask')}、网关 {CFG.get('gateway_v4')}、DNS {', '.join(CFG.get('dns') or [])}。"
        f"还有一个值得记的巧合：网关的 IPv6 链路本地地址 {CFG.get('gateway_v6')}，"
        f"正好是它的 MAC {GW_MAC} 按 EUI-64 规则推出来的（首字节翻转 U/L 位后插入 ff:fe）—— "
        f"脚本里做了这个反推，结果{'完全吻合' if EUI.get('match') else '不一致'}。"
        f"这说明 IPv6 的链路本地地址不是随便分配的，看 MAC 就能猜出它的 IPv6 地址。",

        f"**（5）ping 不通但不是网坏：一次真实的误判与纠正。** 本机 ping 127.0.0.1、网关、223.5.5.5 "
        f"三项全部 transmit failed，第一反应是「网断了」。但换成 TCP 连接测试，"
        f"223.5.5.5:443 只用 {TCP[0]['ms']} ms 就连上了 —— 说明 IP 路由、NAT、DNS 全都正常，"
        f"被拦的只是 ICMP 这一种协议。这正是「常见问题」最后一条说的："
        f"ping 不通可能是 DNS、防火墙或目标主机的问题，不能直接判「网线坏了」。"
        f"诊断顺序应该是：先看能不能连上某个已知端口，再回头怀疑线路。",

        f"**（6）报文头部：54 字节里每一段都能说清。** 以太网头 14 字节（目的 MAC 6 + 源 MAC 6 + "
        f"类型 2）负责「这一跳」；IP 头 20 字节（版本/长度、TTL、协议号、校验和、源目的 IP）"
        f"负责「跨网段」；TCP 头 20 字节（源目的端口、序号、标志位、窗口、校验和）负责「哪个进程、"
        f"可靠有序」。三个校验和各有分工：以太网用 FCS（帧尾 4 字节）、IP 只校验首部、"
        f"TCP 要带伪首部（把 IP 地址也算进去），所以改 IP 地址能被 TCP 发现。",

        "**（7）拓展：HTTPS 与 HTTP 在抓包里差在哪。** 明文 HTTP 能看到请求行、Host、Cookie、"
        "响应正文，几乎等于全裸；HTTPS 只剩三层外壳可看 —— 能看到的只有：IP 头（对端是谁）、"
        "端口 443、TLS 握手里的 SNI（明文域名）与证书，载荷全是密文。"
        "也就是说「加密只保护应用层的内容，改不了网络层要暴露的信息」。"
        "另一个拓展是 tracert：每一跳回 ICMP 超时的都是路由器（三层设备），"
        "而同一网段内不会有路由器出现 —— 这也从侧面印证了「交换机看 MAC、路由器看 IP」。",
    ]


def c(v):
    """把 None 变成占位符，避免报告里出现 None。"""
    return v if v not in (None, "", []) else "—"


def main() -> int:
    doc = Document(TPL)
    U.drop_page_breaks(doc)
    t0, t1, t2, t3, t4, t5, t6, t7, t8 = doc.tables[:9]
    U.fill_header_card(t0, STUDENT)

    for i, g in enumerate(GOALS):
        U.set_cell(t1.rows[i].cells[0], g, size=10.5)
    for i, txt in enumerate(ENV):
        U.set_cell(t2.rows[i].cells[1], txt, size=10.5)
    for i, (op, params, result) in enumerate(STEPS, start=1):
        row = t3.rows[i]
        U.set_cell(row.cells[1], op, size=9.5)
        U.set_cell(row.cells[2], params, size=9.5)
        U.set_cell(row.cells[3], result, size=9.5)

    # ---- 4.1 十场景表（模板自带的 11×6）----
    for i, row in enumerate(SC["rows"], start=1):
        cells = t4.rows[i].cells
        U.set_cell(cells[0], str(row["id"]), size=8.5, align="center")
        U.set_cell(cells[1], row["story"], size=8.5)
        U.set_cell(cells[2], row["app"], size=8.5)
        U.set_cell(cells[3], row["trans"], size=8.5)
        U.set_cell(cells[4], row["net"], size=8.5)
        U.set_cell(cells[5], row["link"], size=8.5)
    U.set_col_widths(t4, [1.2, 4.2, 3.2, 4.0, 1.5, 2.5])
    U.keep_table_together(t4)

    # ---- 清掉模板里的提示语 ----
    for needle in ("示例：浏览网页", "自查：发送端加头", "（粘贴 2–4 张关键截图",
                   "需含：本机 IPv4", "记录：本机 IPv4", "（对照实验指南的「实验目标」",
                   "（按实验指南的步骤记录实际操作", "（至少记录 1 个真实问题",
                   "（结论回答实验目标"):
        p = U.find_paragraph(doc, needle)
        if p is not None:
            U.delete(p._element)

    # ---- 4.1 配图（矩阵） + 4.2 封装示意 + 4.3 验证 ----
    pic = U.add_picture(doc, t4._tbl, os.path.join(FIG, "fig2_matrix.png"), width_cm=16.2)
    U.add_caption(doc, pic._element, FIGURES[0][1])

    p42 = U.find_paragraph(doc, "4.2")
    p42.paragraph_format.keep_with_next = True
    lead = U.new_paragraph(doc, p42._element, before=False)
    U.write_para(lead, "封装示意见下图。画法说明：左侧主机 A 自上而下每层加一个头（条越来越长），"
                       "右侧主机 B 自下而上逐层剥掉（条越来越短），中间经一台交换机（二层）和一台"
                       "路由器（三层）；四层的 PDU 依次是 报文 → 段 → 数据报 → 帧。",
                 size=9.5, space_after=4)
    pic = U.add_picture(doc, lead._element, os.path.join(FIG, "fig1_encap.png"), width_cm=16.2)
    cap = U.add_caption(doc, pic._element, FIGURES[1][1])

    # 4.3：验证表
    p43 = U.find_paragraph(doc, "4.3")
    p43.paragraph_format.keep_with_next = True
    lead = U.new_paragraph(doc, p43._element, before=False)
    U.write_para(lead, "命令输出整理成下表（原始输出存在 results/verify.json，由 verify.py 真实执行采集）。"
                       "其中 ping 一项全部失败，正好成为「ping 不通 ≠ 网不通」的实证。",
                 size=9.5, space_after=4)
    tbl = U.add_table(doc, lead._element, ["验证项", "命令 / 方法", "实测结果", "怎么读这个结果"],
                      VERIFY_ROWS, widths_cm=[2.6, 3.6, 5.0, 5.2], size=8.0)
    U.keep_table_together(tbl)

    # 4.3：报文图
    pic = U.add_picture(doc, tbl._tbl, os.path.join(FIG, "fig3_packet.png"), width_cm=16.2)
    U.add_caption(doc, pic._element, FIGURES[2][1])
    U.delete(t5._tbl)          # 原来的「粘贴截图」占位框，已经用真图替代

    # ---- 作品路径 ----
    p = U.find_paragraph(doc, "作品或数据文件路径")
    if p is not None and len(p.runs) >= 2:
        p.runs[1].text = ("dm-prog-labs/lab05_network_layers/"
                          "（scenarios.py / verify.py / packet.py + results/ 三份 JSON + report/ 本报告）")
        p.runs[1].font.color.rgb = U.RGBColor.from_string(U.INK)

    # ---- 五、问题 ----
    while len(t6.rows) - 1 < len(PROBLEMS):
        U.clone_row(t6)
    for i, (q, cause, fix) in enumerate(PROBLEMS, start=1):
        U.set_cell(t6.rows[i].cells[0], q, size=9.5)
        U.set_cell(t6.rows[i].cells[1], cause, size=9.5)
        U.set_cell(t6.rows[i].cells[2], fix, size=9.5)

    # ---- 六、结论 ----
    heading6 = U.find_paragraph(doc, "六、结论与拓展")
    anchor = heading6._element
    for para in analysis():
        anchor = U.add_para(doc, anchor, para, space_after=6)._element
    U.delete(t7._tbl)

    # ---- 七、提交物 ----
    for needle in ("10 场景标注", "封装示意", "验证与抓包记录"):
        for p in doc.paragraphs:                   # 遍历全部，跳过 4.2/4.3 那种小标题
            if needle in p.text and p.runs and "□" in p.runs[0].text:
                p.runs[0].text = "√  "

    p = U.find_paragraph(doc, "其他附件")
    if p is not None and len(p.runs) >= 2:
        p.runs[1].text = ("git 仓库 dm-prog-labs（含五讲实验）；本讲另附 "
                          "results/scenarios.md、results/verify.md、results/packet.json")
        p.runs[1].font.color.rgb = U.RGBColor.from_string(U.INK)

    U.keep_table_together(t8)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    doc.save(OUT)
    print(f"[saved] {os.path.relpath(OUT, ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
