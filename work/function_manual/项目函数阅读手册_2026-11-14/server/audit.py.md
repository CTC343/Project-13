# server/audit.py

把每轮节点结果、表决、信誉和考核状态追加到业务审计 JSONL 文件，并提供读取入口。

## save_round

```python
def save_round(task_state, trusted_value):
```

**用途：** 读取当前轮次的任务状态，将结果、证明、可信值、整合结果、信誉及考核信息作为一条 JSON 记录追加到 data/audit.jsonl。

| 参数 | 含义 |
| --- | --- |
| `task_state` | [输入] 当前 TaskState 对象；从中读取轮次、任务 ID、各节点结果与证明、整合结果、信誉、恶意节点和考核报告，不由此函数修改任务状态。 |
| `trusted_value` | [输入] 本轮严格多数表决选出的可信子任务结果；无严格多数时调用方传入 None，审计中保存为 null。 |

## read_rounds

```python
def read_rounds():
```

**用途：** 读取 data/audit.jsonl 并返回记录列表；文件不存在时返回空列表，无法解析为 JSON 的单独一行会被跳过。

**参数：** 无。
