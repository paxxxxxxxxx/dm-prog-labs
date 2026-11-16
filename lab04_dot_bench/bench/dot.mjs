// ---------------------------------------------------------------------------
// dot.mjs —— 点积的 JavaScript（Node / V8）实现
//
// 同样是「替代基准」：本机没有 C 编译器，但有 Node（V8 带 JIT）。
// V8 会把热点循环编译成机器码，用它可以看出「JIT 编译」离「纯解释」有多远。
//
// 关键点：必须用 Float64Array 直接套在 Buffer 上，零拷贝；
// 如果先 JSON.parse 或转成普通数组，光是装箱就能把差距放大 10 倍以上，
// 那时测的就不是点积，而是数据结构的代价。
//
// 运行：
//   node bench/dot.mjs 1000000
// ---------------------------------------------------------------------------
import fs from "node:fs";
import { performance } from "node:perf_hooks";

const WARMUP = 3;
const TIMES = 10;

let sink = 0.0;

function load(path) {
  const buf = fs.readFileSync(path);
  // Buffer 是 Node 的 Uint8Array 子类；按字节偏移套一个 Float64Array，零拷贝
  return new Float64Array(buf.buffer, buf.byteOffset, buf.byteLength / 8);
}

function dot(a, b) {
  let s = 0.0;
  for (let i = 0; i < a.length; i++) {
    s += a[i] * b[i];
  }
  return s;
}

const n = process.argv[2] ? Number(process.argv[2]) : 1_000_000;
const dir = process.argv[3] ?? "data";

const a = load(`${dir}/a_f64_${n}.bin`);
const b = load(`${dir}/b_f64_${n}.bin`);

const v = dot(a, b);

for (let r = 0; r < WARMUP; r++) sink += dot(a, b);

const samples = [];
for (let r = 0; r < TIMES; r++) {
  const t0 = performance.now();
  const s = dot(a, b);
  const t1 = performance.now();
  sink += s;
  samples.push(t1 - t0);
}
samples.sort((x, y) => x - y);
const median = (samples[TIMES / 2 - 1] + samples[TIMES / 2]) / 2;

console.log(
  `RESULT lang=javascript n=${n} median_ms=${median.toFixed(6)} ` +
  `min_ms=${samples[0].toFixed(6)} value=${v.toPrecision(17)} checksum=${sink.toPrecision(17)}`
);
