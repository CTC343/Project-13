#ifndef PROJECT13_SECURITY_H
#define PROJECT13_SECURITY_H

int sha256_hex(const char *message, char output_hex[65]);
int sha256_file_hex(const char *path, char output_hex[65]);
int hmac_sha256(const unsigned char *key, int key_size,
                const unsigned char *data, int data_size,
                unsigned char output[32]);
int hmac_sha256_hex(const unsigned char *key, int key_size,
                    const char *text, char output_hex[65]);
int secure_random(unsigned char *output, int output_size);
void bytes_to_hex(const unsigned char *bytes, int byte_count, char *hex);
int hex_to_bytes(const char *hex, unsigned char *bytes, int byte_count);
int constant_time_equal(const char *left, const char *right);
void clear_sensitive(void *data, int size);

#endif
