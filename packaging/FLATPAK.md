# Experimental self-contained Flatpak

This prototype bundles the Qt/QML settings application, PyQt radial overlay and
Rust daemon. It targets x86_64 KDE Plasma with Wayland and XWayland. It does not
require a separate daemon RPM, sysext or systemd service.

## Build

Use `flatpak-builder`, KDE Platform and SDK 6.10, and the corresponding
`org.freedesktop.Sdk.Extension.rust-stable` SDK extension. From the repository root:

```sh
flatpak-builder --jobs=4 --repo=repo build-dir packaging/org.juhlabs.JuhRadialMX.yaml
flatpak build-bundle repo JuhRadialMX.flatpak org.juhlabs.JuhRadialMX master
```

The manifest builds the local checkout. Dependency artifacts have pinned hashes;
Cargo compilation uses vendored sources and runs offline. Python wheels currently
limit the package to x86_64. Qt libraries come from the KDE runtime.

The launcher supervises the bundled processes and uses an app-private Unix socket
for communication between Flatpak instances. It supports `--background`,
`--restart-daemon`, `--restart-overlay` and `--quit`. It stores configuration in
Flatpak's private XDG directories. Temporary KWin scripts use the app's shared
runtime directory so the host compositor can read them.

## Validation

Tested on Bazzite 45 with flatpak-builder 1.4.12 and Flatpak 1.18.4, based on
upstream commit `33d01b2e6a4cce0f7fa0dee1fca128c80dce161e`:

- Release build and bundle export succeeded; six MX Keypad protocol tests passed.
- All 14 QML targets compiled and instantiated in the upstream smoke harness.
  That harness emits image-provider and teardown warnings; this is not a
  warning-free UI test.
- The actual settings window rendered on native Wayland and XWayland.
- HID++ connected to an MX Master 2S via Unifying and returned battery and DPI.
- Filtered D-Bus communication, input-event access, KWin tracking scripts, and
  the cursor-script -> daemon -> radial-overlay show/hide round trip succeeded.
- Duplicate launches, independent daemon/overlay restarts and shutdown passed.
- The upstream GUI frame-timing benchmark stalled; no benchmark result is claimed.

## Remaining limitations

- `--device=all` remains necessary for the current hidraw/evdev/uinput design.
  A test with only `dri`, `input` and `usb` hid both hidraw and uinput. Flatpak
  exposure does not grant Unix device permissions: the test desktop already had
  suitable ACLs and input-group membership. Clean-host operation is unverified.
- KWin scripting access is powerful. The overlay still needs XWayland for
  positioning; the settings window can use native Wayland.
- Login autostart is explicitly unavailable until Background portal integration
  is implemented. No host autostart file or service is installed.
- Commands targeting host programs are restricted to the sandbox. Arbitrary
  host program launching requires further integration; no host escape is added.
- Network sharing is not granted, so cross-computer Flow and network update
  checks are not functional. GTK fallback settings and niri layer-shell support
  are not bundled in this KDE prototype.
- Physical button interaction, all mappings/actions, synthetic input, Bluetooth,
  haptics and MX Keypad hardware were not comprehensively verified.

This is not a Flathub submission. The manifest is AI-assisted; current
[Flathub requirements](https://docs.flathub.org/docs/for-app-authors/requirements)
prohibit AI-assisted manifests. Technical acceptance is also not established.
See [Flatpak permission documentation](https://docs.flatpak.org/en/latest/sandbox-permissions.html)
for the distinction between device exposure, host permissions and portals.
