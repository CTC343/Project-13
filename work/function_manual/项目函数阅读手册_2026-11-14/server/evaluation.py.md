# server/evaluation.py

计算准确性误差、固定微基准中的安全开销和恶意节点指标，并保存、读取考核报告。

## standard_answer

```python
def standard_answer():
```

**用途：** 根据当前配置的运算类型和完整任务区间，调用 expected_result() 返回整个任务的参考答案。

**参数：** 无。

## slow_sum

```python
def slow_sum(limit):
```

**用途：** 逐个累加 1 到 limit 的整数并返回总和，用作性能微基准的计算负载；limit 小于 1 时循环不执行，返回 0。

| 参数 | 含义 |
| --- | --- |
| `limit` | [输入] 累加上界，包含该数；微基准中传入 2000000。 |

## measure_security_overhead

```python
def measure_security_overhead():
```

**用途：** 先测三次逐项累加的耗时，再测三次任务签名、公钥模幂、摘要、Merkle 根构造及会话加解密的耗时，返回额外安全耗时占计算基线耗时的百分比。它是固定 Python 微基准，不是整个 C/S 系统的端到端性能测试，公钥模幂步骤也不等于完整的签名编码校验。

**参数：** 无。

## create_evaluation_report

```python
def create_evaluation_report(task_state, trusted_value):
```

**用途：** 将整合结果与完整区间的参考答案比较，计算误差、安全微基准开销和已识别恶意节点比例，返回包含指标及通过标记的字典；参考答案为 0 时误差字段保存绝对差。

| 参数 | 含义 |
| --- | --- |
| `task_state` | [输入] 当前 TaskState 对象；此处读取 malicious_nodes 集合，以其大小除以配置的 REQUIRED_NODES 计算恶意节点比例。 |
| `trusted_value` | [输入] 所有已采纳子任务合并后的完整任务结果；虽然参数名叫可信值，此处比较的是整体答案，而非单独一轮的小计。 |

## save_evaluation_report

```python
def save_evaluation_report(report):
```

**用途：** 将报告字典写入 data/evaluation.json；文件已存在时覆盖原报告。

| 参数 | 含义 |
| --- | --- |
| `report` | [输入] 要保存的考核报告字典，通常来自 create_evaluation_report()，含运算、各项指标和通过标记。 |

## read_evaluation_report

```python
def read_evaluation_report():
```

**用途：** 读取 data/evaluation.json 并返回解析后的报告；文件不存在时返回空字典，其他读写或 JSON 解析异常未在此处吞掉。

**参数：** 无。
