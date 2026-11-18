#ifndef PROJECT13_SECURITY_H
#define PROJECT13_SECURITY_H

/* 返回 64 个十六进制字符的 SHA-256 摘要（输出缓冲区需容纳 65 字节）。 */
int sha256_hex(const char *message, char output_hex[65]);
int sha256_file_hex(const char *path, char output_hex[65]);

/* 计算原始字节或文本形式的 HMAC-SHA-256。 */
int hmac_sha256(const unsigned char *key, int key_size,
                const unsigned char *data, int data_size,
                unsigned char output[32]);
int hmac_sha256_hex(const unsigned char *key, int key_size,
                    const char *text, char output_hex[65]);

/* 从系统随机数生成器取随机字节；成功返回非零。 */
int secure_random(unsigned char *output, int output_size);

/* 二进制与十六进制文本之间的转换工具。 */
void bytes_to_hex(const unsigned char *bytes, int byte_count, char *hex);
int hex_to_bytes(const char *hex, unsigned char *bytes, int byte_count);

/* 比较认证文本并清理内存中的敏感数据。 */
int constant_time_equal(const char *left, const char *right);
void clear_sensitive(void *data, int size);

#endif
