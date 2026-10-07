/* Compare Base's socket layouts with the host headers, independently of its ABI declarations. */
#define _GNU_SOURCE
#include <arpa/inet.h>
#include <dlfcn.h>
#include <errno.h>
#include <fcntl.h>
#include <netdb.h>
#include <assert.h>
#include <stdint.h>
#include <string.h>
#include <sys/socket.h>

int reference_endpoint(int fd, int peer, uint8_t *bytes, uint16_t *port, uint32_t *scope) {
    struct sockaddr_storage storage;
    socklen_t length = sizeof(storage);
    int result = peer ? getpeername(fd, (struct sockaddr *)&storage, &length)
                      : getsockname(fd, (struct sockaddr *)&storage, &length);
    assert(result == 0);
    if (storage.ss_family == AF_INET) {
        const struct sockaddr_in *address = (const struct sockaddr_in *)&storage;
        assert(length == sizeof(*address));
        memcpy(bytes, &address->sin_addr, 4);
        *port = ntohs(address->sin_port);
        *scope = 0;
        return 4;
    }
    assert(storage.ss_family == AF_INET6);
    const struct sockaddr_in6 *address = (const struct sockaddr_in6 *)&storage;
    assert(length == sizeof(*address));
    memcpy(bytes, &address->sin6_addr, 16);
    *port = ntohs(address->sin6_port);
    *scope = address->sin6_scope_id;
    return 6;
}

int reference_ipv6_only(int fd) {
    int value = -1;
    socklen_t length = sizeof(value);
    assert(getsockopt(fd, IPPROTO_IPV6, IPV6_V6ONLY, &value, &length) == 0);
    assert(length == sizeof(value));
    return value;
}

/* Nonzero scope IDs need no real interface: inspect the outgoing ABI before
 * rejecting the bind, and supply a resolver record using the host's layout. */
static int scoped_descriptor = -1;
static int scoped_released;
static struct sockaddr_in6 scoped_address;
static struct addrinfo scoped_info;

int bind(int fd, const struct sockaddr *address, socklen_t length) {
    if (address->sa_family == AF_INET6 &&
        ((const struct sockaddr_in6 *)address)->sin6_scope_id == 0x01020304) {
        const struct sockaddr_in6 *ip = (const struct sockaddr_in6 *)address;
        assert(length == sizeof(*ip));
#ifdef __APPLE__
        assert(ip->sin6_len == sizeof(*ip));
#endif
        struct in6_addr expected;
        assert(inet_pton(AF_INET6, "fe80::1234", &expected) == 1);
        assert(memcmp(&ip->sin6_addr, &expected, sizeof(expected)) == 0);
        assert(ntohs(ip->sin6_port) == 0x1234 && ip->sin6_flowinfo == 0);
        scoped_descriptor = fd;
        errno = EINVAL;
        return -1;
    }
    __typeof__(&bind) real = (__typeof__(&bind))dlsym(RTLD_NEXT, "bind");
    assert(real);
    return real(fd, address, length);
}

int reference_scope_closed(void) {
    return scoped_descriptor >= 0 && fcntl(scoped_descriptor, F_GETFD) == -1 && errno == EBADF;
}

int getaddrinfo(const char *host, const char *service, const struct addrinfo *hints,
                struct addrinfo **result) {
    if (strcmp(host, "scoped.invalid") == 0) {
        assert(!service && hints && hints->ai_family == AF_INET6 && hints->ai_socktype == SOCK_STREAM);
        memset(&scoped_address, 0, sizeof(scoped_address));
        memset(&scoped_info, 0, sizeof(scoped_info));
#ifdef __APPLE__
        scoped_address.sin6_len = sizeof(scoped_address);
#endif
        scoped_address.sin6_family = AF_INET6;
        scoped_address.sin6_port = htons(999);
        scoped_address.sin6_scope_id = 0x01020304;
        assert(inet_pton(AF_INET6, "fe80::1234", &scoped_address.sin6_addr) == 1);
        scoped_info.ai_family = AF_INET6;
        scoped_info.ai_socktype = SOCK_STREAM;
        scoped_info.ai_addrlen = sizeof(scoped_address);
        scoped_info.ai_addr = (struct sockaddr *)&scoped_address;
        *result = &scoped_info;
        return 0;
    }
    __typeof__(&getaddrinfo) real = (__typeof__(&getaddrinfo))dlsym(RTLD_NEXT, "getaddrinfo");
    assert(real);
    return real(host, service, hints, result);
}

void freeaddrinfo(struct addrinfo *info) {
    if (info == &scoped_info) {
        assert(!scoped_released);
        scoped_released = 1;
        return;
    }
    __typeof__(&freeaddrinfo) real = (__typeof__(&freeaddrinfo))dlsym(RTLD_NEXT, "freeaddrinfo");
    assert(real);
    real(info);
}

int reference_scope_released(void) { return scoped_released; }
