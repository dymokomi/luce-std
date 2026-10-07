/* Atomic replacement must expose one complete generation to every open handle. */
#define _GNU_SOURCE
#include <assert.h>
#include <errno.h>
#include <fcntl.h>
#include <pthread.h>
#include <sched.h>
#include <stdatomic.h>
#include <stdint.h>
#include <sys/stat.h>
#include <unistd.h>

#ifdef _WIN32
#include <io.h>
#include <windows.h>
/* A reader shares deletion, as luce-std's own File.open does: Windows refuses to replace
 * a file that a handle without FILE_SHARE_DELETE holds open. Binary mode keeps the C
 * runtime from translating line ends. */
static int open_reader(const char *path) {
    HANDLE handle = CreateFileA(path, GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
                                NULL, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
    if (handle == INVALID_HANDLE_VALUE) { errno = EACCES; return -1; }
    return _open_osfhandle((intptr_t)handle, _O_RDONLY | _O_BINARY);
}
#else
static int open_reader(const char *path) { return open(path, O_RDONLY); }
#endif

#define READERS 3
#define CAPACITY 65536
static const char *publication_path;
static pthread_t readers[READERS];
static atomic_uint ready, snapshots;
static atomic_int stopped;

void publication_verify(const unsigned char *data, size_t length) {
    assert(length >= 2);
    unsigned identity = data[0], generation = data[1];
    assert(identity <= 4 && generation <= 64);
    assert(length == 4096 + (generation * 7919) % 61441);
    for (size_t i = 2; i < length; ++i) {
        unsigned char expected = (unsigned char)(identity * 31 + generation * 17 + i * 13 + (i >> 8));
        assert(data[i] == expected);
    }
}

static void snapshot(void) {
    int fd;
    do { fd = open_reader(publication_path); } while (fd < 0 && errno == EINTR);
    assert(fd >= 0);
    struct stat metadata;
    assert(fstat(fd, &metadata) == 0);
    unsigned char data[CAPACITY + 1];
    size_t used = 0;
    for (;;) {
        assert(used < sizeof data);
        ssize_t count = read(fd, data + used, sizeof data - used);
        if (count < 0 && errno == EINTR) continue;
        assert(count >= 0);
        if (!count) break;
        used += (size_t)count;
    }
    assert(close(fd) == 0);
    assert(metadata.st_size >= 0 && (uint64_t)metadata.st_size == used);
    publication_verify(data, used);
    atomic_fetch_add(&snapshots, 1);
}

static void *reader(void *unused) {
    (void)unused;
    snapshot();
    atomic_fetch_add(&ready, 1);
    while (!atomic_load(&stopped)) snapshot();
    return NULL;
}

void publication_start(const char *path) {
    publication_path = path;
    atomic_store(&ready, 0);
    atomic_store(&snapshots, 0);
    atomic_store(&stopped, 0);
    for (unsigned i = 0; i < READERS; ++i) assert(pthread_create(&readers[i], NULL, reader, NULL) == 0);
    while (atomic_load(&ready) != READERS) sched_yield();
}

uint32_t publication_finish(void) {
    atomic_store(&stopped, 1);
    for (unsigned i = 0; i < READERS; ++i) assert(pthread_join(readers[i], NULL) == 0);
    return atomic_load(&snapshots);
}
