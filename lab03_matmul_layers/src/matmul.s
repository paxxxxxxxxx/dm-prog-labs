# =============================================================================
# matmul.s —— 内层乘加落到 x86-64 指令上的样子（讲解用，AT&T 语法）
#
# 【这份文件的来源，必须说清楚】
#   本机没有 gcc（也没有任何 C 编译器、没有外网），所以这一份不是 gcc 的输出，
#   而是按 System V AMD64 ABI 手工推导的等价代码：参数用 rdi/rsi/rdx/rcx 传，
#   局部变量落在 rbp 负偏移上，整数乘用 imull、加用 addl，与 gcc -O0 的生成风格一致。
#   在装有 gcc 的机器上执行：
#       gcc -S -O0 -masm=att matmul.c -o matmul_O0.s
#   会得到结构相同的输出（标签编号、栈帧大小可能不同），可以逐条对照本文的注释。
#   这样做的目的只有一个：回答实验指南步骤 3 的问题 ——
#   「一条 c[i][j] += a[i][k]*b[k][j] 到底对应几条指令」。
#
# 函数原型：void matmul_naive(const int32_t *a, const int32_t *b, int32_t *c, int n)
#   参数：a = -24(%rbp)  b = -32(%rbp)  c = -40(%rbp)  n = -44(%rbp)
#   局部：s = -4(%rbp)   i = -8(%rbp)   j = -12(%rbp)  k = -16(%rbp)
#   元素宽度 4 字节，所以地址换算里出现 leaq 0(,%rax,4)
# =============================================================================

    .text
    .globl  matmul_naive
    .type   matmul_naive, @function
matmul_naive:
    pushq   %rbp
    movq    %rsp, %rbp
    subq    $48, %rsp
    movq    %rdi, -24(%rbp)          # a
    movq    %rsi, -32(%rbp)          # b
    movq    %rdx, -40(%rbp)          # c
    movl    %ecx, -44(%rbp)          # n
    movl    $0, -8(%rbp)             # i = 0

.L2:                                 # ---- for (i = 0; i < n; i++) ----
    movl    -8(%rbp), %eax
    cmpl    -44(%rbp), %eax
    jge     .L9
    movl    $0, -12(%rbp)            # j = 0

.L3:                                 # ---- for (j = 0; j < n; j++) ----
    movl    -12(%rbp), %eax
    cmpl    -44(%rbp), %eax
    jge     .L8
    movl    $0, -4(%rbp)             # s = 0
    movl    $0, -16(%rbp)            # k = 0

.L4:                                 # ---- for (k = 0; k < n; k++) ----
    movl    -16(%rbp), %eax
    cmpl    -44(%rbp), %eax
    jge     .L7

    # =========================================================================
    # 核心：s += a[i*n+k] * b[k*n+j]      以下 23 条指令就是「一条 C 语句」的代价
    # =========================================================================
    movl    -8(%rbp), %eax           # 1  eax = i
    imull   -44(%rbp), %eax          # 2  eax = i * n            ← imull #1
    movl    %eax, %edx               # 3  edx = i*n
    movl    -16(%rbp), %eax          # 4  eax = k
    addl    %edx, %eax               # 5  eax = i*n + k
    cltq                             # 6  符号扩展到 64 位（为了下面的地址计算）
    leaq    0(,%rax,4), %rdx         # 7  rdx = (i*n+k) * 4      ← 乘 4 用 lea，不用 imul
    movq    -24(%rbp), %rax          # 8  rax = a
    addq    %rdx, %rax               # 9  rax = &a[i*n+k]
    movl    (%rax), %eax             # 10 eax = a[i*n+k]          ← 第 1 次访存
    movl    %eax, -20(%rbp)          # 11 暂存到栈上（-O0 不分配寄存器）
    movl    -16(%rbp), %eax          # 12 eax = k
    imull   -44(%rbp), %eax          # 13 eax = k * n            ← imull #2
    movl    %eax, %edx               # 14 edx = k*n
    movl    -12(%rbp), %eax          # 15 eax = j
    addl    %edx, %eax               # 16 eax = k*n + j
    cltq                             # 17
    leaq    0(,%rax,4), %rdx         # 18 rdx = (k*n+j) * 4
    movq    -32(%rbp), %rax          # 19 rax = b
    addq    %rdx, %rax               # 20 rax = &b[k*n+j]
    movl    (%rax), %eax             # 21 eax = b[k*n+j]          ← 第 2 次访存
    imull   -20(%rbp), %eax          # 22 eax = a * b            ← imull #3
    addl    %eax, -4(%rbp)           # 23 s += a*b               ← addl #1（累加）
    # =========================================================================
    # 计数小结（-O0，一条 s += a[i*n+k]*b[k*n+j]，共 23 条）：
    #   3 × imull       —— 两次 i*n / k*n，一次真正的 a*b
    #   2 × addq        —— 数组基址 + 偏移
    #   3 × addl        —— 2 次下标相加 + 1 次 s 累加
    #   2 × cltq        —— 32 位下标扩展到 64 位地址
    #   2 × leaq        —— 下标 × 4（用 lea 代替 imul）
    #   9 × movl        —— 取 i/j/k、取 a/b 数据、栈上暂存
    #   2 × movq        —— 取 a/b 数组基址
    #   其中「有用」的只有 1 次乘、1 次加、2 次取数据；其余 19 条都在算下标、搬数据。
    #   这就是「同一算法、几种代价」的第一层：算法一样，取数方式不同，代价差一个量级。
    # =========================================================================

    addl    $1, -16(%rbp)            # k++
    jmp     .L4
.L7:                                 # 内层结束：一轮 3 个 k 走完
    movl    -8(%rbp), %eax           # eax = i
    imull   -44(%rbp), %eax          # i * n
    movl    %eax, %edx
    movl    -12(%rbp), %eax          # j
    addl    %edx, %eax               # i*n + j
    cltq
    leaq    0(,%rax,4), %rdx
    movq    -40(%rbp), %rax          # c
    addq    %rdx, %rax
    movl    -4(%rbp), %edx           # s
    movl    %edx, (%rax)             # c[i*n+j] = s   ← 一轮只写一次内存
    addl    $1, -12(%rbp)            # j++
    jmp     .L3
.L8:
    addl    $1, -8(%rbp)             # i++
    jmp     .L2
.L9:
    nop
    leave
    ret
    .size   matmul_naive, .-matmul_naive

# =============================================================================
# -O2 会变成什么样（同一句，量级对比；详细解释见报告第三节）
#
#   gcc -O2 -S matmul.c 之后，编译器会做三件事：
#   1) 把 i、j、k 和 s 全部提升到寄存器（%eax/%edx/%ecx），不再有 -8(%rbp) 这种访存；
#   2) 把 i*n 提到外层、把 k*n 提到中层（循环不变量外提），内层只剩「取数 + 乘 + 加」；
#   3) 内层 3 次迭代直接展开（N=3 是编译期常量），再用 -O2 的自动向量化
#      把 3 个 int32 的乘加打包成 SSE 指令（pmulld / paddd）一次算完。
#
#   结果是：内层一条语句从「23 条指令」压到摊薄后约 2 条，
#   同时循环判断次数从 27 次降到 9 次，所以 -O2 相对 -O0 通常有 5~15 倍差距
#   （具体数字要在装了 gcc 的机器上用 -DBENCH -DN=256 跑 matmul_bench 才准；
#     本机没有 gcc，报告里只做指令级分析，不报编造的耗时）。
# =============================================================================
    .section    .note.GNU-stack,"",@progbits
