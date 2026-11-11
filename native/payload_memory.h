/* Drop unused onefile payload pages after extraction, before starting the UI.
 * Only the launcher changes its own residency. This is not a memory limit.
 */
#ifndef OCREADY_PAYLOAD_MEMORY_H
#define OCREADY_PAYLOAD_MEMORY_H

#include <stdint.h>
#if defined(__linux__)
#include <sys/mman.h>
#include <unistd.h>
#elif defined(_WIN32)
#include <windows.h>
#endif

static void ocready_release_payload_pages(const unsigned char *payload, unsigned long long size) {
#if defined(__linux__)
    long page_value = sysconf(_SC_PAGESIZE);
    if (!payload || page_value <= 0) return;
    uintptr_t page = (uintptr_t)page_value;
    uintptr_t base = (uintptr_t)payload;
    if (size > UINTPTR_MAX - base || base > UINTPTR_MAX - (page - 1)) return;
    /* Round inward: adjacent code/data on boundary pages must stay untouched.
     * Nuitka's linked const blob is file-backed, never anonymous storage.
     */
    uintptr_t start = ((base + page - 1) / page) * page;
    uintptr_t end = ((base + (uintptr_t)size) / page) * page;
    if (end > start) (void)madvise((void *)start, (size_t)(end - start), MADV_DONTNEED);
#elif defined(_WIN32)
    (void)payload;
    (void)size;
    /* Trim this launcher's working set once, after decompression is finished. */
    (void)SetProcessWorkingSetSize(GetCurrentProcess(), (SIZE_T)-1, (SIZE_T)-1);
#else
    (void)payload;
    (void)size;
#endif
}

#endif
