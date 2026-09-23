/* Error numbers come from host headers, independently of Base's ABI constants. */
#define _GNU_SOURCE
#include <assert.h>
#include <dlfcn.h>
#include <errno.h>
#include <fcntl.h>
#include <netdb.h>
#include <stdarg.h>
#include <sys/socket.h>
#include <unistd.h>

struct error_case { int number, category; };
static const struct error_case errors[] = {
    {EAGAIN,1}, {EWOULDBLOCK,1},
    {EBADF,2}, {EPIPE,2}, {ECONNRESET,2}, {ENOTCONN,2}, {ESHUTDOWN,2}, {ENETRESET,2},
    {ETIMEDOUT,3}, {ECANCELED,4}, {ECONNREFUSED,5},
    {ENETDOWN,6}, {ENETUNREACH,6}, {EHOSTDOWN,6}, {EHOSTUNREACH,6},
    {EADDRINUSE,7}, {EADDRNOTAVAIL,8}, {EPERM,9}, {EACCES,9},
    {ENOMEM,10}, {ENFILE,10}, {EMFILE,10}, {ENOBUFS,10}, {ECONNABORTED,11}, {EMSGSIZE,12},
    {EINVAL,13}, {ENOTSOCK,13}, {EDESTADDRREQ,13}, {EPROTOTYPE,13},
    {ENOPROTOOPT,14}, {EPROTONOSUPPORT,14}, {ESOCKTNOSUPPORT,14}, {ENOTSUP,14},
    {EOPNOTSUPP,14}, {EPFNOSUPPORT,14}, {EAFNOSUPPORT,14}, {ENOSYS,14}, {EIO,15}, {999,15}
};
static const struct error_case resolver_errors[] = {
    {EAI_AGAIN,16}, {EAI_MEMORY,10}, {EAI_SYSTEM,9}, {EAI_NONAME,17},
    {EAI_FAMILY,14}, {EAI_SOCKTYPE,14}, {EAI_BADFLAGS,13}, {EAI_SERVICE,13}, {EAI_FAIL,15}
};
static int armed, selected, clobber_descriptor = -1;
int reference_count(void) { return sizeof(errors)/sizeof(errors[0]); }
int reference_category(int index) { assert(index >= 0 && index < reference_count()); return errors[index].category; }
int reference_resolver_count(void) { return sizeof(resolver_errors)/sizeof(resolver_errors[0]); }
int reference_resolver_category(int index) { assert(index >= 0 && index < reference_resolver_count()); return resolver_errors[index].category; }
void reference_arm(int stage, int index) { assert(!armed); armed = stage; selected = index; }
int reference_consumed(void) { return armed == 0; }

ssize_t sendto(int fd, const void *data, size_t length, int flags, const struct sockaddr *address, socklen_t address_length) {
    if (armed == 1) { armed = 0; errno = errors[selected].number; return -1; }
    __typeof__(&sendto) real = (__typeof__(&sendto))dlsym(RTLD_NEXT, "sendto");
    assert(real);
    return real(fd, data, length, flags, address, address_length);
}
int socket(int family, int kind, int protocol) {
    if (armed == 2) { armed = 0; errno = errors[selected].number; return -1; }
    __typeof__(&socket) real = (__typeof__(&socket))dlsym(RTLD_NEXT, "socket");
    assert(real);
    return real(family, kind, protocol);
}
int getaddrinfo(const char *host, const char *service, const struct addrinfo *hints, struct addrinfo **result) {
    if (armed == 3) { armed = 0; *result = NULL; errno = EACCES; return resolver_errors[selected].number; }
    __typeof__(&getaddrinfo) real = (__typeof__(&getaddrinfo))dlsym(RTLD_NEXT, "getaddrinfo");
    assert(real);
    return real(host, service, hints, result);
}
int fcntl(int fd, int command, ...) {
    if (armed == 4 && command == F_GETFD) { armed = 0; clobber_descriptor = fd; errno = EACCES; return -1; }
    __typeof__(&fcntl) real = (__typeof__(&fcntl))dlsym(RTLD_NEXT, "fcntl");
    assert(real);
    if (command == F_GETFD || command == F_GETFL) return real(fd, command);
    assert(command == F_SETFD || command == F_SETFL);
    va_list arguments;
    va_start(arguments, command);
    int value = va_arg(arguments, int);
    va_end(arguments);
    return real(fd, command, value);
}
int close(int fd) {
    __typeof__(&close) real = (__typeof__(&close))dlsym(RTLD_NEXT, "close");
    assert(real);
    int result = real(fd);
    if (fd == clobber_descriptor) { assert(result == 0); errno = EIO; }
    return result;
}
int reference_closed(void) { return clobber_descriptor >= 0 && fcntl(clobber_descriptor,F_GETFD) == -1 && errno == EBADF; }
