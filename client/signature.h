#ifndef PROJECT13_SIGNATURE_H
#define PROJECT13_SIGNATURE_H

/* 验证服务端对任务文本的 RSA-2048/SHA-256/PKCS#1 v1.5 签名。 */
int verify_task_signature(const char *task_text, const char *signature_hex);

#endif
