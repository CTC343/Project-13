# server/signature.py

对任务描述生成 RSA-2048/SHA-256 PKCS#1 v1.5 签名，并提供性能微基准使用的摘要整数接口。

## text_checksum

```python
def text_checksum(text):
```

**用途：** 对文本的 UTF-8 字节计算 SHA-256，将 32 字节摘要按大端转换成整数返回；用于性能考核，不是 RSA 签名函数。

| 参数 | 含义 |
| --- | --- |
| `text` | [输入] 待计算摘要的字符串。 |

## sign_task

```python
def sign_task(task_text):
```

**用途：** 读取任务签名私钥，为文本构造 SHA-256 DigestInfo 和 PKCS#1 v1.5 填充，使用两个素数上的模幂及中国剩余定理生成签名，返回定长小写十六进制字符串；签名对象是任务描述，不是客户端 EXE。

| 参数 | 含义 |
| --- | --- |
| `task_text` | [输入] 要签名的完整任务描述字符串；业务调用按 task_id\|operation\|start\|end 拼接，各字段间用竖线分隔，客户端必须使用完全相同的文本验签。 |
