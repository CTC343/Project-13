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

    /* 从当前位置向后查找指定字段；调用者需要读取下一字段时应先 rewind。 */
    while (fgets(line, sizeof(line), file) != NULL) {
        if (strncmp(line, name, name_size) == 0 && line[name_size] == '=') {
            snprintf(value, value_size, "%s", line + name_size + 1);
            value[strcspn(value, "\r\n")] = '\0';
            return 1;
        }
    }
    return 0;
}

static int executable_directory(char *directory, int directory_size, char *executable, int executable_size)
{
    char *separator;
    /* 凭据文件按程序所在目录定位，因此不能依赖进程启动时的工作目录。 */
    DWORD length = GetModuleFileNameA(NULL, executable, executable_size);
    if (length == 0 || length >= (DWORD)executable_size) return 0;
    snprintf(directory, directory_size, "%s", executable);
    separator = strrchr(directory, '\\');
    if (separator == NULL) return 0;
    *separator = '\0';
    return 1;
}

int deployment_directory(char *directory, int capacity)
{
    char executable[MAX_PATH];
    return executable_directory(directory, capacity, executable, sizeof(executable));
}

/* 从节点凭据文件读取许可证和长期认证密钥。 */
int load_node_credential(const char *node_id, NodeCredential *credential,
                         char *error_text, int error_size)
{
    char directory[MAX_PATH];
    char executable[MAX_PATH];
    char path[MAX_PATH];
    char header[64];
    FILE *file;

    /* 即使加载失败，输出结构也保持清零，避免调用者误用未初始化数据。 */
    memset(credential, 0, sizeof(*credential));
    if (!executable_directory(directory, sizeof(directory),
                              executable, sizeof(executable))) {
        snprintf(error_text, error_size, "Cannot locate executable directory.");
        return 0;
    }
    snprintf(path, sizeof(path), "%s\\credentials\\%s.cred", directory, node_id);
    file = fopen(path, "r");
    if (file == NULL) {
        snprintf(error_text, error_size, "Credential not found for %s. Start/provision server first.", node_id);
        return 0;
    }

    if (fgets(header, sizeof(header), file) == NULL || strncmp(header, "PROJECT13-CREDENTIAL-V1", 23) != 0) {
        fclose(file);
        snprintf(error_text, error_size, "Credential format is invalid.");
        return 0;
    }

    /* 字段读取会移动文件位置；每次都回到文件头后的正文再查找。 */
    if (!read_value(file, "node_id", credential->node_id, sizeof(credential->node_id))) goto invalid;
    
    rewind(file); 
    fgets(header, sizeof(header), file);
    
    if (!read_value(file, "license_id", credential->license_id, sizeof(credential->license_id))) goto invalid;
    
    rewind(file); 
    fgets(header, sizeof(header), file);
    
    if (!read_value(file, "expires", credential->expires, sizeof(credential->expires))) goto invalid;
    
    fclose(file);

    if (strcmp(node_id, credential->node_id) != 0) {
        snprintf(error_text, error_size, "Credential does not match node.");
        return 0;
    }
    return 1;

invalid:
    fclose(file);
    snprintf(error_text, error_size, "Credential is incomplete.");
    clear_node_credential(credential);
    return 0;
}

/* 取得当前客户端程序的哈希，用于登录时的白名单检查。 */
int current_executable_hash(char output_hex[65],
                            char *error_text, int error_size)
{
    char directory[MAX_PATH];
    char executable[MAX_PATH];

    /* 将实际运行的可执行文件做 SHA-256，供完整性校验使用。 */
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
    /* 凭据包含认证密钥；生命周期结束时清除整个结构。 */
    clear_sensitive(credential, sizeof(*credential));
}
