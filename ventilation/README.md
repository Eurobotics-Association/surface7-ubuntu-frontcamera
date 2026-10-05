# Surface Pro 7 ventilation check

**Read-only snapshot: 2026-10-05.** No packages, settings, fan controls, firmware, or kernel state were changed.

## Findings

- DMI identifies Surface Pro 7 (model 1866), Intel Core i7-1065G7, Surface UEFI 24.109.140 (2025-07-21); the Surface Serial Hub log reports SAM firmware 14.800.139. Ubuntu is 24.04.5 LTS. The i7 configuration is the fan-equipped SP7 variant.
- At sampling, CPU package was 45°C and cores 46–51°C; the ACPI/DPTF temperature readings were about 35–52°C. CPU temperature sensing works. Several generic ACPI zones logged “No valid trip points”; Surface/DPTF zones `SEN1–SEN9` and `B0D4` are also present.
- `B0D4` exposes firmware “active” trips at 80, 85, 90, and 95°C, plus hot/critical trips at 102/104°C. This makes 95°C a plausible firmware trip value, but does **not** prove that it is the fan-on threshold: the zone has no cooling-device binding.
- Linux exposes no fan RPM sensor, no `Fan` cooling device, and no thermal-zone-to-cooling-device bindings. Processor, power-clamp, TCC-offset, and PCIe cooling devices are present. The fan may be controlled autonomously by firmware, but Linux cannot confirm its rotation or command it directly through the interfaces found.
- `thermald` 2.5.6 and `power-profiles-daemon` 0.21 are installed and their current-boot journal says both started. The Surface platform profile is `balanced`. No `/etc/thermald/thermal-conf.xml` exists; thermald logs “sensor id 24: No temp sysfs for reading raw temp.” That warning indicates a missing thermald sensor mapping, not a missing CPU temperature reading.
- Microsoft publishes no numeric SP7 fan-start temperature. Its guidance says fan speed depends on workload, charging, ambient temperature, and power mode; higher-performance modes allow faster fan operation. Microsoft’s latest SP7 history lists UEFI 24.109.140.0 (September 2025), matching this device; that release is described as a security fix, not a fan fix. Intel lists 100°C Tjunction for this CPU.

## Assessment and safe next steps

The evidence does not establish a failed fan. The clearest software-side lead is the current `balanced` profile: Linux Surface guidance says this profile prevents fan ramping for quieter operation. Sensor data is adequate for CPU monitoring, but fan telemetry/control and ACPI cooling bindings are absent, so a Linux snapshot cannot distinguish a firmware-policy delay from a mechanical fan fault. A Linux Surface report from an SP7 i7 describes temperatures approaching 90°C and severe throttling; the older widely cited SP7 throttling report concerns the fanless i5 and should not be treated as proof about this i7.

To separate causes safely, first compare audible/physical airflow during a similar sustained workload under Windows (if available). If the fan works there but remains quiet on Linux, a supervised, reversible comparison of the built-in balanced and higher-performance profiles is the first software check; log temperatures and stay below the 95°C operating limit. Thermald can limit CPU heat through processor/power controls, but cannot set an unexposed fan curve. If the fan also fails to respond under Windows load, seek a physical fan/vent inspection. No such test or setting change was performed.

## Sources

- [Microsoft: Surface fan behavior](https://support.microsoft.com/en-us/surface/performance/fan-behavior-and-fan-noise-in-a-surface-device)
- [Microsoft: Surface Pro 7 update history](https://support.microsoft.com/en-au/surface/updates/surface-pro-7-update-history)
- [Intel: Core i7-1065G7 specifications](https://www.intel.com/content/www/us/en/products/sku/196597/intel-core-i71065g7-processor-8m-cache-up-to-3-90-ghz/specifications.html)
- [Linux Surface: Surface Pro 7 guidance](https://github.com/linux-surface/linux-surface/wiki/Surface-Pro-7)
- [Linux Surface issue #1098: SP7 i7 thermal performance](https://github.com/linux-surface/linux-surface/issues/1098)
- [Linux Surface issue #221: SP7 throttling (i5)](https://github.com/linux-surface/linux-surface/issues/221)
- [Linux kernel: thermal sysfs interfaces](https://www.kernel.org/doc/html/latest/driver-api/thermal/sysfs-api.html)
- [User report: SP7 i7 fan under Linux QEMU load](https://www.reddit.com/r/SurfaceLinux/comments/1jhkul1/total_newbie_worth_learning_linux_on_a_surface/)
