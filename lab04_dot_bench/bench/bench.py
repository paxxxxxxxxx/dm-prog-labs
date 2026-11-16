#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第 04 讲 统一计时与三语言对照（bench.py）

它做四件事：
    1. 保证 data/ 下的二进制数据存在（没有就调 gen_data.py 生成）；
    2. 用**同一套协议**分别跑 Python / C# / Node，并尝试 gcc、rustc；
       协议：预热 3 轮 → 计 10 轮 → 取中位数 → 结果参与输出防优化 → 只计点积不含读文件；
    3. 做正确性验收：每个实现的结果与 Python 基准的相对误差必须 ≤ 1e-9；
    4. 顺手做一个「计时精度」的真实对照实验：同一段点积分别用 time.time()
       和 time.perf_counter() 计时，看差多少 —— 这是本实验踩到的第一个坑。

用法：
    python bench/bench.py                    # 跑 N=1e4/1e5/1e6
    python bench/bench.py --sizes 100000
    python bench/bench.py --md results/results.md --json results/results.json
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import statistics
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")
CSC = r"C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe"
NODE = shutil.which("node") or r"D:\unitywork\Tuanjie Cowork\cli\bin\win32-x64\node.exe"

SIZES = [10_000, 100_000, 1_000_000]
WARMUP, TIMES = 3, 10


# ---------------------------------------------------------------------------
# 各语言的运行器：都返回 {lang, n, median_ms, min_ms, value, ...}
# ---------------------------------------------------------------------------
def load_module(path: str, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run_python(n: int) -> dict:
    mod = load_module(os.path.join(HERE, "dot.py"), "dot_py")
    r = mod.bench(n, DATA)
    r["available"] = True
    r["how"] = "python 3.12 解释执行（本机实测）"
    return r


def clean(s: str) -> str:
    """子进程输出里可能混进无法编码的字符（GBK 解码失败的替换符），清掉再往屏幕上打。"""
    return (s or "").replace("\ufffd", "?")


def run_numpy(n: int) -> dict:
    """numpy.dot 走的是编译好的 BLAS，代表「同一算法用编译代码能到多快」的天花板。"""
    import numpy as np
    a = np.fromfile(os.path.join(DATA, f"a_f64_{n}.bin"), dtype="<f8")
    b = np.fromfile(os.path.join(DATA, f"b_f64_{n}.bin"), dtype="<f8")
    v = float(np.dot(a, b))
    sink = 0.0
    for _ in range(WARMUP):
        sink += float(np.dot(a, b))
    samples = []
    for _ in range(TIMES):
        t0 = time.perf_counter()
        r = float(np.dot(a, b))
        t1 = time.perf_counter()
        sink += r
        samples.append((t1 - t0) * 1e3)
    return {"lang": "numpy", "n": n, "available": True,
            "how": "numpy.dot（底层 BLAS，编译代码）",
            "median_ms": statistics.median(samples), "min_ms": min(samples),
            "value": v, "checksum": sink}


def parse_result(line: str) -> dict:
    """统一解析 'RESULT lang=... n=... median_ms=... min_ms=... value=... checksum=...'"""
    out = {}
    for tok in line.strip().split():
        if "=" in tok:
            k, v = tok.split("=", 1)
            out[k] = v
    return out


def run_external(cmd: list, lang: str, n: int, how: str, cwd: str = None) -> dict:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=600,
                           cwd=cwd or ROOT, encoding="utf-8", errors="replace")
        p.stdout, p.stderr = clean(p.stdout), clean(p.stderr)
    except FileNotFoundError:
        return {"lang": lang, "n": n, "available": False,
                "reason": f"找不到可执行文件：{cmd[0]}"}
    if p.returncode != 0:
        return {"lang": lang, "n": n, "available": False,
                "reason": f"退出码 {p.returncode}：{(p.stderr or p.stdout)[:400]}"}
    line = next((l for l in p.stdout.splitlines() if l.startswith("RESULT")), None)
    if not line:
        return {"lang": lang, "n": n, "available": False,
                "reason": f"没有输出 RESULT 行：{p.stdout[:400]}"}
    d = parse_result(line)
    return {
        "lang": lang, "n": n, "available": True, "how": how,
        "median_ms": float(d["median_ms"]),
        "min_ms": float(d.get("min_ms", "nan")),
        "value": float(d["value"]),
        "checksum": float(d.get("checksum", "nan")),
    }


def ensure_csharp() -> tuple:
    """编译 dot_cs.cs（一次），返回 (ok, exe_path_or_reason)。"""
    exe = os.path.join(ROOT, "build", "dot_cs.exe")
    src = os.path.join(HERE, "dot_cs.cs")
    os.makedirs(os.path.dirname(exe), exist_ok=True)
    if os.path.exists(exe) and os.path.getmtime(exe) > os.path.getmtime(src):
        return True, exe
    if not os.path.exists(CSC):
        return False, "找不到 csc.exe（.NET Framework 编译器）"
    p = subprocess.run([CSC, "/nologo", "/optimize+", "/unsafe", f"/out:{exe}", src],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    p.stdout, p.stderr = clean(p.stdout), clean(p.stderr)
    if p.returncode != 0 or not os.path.exists(exe):
        return False, f"csc 编译失败：{(p.stdout + p.stderr)[:400]}"
    return True, exe


def ensure_native() -> dict:
    """尝试编译 C 和 Rust；本机没有工具链时如实记录原因（报告第五节要用）。"""
    status = {}
    gcc = shutil.which("gcc")
    if gcc:
        exe = os.path.join(ROOT, "build", "dot_c.exe")
        os.makedirs(os.path.dirname(exe), exist_ok=True)
        p = subprocess.run([gcc, "-O2", os.path.join(HERE, "dot.c"), "-o", exe],
                           capture_output=True, text=True)
        status["c"] = {"available": p.returncode == 0, "exe": exe,
                       "reason": "" if p.returncode == 0 else p.stderr[:300]}
    else:
        status["c"] = {"available": False,
                       "reason": "PATH 中没有 gcc（本机未安装任何 C 编译器，且沙箱不通外网）"}

    rustc = shutil.which("rustc")
    if rustc:
        exe = os.path.join(ROOT, "build", "dot_rust.exe")
        os.makedirs(os.path.dirname(exe), exist_ok=True)
        p = subprocess.run([rustc, "-O", os.path.join(HERE, "dot.rs"), "-o", exe],
                           capture_output=True, text=True)
        status["rust"] = {"available": p.returncode == 0, "exe": exe,
                          "reason": "" if p.returncode == 0 else p.stderr[:300]}
    else:
        status["rust"] = {"available": False,
                          "reason": "PATH 中没有 rustc（本机未安装 Rust 工具链，且沙箱不通外网）"}
    return status


# ---------------------------------------------------------------------------
# 计时精度的真实对照实验
# ---------------------------------------------------------------------------
def probe_timer(n: int = 10_000) -> dict:
    """同一段点积，分别用 time.time() 与 perf_counter() 计时，看谁量得出来。"""
    mod = load_module(os.path.join(HERE, "dot.py"), "dot_py2")
    a = mod.load(os.path.join(DATA, f"a_f64_{n}.bin"))
    b = mod.load(os.path.join(DATA, f"b_f64_{n}.bin"))
    mod.dot(a, b)                      # 预热

    coarse, fine = [], []
    for _ in range(TIMES):
        t0 = time.time()
        mod.dot(a, b)
        t1 = time.time()
        coarse.append((t1 - t0) * 1e3)

        t2 = time.perf_counter()
        mod.dot(a, b)
        t3 = time.perf_counter()
        fine.append((t3 - t2) * 1e3)

    return {
        "n": n,
        "time_time_median_ms": statistics.median(coarse),
        "time_time_zeros": sum(1 for v in coarse if v == 0.0),
        "perf_counter_median_ms": statistics.median(fine),
        "clock_resolution_ms": time.get_clock_info("time").resolution * 1e3,
        "pc_resolution_ms": time.get_clock_info("perf_counter").resolution * 1e3,
    }


# ---------------------------------------------------------------------------
# 汇总
# ---------------------------------------------------------------------------
def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sizes", nargs="*", type=int, default=SIZES)
    ap.add_argument("--md")
    ap.add_argument("--json")
    args = ap.parse_args(argv)

    # 1) 数据
    missing = [n for n in args.sizes
               if not os.path.exists(os.path.join(DATA, f"a_f64_{n}.bin"))]
    if missing:
        print(f"[gen] 缺少 N={missing} 的数据，先调用 gen_data.py")
        subprocess.run([sys.executable, os.path.join(HERE, "gen_data.py"),
                        "--sizes", *map(str, args.sizes)], check=True, cwd=ROOT)

    # 2) 工具链
    cs_ok, cs = ensure_csharp()
    native = ensure_native()
    print(f"[env] C#: {'可用 -> ' + cs if cs_ok else '不可用 -> ' + str(cs)}")
    print(f"[env] C : {'可用' if native['c']['available'] else '不可用 -> ' + native['c']['reason']}")
    print(f"[env] Rust: {'可用' if native['rust']['available'] else '不可用 -> ' + native['rust']['reason']}")

    results = {"sizes": args.sizes, "runs": [], "env": {
        "csharp": {"available": cs_ok, "detail": cs if cs_ok else str(cs)},
        "c": native["c"], "rust": native["rust"],
        "python": sys.version.split()[0],
        "node": NODE,
    }}

    for n in args.sizes:
        row = {"n": n, "runs": {}}

        r = run_python(n)
        row["runs"]["python"] = r
        try:
            row["runs"]["numpy"] = run_numpy(n)
        except Exception as e:
            row["runs"]["numpy"] = {"lang": "numpy", "n": n, "available": False,
                                    "reason": f"numpy 不可用：{e}"}

        if cs_ok:
            row["runs"]["csharp"] = run_external([cs, str(n), DATA], "csharp", n,
                                                 "C# / .NET JIT（csc /optimize+ /unsafe，本机实测）")
        if NODE and os.path.exists(NODE):
            row["runs"]["javascript"] = run_external([NODE, os.path.join(HERE, "dot.mjs"), str(n), DATA],
                                                     "javascript", n,
                                                     "Node 24 / V8 JIT（本机实测）")
        if native["c"]["available"]:
            row["runs"]["c"] = run_external([native["c"]["exe"], str(n), DATA], "c", n,
                                            "gcc -O2（本机实测）")
        if native["rust"]["available"]:
            row["runs"]["rust"] = run_external([native["rust"]["exe"], str(n), DATA], "rust", n,
                                               "rustc -O（本机实测）")

        # 3) 正确性：与 Python 基准比相对误差
        base = row["runs"]["python"]["value"]
        for lang, rr in row["runs"].items():
            if not rr.get("available"):
                continue
            rr["rel_err"] = abs(rr["value"] - base) / max(1e-300, abs(base))
            rr["passed"] = rr["rel_err"] <= 1e-9
        results["runs"].append(row)

    # 4) 加速倍数（相对 Python）
    for row in results["runs"]:
        py = row["runs"]["python"]["median_ms"]
        for lang, rr in row["runs"].items():
            if rr.get("available") and lang != "python":
                rr["speedup_vs_python"] = py / rr["median_ms"]

    results["timer_probe"] = probe_timer()
    results["protocol"] = {"warmup": WARMUP, "times": TIMES, "statistic": "median",
                           "timer": "time.perf_counter / Stopwatch / Instant / performance.now"}

    # ---- 打印 ----
    print("\n" + "=" * 78)
    print("第 04 讲 点积效率对照（预热 %d 轮，计 %d 轮取中位数）" % (WARMUP, TIMES))
    print("=" * 78)
    for row in results["runs"]:
        n = row["n"]
        print(f"\nN = {n:,}")
        print(f"  {'语言':<12}{'中位数 ms':>12}{'最小 ms':>10}{'相对 Python':>14}{'相对误差':>12}  状态")
        for lang, rr in row["runs"].items():
            name = {"python": "Python", "numpy": "numpy (BLAS)", "csharp": "C# (.NET)",
                    "javascript": "Node (V8)", "c": "C (gcc -O2)",
                    "rust": "Rust (rustc -O)"}.get(lang, lang)
            if not rr.get("available"):
                print(f"  {name:<12}{'—':>12}{'—':>10}{'—':>14}{'—':>12}  未运行")
                continue
            sp = rr.get("speedup_vs_python")
            sp_txt = f"{sp:.1f}×" if sp else "1.0×（基准）"
            print(f"  {name:<12}{rr['median_ms']:>12.3f}{rr['min_ms']:>10.3f}{sp_txt:>14}"
                  f"{rr['rel_err']:>12.2e}  {'通过' if rr['passed'] else '不通过'}")

    tp = results["timer_probe"]
    print(f"\n[计时精度对照] N={tp['n']}，同一段点积：")
    print(f"  time.time()     中位数 {tp['time_time_median_ms']:>8.3f} ms，"
          f"其中有 {tp['time_time_zeros']}/{TIMES} 次测到 0.000（分辨率 {tp['clock_resolution_ms']:.3f} ms）")
    print(f"  perf_counter()  中位数 {tp['perf_counter_median_ms']:>8.3f} ms，"
          f"分辨率 {tp['pc_resolution_ms']:.6f} ms")
    print("  → 用 time.time() 量微秒级函数，量到的其实是计时器的分辨率，不是函数耗时。")

    print("\n" + "=" * 78)
    print("说明：C 与 Rust 在本机没有工具链，未运行；源码与复现命令见 README。")
    print("=" * 78)

    # ---- 落盘 ----
    if args.json:
        os.makedirs(os.path.dirname(os.path.abspath(args.json)), exist_ok=True)
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2, default=str)
        print(f"[已写出] {args.json}")

    if args.md:
        os.makedirs(os.path.dirname(os.path.abspath(args.md)), exist_ok=True)
        lines = ["# 第 04 讲 三语言点积对照（脚本生成）", "",
                 f"协议：预热 {WARMUP} 轮，计 {TIMES} 轮取中位数；只计点积，不含读文件。", ""]
        for row in results["runs"]:
            lines.append(f"## N = {row['n']:,}")
            lines.append("")
            lines.append("| 语言 | 中位数 ms | 最小 ms | 相对 Python | 相对误差 | 状态 |")
            lines.append("| --- | --- | --- | --- | --- | --- |")
            for lang, rr in row["runs"].items():
                name = {"python": "Python", "numpy": "numpy (BLAS)", "csharp": "C# (.NET)",
                        "javascript": "Node (V8)", "c": "C (gcc -O2)",
                        "rust": "Rust (rustc -O)"}.get(lang, lang)
                if not rr.get("available"):
                    lines.append(f"| {name} | — | — | — | — | 未运行（缺工具链） |")
                    continue
                sp = rr.get("speedup_vs_python")
                sp_txt = f"{sp:.1f}×" if sp else "基准"
                lines.append(f"| {name} | {rr['median_ms']:.3f} | {rr['min_ms']:.3f} | {sp_txt} | "
                             f"{rr['rel_err']:.2e} | {'通过' if rr['passed'] else '不通过'} |")
            lines.append("")
        with open(args.md, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        print(f"[已写出] {args.md}")

    # 有任何一项不通过就返回非零，方便脚本化检查
    bad = [k for row in results["runs"] for k, rr in row["runs"].items()
           if rr.get("available") and not rr.get("passed")]
    return 0 if not bad else 1


if __name__ == "__main__":
    raise SystemExit(main())
