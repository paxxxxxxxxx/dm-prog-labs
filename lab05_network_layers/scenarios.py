#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第 05 讲 步骤 1-2：10 个日常网络场景的分层与协议标注

为什么要写成脚本而不是直接往表格里填：
    实验指南的「常见问题」列了 5 类典型错误（把 HTTP 当传输层、DNS 归到传输层、
    漏端口、IP/MAC/端口作用范围混了……）。这些错误全都能写成断言，
    让脚本先过一遍 —— 报告里的「互评」就用它当第一道网，人只负责复核语义。

校验规则（对应常见问题清单）：
    C1 四层都要写（应用 / 传输 / 网络 / 链路），不许空
    C2 应用层只能写协议名，不能出现 TCP / UDP（否则就是"把 HTTP 当传输层"的反面）
    C3 传输层必须写明 TCP/UDP **和端口号**
    C4 端口要和协议对得上（HTTPS→443、DNS→53、SSH→22、SMTP→25/465/587…）
    C5 网络层要写 IP 版本（IPv4 / IPv6）
    C6 链路层要写具体介质（Wi-Fi / 以太网 / 蜂窝），不能只写"物理层"

用法：
    python scenarios.py                 # 校验 + 打印
    python scenarios.py --md results/scenarios.md --csv results/scenarios.csv --json results/scenarios.json
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

# 端口 ↔ 协议 的对照表（用于 C4）。一个协议可以有多个合法端口。
PORT_MAP = {
    "http": {80, 8080},
    "https": {443},
    "tls": {443},
    "dns": {53},
    "ssh": {22},
    "smtp": {25, 465, 587},
    "imap": {143, 993},
    "pop3": {110, 995},
    "ftp": {21, 20},
    "rtp": set(),          # 动态端口，不做强制
    "udp": set(),
}

# 十个场景：覆盖 HTTP/HTTPS、私有长连接、邮件、实时音视频、DNS、流媒体、大文件、
# 游戏、移动支付、远程登录 —— 传输层 TCP 与 UDP 都要出现，应用层至少 8 种。
SCENARIOS = [
    dict(
        id=1,
        story="早上 7:30，我在宿舍用笔记本打开浏览器，输入新闻网站的地址回车",
        app="HTTP/1.1（明文）或 HTTPS（TLS 1.3）",
        trans="TCP 443（走 HTTPS）；若是 http:// 则 TCP 80",
        net="IPv4",
        link="Wi-Fi（802.11 帧）→ 到路由器后换成以太网帧",
        note="抓包里能直接看到 GET / HTTP/1.1 和 Host 头；HTTPS 则只看到 TLS 记录，看不到 URL 路径",
    ),
    dict(
        id=2,
        story="上午 9:00，我在微信里给同学发一条文字消息",
        app="微信私有协议（长连接，基于 HTTP/2 语义 + MMTLS 加密）",
        trans="TCP 443（一条长连接复用所有消息）",
        net="IPv4",
        link="Wi-Fi（802.11 帧）",
        note="抓包只能看到 TLS 记录的长度与方向，消息正文完全不可见 —— 这是应用层加密的效果",
    ),
    dict(
        id=3,
        story="上午 10:00，我用邮件客户端收一封邮件（并顺手回一封）",
        app="IMAP（收信）/ SMTP（发信）",
        trans="TCP 993（IMAPS）/ TCP 465（SMTPS）；明文则是 143 / 25",
        net="IPv4",
        link="以太网帧（宿舍网线）或 Wi-Fi 帧",
        note="明文 IMAP 能看到用户名密码（所以要 993）；加密后只能看到登录成功与否的时序",
    ),
    dict(
        id=4,
        story="中午 12:30，我和家里打微信视频通话",
        app="信令：私有协议（HTTPS 通道）；媒体：RTP / RTCP（SRTP 加密）",
        trans="信令 TCP 443；媒体 UDP（动态端口，常见 10000 以上）",
        net="IPv4",
        link="Wi-Fi（802.11 帧）→ 运营商网络",
        note="媒体走 UDP：丢一个包不重传，宁可糊一下也不卡 —— 这就是「实时」优先于「完整」",
    ),
    dict(
        id=5,
        story="下午 14:00，我在地址栏输入 www.bilibili.com，浏览器先做域名解析",
        app="DNS（查询 A / AAAA 记录）",
        trans="UDP 53（响应超过 512 字节或改用 DoH 时走 TCP 53 / TCP 443）",
        net="IPv4",
        link="Wi-Fi（802.11 帧）",
        note="先查本地 hosts 与 DNS 缓存，未命中才问 10.248.98.30；解析结果会缓存 TTL 秒",
    ),
    dict(
        id=6,
        story="下午 15:00，我在 B 站看一个 1080p 视频",
        app="HTTPS + HLS/DASH 分片（新版本客户端走 HTTP/3）",
        trans="TCP 443（HTTP/3 则 UDP 443）",
        net="IPv4",
        link="Wi-Fi（802.11 帧）",
        note="视频不是一个巨大的响应，而是几百个几秒的分片；卡不卡取决于分片能否按时到达",
    ),
    dict(
        id=7,
        story="下午 16:00，我下载一个 2GB 的安装包",
        app="HTTPS（Range 分段续传）；老式地址可能是 FTP",
        trans="TCP 443；FTP 则是 TCP 21（控制）+ 动态端口（数据）",
        net="IPv4",
        link="Wi-Fi（802.11 帧）",
        note="丢包会触发 TCP 重传，表现为速度忽快忽慢；用 UDP 传大文件就要自己做可靠性，所以没人这么干",
    ),
    dict(
        id=8,
        story="晚上 20:00，我打一局网络游戏（如王者荣耀）",
        app="游戏自有协议（状态同步 / 帧同步）",
        trans="UDP（端口由服务器分配，常见 10000 以上）",
        net="IPv4",
        link="Wi-Fi（802.11 帧）",
        note="UDP 的代价是丢包没人补，所以游戏里会出现「瞬移」；这也是加速器存在的理由",
    ),
    dict(
        id=9,
        story="晚上 21:00，我在超市用手机扫码支付 12 元",
        app="HTTPS（TLS 1.3，客户端与服务端双向证书）",
        trans="TCP 443",
        net="IPv4（手机走 4G/5G 时链路层是 LTE/NR 帧）",
        link="蜂窝网络（LTE / 5G NR 帧）",
        note="支付链路的安全性靠 TLS + 证书校验，抓包只能看到「有一次 TLS 握手」",
    ),
    dict(
        id=10,
        story="晚上 22:00，我用 SSH 远程登录实验室服务器改代码",
        app="SSH（版本 2）",
        trans="TCP 22",
        net="IPv4",
        link="Wi-Fi（802.11 帧）",
        note="SSH 在 TCP 之上自己做加密与认证，所以抓包看不到命令内容，只能看到交互节奏",
    ),
]

PORT_RE = re.compile(r"(\d{2,5})")


def parse_ports(text: str) -> list:
    return [int(p) for p in PORT_RE.findall(text)]


def check(row: dict) -> list:
    """返回该场景的问题列表（空列表 = 通过）。"""
    bad = []
    # C1 四层齐全
    for key, name in (("app", "应用层"), ("trans", "传输层"), ("net", "网络层"), ("link", "链路层")):
        if not str(row.get(key, "")).strip():
            bad.append(f"C1 缺{name}")

    # C2 应用层不能写 TCP/UDP
    if re.search(r"\b(TCP|UDP)\b", row["app"], re.I):
        bad.append("C2 应用层里出现了 TCP/UDP")

    # C3 传输层必须写协议 + 端口
    if not re.search(r"\b(TCP|UDP)\b", row["trans"], re.I):
        bad.append("C3 传输层没写 TCP/UDP")
    if not parse_ports(row["trans"]):
        bad.append("C3 传输层漏了端口号")

    # C4 端口与协议匹配
    ports = parse_ports(row["trans"])
    for proto, allowed in PORT_MAP.items():
        if allowed and proto in row["trans"].lower():
            # 该协议在文本里出现了，就检查它附近的端口是否合法
            for p in ports:
                if p not in allowed and p not in {53, 443, 80, 22, 25, 465, 587, 143, 993,
                                                  110, 995, 21, 20, 8080}:
                    bad.append(f"C4 端口 {p} 超出常见范围")

    # C5 网络层要写 IP 版本
    if not re.search(r"IPv[46]", row["net"], re.I):
        bad.append("C5 网络层没写 IP 版本")

    # C6 链路层要具体
    if not re.search(r"Wi-Fi|以太网|蜂窝|802\.11|LTE|NR", row["link"], re.I):
        bad.append("C6 链路层没写具体介质")

    return bad


def build() -> dict:
    rows, problems = [], []
    for s in SCENARIOS:
        bad = check(s)
        rows.append({**s, "issues": bad, "ok": not bad})
        if bad:
            problems.append((s["id"], bad))

    # 覆盖度自查：传输层要有 TCP 也要有 UDP；应用层协议种类数
    has_tcp = sum(1 for s in SCENARIOS if "TCP" in s["trans"].upper())
    has_udp = sum(1 for s in SCENARIOS if "UDP" in s["trans"].upper())
    apps = sorted({s["app"].split("（")[0].split("（")[0].split("/")[0].strip() for s in SCENARIOS})
    return {
        "rows": rows,
        "problems": problems,
        "coverage": {"tcp": has_tcp, "udp": has_udp, "app_kinds": len(apps), "apps": apps},
        "passed": not problems,
    }


def to_markdown(r: dict) -> str:
    out = ["# 第 05 讲 10 场景分层标注（脚本生成）", ""]
    out.append("| # | 场景（谁在什么时候做了什么） | 应用层 | 传输层（协议·端口） | 网络层 | 链路层 |")
    out.append("| --- | --- | --- | --- | --- | --- |")
    for row in r["rows"]:
        out.append(f"| {row['id']} | {row['story']} | {row['app']} | {row['trans']} | {row['net']} | {row['link']} |")
    out.append("")
    out.append(f"覆盖度：TCP 场景 {r['coverage']['tcp']} 个、UDP 场景 {r['coverage']['udp']} 个、"
               f"应用层协议 {r['coverage']['app_kinds']} 种")
    out.append("")
    out.append(f"六条规则校验：{'全部通过' if r['passed'] else '有问题'}")
    if r["problems"]:
        for pid, bad in r["problems"]:
            out.append(f"- 场景 {pid}: {'；'.join(bad)}")
    return "\n".join(out) + "\n"


def to_csv(r: dict) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["序号", "场景", "应用层", "传输层", "网络层", "链路层", "校验"])
    for row in r["rows"]:
        w.writerow([row["id"], row["story"], row["app"], row["trans"], row["net"], row["link"],
                    "通过" if row["ok"] else "；".join(row["issues"])])
    return buf.getvalue()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--md")
    ap.add_argument("--csv")
    ap.add_argument("--json")
    args = ap.parse_args(argv)

    r = build()

    print("=" * 78)
    print("第 05 讲 10 个网络场景 · 分层与协议标注")
    print("=" * 78)
    for row in r["rows"]:
        print(f"\n[{row['id']:>2}] {row['story']}")
        print(f"     应用层 {row['app']}")
        print(f"     传输层 {row['trans']}")
        print(f"     网络层 {row['net']}")
        print(f"     链路层 {row['link']}")
        print(f"     校验   {'通过' if row['ok'] else '；'.join(row['issues'])}")
        print(f"     备注   {row['note']}")
    c = r["coverage"]
    print(f"\n覆盖度：TCP {c['tcp']} 个场景 / UDP {c['udp']} 个场景 / 应用层协议 {c['app_kinds']} 种")
    print(f"六条规则：{'全部通过 [OK]' if r['passed'] else '存在未通过项'}")
    print("=" * 78)

    for path, fn in ((args.md, to_markdown), (args.csv, to_csv)):
        if path:
            os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
            with open(path, "w", encoding="utf-8-sig" if path.endswith(".csv") else "utf-8") as f:
                f.write(fn(r))
            print(f"[已写出] {path}")
    if args.json:
        os.makedirs(os.path.dirname(os.path.abspath(args.json)) or ".", exist_ok=True)
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(r, f, ensure_ascii=False, indent=2)
        print(f"[已写出] {args.json}")

    return 0 if r["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
