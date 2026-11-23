#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成第 05 讲报告的三张插图（数据来自 lab05_network_layers/results/*.json）。

用法：
    python tools/make_figures_l5.py
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import chart  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
L5 = os.path.join(ROOT, "lab05_network_layers")


# 图 2 用的是压缩后的短标签（完整文本在报告的表格里）
SHORT = {
    1: ("HTTP / HTTPS", "TCP 443", "IPv4", "Wi-Fi"),
    2: ("微信私有 (HTTP/2)", "TCP 443", "IPv4", "Wi-Fi"),
    3: ("IMAP / SMTP", "TCP 993/465", "IPv4", "以太网"),
    4: ("RTP + 私有信令", "UDP 动态 / TCP 443", "IPv4", "Wi-Fi"),
    5: ("DNS", "UDP 53", "IPv4", "Wi-Fi"),
    6: ("HTTPS + HLS", "TCP 443", "IPv4", "Wi-Fi"),
    7: ("HTTPS / FTP", "TCP 443 / 21", "IPv4", "Wi-Fi"),
    8: ("游戏私有协议", "UDP 10000+", "IPv4", "Wi-Fi"),
    9: ("HTTPS (TLS 1.3)", "TCP 443", "IPv4", "蜂窝 LTE/5G"),
    10: ("SSH", "TCP 22", "IPv4", "Wi-Fi"),
}
SCEN = {
    1: "早上 7:30 浏览器看新闻",
    2: "上午 9:00 微信发文字消息",
    3: "上午 10:00 用客户端收发邮件",
    4: "中午 12:30 微信视频通话",
    5: "下午 14:00 输入域名先做 DNS 解析",
    6: "下午 15:00 在线看 1080p 视频",
    7: "下午 16:00 下载 2GB 安装包",
    8: "晚上 20:00 打一局网游",
    9: "晚上 21:00 扫码支付 12 元",
    10: "晚上 22:00 SSH 登录服务器",
}


def load(name: str) -> dict:
    with open(os.path.join(L5, "results", name), encoding="utf-8") as f:
        return json.load(f)


def main() -> int:
    out = os.path.join(L5, "report", "figures")
    made = []

    made.append(chart.encapsulation_figure(os.path.join(out, "fig1_encap.png")))

    items = [(s["id"], SCEN[s["id"]], *SHORT[s["id"]]) for s in load("scenarios.json")["rows"]]
    made.append(chart.layer_matrix_figure(items, os.path.join(out, "fig2_matrix.png")))

    made.append(chart.packet_header_figure(load("packet.json"), os.path.join(out, "fig3_packet.png")))

    for f in made:
        print(f"[figure] {os.path.relpath(f, ROOT)}  {os.path.getsize(f) // 1024} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
