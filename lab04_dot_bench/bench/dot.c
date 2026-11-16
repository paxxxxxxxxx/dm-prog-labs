/* -----------------------------------------------------------------------------
 * dot.c —— 点积的 C 实现（三语言里的「编译型」基准）
 *
 * 验收规格与 dot.py 完全一致：
 *   1. 接口 dot(a, b, n) -> double；
 *   2. 读同一份二进制文件（原生小端 float64）；
 *   3. 与 numpy 结果相对误差 ≤ 1e-9；
 *   4. 先预热 3 轮，再计 10 轮，取中位数；结果累加到全局 sink 并打印；
 *   5. 计时只算点积，不含读文件。
 *
 * 计时为什么不用 clock()？
 *   clock() 在 Windows/MinGW 上是「进程 CPU 时间」，分辨率只有 1ms 量级，
 *   N=1e4 的点积只要几十微秒，根本量不准。这里用：
 *     Windows  -> QueryPerformanceCounter（微秒级）
 *     POSIX    -> clock_gettime(CLOCK_MONOTONIC)（纳秒级）
 *   这就是实验要求「统一计时口径」的第一条：计时器本身要够细。
 *
 * 编译与运行：
 *     gcc -O2 dot.c -o dot_c
 *     ./dot_c 1000000
 * --------------------------------------------------------------------------- */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define WARMUP 3
#define TIMES  10

#if defined(_WIN32)
#include <windows.h>
static double now_ms(void)
{
    static LARGE_INTEGER freq = {0};
    LARGE_INTEGER c;
    if (freq.QuadPart == 0) QueryPerformanceFrequency(&freq);
    QueryPerformanceCounter(&c);
    return 1000.0 * (double)c.QuadPart / (double)freq.QuadPart;
}
#else
#include <time.h>
static double now_ms(void)
{
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return ts.tv_sec * 1e3 + ts.tv_nsec / 1e6;
}
#endif

/* 黑盒累加器：结果参与输出，防止 -O2 把整个循环优化掉 */
static volatile double g_sink = 0.0;

static double *load(const char *path, long n)
{
    FILE *fp = fopen(path, "rb");
    if (!fp) { fprintf(stderr, "打不开 %s\n", path); exit(2); }
    double *p = (double *)malloc((size_t)n * sizeof(double));
    if (!p) { fprintf(stderr, "内存不够\n"); exit(2); }
    size_t got = fread(p, sizeof(double), (size_t)n, fp);
    fclose(fp);
    if (got != (size_t)n) { fprintf(stderr, "文件长度不对：%zu != %ld\n", got, n); exit(2); }
    return p;
}

double dot(const double *a, const double *b, long n)
{
    double s = 0.0;
    for (long i = 0; i < n; i++) {
        s += a[i] * b[i];
    }
    return s;
}

static int cmp_double(const void *x, const void *y)
{
    double a = *(const double *)x, b = *(const double *)y;
    return (a > b) - (a < b);
}

int main(int argc, char **argv)
{
    long n = (argc > 1) ? atol(argv[1]) : 1000000;
    const char *dir = (argc > 2) ? argv[2] : "data";

    char pa[512], pb[512];
    snprintf(pa, sizeof pa, "%s/a_f64_%ld.bin", dir, n);
    snprintf(pb, sizeof pb, "%s/b_f64_%ld.bin", dir, n);

    double *a = load(pa, n);
    double *b = load(pb, n);

    double v = dot(a, b, n);

    for (int r = 0; r < WARMUP; r++) g_sink += dot(a, b, n);

    double samples[TIMES];
    for (int r = 0; r < TIMES; r++) {
        double t0 = now_ms();
        double s = dot(a, b, n);
        double t1 = now_ms();
        g_sink += s;
        samples[r] = t1 - t0;
    }
    qsort(samples, TIMES, sizeof(double), cmp_double);
    double median = (samples[TIMES / 2 - 1] + samples[TIMES / 2]) / 2.0;

    printf("RESULT lang=c n=%ld median_ms=%.6f min_ms=%.6f value=%.17g checksum=%.17g\n",
           n, median, samples[0], v, g_sink);

    free(a);
    free(b);
    return 0;
}
