# Validation

Tested on 2026-11-02 with Fedora 44, GNOME 50.6, an NVIDIA RTX 3060 Laptop GPU with 6 GiB VRAM, and NVIDIA driver 615.78.08. The runner uses GE-Proton 11-11, UMU 1.4.4, and Steam Runtime 4.

## Runtime probes

An empty, dedicated prefix was initialized using the assembled MW4-Proton 0.1.0 runner. All six probe processes exited successfully:

| Probe | Result |
| --- | --- |
| msvcrt-owned standard stream | Reopen, read, EOF, error state, and close passed |
| UCRT-owned standard stream | Same operations passed through the adapter |
| UCRT stream with aliased output pointer | Stream remained valid |
| Exception dispatcher | Layout, CPU fault, software exception, and unwind passed |
| WinHTTP | Twelve option/handle cases and a loopback HTTP/1.1 exchange passed |
| Wine device | Open, authenticated exchange, corrupt input, and unsupported IOCTL passed |

The installed msvcrt, ntdll, and WinHTTP hashes matched the assembled runner. The host test suite passed twelve tests, including the original-driver protocol vector, wrapper routing, prefix locking through shutdown, and sparse CPU topology mapping.

## Campaign coverage

Support covers the single-player campaign only. Multiplayer and online modes are unsupported.

The assembled runner starts the original NTFS installation at 1920×1080 and reaches the campaign menu with the existing Resume entry. Mayhem cinematic playback completed and returned to its menu. Stranded checkpoint loading, keyboard movement, mouse look, pause/resume, and volume control were observed using an explicit process-local CPU topology. Later missions and full campaign completion have not been tested. Performance tuning and the automatic-topology runner retest remain in progress; no stable gameplay frame-rate claim is made yet.

The game selected 7.1 Surround and the Linux audio device exposed eight channels at 48 kHz. PipeWire showed FL, FR, FC, LFE, RL, RR, SL, and SR connected. These observations establish channel configuration and routing, rather than an independent listening test for each channel.
