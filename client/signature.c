/* 使用 Windows CNG 验证 RSA-2048 SHA-256/PKCS#1 任务签名。 */
#include <windows.h>
#include <bcrypt.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "security.h"
#include "signature.h"

static int read_public_key(char *modulus_hex, int modulus_size,
                           unsigned long *public_exponent)
{
    char executable[MAX_PATH];
    char path[MAX_PATH];
    char line[600];
    char *separator;
    FILE *file;
    DWORD length = GetModuleFileNameA(NULL, executable, sizeof(executable));
    int found_modulus = 0;
    int found_exponent = 0;

    if (length == 0 || length >= sizeof(executable)) return 0;
    snprintf(path, sizeof(path), "%s", executable);
    separator = strrchr(path, '\\');
    if (separator == NULL) return 0;
    snprintf(separator + 1, sizeof(path) - (separator + 1 - path),
             "task_public.key");
    file = fopen(path, "r");
    if (file == NULL) return 0;

    while (fgets(line, sizeof(line), file) != NULL) {
        if (strncmp(line, "modulus=", 8) == 0) {
            snprintf(modulus_hex, modulus_size, "%s", line + 8);
            modulus_hex[strcspn(modulus_hex, "\r\n")] = '\0';
            found_modulus = 1;
        } else if (strncmp(line, "public_exponent=", 16) == 0) {
            *public_exponent = strtoul(line + 16, NULL, 10);
            found_exponent = 1;
        }
    }
    fclose(file);
    return found_modulus && found_exponent;
}

static int exponent_bytes(unsigned long exponent, unsigned char output[8])
{
    unsigned char reverse[8];
    int count = 0;
    int index;
    while (exponent > 0) {
        reverse[count++] = (unsigned char)(exponent & 255);
        exponent >>= 8;
    }
    for (index = 0; index < count; index++) output[index] = reverse[count - 1 - index];
    return count;
}

int verify_task_signature(const char *task_text, const char *signature_hex)
{
    BCRYPT_ALG_HANDLE algorithm = NULL;
    BCRYPT_KEY_HANDLE public_key = NULL;
    BCRYPT_RSAKEY_BLOB *header;
    BCRYPT_PKCS1_PADDING_INFO padding = {BCRYPT_SHA256_ALGORITHM};
    unsigned char *blob = NULL;
    unsigned char *modulus;
    unsigned char exponent[8];
    unsigned char signature[256];
    unsigned char digest[32];
    char digest_hex[65];
    char modulus_hex[520];
    unsigned long exponent_value;
    int exponent_size;
    int modulus_size;
    int blob_size;
    NTSTATUS status;
    int verified = 0;

    if (task_text == NULL || signature_hex == NULL ||
        !read_public_key(modulus_hex, sizeof(modulus_hex), &exponent_value)) return 0;
    modulus_size = (int)strlen(modulus_hex) / 2;
    if (modulus_size != 256 || strlen(signature_hex) != 512 ||
        !hex_to_bytes(signature_hex, signature, sizeof(signature))) return 0;
    exponent_size = exponent_bytes(exponent_value, exponent);
    blob_size = sizeof(BCRYPT_RSAKEY_BLOB) + exponent_size + modulus_size;
    blob = calloc(1, blob_size);
    if (blob == NULL) return 0;
    header = (BCRYPT_RSAKEY_BLOB *)blob;
    header->Magic = BCRYPT_RSAPUBLIC_MAGIC;
    header->BitLength = (ULONG)(modulus_size * 8);
    header->cbPublicExp = (ULONG)exponent_size;
    header->cbModulus = (ULONG)modulus_size;
    memcpy(blob + sizeof(*header), exponent, exponent_size);
    modulus = blob + sizeof(*header) + exponent_size;
    if (!hex_to_bytes(modulus_hex, modulus, modulus_size) ||
        !sha256_hex(task_text, digest_hex) ||
        !hex_to_bytes(digest_hex, digest, sizeof(digest))) goto cleanup;

    status = BCryptOpenAlgorithmProvider(
        &algorithm, BCRYPT_RSA_ALGORITHM, NULL, 0
    );
    if (!BCRYPT_SUCCESS(status)) goto cleanup;
    status = BCryptImportKeyPair(
        algorithm, NULL, BCRYPT_RSAPUBLIC_BLOB, &public_key,
        blob, (ULONG)blob_size, 0
    );
    if (!BCRYPT_SUCCESS(status)) goto cleanup;
    status = BCryptVerifySignature(
        public_key, &padding, digest, sizeof(digest),
        signature, sizeof(signature), BCRYPT_PAD_PKCS1
    );
    verified = BCRYPT_SUCCESS(status);

cleanup:
    if (public_key != NULL) BCryptDestroyKey(public_key);
    if (algorithm != NULL) BCryptCloseAlgorithmProvider(algorithm, 0);
    clear_sensitive(signature, sizeof(signature));
    clear_sensitive(digest, sizeof(digest));
    clear_sensitive(blob, blob_size);
    free(blob);
    return verified;
}
