#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include <string.h>

static volatile LONG handled;

static int check_unwind(HMODULE ntdll, const unsigned char *entry)
{
    typedef PRUNTIME_FUNCTION (WINAPI *lookup_fn)(DWORD64, PDWORD64, PUNWIND_HISTORY_TABLE);
    typedef PEXCEPTION_ROUTINE (WINAPI *unwind_fn)(DWORD, DWORD64, DWORD64,
        PRUNTIME_FUNCTION, PCONTEXT, PVOID *, PDWORD64, PKNONVOLATILE_CONTEXT_POINTERS);
    lookup_fn lookup = (lookup_fn)(uintptr_t)GetProcAddress(ntdll, "RtlLookupFunctionEntry");
    unwind_fn unwind = (unwind_fn)(uintptr_t)GetProcAddress(ntdll, "RtlVirtualUnwind");
    unsigned char frame[0x700] __attribute__((aligned(16))) = {0};
    const unsigned int offsets[] = {0x90, 0xa0, 0xa8, 0xb0, 0xd8, 0xe0, 0xe8, 0xf0};
    CONTEXT context = {0};
    DWORD64 base, establisher;
    PVOID handler_data;
    PRUNTIME_FUNCTION function;
    unsigned int i;
    if (!lookup || !unwind)
        return 0;
    for (i = 0; i < sizeof(offsets) / sizeof(offsets[0]); ++i)
        *(DWORD64 *)(frame + offsets[i]) = 0x11 * (i + 1);
    *(DWORD64 *)(frame + 0x590) = 0x1234567800;
    *(DWORD64 *)(frame + 0x598) = 0x33;
    *(DWORD64 *)(frame + 0x5a0) = 0x202;
    *(DWORD64 *)(frame + 0x5a8) = (DWORD64)(uintptr_t)(frame + 0x680);
    *(DWORD64 *)(frame + 0x5b0) = 0x2b;
    context.Rip = (DWORD64)(uintptr_t)(entry + 0x29);
    context.Rsp = (DWORD64)(uintptr_t)frame;
    function = lookup(context.Rip, &base, NULL);
    if (!function)
        return 0;
    unwind(0, base, context.Rip, function, &context, &handler_data, &establisher, NULL);
    return context.Rip == 0x1234567800 &&
        context.Rsp == (DWORD64)(uintptr_t)(frame + 0x680) &&
        context.Rbx == 0x11 && context.Rbp == 0x22 && context.Rsi == 0x33 &&
        context.Rdi == 0x44 && context.R12 == 0x55 && context.R13 == 0x66 &&
        context.R14 == 0x77 && context.R15 == 0x88;
}

static LONG CALLBACK handler(EXCEPTION_POINTERS *exception)
{
    if (exception->ExceptionRecord->ExceptionCode == EXCEPTION_ILLEGAL_INSTRUCTION) {
        exception->ContextRecord->Rip += 2; /* the deliberate UD2 below */
        InterlockedIncrement(&handled);
        return EXCEPTION_CONTINUE_EXECUTION;
    }
    if (exception->ExceptionRecord->ExceptionCode == 0xe0123456) {
        InterlockedIncrement(&handled);
        return EXCEPTION_CONTINUE_EXECUTION;
    }
    return EXCEPTION_CONTINUE_SEARCH;
}

int main(int argc, char **argv)
{
    HMODULE ntdll = GetModuleHandleW(L"ntdll.dll");
    const unsigned char *entry = (const unsigned char *)(uintptr_t)
        GetProcAddress(ntdll, "KiUserExceptionDispatcher");
    HANDLE report;
    PVOID registration;
    DWORD written;
    const char *message;
    int layout, passed;
    if (argc != 2 || !entry)
        return 2;
    report = CreateFileA(argv[1], GENERIC_WRITE, FILE_SHARE_READ, NULL,
                         CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
    if (report == INVALID_HANDLE_VALUE)
        return 3;
    layout = entry[0x29] == 0xe8;
    message = layout ? "LAYOUT: call at Windows offset +0x29\r\n" :
                       "LAYOUT: original Wine dispatcher\r\n";
    if (!WriteFile(report, message, (DWORD)strlen(message), &written, NULL))
        return 4;
    registration = AddVectoredExceptionHandler(1, handler);
    if (!registration)
        return 5;
    __asm__ volatile("ud2");
    RaiseException(0xe0123456, 0, 0, NULL);
    RemoveVectoredExceptionHandler(registration);
    passed = handled == 2 && check_unwind(ntdll, entry);
    message = passed ? "PASS: CPU fault, RaiseException, and frame unwind\r\n" :
                       "FAIL: exception dispatch or frame unwind differs\r\n";
    if (!WriteFile(report, message, (DWORD)strlen(message), &written, NULL))
        return 4;
    CloseHandle(report);
    return passed ? 0 : 6;
}
