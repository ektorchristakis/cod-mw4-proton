#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>
#include <string.h>
#include <wchar.h>
#include "randgrid_protocol.h"
#include "ascon/crypto_aead.h"

static BOOL stop_service(FILE *report, SC_HANDLE service)
{
    SERVICE_STATUS state;
    DWORD started = GetTickCount();
    BOOL stop_sent = FALSE;

    for (;;) {
        if (!QueryServiceStatus(service, &state)) {
            fprintf(report, "QueryServiceStatus during stop error=%lu\n", GetLastError());
            return FALSE;
        }
        if (state.dwCurrentState == SERVICE_STOPPED) return TRUE;
        if (!stop_sent && (state.dwCurrentState == SERVICE_RUNNING ||
                           state.dwCurrentState == SERVICE_PAUSED)) {
            if (!ControlService(service, SERVICE_CONTROL_STOP, &state)) {
                DWORD error = GetLastError();
                if (error != ERROR_SERVICE_NOT_ACTIVE) {
                    fprintf(report, "ControlService stop error=%lu state=%lu\n",
                            error, state.dwCurrentState);
                    return FALSE;
                }
            }
            stop_sent = TRUE;
        }
        if (GetTickCount() - started >= 10000) {
            fprintf(report, "Service stop timed out after 10 seconds; state=%lu\n",
                    state.dwCurrentState);
            return FALSE;
        }
        Sleep(50);
    }
}

static int test_handshake(FILE *report, HANDLE device)
{
    const volatile unsigned char *shared = (const volatile unsigned char *)(uintptr_t)0x7ffe0000;
    struct randgrid_context context;
    unsigned char key[16], nonce[16], encrypted[32], response[144], plaintext[128];
    const unsigned char request[16] = {
        0x70, 0x3a, 0x31, 0xc5, 0, 0, 0, 0, 0x84, 0x7c, 0xb9, 0x3f, 0xfa, 0xc9, 0x3d, 0x94
    };
    const unsigned char expected[8] = {0x7b, 0x83, 0x46, 0xc0, 5, 0x36, 0xc2, 0x6b};
    unsigned long long encrypted_size, plaintext_size;
    uint64_t ticks, bucket;
    DWORD returned;
    BOOL result;
    int decrypted;
    context.tick_multiplier = *(const volatile uint32_t *)(shared + 4);
    context.tick_count = *(const volatile uint64_t *)(shared + 0x320);
    context.cookie = *(const volatile uint32_t *)(shared + 0x330);
    context.process_id = GetCurrentProcessId();
    __asm__("movq %%gs:0x60, %0" : "=r"(context.process_peb));
    ticks = ((uint64_t)context.tick_multiplier * (uint32_t)context.tick_count) >> 24;
    bucket = (ticks + 1023) & ~(uint64_t)1023;
    randgrid_protocol_derive(&context, bucket, key, nonce);
    crypto_aead_encrypt(encrypted, &encrypted_size, request, sizeof(request),
                        NULL, 0, NULL, nonce, key);
    result = DeviceIoControl(device, 0x8231214c, encrypted, sizeof(encrypted),
                             response, sizeof(response), &returned, NULL);
    fprintf(report, "Handshake result=%d error=%lu bytes=%lu\n", result,
            result ? 0 : GetLastError(), returned);
    if (!result || returned != 24) return 0;
    /* The driver can accept the prior bucket and reply using the current one. */
    context.tick_count = *(const volatile uint64_t *)(shared + 0x320);
    ticks = ((uint64_t)context.tick_multiplier * (uint32_t)context.tick_count) >> 24;
    bucket = (ticks + 1023) & ~(uint64_t)1023;
    randgrid_protocol_derive(&context, bucket, key, nonce);
    decrypted = crypto_aead_decrypt(plaintext, &plaintext_size, NULL, response,
                                    returned, NULL, 0, nonce, key);
    if (decrypted) {
        randgrid_protocol_derive(&context, ticks & ~(uint64_t)1023, key, nonce);
        decrypted = crypto_aead_decrypt(plaintext, &plaintext_size, NULL, response,
                                        returned, NULL, 0, nonce, key);
    }
    if (decrypted || plaintext_size != 8 || memcmp(plaintext, expected, 8)) return 0;
    fprintf(report, "PASS: authenticated reply contains the expected marker\n");
    encrypted[0] ^= 1;
    memset(response, 0xcc, sizeof(response));
    returned = 0;
    result = DeviceIoControl(device, 0x8231214c, encrypted, sizeof(encrypted),
                             response, sizeof(response), &returned, NULL);
    fprintf(report, "Corrupt request result=%d error=%lu bytes=%lu\n", result,
            result ? 0 : GetLastError(), returned);
    if (result || returned || response[0] != 0xcc) return 0;
    fprintf(report, "PASS: altered ciphertext rejected without output\n");
    return 1;
}

int wmain(int argc, wchar_t **argv)
{
    SC_HANDLE manager = NULL, service = NULL;
    SERVICE_STATUS status = {0};
    HANDLE device;
    FILE *report;
    DWORD error, returned = 0, start_time;
    unsigned char input[] = {1, 2, 3, 4}, output[16];
    BOOL result;
    int exit_code = 1;

    if (argc < 2 ||
        (wcscmp(argv[1], L"probe") && wcscmp(argv[1], L"game")) ||
        (!wcscmp(argv[1], L"probe") && argc != 4) ||
        (!wcscmp(argv[1], L"game") && argc != 5)) return 2;
    report = _wfopen(argv[3], L"w");
    if (!report) return 3;
    setvbuf(report, NULL, _IONBF, 0);
    manager = OpenSCManagerW(NULL, NULL, SC_MANAGER_ALL_ACCESS);
    if (!manager) {
        fprintf(report, "OpenSCManager error=%lu\n", GetLastError());
        goto cleanup;
    }
    service = CreateServiceW(manager, L"randgrid-wine", L"Randgrid Wine compatibility device",
        SERVICE_ALL_ACCESS, SERVICE_KERNEL_DRIVER, SERVICE_DEMAND_START,
        SERVICE_ERROR_NORMAL, argv[2], NULL, NULL, NULL, NULL, NULL);
    if (!service && GetLastError() == ERROR_SERVICE_EXISTS) {
        service = OpenServiceW(manager, L"randgrid-wine", SERVICE_ALL_ACCESS);
        if (service && !stop_service(report, service)) goto cleanup;
        if (service && !ChangeServiceConfigW(service, SERVICE_NO_CHANGE, SERVICE_NO_CHANGE,
            SERVICE_NO_CHANGE, argv[2], NULL, NULL, NULL, NULL, NULL, NULL)) {
            fprintf(report, "ChangeServiceConfig error=%lu\n", GetLastError());
            goto cleanup;
        }
    }
    if (!service) {
        fprintf(report, "CreateService error=%lu\n", GetLastError());
        goto cleanup;
    }
    if (!StartServiceW(service, 0, NULL) && GetLastError() != ERROR_SERVICE_ALREADY_RUNNING) {
        fprintf(report, "StartService error=%lu\n", GetLastError());
        goto cleanup;
    }
    start_time = GetTickCount();
    do {
        if (!QueryServiceStatus(service, &status)) break;
        if (status.dwCurrentState != SERVICE_START_PENDING) break;
        Sleep(50);
    } while (GetTickCount() - start_time < 10000);
    fprintf(report, "Service state=%lu win32_exit=%lu service_exit=%lu\n",
            status.dwCurrentState, status.dwWin32ExitCode, status.dwServiceSpecificExitCode);
    if (status.dwCurrentState != SERVICE_RUNNING) goto cleanup;
    device = CreateFileW(L"\\\\.\\Randgrid", GENERIC_READ | GENERIC_WRITE,
        FILE_SHARE_READ | FILE_SHARE_WRITE, NULL, OPEN_EXISTING, 0, NULL);
    if (device == INVALID_HANDLE_VALUE) {
        fprintf(report, "CreateFile error=%lu\n", GetLastError());
        goto cleanup;
    }
    memset(output, 0xcc, sizeof(output));
    result = DeviceIoControl(device, 0x223ffc, input, sizeof(input), output,
                             sizeof(output), &returned, NULL);
    error = GetLastError();
    CloseHandle(device);
    fprintf(report, "Unknown IOCTL result=%d error=%lu bytes=%lu output0=%02x\n",
            result, error, returned, output[0]);
    if (result || error != ERROR_INVALID_FUNCTION || returned || output[0] != 0xcc)
        goto cleanup;
    fprintf(report, "PASS: device opens; unsupported request fails without output\n");
    device = CreateFileW(L"\\\\.\\Randgrid", GENERIC_READ | GENERIC_WRITE,
        FILE_SHARE_READ | FILE_SHARE_WRITE, NULL, OPEN_EXISTING, 0, NULL);
    if (device == INVALID_HANDLE_VALUE) {
        fprintf(report, "Handshake device open error=%lu\n", GetLastError());
        goto cleanup;
    }
    result = test_handshake(report, device);
    CloseHandle(device);
    if (!result) goto cleanup;
    exit_code = 0;
    if (argc == 5 && !wcscmp(argv[1], L"game")) {
        STARTUPINFOW startup = { .cb = sizeof(startup) };
        PROCESS_INFORMATION process;
        wchar_t command[2048], directory[1024], *slash;
        DWORD game_exit;
        if (wcslen(argv[4]) >= 1024) { exit_code = 4; goto cleanup; }
        wcscpy(directory, argv[4]);
        slash = wcsrchr(directory, L'\\');
        if (!slash) { exit_code = 4; goto cleanup; }
        *slash = 0;
        slash = wcsrchr(directory, L'\\');
        if (!slash) { exit_code = 4; goto cleanup; }
        *slash = 0;
        swprintf(command, 2048, L"\"%ls\" hdeyguxs3zaumvlgvybm2vyc", argv[4]);
        if (!CreateProcessW(argv[4], command, NULL, NULL, FALSE, 0, NULL, directory,
                            &startup, &process)) {
            fprintf(report, "CreateProcess error=%lu\n", GetLastError());
            exit_code = 4;
            goto cleanup;
        }
        fprintf(report, "Game pid=%lu\n", process.dwProcessId);
        /* The Linux diagnostic harness owns its timeout. An interactive launch
         * must remain open until the player closes the game. */
        WaitForSingleObject(process.hProcess, INFINITE);
        GetExitCodeProcess(process.hProcess, &game_exit);
        fprintf(report, "Game exit=%lu; menu state requires separate observation\n", game_exit);
        exit_code = game_exit ? 4 : 0;
        CloseHandle(process.hThread);
        CloseHandle(process.hProcess);
    }
cleanup:
    if (service) {
        if (!stop_service(report, service)) {
            exit_code = 5;
        } else if (!DeleteService(service)) {
            DWORD delete_error = GetLastError();
            if (delete_error != ERROR_SERVICE_MARKED_FOR_DELETE) {
                fprintf(report, "DeleteService error=%lu\n", delete_error);
                exit_code = 5;
            }
        }
        CloseServiceHandle(service);
    }
    if (manager) CloseServiceHandle(manager);
    fclose(report);
    return exit_code;
}
