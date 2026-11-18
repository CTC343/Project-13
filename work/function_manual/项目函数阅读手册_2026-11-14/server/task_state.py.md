# server/task_state.py

用一个共享对象保存任务会话、轮次、节点结果、信誉与完成状态，并提供任务编号和轮次切换。

## TaskState.__init__

```python
def __init__(self):
```

**用途：** 初始化可重入锁、随机任务会话水印、第一轮编号，以及结果、证明、信誉等容器；根据 TASK_ENABLED 设置初始 completed 状态。

| 参数 | 含义 |
| --- | --- |
| `self` | [输出] 正在创建的 TaskState 实例；锁和全部任务状态字段都会写入此对象，供各连接共用。 |

## TaskState.get_task_id

```python
def get_task_id(self):
```

**用途：** 用任务前缀、当前实例的会话水印和三位十进制轮次拼成任务 ID，例如 task-会话水印-001；只读取状态，不推进轮次。

| 参数 | 含义 |
| --- | --- |
| `self` | [输入] 当前 TaskState；读取 session_id 和 round_number 来生成任务 ID。 |

## TaskState.start_next_round

```python
def start_next_round(self):
```

**用途：** 将轮次加一，并清空本轮结果、结果证明及已分配节点集合；保留历史可信结果、信誉和恶意节点记录。函数内部不加锁，由调用方在持有共享锁时使用。

| 参数 | 含义 |
| --- | --- |
| `self` | [输入／输出] 要切换轮次的 TaskState；更新 round_number、task_results、result_proofs 和 assigned_nodes。 |
