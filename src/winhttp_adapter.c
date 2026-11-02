#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <winhttp.h>
#include <stdint.h>

typedef BOOL (WINAPI *set_option_fn)(HINTERNET, DWORD, void *, DWORD);
typedef BOOL (WINAPI *query_option_fn)(HINTERNET, DWORD, void *, DWORD *);
typedef HMODULE (WINAPI *get_module_handle_fn)(LPCWSTR);
typedef FARPROC (WINAPI *get_proc_address_fn)(HMODULE, LPCSTR);
typedef DWORD (WINAPI *get_last_error_fn)(void);
typedef void (WINAPI *set_last_error_fn)(DWORD);

/* Filled by patch_winhttp.py. All addresses are relative to the host DLL;
 * the helper must remain position independent when copied into its section.
 */
__declspec(dllexport) struct {
    uint32_t self_rva;
    uint32_t original_set_option_rva;
    uint32_t query_option_rva;
    uint32_t get_module_handle_iat_rva;
    uint32_t get_proc_address_iat_rva;
} adapter_state __attribute__((section(".data"))) = {0};

__declspec(dllexport)
BOOL WINAPI http_set_option(HINTERNET handle, DWORD option, void *buffer, DWORD length)
{
    unsigned char *host = (unsigned char *)&adapter_state - adapter_state.self_rva;
    set_option_fn original = (set_option_fn)(host + adapter_state.original_set_option_rva);
    query_option_fn query = (query_option_fn)(host + adapter_state.query_option_rva);
    get_module_handle_fn get_module_handle;
    get_proc_address_fn get_proc_address;
    get_last_error_fn get_error;
    set_last_error_fn set_error;
    HMODULE kernel;
    DWORD error, redirect_policy, policy_size = sizeof(redirect_policy);
    BOOL result;

    if (option != WINHTTP_OPTION_ENABLE_HTTP_PROTOCOL || !buffer || length != sizeof(DWORD))
        return original(handle, option, buffer, length);

    get_module_handle = *(get_module_handle_fn *)(host + adapter_state.get_module_handle_iat_rva);
    get_proc_address = *(get_proc_address_fn *)(host + adapter_state.get_proc_address_iat_rva);
    kernel = get_module_handle(L"kernel32.dll");
    get_error = kernel ? (get_last_error_fn)(uintptr_t)get_proc_address(kernel, "GetLastError") : NULL;
    set_error = kernel ? (set_last_error_fn)(uintptr_t)get_proc_address(kernel, "SetLastError") : NULL;

    result = original(handle, option, buffer, length);
    if (result || !get_error || !set_error)
        return result;
    error = get_error();
    if (error != ERROR_WINHTTP_INVALID_OPTION || *(DWORD *)buffer != 0)
        return result;

    /* Zero restricts negotiation to HTTP/1.1 and prior, which this Wine
     * runtime already implements. Do not claim HTTP/2 or HTTP/3 support.
     * This GE build already accepts it on request handles, but cannot query
     * HANDLE_TYPE. Its redirect-policy query is implemented only on sessions;
     * connection and WebSocket handles reject it. The query changes no policy
     * and revalidates the handle through Wine's object table.
     */
    if (query(handle, WINHTTP_OPTION_REDIRECT_POLICY, &redirect_policy, &policy_size)) {
        /* Match Wine's successful WinHttpSetOption: clear LastError. */
        set_error(ERROR_SUCCESS);
        return TRUE;
    }
    set_error(error);
    return FALSE;
}
