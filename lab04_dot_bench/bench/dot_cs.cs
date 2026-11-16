// ---------------------------------------------------------------------------
// dot_cs.cs —— 点积的 C#（.NET）实现
//
// 为什么三语言之外还要写这一份？
//   作业指定的三语言是 Python / C / Rust。本机没有任何 C 编译器、也没有 rustc
//   （沙箱不通外网，装不了），但 .NET Framework 自带 csc.exe —— 这是一条
//   **真实可用的编译型路径**，可以用来把「解释执行 vs 编译执行」的量级差测出来，
//   而不是把 C/Rust 的数字凭空写上去。报告里把它标成「替代基准」，不当成 C/Rust。
//
// 编译（csc.exe 在 .NET Framework 目录下）：
//   csc /optimize+ /unsafe /out:dot_cs.exe dot_cs.cs
//
// 协议与 dot.py / dot.c 一致：预热 3 轮，计 10 轮取中位数，结果参与输出。
// ---------------------------------------------------------------------------
using System;
using System.Diagnostics;
using System.IO;

internal static class Program
{
    private const int WARMUP = 3;
    private const int TIMES = 10;

    // 注意：C# 的 volatile 不能修饰 double（编译报 CS0677），
    // 这里改用「写静态字段 + 最后打印」的方式防止整段计算被优化掉：
    // 字段可被其它代码观察，JIT 不能证明这次写入无用。
    private static double _sink;

    // unsafe + fixed：跳过数组边界检查，直接按指针扫内存，
    // 这才是「编译型语言该有的样子」；不用 unsafe 的写法里 JIT 仍会插边界检查。
    private static unsafe double Dot(double[] a, double[] b)
    {
        double s = 0.0;
        fixed (double* pa = a)
        fixed (double* pb = b)
        {
            for (int i = 0; i < a.Length; i++)
            {
                s += pa[i] * pb[i];
            }
        }
        return s;
    }

    private static double[] Load(string path)
    {
        byte[] raw = File.ReadAllBytes(path);
        double[] d = new double[raw.Length / 8];
        Buffer.BlockCopy(raw, 0, d, 0, raw.Length);   // 小端机器上直接按位拷贝
        return d;
    }

    private static void Main(string[] args)
    {
        int n = args.Length > 0 ? int.Parse(args[0]) : 1000000;
        string dir = args.Length > 1 ? args[1] : "data";

        double[] a = Load(dir + "/a_f64_" + n + ".bin");
        double[] b = Load(dir + "/b_f64_" + n + ".bin");

        double v = Dot(a, b);

        for (int r = 0; r < WARMUP; r++) _sink += Dot(a, b);

        double[] samples = new double[TIMES];
        Stopwatch sw = new Stopwatch();
        for (int r = 0; r < TIMES; r++)
        {
            sw.Restart();
            double s = Dot(a, b);
            sw.Stop();
            _sink += s;
            samples[r] = sw.Elapsed.TotalMilliseconds;
        }
        Array.Sort(samples);
        double median = (samples[TIMES / 2 - 1] + samples[TIMES / 2]) / 2.0;

        Console.WriteLine(string.Format(
            System.Globalization.CultureInfo.InvariantCulture,
            "RESULT lang=csharp n={0} median_ms={1:F6} min_ms={2:F6} value={3:R} checksum={4:R}",
            n, median, samples[0], v, _sink));
    }
}
