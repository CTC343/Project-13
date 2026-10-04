/* 使用 Windows BCrypt 计算 SHA-256，供 Merkle Tree 模块调用。 */
#include <windows.h>
#include <bcrypt.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "security.h"

#define SHA256_SIZE 32

int sha256_hex(const char *message, char output_hex[65])
{
    BCRYPT_ALG_HANDLE algorithm = NULL;
    BCRYPT_HASH_HANDLE hash = NULL;
    DWORD object_size = 0;
    DWORD bytes_written = 0;
    unsigned char *hash_object = NULL;
    unsigned char digest[SHA256_SIZE];
    DWORD index;
    NTSTATUS status;
    int success = 0;

    if (message == NULL || output_hex == NULL) {
        return 0;
    }

    status = BCryptOpenAlgorithmProvider(
        &algorithm, BCRYPT_SHA256_ALGORITHM, NULL, 0
    );
    if (!BCRYPT_SUCCESS(status)) {
        goto cleanup;
    }

    status = BCryptGetProperty(
        algorithm, BCRYPT_OBJECT_LENGTH, (PUCHAR)&object_size,
        sizeof(object_size), &bytes_written, 0
    );
    if (!BCRYPT_SUCCESS(status)) {
        goto cleanup;
    }

    hash_object = malloc(object_size);
    if (hash_object == NULL) {
        goto cleanup;
    }

    status = BCryptCreateHash(
        algorithm, &hash, hash_object, object_size, NULL, 0, 0
    );
    if (!BCRYPT_SUCCESS(status)) {
        goto cleanup;
    }

    status = BCryptHashData(
        hash, (PUCHAR)message, (ULONG)strlen(message), 0
    );
    if (!BCRYPT_SUCCESS(status)) {
        goto cleanup;
    }

    status = BCryptFinishHash(hash, digest, sizeof(digest), 0);
    if (!BCRYPT_SUCCESS(status)) {
        goto cleanup;
    }

    for (index = 0; index < SHA256_SIZE; index++) {
        snprintf(output_hex + index * 2, 3, "%02x", digest[index]);
    }
    success = 1;

cleanup:
    if (hash != NULL) {
        BCryptDestroyHash(hash);
    }
    free(hash_object);
    if (algorithm != NULL) {
        BCryptCloseAlgorithmProvider(algorithm, 0);
    }
    return success;
}

int sha256_file_hex(const char *path, char output_hex[65])
{
    BCRYPT_ALG_HANDLE algorithm = NULL;
    BCRYPT_HASH_HANDLE hash = NULL;
    DWORD object_size = 0;
    DWORD bytes_written = 0;
    unsigned char *hash_object = NULL;
    unsigned char digest[SHA256_SIZE];
    unsigned char buffer[4096];
    FILE *input = NULL;
    size_t read_size;
    NTSTATUS status;
    int success = 0;

    input = fopen(path, "rb");
    if (input == NULL) {
        return 0;
    }
    status = BCryptOpenAlgorithmProvider(
        &algorithm, BCRYPT_SHA256_ALGORITHM, NULL, 0
    );
    if (!BCRYPT_SUCCESS(status)) goto cleanup;
    status = BCryptGetProperty(
        algorithm, BCRYPT_OBJECT_LENGTH, (PUCHAR)&object_size,
        sizeof(object_size), &bytes_written, 0
    );
    if (!BCRYPT_SUCCESS(status)) goto cleanup;
    hash_object = malloc(object_size);
    if (hash_object == NULL) goto cleanup;
    status = BCryptCreateHash(
        algorithm, &hash, hash_object, object_size, NULL, 0, 0
    );
    if (!BCRYPT_SUCCESS(status)) goto cleanup;

    while ((read_size = fread(buffer, 1, sizeof(buffer), input)) > 0) {
        status = BCryptHashData(hash, buffer, (ULONG)read_size, 0);
        if (!BCRYPT_SUCCESS(status)) goto cleanup;
    }
    if (ferror(input)) goto cleanup;
    status = BCryptFinishHash(hash, digest, sizeof(digest), 0);
    if (!BCRYPT_SUCCESS(status)) goto cleanup;
    bytes_to_hex(digest, SHA256_SIZE, output_hex);
    success = 1;

cleanup:
    if (input != NULL) fclose(input);
    if (hash != NULL) BCryptDestroyHash(hash);
    clear_sensitive(buffer, sizeof(buffer));
    clear_sensitive(digest, sizeof(digest));
    if (hash_object != NULL) {
        clear_sensitive(hash_object, (int)object_size);
        free(hash_object);
    }
    if (algorithm != NULL) BCryptCloseAlgorithmProvider(algorithm, 0);
    return success;
}

int hmac_sha256(const unsigned char *key, int key_size,
                const unsigned char *data, int data_size,
                unsigned char output[32])
{
    BCRYPT_ALG_HANDLE algorithm = NULL;
    BCRYPT_HASH_HANDLE hash = NULL;
    DWORD object_size = 0;
    DWORD bytes_written = 0;
    unsigned char *hash_object = NULL;
    NTSTATUS status;
    int success = 0;

    status = BCryptOpenAlgorithmProvider(
        &algorithm, BCRYPT_SHA256_ALGORITHM, NULL,
        BCRYPT_ALG_HANDLE_HMAC_FLAG
    );
    if (!BCRYPT_SUCCESS(status)) goto cleanup;
    status = BCryptGetProperty(
        algorithm, BCRYPT_OBJECT_LENGTH, (PUCHAR)&object_size,
        sizeof(object_size), &bytes_written, 0
    );
    if (!BCRYPT_SUCCESS(status)) goto cleanup;
    hash_object = malloc(object_size);
    if (hash_object == NULL) goto cleanup;
    status = BCryptCreateHash(
        algorithm, &hash, hash_object, object_size,
        (PUCHAR)key, (ULONG)key_size, 0
    );
    if (!BCRYPT_SUCCESS(status)) goto cleanup;
    status = BCryptHashData(hash, (PUCHAR)data, (ULONG)data_size, 0);
    if (!BCRYPT_SUCCESS(status)) goto cleanup;
    status = BCryptFinishHash(hash, output, SHA256_SIZE, 0);
    if (!BCRYPT_SUCCESS(status)) goto cleanup;
    success = 1;

cleanup:
    if (hash != NULL) BCryptDestroyHash(hash);
    if (hash_object != NULL) {
        clear_sensitive(hash_object, (int)object_size);
        free(hash_object);
    }
    if (algorithm != NULL) BCryptCloseAlgorithmProvider(algorithm, 0);
    return success;
}

int hmac_sha256_hex(const unsigned char *key, int key_size,
                    const char *text, char output_hex[65])
{
    unsigned char digest[SHA256_SIZE];
    int success = hmac_sha256(
        key, key_size, (const unsigned char *)text, (int)strlen(text), digest
    );
    if (success) bytes_to_hex(digest, SHA256_SIZE, output_hex);
    clear_sensitive(digest, sizeof(digest));
    return success;
}

int secure_random(unsigned char *output, int output_size)
{
    return BCRYPT_SUCCESS(BCryptGenRandom(
        NULL, output, (ULONG)output_size, BCRYPT_USE_SYSTEM_PREFERRED_RNG
    ));
}

void bytes_to_hex(const unsigned char *bytes, int byte_count, char *hex)
{
    static const char digits[] = "0123456789abcdef";
    int index;
    for (index = 0; index < byte_count; index++) {
        hex[index * 2] = digits[bytes[index] >> 4];
        hex[index * 2 + 1] = digits[bytes[index] & 15];
    }
    hex[byte_count * 2] = '\0';
}

int hex_to_bytes(const char *hex, unsigned char *bytes, int byte_count)
{
    int index;
    unsigned int value;
    if ((int)strlen(hex) != byte_count * 2) return 0;
    for (index = 0; index < byte_count; index++) {
        if (sscanf(hex + index * 2, "%2x", &value) != 1) return 0;
        bytes[index] = (unsigned char)value;
    }
    return 1;
}

int constant_time_equal(const char *left, const char *right)
{
    size_t left_size = strlen(left);
    size_t right_size = strlen(right);
    size_t index;
    unsigned char difference = (unsigned char)(left_size ^ right_size);
    size_t compare_size = left_size < right_size ? left_size : right_size;
    for (index = 0; index < compare_size; index++) {
        difference |= (unsigned char)(left[index] ^ right[index]);
    }
    return difference == 0;
}

void clear_sensitive(void *data, int size)
{
    if (data != NULL && size > 0) SecureZeroMemory(data, (SIZE_T)size);
}
