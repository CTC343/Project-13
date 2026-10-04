/* 凭据文件同时承担许可证绑定；服务端保存独立副本进行校验。 */
#include <windows.h>
#include <stdio.h>
#include <string.h>

#include "credentials.h"
#include "security.h"

static int read_value(FILE *file, const char *name, char *value, int value_size)
{
    char line[256];
    int name_size = (int)strlen(name);
    while (fgets(line, sizeof(line), file) != NULL) {
        if (strncmp(line, name, name_size) == 0 && line[name_size] == '=') {
            snprintf(value, value_size, "%s", line + name_size + 1);
            value[strcspn(value, "\r\n")] = '\0';
            return 1;
        }
    }
    return 0;
}

static int executable_directory(char *directory, int directory_size,
                                char *executable, int executable_size)
{
    char *separator;
    DWORD length = GetModuleFileNameA(NULL, executable, executable_size);
    if (length == 0 || length >= (DWORD)executable_size) return 0;
    snprintf(directory, directory_size, "%s", executable);
    separator = strrchr(directory, '\\');
    if (separator == NULL) return 0;
    *separator = '\0';
    return 1;
}

int load_node_credential(const char *node_id, NodeCredential *credential,
                         char *error_text, int error_size)
{
    char directory[MAX_PATH];
    char executable[MAX_PATH];
    char path[MAX_PATH];
    char key_hex[65];
    char header[64];
    FILE *file;

    memset(credential, 0, sizeof(*credential));
    if (!executable_directory(directory, sizeof(directory),
                              executable, sizeof(executable))) {
        snprintf(error_text, error_size, "Cannot locate executable directory.");
        return 0;
    }
    snprintf(path, sizeof(path), "%s\\credentials\\%s.cred", directory, node_id);
    file = fopen(path, "r");
    if (file == NULL) {
        snprintf(error_text, error_size,
                 "Credential not found for %s. Start/provision server first.", node_id);
        return 0;
    }
    if (fgets(header, sizeof(header), file) == NULL ||
        strncmp(header, "PROJECT13-CREDENTIAL-V1", 23) != 0) {
        fclose(file);
        snprintf(error_text, error_size, "Credential format is invalid.");
        return 0;
    }
    if (!read_value(file, "node_id", credential->node_id,
                    sizeof(credential->node_id))) goto invalid;
    rewind(file); fgets(header, sizeof(header), file);
    if (!read_value(file, "license_id", credential->license_id,
                    sizeof(credential->license_id))) goto invalid;
    rewind(file); fgets(header, sizeof(header), file);
    if (!read_value(file, "expires", credential->expires,
                    sizeof(credential->expires))) goto invalid;
    rewind(file); fgets(header, sizeof(header), file);
    if (!read_value(file, "auth_key", key_hex, sizeof(key_hex))) goto invalid;
    fclose(file);

    if (strcmp(node_id, credential->node_id) != 0 ||
        !hex_to_bytes(key_hex, credential->auth_key, 32)) {
        snprintf(error_text, error_size, "Credential does not match node.");
        clear_sensitive(key_hex, sizeof(key_hex));
        return 0;
    }
    clear_sensitive(key_hex, sizeof(key_hex));
    return 1;

invalid:
    fclose(file);
    snprintf(error_text, error_size, "Credential is incomplete.");
    clear_node_credential(credential);
    return 0;
}

int current_executable_hash(char output_hex[65],
                            char *error_text, int error_size)
{
    char directory[MAX_PATH];
    char executable[MAX_PATH];
    if (!executable_directory(directory, sizeof(directory),
                              executable, sizeof(executable)) ||
        !sha256_file_hex(executable, output_hex)) {
        snprintf(error_text, error_size, "Executable integrity hash failed.");
        return 0;
    }
    return 1;
}

void clear_node_credential(NodeCredential *credential)
{
    clear_sensitive(credential, sizeof(*credential));
}
