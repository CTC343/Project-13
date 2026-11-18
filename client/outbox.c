#include <stdio.h>
#include <string.h>
#include <windows.h>
#include <bcrypt.h>

#include "outbox.h"
#include "security.h"

#define NONCE_SIZE 12
#define TAG_SIZE 16

static int aes_gcm(const Outbox *outbox, int encrypt, unsigned char nonce[NONCE_SIZE],
                   unsigned char tag[TAG_SIZE], const unsigned char *input, DWORD length,
                   unsigned char *output)
{
    BCRYPT_ALG_HANDLE algorithm = NULL;
    BCRYPT_KEY_HANDLE key = NULL;
    BCRYPT_AUTHENTICATED_CIPHER_MODE_INFO info;
    ULONG written = 0;
    int ok = 0;
    if (!BCRYPT_SUCCESS(BCryptOpenAlgorithmProvider(&algorithm, BCRYPT_AES_ALGORITHM, NULL, 0))) return 0;
    if (!BCRYPT_SUCCESS(BCryptSetProperty(algorithm, BCRYPT_CHAINING_MODE,
            (PUCHAR)BCRYPT_CHAIN_MODE_GCM, sizeof(BCRYPT_CHAIN_MODE_GCM), 0)) ||
        !BCRYPT_SUCCESS(BCryptGenerateSymmetricKey(algorithm, &key, NULL, 0,
            (PUCHAR)outbox->key, sizeof(outbox->key), 0))) goto done;
    BCRYPT_INIT_AUTH_MODE_INFO(info);
    info.pbNonce = nonce;
    info.cbNonce = NONCE_SIZE;
    info.pbTag = tag;
    info.cbTag = TAG_SIZE;
    info.pbAuthData = (PUCHAR)outbox->identity;
    info.cbAuthData = 64;
    if (encrypt) {
        ok = BCRYPT_SUCCESS(BCryptEncrypt(key, (PUCHAR)input, length, &info, NULL, 0,
                                         output, length, &written, 0));
    } else {
        ok = BCRYPT_SUCCESS(BCryptDecrypt(key, (PUCHAR)input, length, &info, NULL, 0,
                                         output, length, &written, 0));
    }
done:
    if (key) BCryptDestroyKey(key);
    BCryptCloseAlgorithmProvider(algorithm, 0);
    return ok && written == length;
}

int outbox_init(const ClientLogin *login, Outbox *outbox)
{
    char directory[MAX_PATH];
    char storage[MAX_PATH];
    char identity[512];
    FILE *secret;
    int valid;
    DWORD length = GetEnvironmentVariableA("PROJECT13_OUTBOX_DIR", directory, sizeof(directory));
    if (length == 0) {
        length = GetEnvironmentVariableA("LOCALAPPDATA", directory, sizeof(directory));
        if (length == 0 || length >= sizeof(directory) - 11) return 0;
        snprintf(directory + length, sizeof(directory) - length, "\\Project13");
    } else if (length >= sizeof(directory)) {
        return 0;
    }
    if (!CreateDirectoryA(directory, NULL) && GetLastError() != ERROR_ALREADY_EXISTS) return 0;
    snprintf(identity, sizeof(identity), "%s|%d|%s|%s",
             login->host, login->port, login->node_id, login->username);
    if (!sha256_hex(identity, outbox->identity) ||
        strlen(directory) + sizeof(outbox->identity) + 10 >= MAX_PATH - 50) return 0;
    snprintf(outbox->path, sizeof(outbox->path), "%s\\%s.pending", directory, outbox->identity);
    if (snprintf(storage, sizeof(storage), "%s.storage", login->profile) >= sizeof(storage)) return 0;
    secret = fopen(storage, "rb");
    if (!secret) return 0;
    valid = fread(outbox->key, 1, sizeof(outbox->key), secret) == sizeof(outbox->key) &&
            fgetc(secret) == EOF;
    fclose(secret);
    return valid;
}

int outbox_load(const Outbox *outbox, char *message, int capacity)
{
    unsigned char encrypted[8192];
    DWORD length = 0;
    DWORD overhead = NONCE_SIZE + TAG_SIZE;
    HANDLE file = CreateFileA(outbox->path, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING,
                              FILE_ATTRIBUTE_NORMAL, NULL);
    int result = -1;
    if (file == INVALID_HANDLE_VALUE) return GetLastError() == ERROR_FILE_NOT_FOUND ? 0 : -1;
    if (GetFileSize(file, NULL) < sizeof(encrypted) &&
        ReadFile(file, encrypted, sizeof(encrypted), &length, NULL) &&
        length > overhead && length - overhead < (DWORD)capacity &&
        aes_gcm(outbox, 0, encrypted, encrypted + NONCE_SIZE, encrypted + overhead,
                length - overhead, (unsigned char *)message) &&
        memchr(message, '\0', length - overhead) == NULL) {
        message[length - overhead] = '\0';
        result = 1;
    }
    CloseHandle(file);
    return result;
}

int outbox_save(const Outbox *outbox, const char *message)
{
    char temporary[MAX_PATH];
    unsigned char encrypted[8192];
    DWORD length = (DWORD)strlen(message);
    DWORD overhead = NONCE_SIZE + TAG_SIZE;
    HANDLE file;
    DWORD written = 0;
    int success = 0;
    snprintf(temporary, sizeof(temporary), "%s.%lu.tmp", outbox->path, GetCurrentProcessId());
    if (length > sizeof(encrypted) - overhead || !secure_random(encrypted, NONCE_SIZE) ||
        !aes_gcm(outbox, 1, encrypted, encrypted + NONCE_SIZE, (const unsigned char *)message,
                 length, encrypted + overhead)) return 0;
    file = CreateFileA(temporary, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS,
                       FILE_ATTRIBUTE_NORMAL, NULL);
    if (file != INVALID_HANDLE_VALUE) {
        success = WriteFile(file, encrypted, length + overhead, &written, NULL) &&
                  written == length + overhead && FlushFileBuffers(file);
        if (!CloseHandle(file)) success = 0;
    }
    if (success) success = MoveFileExA(temporary, outbox->path, MOVEFILE_WRITE_THROUGH);
    if (!success) DeleteFileA(temporary);
    return success;
}

int outbox_resolve(const Outbox *outbox, const char *task_id, int accepted)
{
    char retained[MAX_PATH];
    if (accepted) return DeleteFileA(outbox->path) || GetLastError() == ERROR_FILE_NOT_FOUND;
    if (strspn(task_id, "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ-_") != strlen(task_id)) return 0;
    snprintf(retained, sizeof(retained), "%s.%s.stale", outbox->path, task_id);
    return MoveFileExA(outbox->path, retained, MOVEFILE_WRITE_THROUGH);
}
