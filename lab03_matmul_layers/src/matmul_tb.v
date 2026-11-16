/* -----------------------------------------------------------------------------
 * matmul_tb.v —— matmul.v 的 testbench
 *
 * 三组检查，逐位比对（=== / !==，不是 ==）：
 *   1) 固定测试数据：期望值就是 matmul.c 打印出来的那 9 个数，
 *      用来证明「结构级实现」与「C 版」逐位一致；
 *   2) 负数向量：专门检验有符号位扩展（8 位有符号×8 位有符号 → 18 位）；
 *   3) 8 组随机向量：与 testbench 里的行为级参考模型（就是 C 的三重循环）
 *      对比，验证 generate 展开后的下标映射没有错位。
 *
 * 仿真（Icarus Verilog）：
 *     iverilog -o matmul_tb.vvp matmul.v matmul_tb.v
 *     vvp matmul_tb.vvp
 * 期望输出结尾为：PASS: 全部 10 组向量、90 个元素逐位一致
 * --------------------------------------------------------------------------- */
`timescale 1ns / 1ps

module matmul_tb;

    localparam N  = 3;
    localparam W  = 8;
    localparam OW = 18;

    reg  signed [N*N*W-1:0]  a_flat;
    reg  signed [N*N*W-1:0]  b_flat;
    wire signed [N*N*OW-1:0] c_flat;

    // 便于按 [i][j] 写数的解包数组
    reg signed [W-1:0] a_arr [0:N*N-1];
    reg signed [W-1:0] b_arr [0:N*N-1];

    // matmul.c 的标准答案（行主序）
    reg signed [OW-1:0] expect [0:N*N-1];

    integer i, j, vec, errors, checked;
    integer seed = 32'h20261116;

    matmul #(.N(N), .W(W), .OW(OW)) dut (
        .a_flat (a_flat),
        .b_flat (b_flat),
        .c_flat (c_flat)
    );

    // 把 a_arr / b_arr 打包进端口
    task push_inputs;
        integer t;
        begin
            for (t = 0; t < N*N; t = t + 1) begin
                a_flat[t*W +: W] = a_arr[t];
                b_flat[t*W +: W] = b_arr[t];
            end
        end
    endtask

    // 行为级参考模型：就是 C 的三重循环，逐元素算 Σ a[i][k]*b[k][j]
    function signed [OW-1:0] ref_elem;
        input integer ii;
        input integer jj;
        integer kk;
        reg signed [OW-1:0] s;
        begin
            s = 0;
            for (kk = 0; kk < N; kk = kk + 1)
                s = s + a_arr[ii*N + kk] * b_arr[kk*N + jj];
            ref_elem = s;
        end
    endfunction

    // 与 expect[] 比对（固定向量用）
    task check_expect;
        begin
            for (i = 0; i < N; i = i + 1) begin
                for (j = 0; j < N; j = j + 1) begin
                    checked = checked + 1;
                    if ($signed(c_flat[(i*N + j)*OW +: OW]) !== expect[i*N + j]) begin
                        errors = errors + 1;
                        $display("  MISMATCH C[%0d][%0d]: got %0d, expect %0d",
                                 i, j, $signed(c_flat[(i*N + j)*OW +: OW]), expect[i*N + j]);
                    end
                end
            end
        end
    endtask

    // 与行为级参考模型比对（负数/随机向量用）
    task check_ref;
        begin
            for (i = 0; i < N; i = i + 1) begin
                for (j = 0; j < N; j = j + 1) begin
                    checked = checked + 1;
                    if ($signed(c_flat[(i*N + j)*OW +: OW]) !== ref_elem(i, j)) begin
                        errors = errors + 1;
                        $display("  MISMATCH C[%0d][%0d]: got %0d, ref %0d",
                                 i, j, $signed(c_flat[(i*N + j)*OW +: OW]), ref_elem(i, j));
                    end
                end
            end
        end
    endtask

    initial begin
        errors  = 0;
        checked = 0;

        // ---- 向量 1：与 matmul.c 完全相同的固定数据 ----
        a_arr[0] =  1; a_arr[1] =  2; a_arr[2] =  3;
        a_arr[3] =  4; a_arr[4] =  5; a_arr[5] =  6;
        a_arr[6] =  7; a_arr[7] =  8; a_arr[8] =  9;
        b_arr[0] =  9; b_arr[1] =  8; b_arr[2] =  7;
        b_arr[3] =  6; b_arr[4] =  5; b_arr[5] =  4;
        b_arr[6] =  3; b_arr[7] =  2; b_arr[8] =  1;

        expect[0] =  30; expect[1] =  24; expect[2] =  18;
        expect[3] =  84; expect[4] =  69; expect[5] =  54;
        expect[6] = 138; expect[7] = 114; expect[8] =  90;

        push_inputs;
        #1;
        check_expect;
        $display("[1] 固定向量：C = %0d %0d %0d / %0d %0d %0d / %0d %0d %0d",
                 $signed(c_flat[0*OW +: OW]),  $signed(c_flat[1*OW +: OW]),  $signed(c_flat[2*OW +: OW]),
                 $signed(c_flat[3*OW +: OW]),  $signed(c_flat[4*OW +: OW]),  $signed(c_flat[5*OW +: OW]),
                 $signed(c_flat[6*OW +: OW]),  $signed(c_flat[7*OW +: OW]),  $signed(c_flat[8*OW +: OW]));

        // ---- 向量 2：全负数，检验符号位扩展 ----
        for (i = 0; i < N*N; i = i + 1) begin
            a_arr[i] = -i - 1;      // -1 .. -9
            b_arr[i] =  i + 1;      //  1 ..  9
        end
        push_inputs;
        #1;
        check_ref;
        $display("[2] 负数向量：已与行为级参考模型比对");

        // ---- 向量 3~10：8 组随机向量 ----
        for (vec = 0; vec < 8; vec = vec + 1) begin
            for (i = 0; i < N*N; i = i + 1) begin
                a_arr[i] = $random(seed) % 128;   // -127..127
                b_arr[i] = $random(seed) % 128;
            end
            push_inputs;
            #1;
            check_ref;
        end
        $display("[3] 随机向量：8 组，已与行为级参考模型比对");

        // ---- 结果 ----
        if (errors == 0)
            $display("PASS: 全部 10 组向量、%0d 个元素逐位一致", checked);
        else
            $display("FAIL: %0d / %0d 个元素不一致", errors, checked);

        $finish;
    end

    // 组合逻辑只做检查，不需要时钟；200ns 后兜底结束
    initial begin
        #200;
        $display("TIMEOUT: 仿真没有正常结束");
        $finish;
    end

endmodule
