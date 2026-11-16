/* -----------------------------------------------------------------------------
 * matmul.v —— 矩阵乘法的「硬件（RTL）」层实现
 *
 * 第 03 讲 矩阵乘法四层实现：Verilog 这一层要回答的是
 *   「同一句 c[i][j] = Σ a[i][k]*b[k][j]，在电路里是什么形态？」
 * 答案是：不再是「循环」，而是 27 个乘法器 + 18 个加法器同时翻转，
 *        C 在同一个时刻（组合逻辑稳定后）就是全部结果。
 *
 * 位宽推导（报告第三节要用）：
 *   输入 W=8 有符号，范围 [-128, 127]
 *   单个乘积范围 [-16256, 16384]，需要 16 位（含符号位）
 *   N=3 个乘积相加，最大 |Σ| ≤ 3×16384 = 49152 < 2^17 / 2 = 65536
 *   → 输出取 OW=18 位有符号，留 1 位余量，不会溢出
 *
 * 为什么用 generate + genvar 而不是 a[idx]？
 *   idx 是运行时变量时，a[idx] 是「变量下标访问数组」，综合器会直接拒绝
 *   （它没法在电路里做动态索引）。genvar 是编译期常量，
 *   展开后每个实例的下标都是常数，才能映射成固定的连线。
 *
 * 端口用打包向量 a_flat / b_flat 而不是 18 个独立端口，是为了和 testbench、
 * 以及 CUDA 版的一维数组布局保持一致，四层实现共享同一份数据排布。
 * --------------------------------------------------------------------------- */
`timescale 1ns / 1ps

module matmul #(
    parameter N  = 3,      // 矩阵阶数
    parameter W  = 8,      // 输入位宽（有符号）
    parameter OW = 18      // 输出位宽（有符号）
) (
    input  wire signed [N*N*W-1:0]  a_flat,   // A 按行主序打包
    input  wire signed [N*N*W-1:0]  b_flat,   // B 按行主序打包
    output wire signed [N*N*OW-1:0] c_flat    // C 按行主序打包
);

    // 解包后的元素（每个元素一根独立的线）
    wire signed [W-1:0] a [0:N*N-1];
    wire signed [W-1:0] b [0:N*N-1];

    // 乘积：共 N*N*N = 27 个
    wire signed [OW-1:0] prod [0:N*N*N-1];

    // 每个输出元素的累加链前缀和（acc[..,k] = prod[..,0] + ... + prod[..,k]）
    wire signed [OW-1:0] acc [0:N*N*N-1];

    genvar gi, i, j, k;

    // ---- 1. 拆包：把打包端口变成 generate 里能用常数下标访问的数组 ----
    generate
        for (gi = 0; gi < N * N; gi = gi + 1) begin : g_unpack
            assign a[gi] = a_flat[gi*W +: W];
            assign b[gi] = b_flat[gi*W +: W];
        end
    endgenerate

    // ---- 2. 例化 27 个乘法器（每个输出元素 3 个，全组合并行） ----
    generate
        for (i = 0; i < N; i = i + 1) begin : g_row
            for (j = 0; j < N; j = j + 1) begin : g_col
                for (k = 0; k < N; k = k + 1) begin : g_k
                    assign prod[(i*N + j)*N + k] = a[i*N + k] * b[k*N + j];
                end
            end
        end
    endgenerate

    // ---- 3. 每个 C[i][j] 的乘加：k=0 取第一个积，之后逐级相加 ----
    //   N=3 时是 2 级加法链；如果想缩短关键路径，可改成加法树
    //   （先算 p0+p1、p2+p3 再合并），代价是多一组中间线。
    generate
        for (i = 0; i < N; i = i + 1) begin : g_sum_row
            for (j = 0; j < N; j = j + 1) begin : g_sum_col
                assign acc[(i*N + j)*N + 0] = prod[(i*N + j)*N + 0];
                for (k = 1; k < N; k = k + 1) begin : g_acc
                    assign acc[(i*N + j)*N + k] =
                           acc[(i*N + j)*N + k - 1] + prod[(i*N + j)*N + k];
                end
                assign c_flat[(i*N + j)*OW +: OW] = acc[(i*N + j)*N + N - 1];
            end
        end
    endgenerate

endmodule
