#ifndef PROJECT13_CREDENTIALS_H
#define PROJECT13_CREDENTIALS_H

typedef struct {
    char node_id[64];
    char license_id[64];
    char expires[16];
    unsigned char auth_key[32];
} NodeCredential;

int load_node_credential(const char *node_id, NodeCredential *credential,
                         char *error_text, int error_size);
int current_executable_hash(char output_hex[65],
                            char *error_text, int error_size);
void clear_node_credential(NodeCredential *credential);

#endif
