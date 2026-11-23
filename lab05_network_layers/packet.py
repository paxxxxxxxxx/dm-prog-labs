#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第 05 讲 步骤 5：逐层展开一个 TCP 报文（Frame / Ethernet II / IPv4 / TCP）

为什么不是抓包截图：
    本机没装 Wireshark，内置的 pktmon 需要管理员权限（返回码 5 = 拒绝访问），
    沙箱里也拿不到网卡原始数据。所以这里换一种同样能证明「你懂头部」的做法：
    用**本机真实的 MAC / IP / 端口**，手工构造一个合法的 TCP SYN 帧（校验和按
    标准算出并回验），再把它当成抓到的字节逐层解开 —— 字段偏移、十六进制值、
    校验和全部可复算，比截图更难糊弄。

构造依据：
    以太网 II：14 字节（目的 MAC 6 + 源 MAC 6 + 类型 2）
    IPv4：20 字节（无选项），首部校验和 = 反码求和
    TCP：20 字节（无选项），校验和要带 12 字节伪首部

用法：
    python packet.py --json results/packet.json
"""

from __future__ import annotations

import argparse
import json
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


# ---------------------------------------------------------------------------
# 构造
# ---------------------------------------------------------------------------
def ip2b(ip: str) -> bytes:
    return bytes(int(x) for x in ip.split("."))


def mac2b(mac: str) -> bytes:
    return bytes(int(x, 16) for x in mac.replace("-", ":").split(":"))


def checksum(data: bytes) -> int:
    """RFC 1071：16 位反码求和再取反。"""
    if len(data) % 2:
        data += b"\0"
    s = 0
    for i in range(0, len(data), 2):
        s += (data[i] << 8) + data[i + 1]
    while s >> 16:
        s = (s & 0xFFFF) + (s >> 16)
    return (~s) & 0xFFFF


def build_frame(src_mac, dst_mac, src_ip, dst_ip, sport, dport, seq=0x12345678):
    # ---- TCP 头（20 字节，flags=SYN，无选项）----
    tcp = struct.pack(">HHIIBBHHH",
                      sport, dport, seq, 0,
                      5 << 4,        # data offset = 5（20 字节），保留位 0
                      0x02,          # flags = SYN
                      64240,         # window
                      0,             # checksum 先填 0
                      0)             # urgent pointer
    # 伪首部：源 IP + 目的 IP + 0 + 协议号(6) + TCP 长度
    pseudo = ip2b(src_ip) + ip2b(dst_ip) + b"\0" + bytes([6]) + struct.pack(">H", len(tcp))
    tcp_csum = checksum(pseudo + tcp)
    tcp = tcp[:16] + struct.pack(">H", tcp_csum) + tcp[18:]

    # ---- IPv4 头（20 字节）----
    total_len = 20 + len(tcp)
    ip = struct.pack(">BBHHHBBH4s4s",
                     0x45,              # version 4, IHL 5
                     0,                 # DSCP/ECN
                     total_len,
                     0x1C46,            # identification
                     0x4000,            # flags = DF（不分片）
                     128,               # TTL
                     6,                 # protocol = TCP
                     0,                 # checksum 先填 0
                     ip2b(src_ip), ip2b(dst_ip))
    ip_csum = checksum(ip)
    ip = ip[:10] + struct.pack(">H", ip_csum) + ip[12:]

    # ---- 以太网 II 头（14 字节）----
    eth = mac2b(dst_mac) + mac2b(src_mac) + struct.pack(">H", 0x0800)
    return eth + ip + tcp


# ---------------------------------------------------------------------------
# 解析：逐层拆开，记下每个字段的偏移、字节、含义
# ---------------------------------------------------------------------------
def parse(frame: bytes) -> list:
    rows = []
    o = 0

    def add(layer, name, off, raw: bytes, value: str, meaning: str):
        rows.append({"layer": layer, "field": name, "offset": off,
                     "len": len(raw), "hex": raw.hex(" ").upper(),
                     "value": value, "meaning": meaning})

    # ---- 以太网 II ----
    L = "Frame / Ethernet II"
    dst, src = frame[0:6], frame[6:12]
    etype = struct.unpack(">H", frame[12:14])[0]
    o = 0
    add(L, "目的 MAC", o, dst, ":".join(f"{b:02X}" for b in dst), "下一跳（这里是网关）的网卡地址")
    o += 6
    add(L, "源 MAC", o, src, ":".join(f"{b:02X}" for b in src), "本机网卡地址")
    o += 6
    add(L, "类型", o, frame[12:14], f"0x{etype:04X}", "0x0800 = 上层是 IPv4")
    o += 2

    # ---- IPv4 ----
    L = "IPv4"
    vihl = frame[14]
    add(L, "版本 / 首部长度", 14, frame[14:15], f"版本 {vihl >> 4}，首部 {vihl & 0xF} 字（×4 = {(vihl & 0xF) * 4} 字节）",
        "版本号决定了这一层怎么解析")
    add(L, "服务类型", 15, frame[15:16], f"0x{frame[15]:02X}", "DSCP/ECN，本帧为 0（尽力而为）")
    tlen = struct.unpack(">H", frame[16:18])[0]
    add(L, "总长度", 16, frame[16:18], f"{tlen} 字节", "IP 头 + TCP 头 + 数据，不含以太网头")
    ident = struct.unpack(">H", frame[18:20])[0]
    add(L, "标识", 18, frame[18:20], f"0x{ident:04X}", "分片重组时用来认「同一批」")
    flags_frag = struct.unpack(">H", frame[20:22])[0]
    add(L, "标志 / 片偏移", 20, frame[20:22], f"0x{flags_frag:04X}",
        "DF=1 表示不分片；片偏移 0 表示这是第一片")
    add(L, "生存时间 TTL", 22, frame[22:23], f"{frame[22]}", "每过一个路由器减 1，减到 0 就丢弃 —— 防止环路")
    add(L, "协议", 23, frame[23:24], f"{frame[23]}", "6 = TCP，17 = UDP，1 = ICMP")
    csum = struct.unpack(">H", frame[24:26])[0]
    add(L, "首部校验和", 24, frame[24:26], f"0x{csum:04X}",
        f"回验：把整段首部（含此字段）再求反码和 = 0x{checksum(frame[14:34]):04X}，为 0 说明首部正确")
    add(L, "源 IP", 26, frame[26:30], ".".join(str(b) for b in frame[26:30]), "发送方")
    add(L, "目的 IP", 30, frame[30:34], ".".join(str(b) for b in frame[30:34]), "接收方")

    # ---- TCP ----
    L = "TCP"
    t = 34
    sport, dport = struct.unpack(">HH", frame[t:t + 4])
    add(L, "源端口", t, frame[t:t + 2], f"{sport}", "本机浏览器/系统分配的临时端口")
    add(L, "目的端口", t + 2, frame[t + 2:t + 4], f"{dport}",
        {443: "HTTPS", 80: "HTTP", 53: "DNS", 22: "SSH"}.get(dport, "未知"))
    seq = struct.unpack(">I", frame[t + 4:t + 8])[0]
    add(L, "序号 seq", t + 4, frame[t + 4:t + 8], f"{seq}", "本段第一个字节的编号；SYN 会消耗 1 个序号")
    add(L, "确认号 ack", t + 8, frame[t + 8:t + 12], f"{struct.unpack('>I', frame[t+8:t+12])[0]}",
        "只有 ACK 置位时才有意义；SYN 包为 0")
    off = frame[t + 12] >> 4
    add(L, "首部长度", t + 12, frame[t + 12:t + 13], f"{off * 4} 字节", "TCP 头长度 = 数据偏移 × 4")
    flags = frame[t + 13]
    names = [n for b, n in ((0x02, "SYN"), (0x10, "ACK"), (0x01, "FIN"), (0x04, "RST"), (0x08, "PSH"))
             if flags & b]
    add(L, "标志位", t + 13, frame[t + 13:t + 14], f"0x{flags:02X}（{'|'.join(names) or '无'}）",
        "SYN = 请求建立连接")
    add(L, "窗口", t + 14, frame[t + 14:t + 16], f"{struct.unpack('>H', frame[t+14:t+16])[0]}",
        "告诉对方「我还敢收多少字节」，流量控制就靠它")
    tc = struct.unpack(">H", frame[t + 16:t + 18])[0]
    pseudo = frame[26:34] + b"\0" + bytes([6]) + struct.pack(">H", len(frame) - 34)
    add(L, "校验和", t + 16, frame[t + 16:t + 18], f"0x{tc:04X}",
        f"回验 = 0x{checksum(pseudo + frame[34:]):04X}（为 0 说明正确）；带伪首部，IP 地址被改也能发现")
    add(L, "紧急指针", t + 18, frame[t + 18:t + 20], "0", "只有 URG 置位时才用")
    return rows


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json")
    ap.add_argument("--src-mac", default="DC-56-7B-6F-36-B1")
    ap.add_argument("--dst-mac", default="3C-15-FB-A9-72-2F")
    ap.add_argument("--src-ip", default="10.250.206.189")
    ap.add_argument("--dst-ip", default="157.148.69.186")
    ap.add_argument("--sport", type=int, default=50158)
    ap.add_argument("--dport", type=int, default=443)
    args = ap.parse_args(argv)

    frame = build_frame(args.src_mac, args.dst_mac, args.src_ip, args.dst_ip,
                        args.sport, args.dport)
    rows = parse(frame)

    print("=" * 78)
    print("逐层展开一个 TCP SYN（54 字节）")
    print("=" * 78)
    print(f"源 {args.src_ip}:{args.sport}（MAC {args.src_mac}）")
    print(f"目的 {args.dst_ip}:{args.dport}（下一跳 MAC {args.dst_mac}）")
    print(f"以太网头 14 + IP 头 20 + TCP 头 20 = {len(frame)} 字节\n")

    cur = None
    for r in rows:
        if r["layer"] != cur:
            cur = r["layer"]
            print(f"\n[{cur}]")
            print(f"  {'偏移':>4}  {'字段':<14}{'字节':<18}{'值':<28}含义")
        print(f"  {r['offset']:>4}  {r['field']:<14}{r['hex']:<18}{r['value']:<28}{r['meaning']}")

    print("\n" + "=" * 78)
    print("说明：本机 Wireshark 未安装、pktmon 无权限（返回码 5），"
          "所以用真实的 MAC/IP/端口手工构造了这个帧，\n"
          "      校验和按 RFC 1071 计算并回验 —— 字段含义与抓包完全一致。")
    print("=" * 78)

    if args.json:
        os.makedirs(os.path.dirname(os.path.abspath(args.json)) or ".", exist_ok=True)
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump({"frame_len": len(frame), "hex": frame.hex(" ").upper(),
                       "src": f"{args.src_ip}:{args.sport}", "dst": f"{args.dst_ip}:{args.dport}",
                       "src_mac": args.src_mac, "dst_mac": args.dst_mac,
                       "fields": rows}, f, ensure_ascii=False, indent=2)
        print(f"[已写出] {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
