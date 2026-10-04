/* HMAC-SHA256 派生密钥流加密，并使用独立标签认证消息。 */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "protocol.h"
#include "secure_channel.h"
#include "security.h"

static void write_u64_big_endian(unsigned char output[8], uint64_t value)
{
    int index;
    for (index = 7; index >= 0; index--) {
        output[index] = (unsigned char)(value & 255);
        value >>= 8;
    }
}

static int make_keystream(const unsigned char key[32], const char *direction,
                          const char *session_id, long sequence,
                          const unsigned char nonce[16],
                          unsigned char *output, int output_size)
{
    unsigned char input[160];
    unsigned char block[32];
    unsigned char sequence_bytes[8];
    unsigned char counter_bytes[4];
    int prefix_size;
    int offset = 0;
    unsigned int counter = 0;
    int copy_size;

    prefix_size = snprintf((char *)input, sizeof(input), "%s|%s|",
                           direction, session_id);
    write_u64_big_endian(sequence_bytes, (uint64_t)sequence);
    memcpy(input + prefix_size, sequence_bytes, 8);
    prefix_size += 8;
    memcpy(input + prefix_size, nonce, 16);
    prefix_size += 16;

    while (offset < output_size) {
        counter_bytes[0] = (unsigned char)(counter >> 24);
        counter_bytes[1] = (unsigned char)(counter >> 16);
        counter_bytes[2] = (unsigned char)(counter >> 8);
        counter_bytes[3] = (unsigned char)counter;
        memcpy(input + prefix_size, counter_bytes, 4);
        if (!hmac_sha256(key, 32, input, prefix_size + 4, block)) return 0;
        copy_size = output_size - offset;
        if (copy_size > 32) copy_size = 32;
        memcpy(output + offset, block, copy_size);
        offset += copy_size;
        counter++;
    }
    clear_sensitive(input, sizeof(input));
    clear_sensitive(block, sizeof(block));
    return 1;
}

int derive_session_key(const unsigned char auth_key[32],
                       const char *client_nonce, const char *server_nonce,
                       const char *session_id, unsigned char output[32])
{
    char material[256];
    snprintf(material, sizeof(material), "SESSION|%s|%s|%s",
             client_nonce, server_nonce, session_id);
    return hmac_sha256(auth_key, 32, (unsigned char *)material,
                       (int)strlen(material), output);
}

static int crypt_message(const unsigned char key[32], const char *direction,
                         const char *session_id, long sequence,
                         const unsigned char nonce[16],
                         const unsigned char *input, int input_size,
                         unsigned char *output)
{
    unsigned char *stream = malloc(input_size > 0 ? input_size : 1);
    int index;
    if (stream == NULL) return 0;
    if (!make_keystream(key, direction, session_id, sequence,
                        nonce, stream, input_size)) {
        free(stream);
        return 0;
    }
    for (index = 0; index < input_size; index++) output[index] = input[index] ^ stream[index];
    clear_sensitive(stream, input_size);
    free(stream);
    return 1;
}

int protect_client_message(SecureSession *session, const char *plain_json,
                           char *envelope, int envelope_size)
{
    unsigned char nonce[16];
    unsigned char *ciphertext;
    int plain_size = (int)strlen(plain_json);
    char nonce_hex[33];
    char *ciphertext_hex;
    char *tag_text;
    char tag[65];
    int needed;

    session->send_sequence++;
    ciphertext = malloc(plain_size > 0 ? plain_size : 1);
    ciphertext_hex = malloc(plain_size * 2 + 1);
    tag_text = malloc(plain_size * 2 + 256);
    if (ciphertext == NULL || ciphertext_hex == NULL || tag_text == NULL ||
        !secure_random(nonce, sizeof(nonce)) ||
        !crypt_message(session->key, "C2S", session->session_id,
                       session->send_sequence, nonce,
                       (const unsigned char *)plain_json, plain_size, ciphertext)) {
        free(ciphertext); free(ciphertext_hex); free(tag_text);
        return 0;
    }
    bytes_to_hex(nonce, sizeof(nonce), nonce_hex);
    bytes_to_hex(ciphertext, plain_size, ciphertext_hex);
    snprintf(tag_text, plain_size * 2 + 256, "C2S|%s|%ld|%s|%s",
             session->session_id, session->send_sequence,
             nonce_hex, ciphertext_hex);
    if (!hmac_sha256_hex(session->key, 32, tag_text, tag)) {
        free(ciphertext); free(ciphertext_hex); free(tag_text);
        return 0;
    }
    needed = snprintf(envelope, envelope_size,
        "{\"session_id\":\"%s\",\"sequence\":%ld,\"nonce\":\"%s\","
        "\"ciphertext\":\"%s\",\"tag\":\"%s\"}",
        session->session_id, session->send_sequence, nonce_hex,
        ciphertext_hex, tag);
    clear_sensitive(ciphertext, plain_size);
    clear_sensitive(tag_text, plain_size * 2 + 256);
    free(ciphertext); free(ciphertext_hex); free(tag_text);
    return needed > 0 && needed < envelope_size;
}

int open_server_message(SecureSession *session, const char *envelope,
                        char *plain_json, int plain_size)
{
    char received_session[64];
    char nonce_hex[33];
    char ciphertext_hex[PROTOCOL_BODY_SIZE];
    char received_tag[65];
    char expected_tag[65];
    long sequence;
    unsigned char nonce[16];
    unsigned char *ciphertext;
    int ciphertext_size;
    char *tag_text;
    int success = 0;

    if (!json_get_string(envelope, "session_id", received_session, sizeof(received_session)) ||
        !json_get_long(envelope, "sequence", &sequence) ||
        !json_get_string(envelope, "nonce", nonce_hex, sizeof(nonce_hex)) ||
        !json_get_string(envelope, "ciphertext", ciphertext_hex, sizeof(ciphertext_hex)) ||
        !json_get_string(envelope, "tag", received_tag, sizeof(received_tag))) return 0;
    if (strcmp(received_session, session->session_id) != 0 ||
        sequence != session->receive_sequence + 1 ||
        !hex_to_bytes(nonce_hex, nonce, 16) || strlen(ciphertext_hex) % 2 != 0) return 0;

    ciphertext_size = (int)strlen(ciphertext_hex) / 2;
    if (ciphertext_size < 2 || ciphertext_size + 1 > plain_size) return 0;
    ciphertext = malloc(ciphertext_size > 0 ? ciphertext_size : 1);
    tag_text = malloc(strlen(ciphertext_hex) + 256);
    if (ciphertext == NULL || tag_text == NULL ||
        !hex_to_bytes(ciphertext_hex, ciphertext, ciphertext_size)) goto cleanup;
    snprintf(tag_text, strlen(ciphertext_hex) + 256, "S2C|%s|%ld|%s|%s",
             session->session_id, sequence, nonce_hex, ciphertext_hex);
    if (!hmac_sha256_hex(session->key, 32, tag_text, expected_tag) ||
        !constant_time_equal(received_tag, expected_tag)) goto cleanup;
    if (!crypt_message(session->key, "S2C", session->session_id, sequence,
                       nonce, ciphertext, ciphertext_size,
                       (unsigned char *)plain_json)) goto cleanup;
    plain_json[ciphertext_size] = '\0';
    if (plain_json[0] != '{' || plain_json[ciphertext_size - 1] != '}') goto cleanup;
    session->receive_sequence = sequence;
    success = 1;

cleanup:
    if (ciphertext != NULL) { clear_sensitive(ciphertext, ciphertext_size); free(ciphertext); }
    if (tag_text != NULL) { clear_sensitive(tag_text, (int)strlen(ciphertext_hex) + 256); free(tag_text); }
    return success;
}

void clear_secure_session(SecureSession *session)
{
    clear_sensitive(session, sizeof(*session));
}
