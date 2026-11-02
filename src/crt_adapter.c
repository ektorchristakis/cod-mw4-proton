#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>

typedef struct crt_file crt_file;
typedef int (__cdecl *freopen_s_fn)(crt_file **, const char *, const char *, crt_file *);
typedef crt_file *(__cdecl *iob_fn)(unsigned int);
typedef HMODULE (WINAPI *get_module_handle_fn)(LPCWSTR);
typedef FARPROC (WINAPI *get_proc_address_fn)(HMODULE, LPCSTR);

/* The PE patcher fills these host-relative addresses before installation.
 * No pointer initializers: this image is copied into another DLL without
 * applying base relocations. self_rva identifies this state, not the function.
 */
__declspec(dllexport) struct {
    uint32_t self_rva;
    uint32_t original_freopen_s_rva;
    uint32_t get_module_handle_iat_rva;
    uint32_t get_proc_address_iat_rva;
} adapter_state __attribute__((section(".data"))) = {0};

__declspec(dllexport)
int __cdecl crt_freopen_s(crt_file **output, const char *path,
                         const char *mode, crt_file *stream)
{
    unsigned char *host = (unsigned char *)&adapter_state - adapter_state.self_rva;
    freopen_s_fn original = (freopen_s_fn)(host + adapter_state.original_freopen_s_rva);
    get_module_handle_fn get_module_handle =
        *(get_module_handle_fn *)(host + adapter_state.get_module_handle_iat_rva);
    get_proc_address_fn get_proc_address =
        *(get_proc_address_fn *)(host + adapter_state.get_proc_address_iat_rva);
    HMODULE owner;
    iob_fn owner_iob;
    freopen_s_fn owner_reopen;
    unsigned int i;

    /* Leave invalid parameters and all unrecognized FILE objects to msvcrt. */
    if (!output || !path || !mode || !stream)
        return original(output, path, mode, stream);

    owner = get_module_handle(L"ucrtbase.dll");
    if (!owner || owner == (HMODULE)host)
        return original(output, path, mode, stream);

    owner_iob = (iob_fn)(uintptr_t)get_proc_address(owner, "__acrt_iob_func");
    owner_reopen = (freopen_s_fn)(uintptr_t)get_proc_address(owner, "freopen_s");
    if (!owner_iob || !owner_reopen)
        return original(output, path, mode, stream);

    for (i = 0; i < 3; ++i) {
        if (stream == owner_iob(i)) {
            crt_file *opened = NULL;
            int result = owner_reopen(&opened, path, mode, stream);

            /* Some callers pass the FILE itself as the FILE** output slot.
             * Writing there would corrupt the stream that was just reopened.
             */
            if ((void *)output != (void *)stream)
                *output = opened;
            return result;
        }
    }

    return original(output, path, mode, stream);
}
