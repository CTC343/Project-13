# server/merkle.py

构造四个步骤值的 SHA-256 Merkle 根，并检查步骤、汇总结果与提交根之间是否一致；不验证步骤是否真的来自任务区间。

## hash_text

```python
def hash_text(text):
```

**用途：** 将字符串按 UTF-8 编码并计算 SHA-256，返回 64 个字符的小写十六进制摘要，供 Merkle 树的叶子与父节点使用。

| 参数 | 含义 |
| --- | --- |
| `text` | [输入] 待计算摘要的字符串；叶子使用步骤值的十进制文本，父节点使用两个子摘要的十六进制文本拼接。 |

## build_merkle_root

```python
def build_merkle_root(step_values):
```

**用途：** 把步骤整数转换成文本并逐个哈希，再将前四个叶子两两组合成两层树，返回根摘要。内部直接访问前四项，本函数未检查长度是否恰为四；正常调用应传入四个步骤值。

| 参数 | 含义 |
| --- | --- |
| `step_values` | [输入] 按计算顺序排列的四个步骤整数；函数不修改该序列，先将每个值转换成字符串，再生成叶子摘要。 |

## verify_result_proof

```python
def verify_result_proof(operation, result_value, proof_text, expected_root):
```

**用途：** 把逗号分隔的证明转换成四个整数，检查按指定运算合并后是否等于提交结果，并重建 Merkle 根进行比较。通过时返回 True，整数转换失败、数量不符、合并值或根不符时返回 False。这里只验证提交内容是否自洽，不能单独证明计算正确。

| 参数 | 含义 |
| --- | --- |
| `operation` | [输入] 步骤合并规则：SUM_RANGE 和 COUNT_RANGE 相加，MIN_RANGE 取最小值，MAX_RANGE 取最大值。 |
| `result_value` | [输入] 客户端提交的整体结果整数；必须与四个步骤值按 operation 合并得到的值相同。 |
| `proof_text` | [输入] 四个十进制整数用英文逗号连接的字符串，例如 1,2,3,4；此实现发送全部步骤，不是抽样路径证明。 |
| `expected_root` | [输入] 客户端提交的 Merkle 根摘要文本；与服务端根据 proof_text 重建的根比较，并非预先由可信计算生成的根。 |
