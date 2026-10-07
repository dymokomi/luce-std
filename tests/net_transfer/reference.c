/* Independent POSIX peers verify every byte across simultaneous TCP streams. */
#define _GNU_SOURCE
#include <assert.h>
#include <errno.h>
#include <netinet/in.h>
#include <netinet/tcp.h>
#include <poll.h>
#include <pthread.h>
#include <stdatomic.h>
#include <stdint.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <unistd.h>

#define CLIENTS 4
#define TRANSFER_BYTES (2u * 1024u * 1024u)
static int listener;
static pthread_t server;
static atomic_uint identities;

static ssize_t receive(int fd, void *data, size_t length) {
    ssize_t count;
    do { count = recv(fd, data, length, 0); } while (count < 0 && errno == EINTR);
    return count;
}

static void *serve_client(void *raw) {
    int fd = (int)(intptr_t)raw;
    unsigned char identity;
    assert(receive(fd, &identity, 1) == 1 && identity < CLIENTS);
    assert(!(atomic_fetch_or(&identities, 1u << identity) & (1u << identity)));
    unsigned char data[4093];
    size_t offset = 0;
    while (offset < TRANSFER_BYTES) {
        ssize_t count = receive(fd, data, sizeof data);
        assert(count > 0 && (size_t)count <= TRANSFER_BYTES - offset);
        for (ssize_t i = 0; i < count; ++i) {
            size_t position = offset + (size_t)i;
            unsigned char expected = (unsigned char)(position * 17 + (position >> 8) + identity * 31);
            assert(data[i] == expected);
            data[i] ^= 0xa5;
        }
        size_t written = 0;
        while (written < (size_t)count) {
            size_t length = (size_t)count - written;
            if (length > 977) length = 977;
            ssize_t sent = send(fd, data + written, length, 0);
            if (sent < 0 && errno == EINTR) continue;
            assert(sent > 0);
            written += (size_t)sent;
        }
        offset += (size_t)count;
    }
    assert(receive(fd, data, 1) == 0);
    assert(close(fd) == 0);
    return NULL;
}

static void *serve(void *unused) {
    (void)unused;
    pthread_t clients[CLIENTS];
    for (unsigned i = 0; i < CLIENTS; ++i) {
        struct pollfd watched = {.fd = listener, .events = POLLIN};
        int ready;
        do { ready = poll(&watched, 1, 45000); } while (ready < 0 && errno == EINTR);
        assert(ready == 1);
        int fd;
        do { fd = accept(listener, NULL, NULL); } while (fd < 0 && errno == EINTR);
        assert(fd >= 0);
        int enabled = 1;
        struct timeval timeout = {.tv_sec = 45};
        assert(setsockopt(fd, IPPROTO_TCP, TCP_NODELAY, &enabled, sizeof enabled) == 0);
        assert(setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof timeout) == 0);
        assert(setsockopt(fd, SOL_SOCKET, SO_SNDTIMEO, &timeout, sizeof timeout) == 0);
        assert(pthread_create(&clients[i], NULL, serve_client, (void *)(intptr_t)fd) == 0);
    }
    for (unsigned i = 0; i < CLIENTS; ++i) assert(pthread_join(clients[i], NULL) == 0);
    assert(close(listener) == 0);
    return NULL;
}

uint16_t transfer_start(int32_t version) {
    assert(version == 4 || version == 6);
    atomic_store(&identities, 0);
    listener = socket(version == 4 ? AF_INET : AF_INET6, SOCK_STREAM, 0);
    assert(listener >= 0);
    uint16_t port;
    if (version == 4) {
        struct sockaddr_in address = {.sin_family = AF_INET, .sin_addr.s_addr = htonl(INADDR_LOOPBACK)};
        assert(bind(listener, (struct sockaddr *)&address, sizeof address) == 0);
        socklen_t length = sizeof address;
        assert(getsockname(listener, (struct sockaddr *)&address, &length) == 0);
        port = ntohs(address.sin_port);
    } else {
        struct sockaddr_in6 address = {.sin6_family = AF_INET6, .sin6_addr = IN6ADDR_LOOPBACK_INIT};
        assert(bind(listener, (struct sockaddr *)&address, sizeof address) == 0);
        socklen_t length = sizeof address;
        assert(getsockname(listener, (struct sockaddr *)&address, &length) == 0);
        port = ntohs(address.sin6_port);
    }
    assert(listen(listener, CLIENTS) == 0);
    assert(pthread_create(&server, NULL, serve, NULL) == 0);
    return port;
}

void transfer_finish(void) {
    assert(pthread_join(server, NULL) == 0);
    assert(atomic_load(&identities) == (1u << CLIENTS) - 1);
}
