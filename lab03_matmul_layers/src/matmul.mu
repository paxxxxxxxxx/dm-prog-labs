/* -----------------------------------------------------------------------------
 * matmul.mu —— 同一份实现迁到摩尔线程 MUSA（静态对比用，本机无国产卡不运行）
 *
 * 第 03 讲 步骤 8：把 matmul.cu 里的 cuda 前缀换成 musa，统计改动行数，
 * 说明 MUSA 与 CUDA 的接口关系。
 *
 * 结论先写在这里（数字由 ref/ref_matmul.py 统计）：
 *   核函数体一行没动 —— __global__、blockIdx/blockDim/threadIdx、<<<>>> 启动语法全部保留；
 *   改的只有「运行时 API 的名字」和头文件名：cuda_runtime.h → musa_runtime.h，
 *   cudaMalloc/cudaMemcpy/cudaFree → musaMalloc/musaMemcpy/musaFree，
 *   加上检查宏 CUDA_CHECK → MUSA_CHECK，共 17 行（逐行对照见 ref/results.md）。
 *   也就是说 MUSA 在「源码级」刻意对齐 CUDA：换掉运行时前缀就能编译，
 *   迁移成本集中在驱动/工具链（mcc 对 nvcc）和算子库（muBLAS 对 cuBLAS），
 *   不在语言层。
 *
 * 编译（需摩尔线程 MUSA SDK）：
 *     mcc -O2 matmul.mu -o matmul_musa
 * --------------------------------------------------------------------------- */
#include <cstdio>
#include <musa_runtime.h>

#define N        3
#define BLOCK_DIM 32

/* 一个线程负责一个输出元素：c[idx] = Σ_k a[i][k] * b[k][j] */
__global__ void matmul_kernel(const int *a, const int *b, int *c, int n)
{
    const int idx = blockIdx.x * blockDim.x + threadIdx.x;
    if (idx >= n * n) {
        return;                      /* 越界线程直接退出（3×3 时有 23 个） */
    }

    const int i = idx / n;           /* 行 */
    const int j = idx % n;           /* 列 */

    int s = 0;
    for (int k = 0; k < n; k++) {
        s += a[i * n + k] * b[k * n + j];
    }
    c[idx] = s;
}

#define MUSA_CHECK(call)                                                    \
    do {                                                                    \
        musaError_t err_ = (call);                                          \
        if (err_ != musaSuccess) {                                          \
            printf("MUSA error %s at %s:%d\n",                              \
                   musaGetErrorString(err_), __FILE__, __LINE__);           \
            return 1;                                                       \
        }                                                                   \
    } while (0)

int main(void)
{
    const int n = N;
    const int bytes = n * n * sizeof(int);

    const int h_a[N * N] = {1, 2, 3, 4, 5, 6, 7, 8, 9};
    const int h_b[N * N] = {9, 8, 7, 6, 5, 4, 3, 2, 1};
    const int expect[N * N] = {30, 24, 18, 84, 69, 54, 138, 114, 90};
    int h_c[N * N] = {0};

    int *d_a = nullptr, *d_b = nullptr, *d_c = nullptr;
    MUSA_CHECK(musaMalloc(&d_a, bytes));
    MUSA_CHECK(musaMalloc(&d_b, bytes));
    MUSA_CHECK(musaMalloc(&d_c, bytes));
    MUSA_CHECK(musaMemcpy(d_a, h_a, bytes, musaMemcpyHostToDevice));
    MUSA_CHECK(musaMemcpy(d_b, h_b, bytes, musaMemcpyHostToDevice));

    const int threads = BLOCK_DIM;
    const int blocks = (n * n + threads - 1) / threads;
    printf("n = %d，需要 %d 个线程，blockDim = %d，gridDim = %d\n", n, n * n, threads, blocks);
    printf("实际启动 %d 个线程，其中有效 %d 个、空转 %d 个\n",
           blocks * threads, n * n, blocks * threads - n * n);

    matmul_kernel<<<blocks, threads>>>(d_a, d_b, d_c, n);
    MUSA_CHECK(musaGetLastError());          /* 检查核函数启动是否失败 */
    MUSA_CHECK(musaDeviceSynchronize());     /* 等 GPU 算完再拷回 */
    MUSA_CHECK(musaMemcpy(h_c, d_c, bytes, musaMemcpyDeviceToHost));

    printf("\nC =\n");
    int bad = 0;
    for (int i = 0; i < n; i++) {
        printf("   ");
        for (int j = 0; j < n; j++) {
            printf("%6d", h_c[i * n + j]);
            if (h_c[i * n + j] != expect[i * n + j]) bad++;
        }
        printf("\n");
    }
    printf("\n与 C 版标准答案比对：%s（不匹配 %d 项）\n", bad == 0 ? "PASS" : "FAIL", bad);

    musaFree(d_a);
    musaFree(d_b);
    musaFree(d_c);
    return bad == 0 ? 0 : 1;
}
