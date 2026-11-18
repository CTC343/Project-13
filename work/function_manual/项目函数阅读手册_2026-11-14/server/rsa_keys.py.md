# server/rsa_keys.py

为任务签名生成、保存及读取 RSA-2048 密钥；私钥写入 data，公钥文件写入 client。

## _probably_prime

```python
def _probably_prime(number, rounds=24):
```

**用途：** 用随机底数执行 Miller–Rabin 概率素性检查，返回候选数是否通过；它是概率判断，并非严格素数证明。

| 参数 | 含义 |
| --- | --- |
| `number` | [输入] 待检查的整数；小于 2 或大于 2 的偶数会被直接判为非素数。 |
| `rounds` | [输入，可选，默认 24] 对候选数执行随机底数测试的轮数；增加轮数可降低合数误判概率，当前代码未单独校验其取值范围。 |

## _generate_prime

```python
def _generate_prime(bit_count):
```

**用途：** 不断生成指定位数的奇数候选值，要求候选值减一与公开指数 65537 互素，并通过概率素性检查，最后返回候选素数。

| 参数 | 含义 |
| --- | --- |
| `bit_count` | [输入] 候选数的二进制位数；通过设置最高位和最低位保证长度及奇数属性，当前调用中为 1024。 |

## ensure_task_signing_keys

```python
def ensure_task_signing_keys():
```

**用途：** 检查任务私钥和公钥文件是否存在，且私钥 JSON 是否含两个素数因子字段；满足则直接保留，否则生成两个不同的 1024 位素数组成 2048 位 RSA 模数，并写入私钥 JSON 与客户端公钥文件。现有文件分支并未完整验证公私钥是否匹配。

**参数：** 无。

## read_private_key

```python
def read_private_key():
```

**用途：** 先确保任务签名密钥文件存在，再解析私钥 JSON，返回五元组：(模数 n, 公开指数 e, 私有指数 d, 第一个素数 p, 第二个素数 q)，均转换为整数。

**参数：** 无。
