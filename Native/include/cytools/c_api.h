#pragma once
#if defined(_WIN32)
# if defined(CYTOOLS_COMMUNICATION_EXPORTS)
#  define CYTOOLS_API __declspec(dllexport)
# else
#  define CYTOOLS_API __declspec(dllimport)
# endif
#else
# define CYTOOLS_API __attribute__((visibility("default")))
#endif
#ifdef __cplusplus
extern "C" {
#endif
/* UTF-8 JSON. Returned strings remain valid until the next call on this thread.
 * Callback result buffers must remain alive until the next callback on that worker.
 * Destroy the host only after its embedding calls have returned. */
typedef const char* (*cytools_callback)(const char* request, void* user);
CYTOOLS_API const char* cytools_native_info(void);
CYTOOLS_API void* cytools_communication_create(cytools_callback, void*);
CYTOOLS_API const char* cytools_communication_call(void*, const char*);
CYTOOLS_API void cytools_communication_destroy(void*);
CYTOOLS_API const char* cytools_http_call(const char*);
#ifdef __cplusplus
}
#endif
