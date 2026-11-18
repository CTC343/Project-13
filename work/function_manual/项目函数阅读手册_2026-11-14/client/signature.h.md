# client/signature.h

声明任务 RSA-2048 数字签名验证接口。

## verify_task_signature

```c
int verify_task_signature(const char *task_text, const char *signature_hex);
```

**用途：** 接口声明，对应实现在同名 .c 文件中。读取任务公钥，计算任务文本 SHA-256，导入 RSA 公钥并调用 BCryptVerifySignature 进行 RSA-2048／SHA-256／PKCS#1 v1.5 验签。验签成功返回 1，格式、密钥读取或验证失败返回 0；此处验证的是任务而非程序文件。

| 参数 | 含义 |
| --- | --- |
| `task_text` | [输入] 签名覆盖的原始任务文本，格式为 task_id\|operation\|start\|end，必须与服务端签名时完全一致。 |
| `signature_hex` | [输入] 服务端任务签名的十六进制字符串；当前要求恰好 512 字符，对应 256 字节的 RSA-2048 签名。 |
