# client/signature.c

读取任务 RSA 公钥并调用 BCrypt 验证任务数字签名。

## read_public_key

```c
static int read_public_key(char *modulus_hex, int modulus_size, unsigned long *public_exponent);
```

**用途：** 读取当前 EXE 同目录下的 task_public.key，提取 RSA 模数和公钥指数；两个字段均找到时返回 1，否则返回 0。

| 参数 | 含义 |
| --- | --- |
| `modulus_hex` | [输出] 保存模数十六进制文本的字符缓冲区，不包含 modulus= 前缀和行尾换行。 |
| `modulus_size` | [输入] modulus_hex 容量，单位为字节，包含结尾空字符。2048 位模数通常需要 513 字节。 |
| `public_exponent` | [输出] unsigned long 指针，接收文件中十进制公钥指数，通常为 65537。 |

## exponent_bytes

```c
static int exponent_bytes(unsigned long exponent, unsigned char output[8]);
```

**用途：** 把无符号公钥指数转为没有多余前导零的大端字节序，并返回实际字节数，供 BCrypt 的 RSA 公钥 Blob 使用。

| 参数 | 含义 |
| --- | --- |
| `exponent` | [输入] RSA 公钥指数的整数值。 |
| `output` | [输出] 至少八字节的数组，写入大端序指数；只有返回长度范围内的字节有效。 |

## verify_task_signature

```c
int verify_task_signature(const char *task_text, const char *signature_hex);
```

**用途：** 读取任务公钥，计算任务文本 SHA-256，导入 RSA 公钥并调用 BCryptVerifySignature 进行 RSA-2048／SHA-256／PKCS#1 v1.5 验签。验签成功返回 1，格式、密钥读取或验证失败返回 0；此处验证的是任务而非程序文件。

| 参数 | 含义 |
| --- | --- |
| `task_text` | [输入] 签名覆盖的原始任务文本，格式为 task_id\|operation\|start\|end，必须与服务端签名时完全一致。 |
| `signature_hex` | [输入] 服务端任务签名的十六进制字符串；当前要求恰好 512 字符，对应 256 字节的 RSA-2048 签名。 |
