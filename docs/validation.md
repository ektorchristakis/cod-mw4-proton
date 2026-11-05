# Validation

This page separates the current beta.3 checks from the retained beta.1/beta.2 observations. A built or API-tested runtime, a visible menu, a private diagnostic comparison and actual gameplay are different evidence. Each result below is limited to the recorded artifact and session.

## Beta.3 validation

Record for the 6 GiB RTX 3060 Laptop test host. Beta.3 includes both the aligned-heap renderer patch and the budget-only x64 DXGI DLL, SHA-256 `f3b1dccd1b6d7471b5e72c66ecdbfcf24f2ef07f9804f4616a229199c468b9a0`. The latter was built from the pinned GE-prepared DXVK source without the private diagnostic logging used in earlier comparisons. Final archive identity is established by the release's published `SHA256SUMS` and manifests; a provisional overlay hash is not a published-release identity.

### Aligned heaps and external memory pressure

A private instrumented checkpoint comparison found 4,688 MiB in 16 MiB device-local pools containing about 208 MiB of live suballocations. With the aligned-heap patch, that class of pool fell to 32 MiB. In a later 31-minute direct Wine session using a clean build of the patch, NVIDIA reported 4,615–4,743 MiB used on the GPU; the player also reported better performance. Most of that measured interval was stationary. The clean build used for that session is not byte-identical to the renderer produced by the public Git build recipe, which has a different shader-cache identity. These observations do not prove that allocations cannot grow or that all campaign scenes sustain 30 FPS. See [VRAM allocation](vram.md) for the tradeoff.

The Git-built release candidate's `d3d12core.dll` has SHA-256 `0371337bfc9363c7b52a3d2e3865cd897dea5542ba2699bd90efee4804ac8d3d`. In a separate visible UMU session, its installed prefix DLL matched that hash, Resume loaded the existing Stranded checkpoint, and brief movement was observed. The pause screen showed the SAM site objective. Over 313 GPU-memory samples spanning about 11 minutes, usage rose from 3,452 MiB to 4,647 MiB as the scene loaded and then stayed near that value; most of the observation was stationary. The game exited with code zero. The first load followed a renderer change and shader-cache invalidation. These checks do not qualify later missions, cinematics with this renderer, a stable frame-rate floor or long-term memory behavior.

Another visible direct Wine run used the local renderer build `cba46169ad0fdfef147c9ec4f3bee92574295f11f1465c7d095c31e54ac0d4fa` and DXGI `f9f2dd88f49a5fe5b439f01af463d4503c1d10f05d9798e2d3e31b5752b92231`, which are not the release binaries. Resume loaded the existing checkpoint, brief sidesteps changed the view, and the pause screen showed the remaining SAM site objective. Ninety GPU samples over approximately 191 seconds showed 3,076–4,614 MiB in use, reaching 4,614 MiB at the end. Eight screenshots of the game's FPS counter showed 34–45 FPS; most of this short observation was stationary. The game exited with code zero. These sparse readings do not measure frame times, content-streaming drops, extended traversal or a 30 FPS floor.

In a separate diagnostic run, an independent Vulkan process used 1,540 MiB while the game's settings page still showed `Other Apps: 0 GB`. During that load, the game's queried DXGI LOCAL budget decreased by about 1.5 GiB and returned after the process exited. A repeat with the normal direct Wine launcher still showed zero after reopening the settings page while the 1,540 MiB allocation was active. The label is therefore misleading in this setup, even though that budget responded to external pressure. The source of the displayed value and the game's use of the information are not established; the runner does not claim to fix the label.

### Build, package and API checks

The fresh Git recipe built that DXGI DLL. The host suite passed 41 tests with the aligned-heap packaging and installed-runner checks included. A staging overlay was installed offline over the existing extracted GE base, and its installed renderer and DXGI hashes matched the candidate DLLs. The installed manifest, inherited x86 DXGI, source archives and notices were verified in staging. This establishes those source/package/runtime inputs, not campaign performance. The exported-source offline rebuild recipe has not been run.

Five API cases used the staged core through UMU in a fresh, dedicated prefix with the actual game closed. The probe loaded the identified DLL from that prefix's `system32`. The raw LOCAL budget was `6072696832` bytes. Limits of 5120, 4096 and 1 MiB capped the reported LOCAL budget; zero and 8192 MiB retained the lower raw budget. NON_LOCAL reporting was unchanged. The probe allocated no game workload and its usage value was zero. Source inspection establishes that the patch leaves the existing usage calculation untouched; these cases are not a residency, over-budget usage or sustained memory-pressure test.

### Earlier budget-only candidate coverage

The identified DXGI DLL was used through UMU with the earlier, unpatched renderer, from the original NTFS game installation with the existing dedicated campaign prefix. With `dxgi.maxDeviceMemory = 5120`, Resume loaded the existing checkpoint. Walking, strafing, aim and camera movement responded during focused input checks. Advancing video and subtitles were observed in Mayhem and Out in the Cold; Kin Punishment video advanced and responded to pause before returning to the gallery. A Mute Game When Minimized setting was toggled and restored. Master volume remained zero. A clean Quit to Desktop was requested and the game process exited. This does not qualify the final renderer build.

The two public-binary memory-budget trials used the same identified DLL, with no graphics-quality changes recorded:

| Reported limit | Approximately 1 Hz counter samples | Median displayed FPS | Range | Samples below 30 | Final 120-sample mean |
| --- | ---: | ---: | ---: | ---: | ---: |
| 5120 MiB, wider view | 900 | 32 | 19–33 | 156 | 27.49 |
| 4096 MiB | 1000 | 13 | 11–34 | 951 | 13 |

The 5120 MiB sample covered about 15 minutes and ended in the mid-20s with drops. The 4096 MiB trial deteriorated to sustained readings around 13 FPS and was stopped; it is not a recommended setting. These are sampled in-game counter readings, not frame-time measurements, frame counts or 1% lows. The trials do not establish a controlled causal improvement, identical resolved texture quality or a stable 30 FPS floor. The user recalls similar fluctuations on Windows, but saved Windows settings differed in shadows and screen-space reflections, and no matched Windows baseline was measured. The cause of the slowdown remains unresolved.

These earlier campaign trials used positive limits and the unpatched renderer; the later aligned-heap checkpoint check above used the default zero limit. Earlier Steam/Bottles beta.2 client results remain specific to those labelled sessions and do not qualify beta.3 play through those clients. Later missions, full campaign completion, sustained representative performance, audible output and quality, other GPU/runtime combinations and an ongoing Windows/Linux save roundtrip remain unqualified.

### Private diagnostic motivation

The following earlier observations used private diagnostic DLLs, not the budget-only DXGI DLL identified above. They motivated the optional setting and do not qualify the release candidate's sustained gameplay.

| Private observation | Approximately 1 Hz counter samples | Median displayed FPS | Samples below 30 |
| --- | ---: | ---: | ---: |
| GE-prepared logging-only control | 455 | 16 | 368 |
| GE-prepared budget candidate | 660 | 41 | 16 |
| Additional wider candidate view | 360 | 32 | 33 |

The candidate minima were 23 FPS in the first view and 17 in the wider view. These were sampled in-game counter readings, not frame times, frame counts or 1% low measurements. The control sampling began 4 minutes 9 seconds after launch and candidate sampling 9 minutes 8 seconds after launch. The runs were sequential, with launch-age and warm-cache confounds; checkpoint bytes differed despite the same initial scene and position. The wider workload had no matched control. Inputs were given every ten seconds to limit the 30-second idle-quality confound during those private trials.

Settings files were byte-identical before and after, but identical resolved textures or mip levels were not established. Physical VRAM remained approximately full at 5854/5857 MiB. These observations do not establish a physical memory cap, reclaimed VRAM, identical rendered quality, a 30 FPS floor, a general fix or a controlled causal performance effect. The manually selected 5120 MiB value is not a qualified profile for other GPUs. A later user-controlled run with private instrumented components also exhibited large drops. It was not a qualification run of the public beta.3 binary.

## Historical beta.1 cutoff record

The cutoff record below is retained from the [published beta.1](https://github.com/ektorchristakis/cod-mw4-proton/blob/v0.1.0-beta.1/docs/validation.md). Later [post-beta observations](#post-beta-observations-2026-11-03) and [beta.2 launcher checks](#beta2-launcher-checks) remain separately labelled. They do not alter those releases or the original cutoff record.

Tested on 2026-11-02 with Fedora 44, GNOME 50.6, an NVIDIA RTX 3060 Laptop GPU with 6 GiB VRAM, and NVIDIA driver 615.78.08. The runner uses GE-Proton 11-11, UMU 1.4.4, and Steam Runtime 4.

### Beta.1 cutoff status

The following cutoff record describes `0.1.0-beta.1`, an experimental prerelease published with incomplete testing. The results below describe specific observed sessions, not full campaign, performance, installation, audio-quality, account-safety, or multiplayer qualification.

### Runtime probes

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

### Campaign coverage

Support covers the single-player campaign only. Multiplayer and online modes are unsupported.

The assembled runner starts the original NTFS installation at 1920×1080 and reaches the campaign menu with the existing Resume entry. Mayhem cinematic playback completed and returned to its menu; another existing cinematic also played. Stranded checkpoint loading, keyboard movement, mouse look, pause/resume, and setting master volume to zero were observed using an explicit process-local CPU topology. Later missions and full campaign completion have not been tested.

The automatic-topology candidate selected `6s:0,1,4,5,6,7,8,9,10,11,12,13` on the sparse-CPU host, and its actual process affinity matched that subset. Checkpoint testing of that automatic launch was still in progress at the beta evidence cutoff. The host regression suite also checks the child's affinity without changing the parent process affinity.

Earlier gameplay under imported or re-detected high settings showed roughly 10–30 FPS and about 5.59 GiB of video memory in use. Matching the existing Windows medium/low settings was in progress at the cutoff. A 30 FPS target has not been demonstrated, and no stable or representative performance result is claimed. Initial shader processing and menu frame rates are not gameplay benchmarks.

The game selected 7.1 Surround and the configured local Linux audio device exposed eight channels at 48 kHz. PipeWire showed FL, FR, FC, LFE, RL, RR, SL, and SR connected. These observations establish channel configuration and routing on that machine. Audible output and quality were not tested because master volume was zero; this beta does not configure or provide a surround device.

A local desktop launcher was installed and its configuration check passed. Launching the game by activating that desktop entry had not been verified at the cutoff. The portable release documents Steam and UMU setup; it does not ship or qualify that machine's desktop entry.

### Remaining checks

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
