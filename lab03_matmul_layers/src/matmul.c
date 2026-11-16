/* -----------------------------------------------------------------------------
 * matmul.c —— 矩阵乘法的「纯 C」层实现
 *
 * 实验：第 03 讲 矩阵乘法四层实现（Verilog → 汇编 → C → CUDA）
 * 规格：C[i][j] = Σ_k A[i][k] * B[k][j]，3×3 有符号整数，固定测试数据
 *
 * 编译与运行：
 *     gcc -O0 -g matmul.c -o matmul_O0      # 不优化，看汇调用
 *     gcc -O2    matmul.c -o matmul_O2      # 优化版，比运行时间用
 *     ./matmul_O0                           # 打印 A、B、C 并与标准答案逐项比对
 *
 * 扩展任务（N 从 3 扩到 256，比较循环顺序）：
 *     gcc -O2 -DBENCH -DN=256 matmul.c -o matmul_bench && ./matmul_bench
 *
 * 两个约定（都是为了报告里能讲清楚「一条语句落成几条指令」）：
 *  1. 用一维数组 + 显式下标 a[i*N+k]，不用 int a[N][N]。
 *     二维数组在 -O0 下会多一层「取行指针再偏移」的 movq；一维数组直接
 *     算地址（imul + lea），指令数更干净，也好和汇编逐条对上。
 *  2. 内层用寄存器累加 s，最后一次性写回 c[i][j]。
 *     如果直接写 c[i][j] += ...，-O0 下每轮都要把 c[i][j] 读回、相加、存回，
 *     一条语句会多出 2 次内存访问，这正是报告里要量的差异。
 * --------------------------------------------------------------------------- */
#include <stdio.h>
#include <stdint.h>
#include <time.h>

#ifndef N
#define N 3
#endif

/* ---------------------------------------------------------------------------
 * 固定测试数据（3×3）
 *   A = [[1,2,3],[4,5,6],[7,8,9]]
 *   B = [[9,8,7],[6,5,4],[3,2,1]]
 * 手算标准答案（报告里逐项复核过）：
 *   C[0][0] = 1*9 + 2*6 + 3*3 =  9+12+ 9 =  30
 *   C[0][1] = 1*8 + 2*5 + 3*2 =  8+10+ 6 =  24
 *   C[0][2] = 1*7 + 2*4 + 3*1 =  7+ 8+ 3 =  18
 *   C[1][0] = 4*9 + 5*6 + 6*3 = 36+30+18 =  84
 *   C[1][1] = 4*8 + 5*5 + 6*2 = 32+25+12 =  69
 *   C[1][2] = 4*7 + 5*4 + 6*1 = 28+20+ 6 =  54
 *   C[2][0] = 7*9 + 8*6 + 9*3 = 63+48+27 = 138
 *   C[2][1] = 7*8 + 8*5 + 9*2 = 56+40+18 = 114
 *   C[2][2] = 7*7 + 8*4 + 9*1 = 49+32+ 9 =  90
 * ------------------------------------------------------------------------- */
static const int32_t A[N * N] = {
    1, 2, 3,
    4, 5, 6,
    7, 8, 9,
};
static const int32_t B[N * N] = {
    9, 8, 7,
    6, 5, 4,
    3, 2, 1,
};

/* ---------------------------------------------------------------------------
 * 教科书版：i-j-k 三重循环，内层在 k 上做寄存器累加。
 * 这就是实验指南步骤 2 要求的那一份，也是汇编分析的对象。
 * ------------------------------------------------------------------------- */
void matmul_naive(const int32_t *a, const int32_t *b, int32_t *c, int n)
{
    for (int i = 0; i < n; i++) {
        for (int j = 0; j < n; j++) {
            int32_t s = 0;                        /* 寄存器累加器 */
            for (int k = 0; k < n; k++) {
                s += a[i * n + k] * b[k * n + j]; /* 报告第三节逐条对应到 imul/addl */
            }
            c[i * n + j] = s;                     /* 一轮只写一次内存 */
        }
    }
}

/* ---------------------------------------------------------------------------
 * 缓存友好版：i-k-j 顺序。
 *   C 是行主序，i-j-k 时内层固定 j 变 k，B[k*n+j] 的地址步长是 n（跨行跳），
 *   每次换缓存行；i-k-j 时内层固定 i、k 变 j，B 和 C 都是顺序访问。
 *   这就是「常见问题」里 i/k/j 写反、缓存不命中、慢几倍的定量来源。
 * ------------------------------------------------------------------------- */
void matmul_ikj(const int32_t *a, const int32_t *b, int32_t *c, int n)
{
    for (int i = 0; i < n; i++) {
        for (int k = 0; k < n; k++) {
            const int32_t aik = a[i * n + k];     /* 内层复用，少一次访存 */
            for (int j = 0; j < n; j++) {
                c[i * n + j] += aik * b[k * n + j];
            }
        }
    }
}

static void print_matrix(const char *name, const int32_t *m, int n)
{
    printf("%s =\n", name);
    for (int i = 0; i < n; i++) {
        printf("   ");
        for (int j = 0; j < n; j++) {
            printf("%6d", (int)m[i * n + j]);
        }
        printf("\n");
    }
}

#ifdef BENCH
/* ---------------------------------------------------------------------------
 * 扩展任务：N=256 的耗时对比（clock() 分辨率 1ms，256³ = 1677 万次乘加够用）
 * ------------------------------------------------------------------------- */
static int32_t bufA[N * N], bufB[N * N], bufC[N * N];

static double bench(void (*fn)(const int32_t *, const int32_t *, int32_t *, int),
                    const char *name, int rounds)
{
    double best = 1e30;
    for (int r = 0; r < rounds; r++) {
        for (int i = 0; i < N * N; i++) bufC[i] = 0;
        clock_t t0 = clock();
        fn(bufA, bufB, bufC, N);
        clock_t t1 = clock();
        double ms = 1000.0 * (double)(t1 - t0) / (double)CLOCKS_PER_SEC;
        if (ms < best) best = ms;
    }
    long long chk = 0;
    for (int i = 0; i < N * N; i++) chk += bufC[i];   /* 结果参与输出，防止被优化掉 */
    printf("%-10s N=%-4d 最好一轮 %8.3f ms   校验和 %lld\n", name, (int)N, best, chk);
    return best;
}

int main(void)
{
    for (int i = 0; i < N * N; i++) {
        bufA[i] = (i * 7 + 1) % 100;
        bufB[i] = (i * 13 + 5) % 100;
    }
    double t1 = bench(matmul_naive, "i-j-k", 5);
    double t2 = bench(matmul_ikj, "i-k-j", 5);
    printf("i-k-j 相对 i-j-k 加速：%.2f 倍\n", t1 / t2);
    return 0;
}
#else
int main(void)
{
    /* 标准答案，用于逐项比对（只对 3×3 有意义） */
    static const int32_t expect[9] = {30, 24, 18, 84, 69, 54, 138, 114, 90};
    int32_t c[9] = {0};

    print_matrix("A", A, N);
    print_matrix("B", B, N);

    matmul_naive(A, B, c, 3);
    print_matrix("C = A x B", c, N);

    int bad = 0;
    printf("\n逐项比对（标准答案取手算结果）：\n");
    for (int i = 0; i < 9; i++) {
        int ok = (c[i] == expect[i]);
        if (!ok) bad++;
        printf("  C[%d][%d] = %4d  期望 %4d  %s\n",
               i / 3, i % 3, (int)c[i], (int)expect[i], ok ? "OK" : "MISMATCH");
    }
    printf("\n结果：%s（不匹配 %d 项）\n", bad == 0 ? "PASS" : "FAIL", bad);
    return bad == 0 ? 0 : 1;
}
#endif
