#define WIN32_LEAN_AND_MEAN
#include <winsock2.h>
#include <windows.h>
#include <winhttp.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

static FILE *report;
static unsigned int failures;

struct server {
    SOCKET listener;
    char request[2048];
    int received;
};

static DWORD WINAPI serve(void *parameter)
{
    struct server *server = parameter;
    const char reply[] = "HTTP/1.1 200 OK\r\nContent-Length: 12\r\nConnection: close\r\n\r\nHTTP/1.1 OK\n";
    struct timeval timeout = {5, 0};
    fd_set ready;
    SOCKET client;
    DWORD socket_timeout = 5000;
    int count, sent = 0;

    FD_ZERO(&ready);
    FD_SET(server->listener, &ready);
    if (select(0, &ready, NULL, NULL, &timeout) != 1)
        return 1;
    client = accept(server->listener, NULL, NULL);
    if (client == INVALID_SOCKET)
        return 2;
    setsockopt(client, SOL_SOCKET, SO_RCVTIMEO, (const char *)&socket_timeout, sizeof(socket_timeout));
    setsockopt(client, SOL_SOCKET, SO_SNDTIMEO, (const char *)&socket_timeout, sizeof(socket_timeout));
    while (server->received < (int)sizeof(server->request) - 1) {
        count = recv(client, server->request + server->received,
                     sizeof(server->request) - 1 - server->received, 0);
        if (count <= 0)
            break;
        server->received += count;
        server->request[server->received] = '\0';
        if (strstr(server->request, "\r\n\r\n"))
            break;
    }
    while (sent < (int)sizeof(reply) - 1) {
        count = send(client, reply + sent, sizeof(reply) - 1 - sent, 0);
        if (count <= 0)
            break;
        sent += count;
    }
    shutdown(client, SD_BOTH);
    closesocket(client);
    return sent == sizeof(reply) - 1 ? 0 : 3;
}

static void check_option(const char *name, HINTERNET handle, DWORD option,
                         void *buffer, DWORD size, BOOL expected, DWORD expected_error)
{
    BOOL result;
    DWORD error;
    SetLastError(0xdeadbeef);
    result = WinHttpSetOption(handle, option, buffer, size);
    error = GetLastError();
    fprintf(report, "%s: result=%d error=%lu %s\n", name, result, error,
            result == expected && error == expected_error ? "PASS" : "FAIL");
    if (result != expected || error != expected_error)
        ++failures;
}

int main(int argc, char **argv)
{
    HINTERNET session = NULL, connection = NULL, request = NULL, closed;
    HMODULE module;
    char path[MAX_PATH], response[64] = {0};
    DWORD zero = 0, nonzero = 1, protocols = 0x2800, received = 0, chunk, thread_result = 1;
    DWORD status = 0, status_size = sizeof(status);
    WSADATA sockets;
    struct sockaddr_in address;
    int address_size = sizeof(address), expected, http_ok = 0;
    struct server server = {INVALID_SOCKET, {0}, 0};
    HANDLE thread = NULL;

    if (argc < 2 || argc > 3 || (strcmp(argv[1], "baseline") && strcmp(argv[1], "patched"))) {
        fprintf(stderr, "Usage: winhttp_probe.exe baseline|patched [report-file]\n");
        return 2;
    }
    expected = !strcmp(argv[1], "patched");
    report = argc == 3 ? fopen(argv[2], "w") : stdout;
    if (!report)
        return 2;
    module = GetModuleHandleW(L"winhttp.dll");
    if (!GetModuleFileNameA(module, path, sizeof(path)))
        return 3;
    fprintf(report, "module=%s WinHttpSetOption_RVA=0x%llx mode=%s\n", path,
            (unsigned long long)((uintptr_t)GetProcAddress(module, "WinHttpSetOption") - (uintptr_t)module), argv[1]);

    if (WSAStartup(MAKEWORD(2, 2), &sockets))
        return 3;
    server.listener = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
    memset(&address, 0, sizeof(address));
    address.sin_family = AF_INET;
    address.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
    if (server.listener == INVALID_SOCKET ||
        bind(server.listener, (const struct sockaddr *)&address, sizeof(address)) ||
        getsockname(server.listener, (struct sockaddr *)&address, &address_size) ||
        listen(server.listener, 1)) {
        ++failures;
        goto done;
    }
    session = WinHttpOpen(L"Wine HTTP compatibility probe", WINHTTP_ACCESS_TYPE_NO_PROXY,
                          WINHTTP_NO_PROXY_NAME, WINHTTP_NO_PROXY_BYPASS, 0);
    if (!session || !WinHttpSetTimeouts(session, 3000, 3000, 3000, 3000)) {
        ++failures;
        goto done;
    }
    check_option("session-zero", session, 133, &zero, 4, expected,
                 expected ? 0 : ERROR_WINHTTP_INVALID_OPTION);
    check_option("http2-unsupported", session, 133, &nonzero, 4, FALSE, ERROR_WINHTTP_INVALID_OPTION);
    check_option("short-buffer", session, 133, &zero, 3, FALSE, ERROR_WINHTTP_INVALID_OPTION);
    check_option("long-buffer", session, 133, &zero, 5, FALSE, ERROR_WINHTTP_INVALID_OPTION);
    check_option("null-buffer", session, 133, NULL, 4, FALSE, ERROR_INVALID_PARAMETER);
    check_option("empty-buffer", session, 133, NULL, 0, FALSE, ERROR_WINHTTP_INVALID_OPTION);
    check_option("unknown-option", session, 0xffffffff, &zero, 4, FALSE, ERROR_WINHTTP_INVALID_OPTION);
    check_option("null-handle", NULL, 133, &zero, 4, FALSE, ERROR_INVALID_HANDLE);
    check_option("ordinary-tls-option", session, WINHTTP_OPTION_SECURE_PROTOCOLS, &protocols, 4, TRUE, 0);
    connection = WinHttpConnect(session, L"127.0.0.1", ntohs(address.sin_port), 0);
    request = connection ? WinHttpOpenRequest(connection, L"GET", L"/probe", NULL,
                                             WINHTTP_NO_REFERER, WINHTTP_DEFAULT_ACCEPT_TYPES, 0) : NULL;
    if (!connection || !request) {
        ++failures;
        goto done;
    }
    check_option("connection-handle", connection, 133, &zero, 4, FALSE, ERROR_WINHTTP_INCORRECT_HANDLE_TYPE);
    /* The stock GE runtime already implements this option on requests. */
    check_option("request-zero", request, 133, &zero, 4, TRUE, 0);
    closed = WinHttpOpenRequest(connection, L"GET", L"/closed", NULL,
                                WINHTTP_NO_REFERER, WINHTTP_DEFAULT_ACCEPT_TYPES, 0);
    if (!closed || !WinHttpCloseHandle(closed)) {
        ++failures;
        goto done;
    }
    check_option("closed-handle", closed, 133, &zero, 4, FALSE, ERROR_INVALID_HANDLE);

    thread = CreateThread(NULL, 0, serve, &server, 0, NULL);
    if (!thread) {
        ++failures;
        goto done;
    }
    http_ok = WinHttpSendRequest(request, WINHTTP_NO_ADDITIONAL_HEADERS, 0,
                                WINHTTP_NO_REQUEST_DATA, 0, 0, 0) &&
              WinHttpReceiveResponse(request, NULL) &&
              WinHttpQueryHeaders(request, WINHTTP_QUERY_STATUS_CODE | WINHTTP_QUERY_FLAG_NUMBER,
                                  NULL, &status, &status_size, NULL);
    while (http_ok && received < sizeof(response) - 1) {
        http_ok = WinHttpReadData(request, response + received,
                                 sizeof(response) - 1 - received, &chunk);
        if (!http_ok || !chunk)
            break;
        received += chunk;
    }
    if (WaitForSingleObject(thread, 7000) != WAIT_OBJECT_0) {
        fprintf(report, "FAIL: bounded loopback server did not finish\n");
        fflush(report);
        /* Its stack context must remain alive until the process terminates. */
        ExitProcess(5);
    }
    GetExitCodeThread(thread, &thread_result);
    http_ok = http_ok && status == 200 && received == 12 &&
              !memcmp(response, "HTTP/1.1 OK\n", 12) && thread_result == 0 &&
              !strncmp(server.request, "GET /probe HTTP/1.1\r\n", 21);
    fprintf(report, "loopback-http11: status=%lu bytes=%lu thread=%lu %s\n",
            status, received, thread_result, http_ok ? "PASS" : "FAIL");
    if (!http_ok)
        ++failures;

done:
    if (thread) CloseHandle(thread);
    if (request) WinHttpCloseHandle(request);
    if (connection) WinHttpCloseHandle(connection);
    if (session) WinHttpCloseHandle(session);
    if (server.listener != INVALID_SOCKET) closesocket(server.listener);
    WSACleanup();
    fprintf(report, "failures=%u\n", failures);
    if (report != stdout) fclose(report);
    return failures ? 4 : 0;
}
