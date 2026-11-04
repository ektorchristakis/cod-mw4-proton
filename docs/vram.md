# VRAM allocation in the campaign

The renderer includes a patch for small heaps that request 4 MiB alignment.
Previously, VKD3D-Proton could place four such heaps in a 16 MiB pool even when
each heap was much smaller. The unused gaps remained allocated as device-local
memory. The patch gives small, highly aligned heaps their own Vulkan allocation,
so each starts at offset zero without reserving a 4 MiB slot in a shared pool.
Resource alignment requirements remain in force.

On an RTX 3060 Laptop GPU with 6 GiB of VRAM, an instrumented campaign checkpoint
showed 4,688 MiB of device-local pools containing 208 MiB of live suballocations.
With the patch, the same class of pools fell to 32 MiB during a checkpoint test;
NVIDIA's reported GPU usage was about 4.5 GiB during subsequent play. These
figures are from one machine and are not a promise of VRAM use or frame rate on
other systems. Pool free space can be reused by compatible allocations; it is
not necessarily a leak. The in-game VRAM figure is an estimate and its exact
calculation has not been established here.

The patch increases the number of Vulkan memory allocations. Long sessions,
other hardware and drivers, other campaign areas, and Steam and Bottles launches
need further testing. This project supports the campaign only; multiplayer and
online services are outside its scope.

`tools/build-vkd3d.sh` applies the patch to the pinned renderer source during
the build, records its hash in `build-info.json`, and restores the source tree
on exit. Rebuilding the renderer can invalidate an existing shader cache and
require shader compilation on the next launch.
