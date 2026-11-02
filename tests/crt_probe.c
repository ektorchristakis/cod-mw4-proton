#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include <string.h>

typedef struct crt_file crt_file;
typedef int (__cdecl *freopen_s_fn)(crt_file **, const char *, const char *, crt_file *);
typedef crt_file *(__cdecl *legacy_iob_fn)(void);
typedef crt_file *(__cdecl *ucrt_iob_fn)(unsigned int);
typedef int (__cdecl *fgetc_fn)(crt_file *);
typedef int (__cdecl *stream_status_fn)(crt_file *);

static HANDLE report_handle;

static void report(const char *message)
{
    DWORD written;
    DWORD length = (DWORD)strlen(message);
    if (!WriteFile(report_handle, message, length, &written, NULL) || written != length)
        ExitProcess(7);
}

static void report_module(HMODULE module, const char *export_name)
{
    char path[MAX_PATH], address[19] = "0x0000000000000000";
    uintptr_t rva = (uintptr_t)GetProcAddress(module, export_name) - (uintptr_t)module;
    unsigned int i;
    if (!GetModuleFileNameA(module, path, sizeof(path)))
        ExitProcess(7);
    report(path);
    report(" ");
    report(export_name);
    report(" RVA ");
    for (i = 0; i < 16; ++i)
        address[17 - i] = "0123456789abcdef"[(rva >> (i * 4)) & 15];
    address[18] = '\0';
    report(address);
    report("\r\n");
}

int main(int argc, char **argv)
{
    HMODULE legacy, owner;
    freopen_s_fn reopen;
    fgetc_fn read_byte;
    stream_status_fn end_of_file, has_error, close_stream;
    crt_file *stream, *opened = NULL;
    const char contents[] = "CRT stream ownership probe\nsecond line\n";
    char directory[MAX_PATH], filename[MAX_PATH];
    HANDLE file;
    DWORD length, written;
    size_t i;
    int alias, result;

    report_handle = argc == 3 ? CreateFileA(argv[2], GENERIC_WRITE, FILE_SHARE_READ,
        NULL, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL) : GetStdHandle(STD_ERROR_HANDLE);
    if (report_handle == INVALID_HANDLE_VALUE || !report_handle)
        return 7;
    if ((argc != 2 && argc != 3) || (strcmp(argv[1], "own") && strcmp(argv[1], "cross") &&
                      strcmp(argv[1], "alias"))) {
        report("Usage: crt_probe.exe own|cross|alias [report-file]\r\n"
               "Run each case in a separate process with a timeout.\r\n");
        return 2;
    }
    alias = !strcmp(argv[1], "alias");

    legacy = LoadLibraryW(L"msvcrt.dll");
    if (!legacy) {
        report("FAIL: cannot load msvcrt.dll\r\n");
        return 3;
    }
    reopen = (freopen_s_fn)(uintptr_t)GetProcAddress(legacy, "freopen_s");
    if (!strcmp(argv[1], "own")) {
        legacy_iob_fn iob = (legacy_iob_fn)(uintptr_t)GetProcAddress(legacy, "__iob_func");
        owner = legacy;
        stream = iob ? iob() : NULL;
    } else {
        ucrt_iob_fn iob;
        owner = LoadLibraryW(L"ucrtbase.dll");
        iob = owner ? (ucrt_iob_fn)(uintptr_t)GetProcAddress(owner, "__acrt_iob_func") : NULL;
        stream = iob ? iob(0) : NULL;
    }
    read_byte = owner ? (fgetc_fn)(uintptr_t)GetProcAddress(owner, "fgetc") : NULL;
    end_of_file = owner ? (stream_status_fn)(uintptr_t)GetProcAddress(owner, "feof") : NULL;
    has_error = owner ? (stream_status_fn)(uintptr_t)GetProcAddress(owner, "ferror") : NULL;
    close_stream = owner ? (stream_status_fn)(uintptr_t)GetProcAddress(owner, "fclose") : NULL;
    if (!reopen || !stream || !read_byte || !end_of_file || !has_error || !close_stream) {
        report("FAIL: missing CRT or required exports\r\n");
        return 3;
    }
    report_module(legacy, "freopen_s");
    report_module(owner, "fgetc");

    length = GetTempPathA(sizeof(directory), directory);
    if (!length || length >= sizeof(directory) ||
        !GetTempFileNameA(directory, "crt", 0, filename)) {
        report("FAIL: cannot create temporary input path\r\n");
        return 3;
    }
    file = CreateFileA(filename, GENERIC_WRITE, 0, NULL, TRUNCATE_EXISTING,
                       FILE_ATTRIBUTE_TEMPORARY, NULL);
    if (file == INVALID_HANDLE_VALUE) {
        DeleteFileA(filename);
        report("FAIL: cannot open temporary input file\r\n");
        return 3;
    }
    if (!WriteFile(file, contents, sizeof(contents) - 1, &written, NULL) ||
        written != sizeof(contents) - 1) {
        CloseHandle(file);
        DeleteFileA(filename);
        report("FAIL: cannot write temporary input file\r\n");
        return 3;
    }
    CloseHandle(file);

    report("Calling msvcrt.freopen_s for case: ");
    report(argv[1]);
    report("\r\n");

    /* A Win32-written input keeps setup independent of either CRT.
     * The alias case reproduces a FILE* passed in the FILE** output position.
     */
    result = reopen(alias ? (crt_file **)stream : &opened, filename, "rb", stream);
    if (result != 0 || (!alias && opened != stream)) {
        DeleteFileA(filename);
        report("FAIL: reopen failed or returned a different stream\r\n");
        return 4;
    }

    /* A successful return alone misses the alias-induced FILE corruption.
     * Its owning CRT must still be able to read and query this stream.
     */
    for (i = 0; i < sizeof(contents) - 1; ++i) {
        if (read_byte(stream) != (unsigned char)contents[i]) {
            DeleteFileA(filename);
            report("FAIL: owning CRT read the wrong input bytes\r\n");
            return 5;
        }
    }
    if (read_byte(stream) != -1 || !end_of_file(stream) || has_error(stream)) {
        DeleteFileA(filename);
        report("FAIL: reopened stream is not usable by its owning CRT\r\n");
        return 5;
    }
    if (close_stream(stream) || !DeleteFileA(filename)) {
        report("FAIL: cannot close or remove temporary input file\r\n");
        return 6;
    }
    report("PASS: reopen and owner-CRT stream operations succeeded\r\n");
    return 0;
}
