# Validation

Tested on 2026-11-02 with Fedora 44, GNOME 50.6, an NVIDIA RTX 3060 Laptop GPU with 6 GiB VRAM, and NVIDIA driver 615.78.08. The runner uses GE-Proton 11-11, UMU 1.4.4, and Steam Runtime 4.

## Beta status

This is `0.1.0-beta.1`, an experimental prerelease published with incomplete testing. The results below describe specific observed sessions, not full campaign, performance, installation, audio-quality, account-safety, or multiplayer qualification.

## Runtime probes

An empty, dedicated prefix was initialized using an assembled pre-beta MW4-Proton runner. All six probe processes exited successfully:

| Probe | Result |
| --- | --- |
| msvcrt-owned standard stream | Reopen, read, EOF, error state, and close passed |
| UCRT-owned standard stream | Same operations passed through the adapter |
| UCRT stream with aliased output pointer | Stream remained valid |
| Exception dispatcher | Layout, CPU fault, software exception, and unwind passed |
| WinHTTP | Twelve option/handle cases and a loopback HTTP/1.1 exchange passed |
| Wine device | Open, authenticated exchange, corrupt input, and unsupported IOCTL passed |

The installed msvcrt, ntdll, and WinHTTP hashes matched that pre-beta runner. After the packaging repairs, the host test suite passed twelve tests, including the original-driver protocol vector, wrapper routing, prefix locking through shutdown, and sparse CPU topology mapping.

## Campaign coverage

Support covers the single-player campaign only. Multiplayer and online modes are unsupported.

The assembled runner starts the original NTFS installation at 1920×1080 and reaches the campaign menu with the existing Resume entry. Mayhem cinematic playback completed and returned to its menu; another existing cinematic also played. Stranded checkpoint loading, keyboard movement, mouse look, pause/resume, and setting master volume to zero were observed using an explicit process-local CPU topology. Later missions and full campaign completion have not been tested.

The automatic-topology candidate selected `6s:0,1,4,5,6,7,8,9,10,11,12,13` on the sparse-CPU host, and its actual process affinity matched that subset. Checkpoint testing of that automatic launch was still in progress at the beta evidence cutoff. The host regression suite also checks the child's affinity without changing the parent process affinity.

Earlier gameplay under imported or re-detected high settings showed roughly 10–30 FPS and about 5.59 GiB of video memory in use. Matching the existing Windows medium/low settings was in progress at the cutoff. A 30 FPS target has not been demonstrated, and no stable or representative performance result is claimed. Initial shader processing and menu frame rates are not gameplay benchmarks.

The game selected 7.1 Surround and the configured local Linux audio device exposed eight channels at 48 kHz. PipeWire showed FL, FR, FC, LFE, RL, RR, SL, and SR connected. These observations establish channel configuration and routing on that machine. Audible output and quality were not tested because master volume was zero; this beta does not configure or provide a surround device.

A local desktop launcher was installed and its configuration check passed. Launching the game by activating that desktop entry had not been verified at the cutoff. The portable release documents Steam and UMU setup; it does not ship or qualify that machine's desktop entry.

## Remaining checks

Automatic-topology checkpoint completion, comparable-settings performance, desktop activation, audible channel quality, later missions, and full campaign completion remain unqualified. Steam and UMU integration beyond the recorded sessions and hardware has not been broadly tested. Multiplayer and online modes are unsupported; no account or ban-safety guarantee is made.
