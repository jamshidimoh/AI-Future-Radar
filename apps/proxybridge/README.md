# ProxyBridge

ProxyBridge is a free, open-source Windows utility for managing one proxy configuration across Windows, Chrome, and (optionally) a real VPN/TUN engine.

## What it does

- Serves a local PAC endpoint at `http://127.0.0.1:8787/proxy.pac`.
- Enables/disables the Windows Internet (WinINet) proxy using that PAC and imports the same settings into WinHTTP.
- Provides a small Chrome MV3 extension that can apply the same PAC directly in Chrome.
- Can launch `sing-box` for a real TUN/VPN mode when you provide a valid sing-box configuration.
- Keeps a backup of Windows proxy settings so the previous state can be restored.
- Has no telemetry, paid API dependency, or bundled subscription service.

## Important: free software is not a free VPN service

A client can be completely free, but a real VPN still needs an upstream/server or a working user-owned remote configuration. ProxyBridge does not invent or provide an anonymous free VPN network. For a genuinely system-wide VPN, use a valid WireGuard/OpenVPN/Hysteria2/VLESS or other sing-box-compatible configuration.

The PAC/System Proxy mode is useful for HTTP/HTTPS-aware applications. It is not equivalent to a kernel-level VPN and does not automatically capture applications that bypass system proxy settings or use arbitrary UDP/TCP sockets.

## Windows build

Requirements: Go 1.23.x or newer.

```powershell
$env:GOOS='windows'
$env:GOARCH='amd64'
go build -trimpath -ldflags '-s -w' -o dist\ProxyBridge.exe .\cmd\proxybridge
```

Or run:

```powershell
.\scripts\build-windows.ps1
```

Start the local dashboard:

```powershell
.\dist\ProxyBridge.exe
```

Then open `http://127.0.0.1:8787/`.

For Windows system-proxy changes, run ProxyBridge with appropriate Windows permissions.

## Chrome

1. Open `chrome://extensions`.
2. Enable **Developer mode**.
3. Select **Load unpacked**.
4. Choose the `extension` directory.
5. Click the ProxyBridge extension and enable it.

The default PAC URL is `http://127.0.0.1:8787/proxy.pac`.

## TUN / real VPN mode

ProxyBridge deliberately delegates the VPN/TUN data plane to `sing-box` instead of implementing a packet engine itself.

Run:

```powershell
.\scripts\bootstrap-singbox.ps1
```

This downloads the pinned Windows x64 sing-box release and verifies its SHA-256 before extraction.

Then provide a valid sing-box configuration in the dashboard and start **TUN**. Windows TUN operation generally requires Administrator privileges.

The sample configuration in `configs/sample-http-proxy-singbox.json` is only a protocol/example configuration; an HTTP proxy is not a full VPN replacement. Supply your own valid remote configuration for real TUN use.

## Architecture

```text
Chrome ──┐
         ├── local PAC ──> upstream HTTP/HTTPS proxy
Windows ─┘

Windows apps that bypass System Proxy ──> sing-box TUN ──> your configured upstream
```

## Security and privacy

ProxyBridge itself does not collect telemetry. However, the upstream proxy/server you configure can observe traffic that passes through it. Do not use an upstream you do not trust for sensitive traffic.

## License

ProxyBridge source code is MIT licensed. `sing-box` is a separate project under GPL-3.0-or-later; its license applies to that component and distribution.
