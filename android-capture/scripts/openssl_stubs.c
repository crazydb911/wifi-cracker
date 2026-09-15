#include <openssl/evp.h>
#include <openssl/core.h>
/* Dummy bodies: hcxpcapngtool uses these only for candidate-checking,
   which is not run in extract mode. Signatures match the openssl 3.0 headers. */
int OPENSSL_init_crypto(uint64_t opts, const OPENSSL_INIT_SETTINGS *s){ (void)opts;(void)s; return 1; }
int OPENSSL_init_ssl(uint64_t opts, const OPENSSL_INIT_SETTINGS *s){ (void)opts;(void)s; return 1; }
const EVP_MD *EVP_sha1(void){ return NULL; }
int EVP_DigestInit_ex(EVP_MD_CTX *ctx, const EVP_MD *type, ENGINE *impl){ (void)ctx;(void)type;(void)impl; return 1; }
int EVP_DigestInit(EVP_MD_CTX *ctx, const EVP_MD *type){ (void)ctx;(void)type; return 1; }
int EVP_DigestUpdate(EVP_MD_CTX *ctx, const void *data, size_t cnt){ (void)ctx;(void)data;(void)cnt; return 1; }
int EVP_DigestFinal_ex(EVP_MD_CTX *ctx, unsigned char *md, unsigned int *size){ (void)ctx;(void)md;(void)size; return 1; }
EVP_MD_CTX *EVP_MD_CTX_new(void){ return (EVP_MD_CTX*)0x1; }
void EVP_MD_CTX_free(EVP_MD_CTX *ctx){ (void)ctx; }
int EVP_MD_CTX_reset(EVP_MD_CTX *ctx){ (void)ctx; return 1; }
int PKCS5_PBKDF2_HMAC_SHA1(const char *pass, int passlen, const unsigned char *salt, int saltlen, int iter, int outlen, unsigned char *out){
  (void)pass;(void)passlen;(void)salt;(void)saltlen;(void)iter;(void)outlen;(void)out; return 1; }
EVP_MAC *EVP_MAC_fetch(OSSL_LIB_CTX *libctx, const char *algorithm, const char *properties){ (void)libctx;(void)algorithm;(void)properties; return (EVP_MAC*)0x1; }
void EVP_MAC_free(EVP_MAC *mac){ (void)mac; }
EVP_MAC_CTX *EVP_MAC_CTX_new(EVP_MAC *mac){ (void)mac; return (EVP_MAC_CTX*)0x1; }
void EVP_MAC_CTX_free(EVP_MAC_CTX *ctx){ (void)ctx; }
int EVP_MAC_init(EVP_MAC_CTX *ctx, const unsigned char *key, size_t keylen, const OSSL_PARAM params[]){ (void)ctx;(void)key;(void)keylen;(void)params; return 1; }
int EVP_MAC_update(EVP_MAC_CTX *ctx, const unsigned char *data, size_t datalen){ (void)ctx;(void)data;(void)datalen; return 1; }
int EVP_MAC_final(EVP_MAC_CTX *ctx, unsigned char *out, size_t *outl, size_t outsize){ (void)ctx;(void)out;(void)outl;(void)outsize; return 1; }
#include <openssl/params.h>
#include <string.h>
OSSL_PARAM OSSL_PARAM_construct_utf8_string(const char *key, char *buf, size_t bsize){ (void)key;(void)buf;(void)bsize; OSSL_PARAM p; memset(&p,0,sizeof p); return p; }
OSSL_PARAM OSSL_PARAM_construct_end(void){ OSSL_PARAM p; memset(&p,0,sizeof p); return p; }
unsigned long OpenSSL_version_num(void){ return 0x30000000L; }
