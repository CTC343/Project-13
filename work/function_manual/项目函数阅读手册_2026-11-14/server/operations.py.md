# server/operations.py

集中登记四种区间运算，提供运算识别、中文名称、结果合并和标准结果计算。

## is_supported

```python
def is_supported(operation):
```

**用途：** 检查运算代码是否出现在 OPERATION_OPTIONS 中，返回布尔值，用于拒绝未知运算。

| 参数 | 含义 |
| --- | --- |
| `operation` | [输入] 待检查的运算代码字符串，支持 SUM_RANGE、COUNT_RANGE、MIN_RANGE、MAX_RANGE，比较区分大小写。 |

## operation_label

```python
def operation_label(operation):
```

**用途：** 把已知运算代码转换成配置中的中文名称；遇到未知代码时原样返回该代码。

| 参数 | 含义 |
| --- | --- |
| `operation` | [输入] 运算代码字符串，如 SUM_RANGE；作为名称查找键。 |

## merge_values

```python
def merge_values(operation, values):
```

**用途：** 按运算规则合并若干值：求和和计数使用相加，最小值取 min，最大值取 max；空集合返回 None，未知运算抛出 ValueError。可用于合并步骤值或多个子任务的小计。

| 参数 | 含义 |
| --- | --- |
| `operation` | [输入] 决定合并方式的运算代码：SUM_RANGE、COUNT_RANGE、MIN_RANGE 或 MAX_RANGE。 |
| `values` | [输入] 待合并的数值序列，通常为步骤值列表或历史可信子任务结果列表；不在原序列中写入结果。 |

## expected_result

```python
def expected_result(operation, start, end):
```

**用途：** 直接计算指定闭区间的理论结果：等差数列求和、整数数量、最小端点或最大端点；未知运算抛出 ValueError，函数内部不检查 start 是否小于等于 end。

| 参数 | 含义 |
| --- | --- |
| `operation` | [输入] 要计算理论结果的运算代码，四种代码与 OPERATION_OPTIONS 一致。 |
| `start` | [输入] 整数闭区间的起点，包含在计算范围内；MIN_RANGE 时直接作为理论结果。 |
| `end` | [输入] 整数闭区间的终点，包含在计算范围内；MAX_RANGE 时直接作为理论结果。 |
