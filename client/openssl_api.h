#ifndef PROJECT13_OPENSSL_API_H
#define PROJECT13_OPENSSL_API_H

/* Public OpenSSL 3 ABI used by the x64 client. Import libraries are generated
 * at build time for the matching DLLs supplied by the x64 Python runtime. */
typedef struct ssl_method_st SSL_METHOD;
typedef struct X509_VERIFY_PARAM_st X509_VERIFY_PARAM;
typedef struct evp_pkey_st EVP_PKEY;
typedef struct evp_md_st EVP_MD;
typedef struct bio_st BIO;
typedef struct bio_method_st BIO_METHOD;
typedef struct X509_req_st X509_REQ;
typedef struct X509_name_st OPENSSL_X509_NAME;
typedef struct x509_store_ctx_st X509_STORE_CTX;

#define SSL_VERIFY_PEER 1
#define SSL_FILETYPE_PEM 1
#define SSL_CTRL_SET_MIN_PROTO_VERSION 123
#define SSL_CTRL_SET_MAX_PROTO_VERSION 124
#define SSL_CTRL_SET_TLSEXT_HOSTNAME 55
#define TLS1_3_VERSION 0x0304
#define SSL_ERROR_SSL 1
#define SSL_ERROR_WANT_READ 2
#define SSL_ERROR_WANT_WRITE 3
#define SSL_ERROR_SYSCALL 5
#define SSL_ERROR_ZERO_RETURN 6
#define SSL_R_UNEXPECTED_EOF_WHILE_READING 294
#define ERR_LIB_SSL 20
#define ERR_LIB_OFFSET 23
#define ERR_LIB_MASK 0xff
#define ERR_REASON_MASK 0x7fffff
#define X509_V_FLAG_CRL_CHECK 0x4
#define X509_V_FLAG_CRL_CHECK_ALL 0x8
#define X509_CHECK_FLAG_NEVER_CHECK_SUBJECT 0x20

const SSL_METHOD *TLS_client_method(void);
SSL_CTX *SSL_CTX_new(const SSL_METHOD *method);
void SSL_CTX_free(SSL_CTX *context);
long SSL_CTX_ctrl(SSL_CTX *context, int command, long value, void *argument);
int SSL_CTX_set_ciphersuites(SSL_CTX *context, const char *suites);
void SSL_CTX_set_verify(SSL_CTX *context, int mode, int (*callback)(int, X509_STORE_CTX *));
int SSL_CTX_load_verify_locations(SSL_CTX *context, const char *file, const char *directory);
int SSL_CTX_use_certificate_chain_file(SSL_CTX *context, const char *file);
int SSL_CTX_use_PrivateKey_file(SSL_CTX *context, const char *file, int type);
int SSL_CTX_check_private_key(const SSL_CTX *context);
SSL *SSL_new(SSL_CTX *context);
void SSL_free(SSL *session);
long SSL_ctrl(SSL *session, int command, long value, void *argument);
int SSL_set_fd(SSL *session, int fd);
X509_VERIFY_PARAM *SSL_get0_param(SSL *session);
int SSL_set1_host(SSL *session, const char *host);
int SSL_connect(SSL *session);
int SSL_get_error(const SSL *session, int result);
long SSL_get_verify_result(const SSL *session);
int SSL_read(SSL *session, void *buffer, int count);
int SSL_write(SSL *session, const void *buffer, int count);
int SSL_shutdown(SSL *session);
void ERR_clear_error(void);
unsigned long ERR_peek_last_error(void);
int X509_VERIFY_PARAM_set_flags(X509_VERIFY_PARAM *parameter, unsigned long flags);
void X509_VERIFY_PARAM_set_hostflags(X509_VERIFY_PARAM *parameter, unsigned int flags);
int X509_VERIFY_PARAM_set1_ip_asc(X509_VERIFY_PARAM *parameter, const char *ip);
EVP_PKEY *EVP_PKEY_Q_keygen(void *context, const char *properties, const char *type, ...);
void EVP_PKEY_free(EVP_PKEY *key);
const EVP_MD *EVP_sha256(void);
BIO *BIO_new(const BIO_METHOD *method);
const BIO_METHOD *BIO_s_mem(void);
int BIO_free(BIO *bio);
int BIO_read(BIO *bio, void *output, int size);
BIO *BIO_new_file(const char *path, const char *mode);
int PEM_write_bio_PrivateKey(BIO *bio, const EVP_PKEY *key, const void *cipher,
                             const unsigned char *pass, int length, void *callback, void *argument);
int PEM_write_bio_X509_REQ(BIO *bio, const X509_REQ *request);
X509_REQ *X509_REQ_new(void);
void X509_REQ_free(X509_REQ *request);
int X509_REQ_set_version(X509_REQ *request, long version);
OPENSSL_X509_NAME *X509_REQ_get_subject_name(const X509_REQ *request);
int X509_NAME_add_entry_by_txt(OPENSSL_X509_NAME *name, const char *field, int type,
                               const unsigned char *text, int length, int location, int set);
int X509_REQ_set_pubkey(X509_REQ *request, EVP_PKEY *key);
int X509_REQ_sign(X509_REQ *request, EVP_PKEY *key, const EVP_MD *algorithm);

#endif
