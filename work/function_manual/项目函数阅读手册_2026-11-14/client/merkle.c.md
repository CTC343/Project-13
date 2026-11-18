# client/merkle.c

将区间分成四步计算，生成总结果、步骤文本和 SHA-256 Merkle 根。

## build_merkle_root

```c
static int build_merkle_root(long step_sums[STEP_COUNT], char merkle_root[65]);
```

**用途：** 将四个步骤值的十进制文本分别做 SHA-256，再两两拼接哈希文本并哈希，最后生成 Merkle 根。成功返回 1，任一摘要计算失败返回 0；证明的是提交值的一致性。

| 参数 | 含义 |
| --- | --- |
| `step_sums` | [输入] STEP_COUNT（当前为 4）个步骤结果，数组内容可以是求和、计数、最小值或最大值步骤结果。 |
| `merkle_root` | [输出] 至少 65 字节的字符数组，保存 64 个字符的小写十六进制根哈希及结尾空字符。 |

## create_result_proof

```c
int create_result_proof(const char *operation, long range_start, long range_end, int simulate_wrong_result, long *result, char *proof_steps, int proof_size, char merkle_root[65]);
```

**用途：** 把闭区间分为四段并计算各段结果，按所选运算合并总结果，生成逗号分隔的步骤文本和 Merkle 根；可按测试标记故意修改一个步骤。成功返回非零，参数检查或摘要生成失败返回 0。

| 参数 | 含义 |
| --- | --- |
| `operation` | [输入] 运算标识：SUM_RANGE、COUNT_RANGE、MIN_RANGE 或 MAX_RANGE。 |
| `range_start` | [输入] 本子任务闭区间的起始整数，包含该值。 |
| `range_end` | [输入] 本子任务闭区间的结束整数，包含该值；调用者需保证范围合理且能形成四段。 |
| `simulate_wrong_result` | [输入] 非零时故意修改一个步骤值，用于模拟恶意节点；0 时按正常结果生成证明。 |
| `result` | [输出] long 指针，接收四段结果按运算规则合并后的值。 |
| `proof_steps` | [输出] 四个步骤值的十进制文本，按逗号连接，例如 1275,3775,6275,8775。 |
| `proof_size` | [输入] proof_steps 容量，单位为字节，包含结尾空字符；应足够容纳全部四个数，当前函数不另行报告 snprintf 截断。 |
| `merkle_root` | [输出] 至少 65 字节的字符数组，保存 64 个字符的十六进制根哈希及结尾空字符。 |
