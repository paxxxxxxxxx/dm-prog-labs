//! ---------------------------------------------------------------------------
//! dot.rs —— 点积的 Rust 实现（三语言里的另一条编译路径）
//!
//! 验收规格与 dot.py / dot.c 完全一致（统一接口、同一份数据、误差 ≤1e-9、
//! 预热 3 轮 + 计 10 轮取中位数、结果参与输出、计时不含读文件）。
//!
//! Rust 这一版要特别注意两件事：
//!   1. 读文件必须按 little-endian 解码（x86 上是原生序，但写清楚才可移植）：
//!      f64::from_le_bytes；
//!   2. 迭代器写法 `a.iter().zip(b).map(|(x,y)| x*y).sum()` 在 --release 下
//!      会被 LLVM 自动向量化，和手写 for 循环等价；这里两种都保留，默认用 for，
//!      因为报告要对比的是「语言本身的代价」，不是「同语言两种写法」。
//!
//! 编译与运行：
//!     rustc -O dot.rs -o dot_rust        （或 cargo build --release）
//!     ./dot_rust 1000000
//! ---------------------------------------------------------------------------
use std::env;
use std::fs::File;
use std::io::Read;
use std::time::Instant;

const WARMUP: usize = 3;
const TIMES: usize = 10;

fn load(path: &str, n: usize) -> Vec<f64> {
    let mut f = File::open(path).expect("打不开数据文件");
    let mut buf = Vec::new();
    f.read_to_end(&mut buf).expect("读取失败");
    assert_eq!(buf.len(), n * 8, "文件长度不对");
    buf.chunks_exact(8)
        .map(|c| f64::from_le_bytes([c[0], c[1], c[2], c[3], c[4], c[5], c[6], c[7]]))
        .collect()
}

#[inline]
fn dot(a: &[f64], b: &[f64]) -> f64 {
    let mut s = 0.0f64;
    for i in 0..a.len() {
        s += a[i] * b[i];
    }
    s
}

fn main() {
    let args: Vec<String> = env::args().collect();
    let n: usize = if args.len() > 1 {
        args[1].parse().expect("n 必须是整数")
    } else {
        1_000_000
    };
    let dir = if args.len() > 2 { args[2].clone() } else { "data".to_string() };

    let a = load(&format!("{}/a_f64_{}.bin", dir, n), n);
    let b = load(&format!("{}/b_f64_{}.bin", dir, n), n);

    let v = dot(&a, &b);

    // 黑盒：结果写进可变累加器并最终打印，防止被优化掉
    let mut sink = 0.0f64;
    for _ in 0..WARMUP {
        sink += dot(&a, &b);
    }
    let mut samples = Vec::with_capacity(TIMES);
    for _ in 0..TIMES {
        let t0 = Instant::now();
        let s = dot(&a, &b);
        let dt = t0.elapsed();
        sink += s;
        samples.push(dt.as_secs_f64() * 1e3);
    }
    samples.sort_by(|x, y| x.partial_cmp(y).unwrap());
    let median = (samples[TIMES / 2 - 1] + samples[TIMES / 2]) / 2.0;

    println!(
        "RESULT lang=rust n={} median_ms={:.6} min_ms={:.6} value={:.17} checksum={:.17}",
        n, median, samples[0], v, sink
    );
}
