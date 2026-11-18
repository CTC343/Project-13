# server/config.py

集中定义网络、协议、任务、许可证和信誉配置，并从环境变量读取可覆盖的任务参数。

## read_int

```python
def read_int(name, default_value):
```

**用途：** 读取指定环境变量并转换为整数；环境变量不存在时使用默认值，内容无法转换成整数时也返回默认值。

| 参数 | 含义 |
| --- | --- |
| `name` | [输入] 要读取的环境变量名称，例如 PROJECT13_TASK_START。 |
| `default_value` | [输入] 环境变量不存在或整数转换失败时采用的默认整数。 |
