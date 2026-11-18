# client/operations.h

声明区间运算识别、计算、合并及错误模拟接口。

## is_operation_supported

```c
int is_operation_supported(const char *operation);
```

**用途：** 接口声明，对应实现在同名 .c 文件中。检查运算名称是否属于四个已支持的区间运算；支持返回非零，否则返回 0。

| 参数 | 含义 |
| --- | --- |
| `operation` | [输入] 要检查的运算标识字符串，应为 SUM_RANGE、COUNT_RANGE、MIN_RANGE 或 MAX_RANGE 之一。 |

## calculate_operation

```c
long calculate_operation(const char *operation, long start, long end);
```

**用途：** 接口声明，对应实现在同名 .c 文件中。按运算类型计算闭区间结果：求和逐个累加，计数返回区间长度，最小值返回起点，最大值返回终点；未知运算返回 0。

| 参数 | 含义 |
| --- | --- |
| `operation` | [输入] 区间运算标识，调用者应先用 is_operation_supported 检查。 |
| `start` | [输入] 闭区间起点，参与运算。 |
| `end` | [输入] 闭区间终点，参与运算；此函数不单独检查起止顺序或 long 溢出。 |

## merge_step_values

```c
long merge_step_values(const char *operation, long values[4]);
```

**用途：** 接口声明，对应实现在同名 .c 文件中。把四个步骤值合并为一个任务结果：求和／计数相加，最小值取四者最小，最大值取四者最大。

| 参数 | 含义 |
| --- | --- |
| `operation` | [输入] 决定合并规则的运算标识，调用者应保证属于支持的四种运算。 |
| `values` | [输入] 恰好四个步骤结果的 long 数组；函数读取但不修改其元素。 |

## change_step_for_wrong_test

```c
void change_step_for_wrong_test(const char *operation, long values[4]);
```

**用途：** 接口声明，对应实现在同名 .c 文件中。故意把一个步骤值加 1，以模拟一个提交自洽错误结果的恶意节点；MIN_RANGE 修改第一段，其他运算修改第四段。

| 参数 | 含义 |
| --- | --- |
| `operation` | [输入] 当前运算标识，用于决定修改第一段还是第四段。 |
| `values` | [输入／输出] 四个步骤结果的数组，在原数组上修改一个元素。 |
