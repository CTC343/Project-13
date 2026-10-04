#ifndef PROJECT13_SECURE_CHANNEL_H
#define PROJECT13_SECURE_CHANNEL_H

typedef struct {
    char session_id[64];
    unsigned char key[32];
    long send_sequence;
    long receive_sequence;
} SecureSession;

int derive_session_key(const unsigned char auth_key[32],
                       const char *client_nonce, const char *server_nonce,
                       const char *session_id, unsigned char output[32]);
int protect_client_message(SecureSession *session, const char *plain_json,
                           char *envelope, int envelope_size);
int open_server_message(SecureSession *session, const char *envelope,
                        char *plain_json, int plain_size);
void clear_secure_session(SecureSession *session);

#endif
