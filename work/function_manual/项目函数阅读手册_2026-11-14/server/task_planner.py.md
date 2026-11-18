# server/task_planner.py

根据配置的总闭区间和子任务数量，计算指定轮次对应的平衡子区间。

## get_subtask_range

```python
def get_subtask_range(round_number):
```

**用途：** 通过整数除法把总闭区间均匀划分到 TOTAL_ROUNDS 轮，返回指定轮次的 (start, end) 闭区间；不同子区间长度最多相差一个数。函数本身不验证轮次范围。

| 参数 | 含义 |
| --- | --- |
| `round_number` | [输入] 从 1 开始的子任务轮次，正常应在 1～TOTAL_ROUNDS；用于定位该轮在总区间中的起点和终点。 |
