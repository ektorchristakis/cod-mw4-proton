#define main crt_probe_main
#include "crt_probe.c"
#undef main

int main(int argc, char **argv)
{
    wchar_t executable[MAX_PATH], working[MAX_PATH], *slash;
    char *test_arguments[] = {"bottles_campaign_probe", "alias"};

    if (argc != 2 || strcmp(argv[1], "hdeyguxs3zaumvlgvybm2vyc")) return 80;
    if (!GetModuleFileNameW(NULL, executable, MAX_PATH) ||
        !GetCurrentDirectoryW(MAX_PATH, working)) return 81;
    slash = wcsrchr(executable, L'\\');
    if (!slash) return 81;
    *slash = 0;
    slash = wcsrchr(executable, L'\\');
    if (!slash) return 81;
    *slash = 0;
    if (_wcsicmp(executable, working)) return 82;
    return crt_probe_main(2, test_arguments);
}
