#include <winsock2.h>
#include <windows.h>
#include <stdio.h>
#include <string.h>

#include "device.h"
#include "network.h"
#include "openssl_api.h"
#include "protocol.h"
#include "security.h"

static int device_directory(char path[MAX_PATH])
{
    DWORD length = GetEnvironmentVariableA("PROJECT13_PROFILE_DIR", path, MAX_PATH);
    if (length == 0) {
        length = GetEnvironmentVariableA("LOCALAPPDATA", path, MAX_PATH);
        if (length == 0 || length >= MAX_PATH - 20) return 0;
        strcat_s(path, MAX_PATH, "\\Project13");
        if (!CreateDirectoryA(path, NULL) && GetLastError() != ERROR_ALREADY_EXISTS) return 0;
        strcat_s(path, MAX_PATH, "\\Devices");
    } else if (length >= MAX_PATH) {
        return 0;
    }
    return CreateDirectoryA(path, NULL) || GetLastError() == ERROR_ALREADY_EXISTS;
}

static int file_replace(const char *name, const void *content, DWORD size)
{
    char temporary[MAX_PATH];
    DWORD written;
    HANDLE stream;
    int success;
    if (snprintf(temporary, sizeof(temporary), "%s.tmp", name) >= (int)sizeof(temporary)) return 0;
    stream = CreateFileA(temporary, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
    if (stream == INVALID_HANDLE_VALUE) return 0;
    success = WriteFile(stream, content, size, &written, NULL) && written == size &&
              FlushFileBuffers(stream);
    if (!CloseHandle(stream)) success = 0;
    if (success) success = MoveFileExA(temporary, name, MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH);
    if (!success) DeleteFileA(temporary);
    return success;
}

static int create_request(const char *key_path, unsigned char csr[2600])
{
    EVP_PKEY *key = EVP_PKEY_Q_keygen(NULL, NULL, "RSA", (size_t)2048);
    X509_REQ *request = X509_REQ_new();
    BIO *private_file = NULL, *encoded = BIO_new(BIO_s_mem());
    int count = -1;
    if (!key || !request || !encoded ||
        !X509_REQ_set_version(request, 0) ||
        !X509_NAME_add_entry_by_txt(X509_REQ_get_subject_name(request), "CN", 0x1001,
            (const unsigned char *)"Project13 client", -1, -1, 0) ||
        !X509_REQ_set_pubkey(request, key) || X509_REQ_sign(request, key, EVP_sha256()) <= 0 ||
        !PEM_write_bio_X509_REQ(encoded, request)) goto done;
    private_file = BIO_new_file(key_path, "wb");
    if (!private_file || !PEM_write_bio_PrivateKey(private_file, key, NULL, NULL, 0, NULL, NULL)) goto done;
    count = BIO_read(encoded, csr, 2600);
done:
    BIO_free(private_file);
    BIO_free(encoded);
    X509_REQ_free(request);
    EVP_PKEY_free(key);
    return count;
}

static int enroll(ClientLogin *login, const char *exe_hash, const char *metadata,
                  char *error, int error_size)
{
    NetworkConnection connection = {INVALID_SOCKET};
    char message[PROTOCOL_BODY_SIZE], response[PROTOCOL_BODY_SIZE], type[32];
    char password_hex[513], csr_hex[5201], pem_hex[6501];
    char temporary_key[MAX_PATH], private_key[MAX_PATH], certificate[MAX_PATH], storage[MAX_PATH];
    unsigned char csr[2600], pem[3251], secret[32];
    FILE *saved;
    int csr_size, cert_size, status, result;
    snprintf(private_key, sizeof(private_key), "%s.key", login->profile);
    snprintf(temporary_key, sizeof(temporary_key), "%s.key.tmp", login->profile);
    snprintf(certificate, sizeof(certificate), "%s.pem", login->profile);
    snprintf(storage, sizeof(storage), "%s.storage", login->profile);
    result = network_connect(&connection, login->host, login->port + 1, NULL, error, error_size);
    if (result != 1) goto done;
    result = -1;
    csr_size = create_request(temporary_key, csr);
    if (csr_size <= 0) {
        snprintf(error, error_size, "Cannot generate the device key.");
        goto done;
    }
    bytes_to_hex(csr, csr_size, csr_hex);
    bytes_to_hex((const unsigned char *)login->password, (int)strlen(login->password), password_hex);
    snprintf(message, sizeof(message),
        "{\"username\":\"%s\",\"password_hex\":\"%s\",\"exe_hash\":\"%s\",\"csr_hex\":\"%s\"}",
        login->username, password_hex, exe_hash, csr_hex);
    if (!protocol_send_frame(&connection, "ENROLL", 0, message, error, error_size) ||
        !protocol_receive_frame(&connection, type, sizeof(type), &status, response, sizeof(response),
                                error, error_size)) {
        result = connection.security_error ? -1 : 0;
        goto done;
    }
    if (status == 503) {
        snprintf(error, error_size, "Enrollment temporarily unavailable.");
        result = 0;
        goto done;
    }
    if (strcmp(type, "ENROLLED") != 0 || status != 200 ||
        !json_get_string(response, "node_id", login->node_id, sizeof(login->node_id)) ||
        !json_get_string(response, "license_id", login->license_id, sizeof(login->license_id)) ||
        !json_get_string(response, "token", login->session_token, sizeof(login->session_token)) ||
        !json_get_string(response, "cert_hex", pem_hex, sizeof(pem_hex))) {
        snprintf(error, error_size, "Enrollment rejected. Check your account or try again later.");
        goto done;
    }
    cert_size = (int)strlen(pem_hex) / 2;
    if (cert_size < 128 || !hex_to_bytes(pem_hex, pem, cert_size) ||
        !file_replace(certificate, pem, cert_size) ||
        !MoveFileExA(temporary_key, private_key, MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH)) {
        snprintf(error, error_size, "Cannot install the device certificate.");
        goto done;
    }
    saved = fopen(storage, "rb");
    if (saved) {
        fclose(saved);
    } else if (!secure_random(secret, sizeof(secret)) || !file_replace(storage, secret, sizeof(secret))) {
        snprintf(error, error_size, "Cannot store the local result encryption key.");
        goto done;
    }
    snprintf(message, sizeof(message), "%s\n%s\n", login->node_id, login->license_id);
    if (!file_replace(metadata, message, (DWORD)strlen(message))) {
        snprintf(error, error_size, "Cannot save the new device identity.");
        goto done;
    }
    clear_sensitive(login->password, sizeof(login->password));
    result = 1;
done:
    if (result != 1) {
        DeleteFileA(temporary_key);
        clear_sensitive(login->session_token, sizeof(login->session_token));
    }
    clear_sensitive(secret, sizeof(secret));
    clear_sensitive(password_hex, sizeof(password_hex));
    clear_sensitive(message, sizeof(message));
    clear_sensitive(response, sizeof(response));
    network_close(&connection);
    return result;
}

int device_prepare(ClientLogin *login, const char *exe_hash, char *error, int error_size)
{
    char directory[MAX_PATH], identity[512], digest[65], metadata[MAX_PATH], mutex_name[100];
    HANDLE mutex;
    DWORD wait;
    FILE *record;
    int result;
    snprintf(error, error_size, "Cannot open the local device profile.");
    if (!device_directory(directory) || strlen(directory) > MAX_PATH - 80) return -1;
    snprintf(identity, sizeof(identity), "%s|%d|%s", login->host, login->port, login->username);
    if (!sha256_hex(identity, digest)) return -1;
    snprintf(login->profile, sizeof(login->profile), "%s\\%s", directory, digest);
    snprintf(metadata, sizeof(metadata), "%s.identity", login->profile);
    snprintf(mutex_name, sizeof(mutex_name), "Local\\Project13-Device-%s", digest);
    mutex = CreateMutexA(NULL, FALSE, mutex_name);
    if (!mutex) return -1;
    wait = WaitForSingleObject(mutex, 15000);
    if (wait != WAIT_OBJECT_0 && wait != WAIT_ABANDONED) {
        CloseHandle(mutex);
        return 0;
    }
    record = fopen(metadata, "r");
    if (record) {
        result = fgets(login->node_id, sizeof(login->node_id), record) != NULL &&
                 fgets(login->license_id, sizeof(login->license_id), record) != NULL ? 1 : -1;
        login->node_id[strcspn(login->node_id, "\r\n")] = '\0';
        login->license_id[strcspn(login->license_id, "\r\n")] = '\0';
        fclose(record);
    } else {
        result = enroll(login, exe_hash, metadata, error, error_size);
    }
    ReleaseMutex(mutex);
    CloseHandle(mutex);
    return result;
}
