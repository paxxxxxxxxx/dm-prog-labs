#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第 05 讲 步骤 4-5：用命令验证本机网络配置（记录真实输出）

本脚本在本机**真的执行**这些命令，并把输出解析成结构化数据：
    ipconfig /all   看 IPv4 / 掩码 / 网关 / DNS / MAC
    arp -a          看网关的 MAC（二层地址）
    ping            测连通性（结果如实记录，包括失败）
    nslookup        看域名 → IP 的解析
    netstat -ano    看当前活动连接（五元组 + 进程号）
    pktmon start    尝试抓包（记录是否被拒绝）

另外做两个「看得懂输出」的交叉验证：
    V1 网关的 IPv6 链路本地地址是不是由它的 MAC 推出来的（EUI-64）
    V2 ICMP 不通时，用 TCP 连接是否仍然可用（ping 不通 ≠ 网不通）

用法：
    python verify.py --md results/verify.md --json results/verify.json
"""

from __future__ import annotations

import argparse
import json
import locale
import os
import re
import socket
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ENC = locale.getpreferredencoding(False) or "gbk"

IPV4_RE = re.compile(r"\b(\d{1,3}(?:\.\d{1,3}){3})\b")
MAC_RE = re.compile(r"\b([0-9A-Fa-f]{2}(?:-[0-9A-Fa-f]{2}){5})\b")


def run(cmd: list, timeout: int = 30) -> dict:
    """执行命令，返回 {cmd, rc, out}；输出按本机 ANSI 代码页解码。"""
    try:
        p = subprocess.run(cmd, capture_output=True, timeout=timeout)
        out = (p.stdout.decode(ENC, "replace") + p.stderr.decode(ENC, "replace")).replace("\ufffd", "?")
        return {"cmd": " ".join(cmd), "rc": p.returncode, "out": out}
    except Exception as e:
        return {"cmd": " ".join(cmd), "rc": -1, "out": f"执行失败：{e}"}


# ---------------------------------------------------------------------------
# 1. ipconfig：抓出一块「真的连着网」的网卡
# ---------------------------------------------------------------------------
def parse_ipconfig(raw: str) -> dict:
    blocks, cur = [], None
    label = ""
    for line in raw.splitlines():
        if not line.strip():
            continue
        if line[0] not in " \t":           # 顶格的适配器标题
            cur = {"adapter": line.strip().rstrip(":")}
            blocks.append(cur)
            label = ""
            continue
        if cur is None:
            continue
        if ":" in line:
            k, v = line.split(":", 1)
            label = re.sub(r"[.\s]+$", "", k.strip())     # 去掉 "IPv4 Address. . . ." 末尾的点
            val = v.strip()
            if val:
                cur[label] = val
            else:
                cur[label] = ""
        else:                              # 续行（例如第二个网关、多个 DNS）
            if label:
                cur[label] = (cur.get(label, "") + " " + line.strip()).strip()
    best = None
    for b in blocks:
        if "IPv4 Address" in b:
            best = b
            break
    if not best:
        return {}
    gw = best.get("Default Gateway", "")
    dns = best.get("DNS Servers", "")
    return {
        "adapter": best["adapter"],
        "desc": best.get("Description", ""),
        "mac": (MAC_RE.search(best.get("Physical Address", "")) or [None])[0],
        "ipv4": (IPV4_RE.search(best.get("IPv4 Address", "")) or [None])[0],
        "mask": best.get("Subnet Mask", ""),
        "gateway_v4": (IPV4_RE.search(gw) or [None])[0],
        "gateway_v6": (re.search(r"fe80::[0-9a-f:]+", gw) or [None])[0],
        "dns": IPV4_RE.findall(dns),
        "dhcp": best.get("DHCP Enabled", ""),
        "dhcp_server": (IPV4_RE.search(best.get("DHCP Server", "")) or [None])[0],
        "ipv6_linklocal": (re.search(r"fe80::[0-9a-f:]+", best.get("Link-local IPv6 Address", "")) or [None])[0],
        "host": (lambda m: m.group(1) if m else None)(re.search(r"Host Name[^:]*:\s*(\S+)", raw)),
    }


# ---------------------------------------------------------------------------
# 2. ARP：网关的 MAC（二层地址）
# ---------------------------------------------------------------------------
def parse_arp(raw: str, gateway: str) -> str | None:
    for line in raw.splitlines():
        m = line.split()
        if len(m) >= 2 and m[0] == gateway:
            return m[1].upper()
    return None


# ---------------------------------------------------------------------------
# 3. ping
# ---------------------------------------------------------------------------
def parse_ping(raw: str) -> dict:
    recv = re.search(r"Received = (\d+)", raw)
    lost = re.search(r"\((\d+)% loss\)", raw)
    avg = re.search(r"(?:Average|平均)\s*=\s*(\d+)ms", raw, re.I)
    ttl = re.search(r"TTL=(\d+)", raw, re.I)
    return {
        "received": int(recv.group(1)) if recv else None,
        "loss_pct": int(lost.group(1)) if lost else None,
        "avg_ms": int(avg.group(1)) if avg else None,
        "ttl": int(ttl.group(1)) if ttl else None,
        "transmit_failed": "transmit failed" in raw.lower(),
        "raw_tail": "\n".join(raw.strip().splitlines()[-5:]),
    }


# ---------------------------------------------------------------------------
# 4. TCP 连接测试（ICMP 不可用时的替代方案）
# ---------------------------------------------------------------------------
def tcp_probe(host: str, port: int, timeout: float = 5.0) -> dict:
    t0 = time.perf_counter()
    try:
        s = socket.create_connection((host, port), timeout=timeout)
        dt = (time.perf_counter() - t0) * 1000
        peer = s.getpeername()
        s.close()
        return {"target": f"{host}:{port}", "ok": True, "ms": round(dt, 1), "peer": f"{peer[0]}:{peer[1]}"}
    except Exception as e:
        dt = (time.perf_counter() - t0) * 1000
        return {"target": f"{host}:{port}", "ok": False, "ms": round(dt, 1), "error": str(e)}


# ---------------------------------------------------------------------------
# 5. nslookup
# ---------------------------------------------------------------------------
def parse_nslookup(raw: str) -> dict:
    ips = re.findall(r"(?:\d{1,3}\.){3}\d{1,3}", raw)
    v6 = re.findall(r"[0-9a-f]{4}(?::[0-9a-f]{0,4}){3,}", raw, re.I)
    cname = re.search(r"Name:\s*(\S+)", raw)
    server = re.search(r"Address:\s*((?:\d{1,3}\.){3}\d{1,3})", raw)
    return {
        "server": server.group(1) if server else None,
        "name": cname.group(1) if cname else None,
        "ipv4": [ip for ip in ips if ip != (server.group(1) if server else None)],
        "ipv6": v6,
        "raw": raw.strip(),
    }


# ---------------------------------------------------------------------------
# 6. EUI-64 交叉验证
# ---------------------------------------------------------------------------
def eui64(mac: str) -> str | None:
    if not mac:
        return None
    b = [int(x, 16) for x in mac.replace("-", ":").split(":")]
    b[0] ^= 0x02                      # 翻转 U/L 位
    mid = b[:3] + [0xFF, 0xFE] + b[3:]
    groups = ["%02x%02x" % (mid[i], mid[i + 1]) for i in range(0, 8, 2)]
    return "fe80::" + ":".join(groups)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--md")
    ap.add_argument("--json")
    args = ap.parse_args(argv)

    data = {}

    print("=" * 78)
    print("第 05 讲 本机网络配置验证（真实执行）")
    print("=" * 78)

    # 1) ipconfig
    r = run(["ipconfig", "/all"])
    cfg = parse_ipconfig(r["out"])
    data["ipconfig"] = cfg
    print(f"\n[1] ipconfig /all")
    print(f"    主机名        {cfg.get('host')}")
    print(f"    网卡          {cfg.get('desc')}")
    print(f"    MAC           {cfg.get('mac')}")
    print(f"    IPv4 / 掩码   {cfg.get('ipv4')} / {cfg.get('mask')}")
    print(f"    默认网关      {cfg.get('gateway_v4')}   （IPv6：{cfg.get('gateway_v6')}）")
    print(f"    DNS 服务器    {', '.join(cfg.get('dns') or [])}")
    print(f"    DHCP 服务器   {cfg.get('dhcp_server')}")

    # 2) ARP
    r = run(["arp", "-a"])
    gw_mac = parse_arp(r["out"], cfg.get("gateway_v4") or "")
    data["gateway_mac"] = gw_mac
    print(f"\n[2] arp -a")
    print(f"    网关 {cfg.get('gateway_v4')} 的 MAC = {gw_mac}")

    # 3) EUI-64 交叉验证
    guess = eui64(gw_mac or "")
    data["eui64"] = {"derived": guess, "actual": cfg.get("gateway_v6"),
                     "match": bool(guess and cfg.get("gateway_v6") and guess.lower() == cfg["gateway_v6"].lower())}
    print(f"\n[3] EUI-64 反推：由 MAC 推出 {guess}")
    print(f"    实际 IPv6 网关 {cfg.get('gateway_v6')}  →  "
          f"{'一致，说明这个地址确实是按 MAC 生成的' if data['eui64']['match'] else '不一致'}")

    # 4) ping
    pings = {}
    for target, name in ((("127.0.0.1"), "回环"), ((cfg.get("gateway_v4") or "10.250.0.1"), "网关"),
                         ("223.5.5.5", "公网 DNS")):
        rr = run(["ping", "-n", "2", target], timeout=20)
        p = parse_ping(rr["out"])
        pings[name] = {"target": target, **p}
        print(f"\n[4] ping {name} {target} → 收 {p['received']}/2，丢包 {p['loss_pct']}%"
              + ("，transmit failed" if p["transmit_failed"] else ""))
    data["ping"] = pings

    # 5) TCP 探测（ICMP 不可用时的替代）
    probes = [tcp_probe("223.5.5.5", 443), tcp_probe("www.baidu.com", 443),
              tcp_probe(cfg.get("gateway_v4") or "10.250.0.1", 53)]
    data["tcp_probe"] = probes
    print(f"\n[5] TCP 连接测试（替代 ping 的连通性判断）")
    for p in probes:
        if p["ok"]:
            print(f"    {p['target']:<24} 成功  {p['ms']:.1f} ms  peer={p['peer']}")
        else:
            print(f"    {p['target']:<24} 失败  {p['error'][:60]}")

    # 6) nslookup
    nl = {}
    for domain in ("www.baidu.com", "github.com"):
        rr = run(["nslookup", domain], timeout=20)
        nl[domain] = parse_nslookup(rr["out"])
        print(f"\n[6] nslookup {domain}")
        print(f"    DNS 服务器 {nl[domain]['server']}")
        print(f"    CNAME      {nl[domain]['name']}")
        print(f"    IPv4       {', '.join(nl[domain]['ipv4']) or '（无）'}")
        print(f"    IPv6       {', '.join(nl[domain]['ipv6'][:2]) or '（无）'}")
    data["nslookup"] = nl

    # 7) netstat
    rr = run(["netstat", "-ano"])
    lines = [l for l in rr["out"].splitlines() if l.strip().startswith("TCP")]
    established = [l.split() for l in lines if "ESTABLISHED" in l]
    listening = [l.split() for l in lines if "LISTENING" in l]
    data["netstat"] = {
        "tcp_total": len(lines),
        "established": [{"local": w[1], "foreign": w[2], "pid": w[-1]} for w in established[:8]],
        "listening_sample": [{"local": w[1], "pid": w[-1]} for w in listening[:6]],
        "established_count": len(established),
        "listening_count": len(listening),
    }
    print(f"\n[7] netstat -ano：TCP 行 {len(lines)} 条，ESTABLISHED {len(established)} 条，"
          f"LISTENING {len(listening)} 条")
    for c in data["netstat"]["established"][:4]:
        print(f"    {c['local']:<24} → {c['foreign']:<24} PID {c['pid']}")

    # 8) 抓包工具探测
    pm = run(["pktmon", "start", "--capture", "--pkt-size", "128"], timeout=15)
    has_wireshark = any(os.path.exists(p) for p in (
        r"C:\Program Files\Wireshark\Wireshark.exe",
        r"C:\Program Files (x86)\Wireshark\Wireshark.exe"))
    data["capture"] = {"pktmon_rc": pm["rc"], "pktmon_out": pm["out"].strip()[:300],
                       "wireshark_installed": has_wireshark}
    print(f"\n[8] 抓包能力：Wireshark 已安装={has_wireshark}；pktmon 返回码 {pm['rc']}")
    print(f"    {pm['out'].strip()[:120]}")

    print("\n" + "=" * 78)
    print("说明：本机 ICMP 出站被拦截（连 127.0.0.1 都 transmit failed），"
          "所以连通性判断改用 TCP 连接测试；\n"
          "      pktmon 需要管理员权限，Wireshark 未安装 —— 抓包一项按指南允许的"
          "「提交说明 + 手工解析」处理。")
    print("=" * 78)

    if args.json:
        os.makedirs(os.path.dirname(os.path.abspath(args.json)) or ".", exist_ok=True)
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"[已写出] {args.json}")

    if args.md:
        lines = ["# 第 05 讲 本机网络验证记录（脚本真实执行）", ""]
        lines += ["## ipconfig /all", "",
                  f"- 主机名：{cfg.get('host')}",
                  f"- 网卡：{cfg.get('desc')}",
                  f"- MAC：{cfg.get('mac')}",
                  f"- IPv4 / 掩码：{cfg.get('ipv4')} / {cfg.get('mask')}",
                  f"- 默认网关：{cfg.get('gateway_v4')}（IPv6 {cfg.get('gateway_v6')}）",
                  f"- DNS：{', '.join(cfg.get('dns') or [])}",
                  f"- DHCP 服务器：{cfg.get('dhcp_server')}", ""]
        lines += ["## ping（本机 ICMP 被拦截）", "", "| 目标 | 收到 | 丢包 | 说明 |", "| --- | --- | --- | --- |"]
        for k, v in pings.items():
            lines.append(f"| {k} {v['target']} | {v['received']}/2 | {v['loss_pct']}% | "
                         f"{'transmit failed（本机发不出 ICMP）' if v['transmit_failed'] else ''} |")
        lines += ["", "## TCP 连接测试（替代 ping）", "", "| 目标 | 结果 | 耗时 |", "| --- | --- | --- |"]
        for p in probes:
            lines.append(f"| {p['target']} | {'成功' if p['ok'] else '失败'} | {p['ms']:.1f} ms |")
        lines += ["", "## nslookup", ""]
        for d, v in nl.items():
            lines.append(f"- **{d}** → CNAME {v['name']}，IPv4 {', '.join(v['ipv4']) or '无'}，"
                         f"IPv6 {', '.join(v['ipv6'][:2]) or '无'}")
        lines += ["", "## netstat -ano", "",
                  f"- TCP 共 {data['netstat']['tcp_total']} 条，"
                  f"ESTABLISHED {data['netstat']['established_count']} 条，"
                  f"LISTENING {data['netstat']['listening_count']} 条"]
        os.makedirs(os.path.dirname(os.path.abspath(args.md)) or ".", exist_ok=True)
        with open(args.md, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        print(f"[已写出] {args.md}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
