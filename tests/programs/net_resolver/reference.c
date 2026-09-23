/* A deterministic mixed resolver chain. Poisoning it on release proves that
 * public results own their address bytes rather than borrowing libc storage. */
#define _GNU_SOURCE
#include <arpa/inet.h>
#include <assert.h>
#include <netdb.h>
#include <string.h>

static struct addrinfo entries[8];
static struct sockaddr_in ipv4;
static struct sockaddr_in6 ipv6;
static int active;
static int released;

int getaddrinfo(const char *host, const char *service, const struct addrinfo *hints,
                struct addrinfo **result) {
    assert(!active && !service && (strcmp(host, "mixed.invalid") == 0 || strcmp(host, "empty.invalid") == 0));
    assert(hints && hints->ai_socktype == SOCK_STREAM);
    assert(hints->ai_family == AF_UNSPEC || hints->ai_family == AF_INET || hints->ai_family == AF_INET6);
    active = 1;
    memset(entries, 0, sizeof(entries));
    memset(&ipv4, 0, sizeof(ipv4));
    memset(&ipv6, 0, sizeof(ipv6));
#ifdef __APPLE__
    ipv4.sin_len = sizeof(ipv4);
    ipv6.sin6_len = sizeof(ipv6);
#endif
    ipv4.sin_family = AF_INET;
    ipv4.sin_port = htons(999);
    assert(inet_pton(AF_INET, "127.0.0.42", &ipv4.sin_addr) == 1);
    ipv6.sin6_family = AF_INET6;
    ipv6.sin6_port = htons(888);
    ipv6.sin6_scope_id = 17;
    assert(inet_pton(AF_INET6, "2001:db8::1", &ipv6.sin6_addr) == 1);
    for (int index = 0; index < 8; ++index) {
        entries[index].ai_family = AF_INET6;
        entries[index].ai_socktype = SOCK_STREAM;
        entries[index].ai_addrlen = sizeof(ipv6);
        entries[index].ai_addr = (struct sockaddr *)&ipv6;
        entries[index].ai_next = index == 7 ? NULL : &entries[index + 1];
    }
    entries[0].ai_family = AF_UNSPEC;
    entries[1].ai_addrlen = 1;
    entries[3].ai_family = AF_INET;
    entries[3].ai_addrlen = sizeof(ipv4);
    entries[3].ai_addr = (struct sockaddr *)&ipv4;
    entries[5].ai_family = AF_INET; /* Deliberately contradict the address bytes. */
    entries[6].ai_socktype = SOCK_DGRAM;
    entries[7].ai_addr = NULL;
    if (strcmp(host, "empty.invalid") == 0) {
        for (int index = 0; index < 8; ++index) entries[index].ai_addr = NULL;
    }
    *result = entries;
    return 0;
}

void freeaddrinfo(struct addrinfo *head) {
    assert(active && head == entries);
    active = 0;
    ++released;
    memset(entries, 0xa5, sizeof(entries));
    memset(&ipv4, 0xa5, sizeof(ipv4));
    memset(&ipv6, 0xa5, sizeof(ipv6));
}

int reference_released(void) { assert(!active); return released; }
