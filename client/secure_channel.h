#ifndef PROJECT13_SECURE_CHANNEL_H
#define PROJECT13_SECURE_CHANNEL_H

typedef struct {
    char session_id[64];
    unsigned char key[32];
    /* 两个方向分别维护严格递增序号，避免相互影响。 */
    long send_sequence;
    long receive_sequence;
} SecureSession;

/* 用长期认证密钥与本次握手材料派生会话密钥。 */
int derive_session_key(const unsigned char auth_key[32],
                       const char *client_nonce, const char *server_nonce,
                       const char *session_id, unsigned char output[32]);

/* 将客户端明文 JSON 封装为加密且带认证标签的安全信封。 */
int protect_client_message(SecureSession *session, const char *plain_json,
                           char *envelope, int envelope_size);

/* 验证服务端安全信封并输出解密后的 JSON。 */
int open_server_message(SecureSession *session, const char *envelope,
                        char *plain_json, int plain_size);

/* 会话结束时清除会话密钥和状态。 */
void clear_secure_session(SecureSession *session);

#endif
