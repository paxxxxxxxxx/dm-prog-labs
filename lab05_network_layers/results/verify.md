# 第 05 讲 本机网络验证记录（脚本真实执行）

## ipconfig /all

- 主机名：LAPTOP-3HTFMKHB
- 网卡：MediaTek Wi-Fi 7 MT7925 Wireless LAN Card
- MAC：DC-56-7B-6F-36-B1
- IPv4 / 掩码：10.250.206.189 / 255.255.0.0
- 默认网关：10.250.0.1（IPv6 fe80::3e15:fbff:fea9:722f）
- DNS：10.248.98.30
- DHCP 服务器：10.250.0.1

## ping（本机 ICMP 被拦截）

| 目标 | 收到 | 丢包 | 说明 |
| --- | --- | --- | --- |
| 回环 127.0.0.1 | 0/2 | 100% | transmit failed（本机发不出 ICMP） |
| 网关 10.250.0.1 | 0/2 | 100% | transmit failed（本机发不出 ICMP） |
| 公网 DNS 223.5.5.5 | 0/2 | 100% | transmit failed（本机发不出 ICMP） |

## TCP 连接测试（替代 ping）

| 目标 | 结果 | 耗时 |
| --- | --- | --- |
| 223.5.5.5:443 | 成功 | 40.2 ms |
| www.baidu.com:443 | 成功 | 45.7 ms |
| 10.250.0.1:53 | 失败 | 2153.4 ms |

## nslookup

- **www.baidu.com** → CNAME www.a.shifen.com，IPv4 157.148.69.151, 157.148.69.186，IPv6 2408:8756:c52:1a18:0:ff:b030:7606, 2408:8756:c52:15df:0:ff:b073:d207
- **github.com** → CNAME github.com，IPv4 20.6.7.17，IPv6 无

## netstat -ano

- TCP 共 310 条，ESTABLISHED 55 条，LISTENING 55 条
