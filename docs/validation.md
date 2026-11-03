# Validation

The cutoff record below is retained from the [published beta](https://github.com/ektorchristakis/cod-mw4-proton/blob/v0.1.0-beta.1/docs/validation.md). Later observations on `main` are recorded [separately below](#post-beta-observations-2026-11-03); they do not alter that release or its original testing record.

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

## Post-beta observations (2026-11-03)

These observations were recorded after publication. They add evidence for the specific paths below; they do not qualify other missions, the full campaign, multiplayer, online modes, account safety, or general performance.

The released beta automatically selected `6s:0,1,4,5,6,7,8,9,10,11,12,13` and loaded the Stranded checkpoint. Keyboard movement was observed, and that run exited with code zero. This extends the cutoff record's mapping-and-affinity check to an observed checkpoint load with automatic mapping.

A headless Linux run with the Windows-quality configuration had a 120-second MangoHUD average of 23.2 FPS, with reported 1% and 0.1% lows of about 10 FPS and 6.64 FPS. MangoHUD later asserted and ended that session. This is a result from one instrumented headless session, not a representative performance guarantee.

In a later configuration, texture and streaming settings were lower, GPU upload heaps and background shader preload were disabled, CNN DLSS was selected, and MangoHUD was not running. The in-game counter showed 30 FPS in several headless spot checks. This was not a sustained minimum or a timed performance qualification. An unfocused-window frame-rate cap may explain the repeated 30 FPS value; the observations do not isolate which setting affected performance. No native Windows FPS baseline accompanies these measurements.

A local GNOME `.desktop` entry was activated with `gio launch`, and the game reached its menu on the desktop. Actual mouse double-click of the icon was not tested. The game selected the local eight-channel 7.1 virtual-surround route with audio muted. Audible output, per-channel listening, and audio quality remain untested. The portable release does not provide that machine's desktop entry or surround device.

After backups, the Linux campaign save directories were linked to the Windows profile. An earlier running launch used writable bind mounts for those paths. Later, both save trees were backed up, the recovered Linux checkpoint was copied to the Windows-side shared-save location, and its body checksum and script aggregate were checked. A regular launch from the original installation path with the shared save was subsequently observed running visibly on the desktop. These observations do not establish save-write persistence across a Windows boot or an ongoing cross-OS save roundtrip; those checks remain untested.

### Checkpoint recovery

A later visible Stranded test recovered the original Windows checkpoint after restoring missing campaign content. The user reported that the original checkpoint had the bunker and clifftop jamming objectives completed, with the SAM objective remaining, and confirmed that the recovery restored the expected objectives, position, and loadout. Earlier Linux runs appeared to resume the mission but started fresh.

The failing run read the full 7,330,182-byte checkpoint payload and returned success from body validation. Its loaded script aggregate was `e909037b`, while the checkpoint required `cd2bd106`. This was a content compatibility rejection after a successful read, rather than evidence of a truncated save or missing save-directory link.

The missing content was the campaign application `7501` CCS patch for content build `13.1.29269899_874`, manifest version `31`. The official main and development packs were checked against their matching manifests: all 442 main-pack chunks and 465 development-pack chunks matched, with no trailing or missing pack bytes. A visible A/B test mounted the staged content and observed script aggregate `cd2bd106` matching the unchanged checkpoint. The checkpoint was accepted; the detailed restored gameplay state is user-confirmed. This successful content repair required no save-header edits, checksum bypasses, or changes to the campaign executable.

The tested setup also contained a locally constructed version-cache JSON in the existing downloader schema, using the campaign configuration and manifest version. That cache was not downloaded as official version metadata, and its independent necessity was not isolated. The four official content files were later installed under `sp26/main/extccs/31/`, with the cache at the `extccs` root. All five installed file hashes matched staging on readback. A subsequent regular original-path launch was observed running visibly on the desktop with the permanent content installation and shared save, without the staged-content mount override. This adds a regular-launch observation to the staged recovery and installed-file checks; it does not establish a Windows boot or cross-OS save roundtrip.

This establishes recovery of that checkpoint with matching content. Save-write persistence across a Windows boot, an ongoing cross-OS roundtrip, other checkpoints, later missions, and full campaign completion remain unqualified. The content repair does not establish a sustained 30 FPS result or stability guarantee. The [troubleshooting guidance](compatibility.md#checkpoint-content-mismatch) gives the exact-build checks, recorded official content sources, local cache record, and reversible setup. Game content and private save/debugging artifacts are not included in this repository or the runner release.

## Beta.2 launcher checks

Version `0.1.0-beta.2` adds the Steam and Bottles installers and pins DXVK-NVAPI 0.9.3. The host suite passed 34 tests, including archive integrity, copied-path containment, required runtime files, Steam detection and registration, and Bottles adapter fixtures. An offline overlay-installation fixture used the real GE Wine inputs and renderer with network access and compilation disabled; installed component hashes and the relocated Vulkan layer path matched, and original input files were preserved. These checks do not qualify a complete new client installation or campaign play.

### Native Steam (2026-11-03)

The native Steam client registered **MW4-Proton 0.1.0-beta.2**, selected it for a non-Steam campaign shortcut, installed Steam Linux Runtime 4, and invoked the custom runner directly. The original NTFS game installation rendered the campaign menu visibly. The controller's authenticated device exchange passed; unsupported and corrupted requests were rejected.

This launch used the existing dedicated campaign prefix with shared saves. A new default Steam prefix was not qualified by this session. The session stopped at the menu; Resume and keyboard movement were not verified in this Steam session. The earlier checkpoint recovery and movement observations remain specific to their recorded sessions. Sustained frame rate, stability, audible quality, a Windows boot and shared-save roundtrip, later missions, and full campaign completion remain unqualified.

### Flatpak Bottles 67.5 (2026-11-03)

Flatpak Bottles 67.5 registered **MW4-Bottles-0.1.0-beta.2** and initialized a new Custom 64-bit bottle using the beta.2 runner. Bottles' DXVK, VKD3D and DXVK NVAPI switches were disabled so the adapter supplied the pinned DLLs. The actual campaign launched from the same original NTFS installation used by Steam and rendered its campaign menu visibly. The sparse-host mapping selected twelve logical CPUs, and the controller's authenticated exchange passed while unsupported and corrupted requests were rejected. No game installation was copied.

This verifies prefix creation and menu rendering for that client/runtime combination. Resume and movement were not qualified in the Bottles session. A separate native adapter smoke test initialized a disposable prefix and ran the compiled CRT/controller probe successfully, checking the campaign argument, working directory, authenticated device replies and cleanup. That probe's result covers the launch plumbing; the visible Bottles menu is the separate rendering observation. Other Flatpak/runtime/GPU combinations, sustained performance, audible quality, Windows save roundtrips, later missions and full campaign completion remain unqualified.
