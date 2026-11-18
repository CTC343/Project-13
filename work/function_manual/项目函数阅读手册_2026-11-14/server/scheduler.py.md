# server/scheduler.py

根据信誉门槛和恶意节点集合生成重要任务候选名单；当前领取任务流程没有调用此名单实施拦截。

## choose_important_task_nodes

```python
def choose_important_task_nodes(reputation_scores, malicious_nodes):
```

**用途：** 筛选信誉不低于配置门槛、且不在恶意集合中的节点，按节点 ID 排序返回列表；本函数只生成名单，不分配任务，也不自行禁止节点领取任务。

| 参数 | 含义 |
| --- | --- |
| `reputation_scores` | [输入] 节点 ID 到信誉分的字典；只考虑当前字典中存在的节点。 |
| `malicious_nodes` | [输入] 已标记为恶意的节点集合；其中的节点即使信誉达标也不会进入返回名单。 |
