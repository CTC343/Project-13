# client/security.h

声明摘要、HMAC、随机数、编码转换、比较与敏感内存清理接口。

## sha256_hex

```c
int sha256_hex(const char *message, char output_hex[65]);
```

**用途：** 接口声明，对应实现在同名 .c 文件中。调用 Windows BCrypt 计算文本的 SHA-256，输出小写十六进制摘要；成功返回 1，参数为空或密码接口失败返回 0。

| 参数 | 含义 |
| --- | --- |
| `message` | [输入] 以空字符结尾的待摘要字符串；长度按 strlen 计算，不包含终止符。 |
| `output_hex` | [输出] 至少 65 字节的字符数组：64 个小写十六进制摘要字符加结尾空字符。 |

## sha256_file_hex

```c
int sha256_file_hex(const char *path, char output_hex[65]);
```

**用途：** 接口声明，对应实现在同名 .c 文件中。以二进制方式分块读取文件并计算完整内容的 SHA-256，供程序完整性检查使用；成功返回 1，打开、读取或摘要计算失败返回 0。

| 参数 | 含义 |
| --- | --- |
| `path` | [输入] 要计算摘要的文件路径字符串。 |
| `output_hex` | [输出] 至少 65 字节的字符数组，保存 64 个字符的小写十六进制文件摘要及结尾空字符。 |

## hmac_sha256

```c
int hmac_sha256(const unsigned char *key, int key_size, const unsigned char *data, int data_size, unsigned char output[32]);
```

**用途：** 接口声明，对应实现在同名 .c 文件中。通过 BCrypt 的 HMAC 模式对指定字节数据计算 HMAC-SHA256，成功返回 1，密码接口或内存分配失败返回 0；结束时清理并释放哈希对象。

| 参数 | 含义 |
| --- | --- |
| `key` | [输入] HMAC 密钥的原始字节地址。 |
| `key_size` | [输入] key 的有效长度，单位为字节。 |
| `data` | [输入] 要认证的原始数据字节地址，可以包含零字节。 |
| `data_size` | [输入] data 的有效长度，单位为字节。 |
| `output` | [输出] 至少 32 字节的数组，保存原始 HMAC 摘要，不附加字符串终止符。 |

## hmac_sha256_hex

```c
int hmac_sha256_hex(const unsigned char *key, int key_size, const char *text, char output_hex[65]);
```

**用途：** 接口声明，对应实现在同名 .c 文件中。对字符串文本计算 HMAC-SHA256，把原始摘要转为小写十六进制，并清理临时摘要数组；成功返回非零。

| 参数 | 含义 |
| --- | --- |
| `key` | [输入] HMAC 密钥的原始字节地址。 |
| `key_size` | [输入] key 有效长度，单位为字节。 |
| `text` | [输入] 以空字符结尾的待认证文本；按 strlen 计算长度。 |
| `output_hex` | [输出] 至少 65 字节的字符数组，保存 64 个十六进制标签字符及结尾空字符。 |

## secure_random

```c
int secure_random(unsigned char *output, int output_size);
```

**用途：** 接口声明，对应实现在同名 .c 文件中。调用 Windows 系统首选的密码学安全随机数生成器 BCryptGenRandom 填充缓冲区；成功返回非零，失败返回 0。

| 参数 | 含义 |
| --- | --- |
| `output` | [输出] 接收原始随机字节的缓冲区。 |
| `output_size` | [输入] 需要生成的随机字节数，output 至少具有此容量。 |

## bytes_to_hex

```c
void bytes_to_hex(const unsigned char *bytes, int byte_count, char *hex);
```

**用途：** 接口声明，对应实现在同名 .c 文件中。把原始字节逐个转换为两个小写十六进制字符，并在末尾追加空字符。

| 参数 | 含义 |
| --- | --- |
| `bytes` | [输入] 待转换的原始字节数组。 |
| `byte_count` | [输入] 要转换的原始字节数。 |
| `hex` | [输出] 接收十六进制文本的缓冲区，至少需要 2×byte_count+1 字节。 |

## hex_to_bytes

```c
int hex_to_bytes(const char *hex, unsigned char *bytes, int byte_count);
```

**用途：** 接口声明，对应实现在同名 .c 文件中。要求输入文本长度等于目标字节数的两倍，随后每两字符尝试用 sscanf 转为一个字节；成功返回 1，长度或转换失败返回 0。当前使用 %2x，并非严格逐字符十六进制合法性检查。

| 参数 | 含义 |
| --- | --- |
| `hex` | [输入] 以空字符结尾的十六进制文本，长度应恰好为 2×byte_count。 |
| `bytes` | [输出] 接收解码结果的二进制缓冲区，至少具有 byte_count 字节。 |
| `byte_count` | [输入] 预期得到的原始字节数，同时决定输入文本所需长度。 |

## constant_time_equal

```c
int constant_time_equal(const char *left, const char *right);
```

**用途：** 接口声明，对应实现在同名 .c 文件中。累积两字符串对应字节的异或差异，避免发现第一个不同字符后立即退出，供认证标签比较使用；相等返回 1。循环次数仍依赖字符串长度，且当前长度差存入 unsigned char，因此不能视作任意长度输入的严格恒定时间比较器。

| 参数 | 含义 |
| --- | --- |
| `left` | [输入] 第一个以空字符结尾的待比较字符串，当前常用于 64 字符 HMAC 标签。 |
| `right` | [输入] 第二个以空字符结尾的待比较字符串。 |

## clear_sensitive

```c
void clear_sensitive(void *data, int size);
```

**用途：** 接口声明，对应实现在同名 .c 文件中。当地址非空且长度大于 0 时调用 SecureZeroMemory，将指定内存区域全部置零，用于清除密钥、凭据和临时敏感数据。

| 参数 | 含义 |
| --- | --- |
| `data` | [输出／清除] 要清零内存区域的起始地址，可以为 NULL。 |
| `size` | [输入] 要清零的字节数；小于等于 0 时不执行清零。 |
