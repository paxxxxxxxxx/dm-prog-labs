/* -----------------------------------------------------------------------------
 * matmul.cu —— 矩阵乘法的「GPU（CUDA）」层实现
 *
 * 第 03 讲 矩阵乘法四层实现：GPU 这一层的并行粒度是「线程」。
 * 本实验按实验指南步骤 7 的要求：一个线程算一个 C[i][j]，blockDim 取 32。
 *
 * N=3 时的网格计算（报告第四节要用）：
 *   需要 9 个线程 → blockDim.x = 32
 *   gridDim.x = ceil(9 / 32) = 1 个块
 *   实际启动 32 个线程，其中 9 个有效、23 个在 if 里直接 return（这就是「线程的浪费」）
 *   —— 和 Verilog 的 27 个乘法器一样，都是「为了并行付出的固定开销」。
 *
 * 编译与运行：
 *     nvcc -O2 matmul.cu -o matmul_gpu
 *     ./matmul_gpu
 *
 * 注意：核函数里那个 if (idx >= n*n) return; 不能省。
 *      3×3 只用到 9 个线程，但硬件启动了 32 个；没有边界判断，
 *      第 9~31 号线程会去写 c[9..31]，直接越界。
 * --------------------------------------------------------------------------- */
#include <cstdio>
#include <cuda_runtime.h>

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

#define CUDA_CHECK(call)                                                    \
    do {                                                                    \
        cudaError_t err_ = (call);                                          \
        if (err_ != cudaSuccess) {                                          \
            printf("CUDA error %s at %s:%d\n",                              \
                   cudaGetErrorString(err_), __FILE__, __LINE__);           \
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
    CUDA_CHECK(cudaMalloc(&d_a, bytes));
    CUDA_CHECK(cudaMalloc(&d_b, bytes));
    CUDA_CHECK(cudaMalloc(&d_c, bytes));
    CUDA_CHECK(cudaMemcpy(d_a, h_a, bytes, cudaMemcpyHostToDevice));
    CUDA_CHECK(cudaMemcpy(d_b, h_b, bytes, cudaMemcpyHostToDevice));

    const int threads = BLOCK_DIM;
    const int blocks = (n * n + threads - 1) / threads;
    printf("n = %d，需要 %d 个线程，blockDim = %d，gridDim = %d\n", n, n * n, threads, blocks);
    printf("实际启动 %d 个线程，其中有效 %d 个、空转 %d 个\n",
           blocks * threads, n * n, blocks * threads - n * n);

    matmul_kernel<<<blocks, threads>>>(d_a, d_b, d_c, n);
    CUDA_CHECK(cudaGetLastError());          /* 检查核函数启动是否失败 */
    CUDA_CHECK(cudaDeviceSynchronize());     /* 等 GPU 算完再拷回 */
    CUDA_CHECK(cudaMemcpy(h_c, d_c, bytes, cudaMemcpyDeviceToHost));

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

    cudaFree(d_a);
    cudaFree(d_b);
    cudaFree(d_c);
    return bad == 0 ? 0 : 1;
}
