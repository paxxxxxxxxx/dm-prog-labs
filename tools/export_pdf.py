#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""用 LibreOffice Kit 把 docx 导出成 pdf（目标已存在时先删掉，否则 convert 会拒绝覆盖）。

用法：
    python tools/export_pdf.py <输入.docx> <输出.pdf>

说明：LibreOffice Kit 是环境里自带的转换器，路径写死在下面；
换机器时改这两行，或者设环境变量 DSH_OFFICE_NODE / DSH_OFFICE_CLI。
"""

from __future__ import annotations

import os
import subprocess
import sys

NODE = os.environ.get(
    "DSH_OFFICE_NODE",
    r"C:\Users\luv\AppData\Local\Programs\DeepSeek Harness\resources\runtime\primary-runtime\dependencies\node\bin\node.exe",
)
CLI = os.environ.get(
    "DSH_OFFICE_CLI",
    r"C:\Users\luv\AppData\Local\Programs\DeepSeek Harness\resources\app.asar.unpacked"
    r"\dsh\node_modules\@deepseek-ai\libreoffice-kit\lib\cli.js",
)


def convert(src: str, dst: str) -> str:
    if not os.path.isfile(src):
        raise SystemExit(f"找不到源文件：{src}")
    if os.path.exists(dst):
        os.remove(dst)          # 转换器不覆盖已存在的目标
    os.makedirs(os.path.dirname(os.path.abspath(dst)), exist_ok=True)

    r = subprocess.run([NODE, CLI, "convert", "--input", src, "--output", dst],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0 or not os.path.exists(dst):
        raise SystemExit(f"导出失败（rc={r.returncode}）：{r.stdout}\n{r.stderr}")

    with open(dst, "rb") as f:
        if f.read(5) != b"%PDF-":
            raise SystemExit("输出不是合法 PDF")
    return dst


def main(argv=None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if len(argv) != 2:
        print("用法：python tools/export_pdf.py <输入.docx> <输出.pdf>")
        return 2
    out = convert(argv[0], argv[1])
    print(f"[pdf] {out}  {os.path.getsize(out):,} bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
