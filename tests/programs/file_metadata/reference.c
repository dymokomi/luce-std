/* Independent host-header decoding of stat, plus deterministic interrupted calls. */
#define _GNU_SOURCE
#include <assert.h>
#include <dlfcn.h>
#include <errno.h>
#include <stdint.h>
#include <sys/stat.h>
#include <unistd.h>

static int armed, hits;
void metadata_fault_arm(int kind) { assert(!armed); armed = kind; hits = 0; }
int metadata_fault_hits(void) { return hits; }
static int take(int kind, int number) {
    if (armed != kind) return 0;
    armed = 0; ++hits; errno = number; return 1;
}
#define REAL(name) __typeof__(&name) real = (__typeof__(&name))dlsym(RTLD_NEXT, #name); assert(real)
int stat(const char *path, struct stat *result) {
    REAL(stat);
    if (take(2, EINTR) || take(5, EACCES)) return -1;
    return real(path, result);
}
int lstat(const char *path, struct stat *result) {
    REAL(lstat);
    if (take(3, EINTR) || take(6, EIO)) return -1;
    return real(path, result);
}
int fstat(int descriptor, struct stat *result) {
    REAL(fstat);
    if (take(1, EINTR) || take(4, EIO)) return -1;
    return real(descriptor, result);
}
int fchmod(int descriptor, mode_t mode) {
    REAL(fchmod);
    if (take(7, EINTR) || take(10, EACCES)) return -1;
    return real(descriptor, mode);
}
int ftruncate(int descriptor, off_t length) {
    REAL(ftruncate);
    if (take(8, EINTR) || take(11, ENOSPC)) return -1;
    return real(descriptor, length);
}
int futimens(int descriptor, const struct timespec times[2]) {
    REAL(futimens);
    if (take(9, EINTR) || take(12, EIO)) return -1;
    return real(descriptor, times);
}
void metadata_prepare(int descriptor) {
    struct timespec times[2] = {{-12345, 123456789}, {1234567890, 987654321}};
    assert(fchmod(descriptor, 0640) == 0);
    assert(futimens(descriptor, times) == 0);
}
void metadata_reference(int descriptor, const char *path, int follow, uint64_t *out) {
    struct stat value;
    int result = descriptor >= 0 ? fstat(descriptor, &value)
                 : follow ? stat(path, &value) : lstat(path, &value);
    assert(result == 0);
    out[0] = (uint64_t)value.st_size;
#ifdef __APPLE__
    out[1] = (uint32_t)value.st_dev;
    out[8] = (uint64_t)value.st_atimespec.tv_sec;
    out[9] = (uint64_t)value.st_atimespec.tv_nsec;
    out[10] = (uint64_t)value.st_mtimespec.tv_sec;
    out[11] = (uint64_t)value.st_mtimespec.tv_nsec;
    out[12] = (uint64_t)value.st_ctimespec.tv_sec;
    out[13] = (uint64_t)value.st_ctimespec.tv_nsec;
    out[14] = (uint64_t)value.st_birthtimespec.tv_sec;
    out[15] = (uint64_t)value.st_birthtimespec.tv_nsec;
    out[16] = 1;
#else
    out[1] = value.st_dev;
    out[8] = (uint64_t)value.st_atim.tv_sec;
    out[9] = (uint64_t)value.st_atim.tv_nsec;
    out[10] = (uint64_t)value.st_mtim.tv_sec;
    out[11] = (uint64_t)value.st_mtim.tv_nsec;
    out[12] = (uint64_t)value.st_ctim.tv_sec;
    out[13] = (uint64_t)value.st_ctim.tv_nsec;
    out[14] = out[15] = out[16] = 0;
#endif
    out[2] = value.st_ino;
    out[3] = value.st_nlink;
    out[4] = value.st_mode & 07777;
    out[5] = value.st_uid;
    out[6] = value.st_gid;
    out[7] = (uint64_t)value.st_blocks;
}
