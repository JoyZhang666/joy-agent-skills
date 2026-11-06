# Optional CDN + WARP workflow

Version: 0.4.0. This optional route requires a managed domain; the default
no-owned-domain HY2 route is documented in [no-domain.md](no-domain.md).
The reference deployment has user-confirmed Windows/Android, YouTube and
subscription acceptance (2026-11-07). System-wide capture and timed playback
measurements are separate from that acceptance.

## Implemented

`scripts/cdn.py --values <private.json> --output <new-private-directory>` creates
`xray.json`, `caddy.json`, and `tunnel-client.yaml`. It does not install, start,
restart, or edit any services. Existing output directories are refused.

Private input fields: `domain` (lowercase ASCII FQDN), `uuid` (canonical UUID),
`ws_path` (slash plus 32–64 random hexadecimal characters), `xray_port` and
`warp_port` (distinct unprivileged ports). Generate credentials once and retain
the protected input for updates. Never print them into chat or command arguments.
Windows input/output directories require owner-restricted ACLs; POSIX files are
mode 0600 and the new output directory is 0700.

The client uses VMess AEAD over WebSocket and verified TLS on TCP 443. Group
`SILICON` selects `SILICON-CDN-WARP`. TUN is initially disabled: export does not
authorize or perform changes to the active client. Test an isolated explicit
proxy first, then enable and separately test the requested capture mode.

Optional private client fields, used only after testing the actual access network:

- `bootstrap_dns`: one to four distinct HTTPS DoH URLs with public IPv4 literals,
  in the form `https://<IPv4>/dns-query`. The legacy default is Cloudflare DoH;
  verify that it is reachable before choosing it. A resolver reachable only
  through the unavailable node cannot bootstrap that node. Select local-region
  DoH resolvers when the network requires them; do not put proxy suffixes here.
- `cdn_addresses`: one to four distinct public IPv4 CDN ingress addresses, in
  priority order. The generator checks address syntax, not CDN ownership or
  route quality. Verify current provider ranges, trusted domain TLS, WebSocket
  and full authenticated requests before including an address. Do not use the
  origin server's address. No deployed address is bundled into this public skill.
  Node names become `SILICON-CDN-WARP-A`, `-B`, etc.; two or more use a `SILICON`
  fallback group with 60-second health checks. The original domain remains both
  TLS server name and WebSocket Host; certificate verification stays enabled.
  Provider IP ownership and route quality can change, so this is not a permanent
  bypass guarantee or independent-host redundancy.

These options alter only the client YAML, not the generated Xray/Caddy contents.
Use `cdn.py` or `manage.py export` for client-only changes. Do not run `apply`
merely to export different edges: the current manager includes client contents
in its release hash and could otherwise create a new service revision.

Business TCP is routed through a loopback WARP SOCKS proxy. There is no freedom
outbound or direct fallback. UDP is rejected at the client and server.
The included `crossborder-warp.service` matches the tested official daemon version
2026.8.2115.0, running with its required host privileges. It is not a sandbox or
a network namespace. Verify the vendor package against its signed repository,
review dependency changes, and place the matching CLI/daemon at the versioned
path before provisioning the unit. Never run a second WARP daemon over an existing
installation. Register through the official CLI under the user's authorization,
set `mode proxy` and `proxy port 40000`, then connect; verify the listener is
loopback-only, `warp=on`, and host routes/resolver and existing services are unchanged.
The template alone does not register WARP or select proxy mode. Vendor terms and
mode behavior must be checked at installation time. Official installation reference:
https://developers.cloudflare.com/warp-client/get-started/linux/ .
Business DNS uses DoH through the SILICON group. Resolving the CDN node itself
uses the selected direct DoH bootstrap resolver(s); this is an explicit bootstrap
exception, not proof that all device DNS is tunneled. IPv6/TUN capture remains
a separate runtime acceptance item.

Caddy uses dedicated JSON configuration, admin disabled, HTTP/1.1 and HTTP/2
only, no automatic port-80 redirects. Certificate files are read from the
dedicated `/etc/crossborder-silicon/tls/` directory. Native Caddy validation needs
actual readable certificates. A synthetic certificate used for offline parsing
is never a deployment certificate.

## Deployment gates for each installation

1. Register the selected domain; retain proxied DNS from initial record creation.
2. Obtain trusted TLS using DNS-01 and a zone-restricted API token; Full (strict).
3. Install official WARP in local-proxy mode only; verify ordinary host routes
   and services remain unchanged. Stop WARP and confirm the node fails closed.
4. Install isolated units/accounts, scoped Cloudflare-source firewall rules,
   renewal hook and a validated rollback manifest. Do not reuse the shared
   Caddy service, disable host firewall, or change SSH/sysctl settings.
5. Complete public TLS/WS handshake, client GUI, egress/DNS/IPv6/UDP and playback
   tests. A native parser success is not connectivity or blocking resistance.

## Management CLI

Private deployment object shape (placeholders are not runnable values):

```json
{
  "domain": "edge.example.com",
  "uuid": "{{GENERATED_UUID}}",
  "ws_path": "{{GENERATED_WS_PATH}}",
  "xray_port": 18443,
  "warp_port": 40000,
  "binaries": {
    "xray": {"path": "/opt/crossborder/artifacts/xray", "sha256": "{{XRAY_SHA256}}"},
    "caddy": {"path": "/opt/crossborder/artifacts/caddy", "sha256": "{{CADDY_SHA256}}"}
  }
}
```

Use an owned domain only after choosing this optional route. Generate UUID and
random paths locally into the protected values file. Add optional `cdn_addresses`,
`bootstrap_dns` and `subscription_path` only after their respective checks. Never
replace the CDN address with the origin address to get a green latency result.

`scripts/manage.py <plan|apply|status|check|export|rollback> --deployment <private.json> --json`
uses the same private fields, plus `binaries.xray` and `binaries.caddy`, each
containing an absolute `path` and verified `sha256`. Export also takes `--output`.
The managed WARP port is 40000. Results always use redacted JSON.

Before apply, provision the dedicated `crossborder-silicon` system account/group,
root-owned `/opt/crossborder/silicon` directory (0750, service group), and the two
provided dedicated systemd units, then daemon-reload. Do not start or enable
them yet. Trusted certificates must be root-owned and service-group readable
at the documented paths. Check Cloudflare-only ingress rules before starting
the HTTPS service. This CLI does not install DNS, firewall, accounts or WARP.

`plan` verifies input and binary pins without changing services; it lists but
does not certify deployment prerequisites. `status` reports the active revision
and pending transaction. `check` tests each service, local origin HTTPS/TLS and the WARP exit; it does
not prove CDN, VMess authentication, GUI capture or video playback.

`apply` copies pinned binaries and private server configs to an immutable release,
validates as the service account, journals the old pointer, switches `current`,
and restarts only the two owned units. A failed check restores the previous
pointer and services. A failed recovery preserves the pending journal. Repeated
apply of the same revision checks health without restarting services.
`rollback` restores the recorded previous revision, or stops both new services
when no prior revision existed. It retains release files for investigation;
it does not delete dependencies, WARP registration, DNS, certificates or firewall
rules. These remain in the separately maintained provisioning/rollback manifest.

After interruption, inspect `pending.json` and use rollback before another apply.
Deployment and renewal mutations share a Linux flock; pending deployment recovery blocks certificate switching. Scheduled renewal also reconciles a previously issued certificate after a failed deploy hook. Test power-loss recovery
separately; callback tests are not a real systemd transaction acceptance.

## Reference and limits

Borrowed operational ideas: independent configuration, generation before apply,
explicit versions and convenient status/export. Independently implemented; no
GPL code copied from https://github.com/233boy/sing-box/tree/6082f1bf70ed4550a5fbd5c9fe147ba5228189d5 .

- Xray SOCKS: https://xtls.github.io/config/outbounds/socks.html
- Mihomo VMess: https://wiki.metacubex.one/config/proxies/vmess/
- WARP local proxy: https://developers.cloudflare.com/warp-client/warp-modes/
- CDN video/large-file limits: https://www.cloudflare.com/service-specific-terms-application-services/

CDN protects ingress; WARP changes egress. Neither guarantees anonymity,
unlimited video carriage or permanent access. First release targets personal
1080p testing on free resources, with domain fees separately authorized.

## Ingress and renewal resources

`firewall.py` builds only the named `inet crossborder_silicon` table from reviewed
Cloudflare IPv4/IPv6 CIDRs. Fetch official lists from https://www.cloudflare.com/ips-v4
and https://www.cloudflare.com/ips-v6, retain their timestamp and hash, run
`nft --check --file`, then install the file and dedicated oneshot unit. It only
filters port 443; loopback TCP is permitted, Cloudflare TCP sources are permitted,
other TCP and all UDP on that port are dropped. The caddy unit requires this
firewall unit. Cloud-provider security groups must independently allow the same
Cloudflare sources. Do not reset or flush other tables. Recheck ranges on upgrades.

`renew_cert.py` is a Certbot DNS-01 deploy hook. Provision the dedicated certificate
revision store and its `tls` symlink before use. It verifies expiry and key pairing,
validates Caddy configuration as its service account, and switches the certificate
pair through one symlink. A failed validation/restart restores the previous pair.
The provided timer checks twice daily with jitter; a scheduled check and a real
DNS-01 dry run must both be verified. Certbot's generic scheduling message does
not prove a custom config directory is covered by the timer. Record API-token
expiration and rotate it before expiry; this timer does not rotate credentials.

`probe.py --config <private-yaml> --mihomo <verified-binary> --sha256 <digest>
--interface <physical-interface> --negative-auth` starts an isolated core on
temporary local ports, keeps TUN off, checks HTTPS through the real node and WARP,
then replaces the UUID of every fallback node before the negative check.
Confirm the interface name locally (for example WLAN or Wi-Fi on Windows).
The flag binds only the test core. Without it, existing system routing/TUN may
carry the probe through another VPN, which does not prove direct access from
the user's network. The output explicitly records the selected binding.
It always terminates that test core. It accepts the generator's unchanged layout;
Windows temporary files inherit the private profile directory ACL. It does not
change the existing Clash subscription, system proxy or TUN. A successful probe
still requires GUI, capture mode, DNS/IPv6 and real video acceptance separately.

## Engineering evidence, 2026-11-06

The reference deployment passed nine public-line checks: valid VMess/WS/TLS through
CDN to WARP; wrong UUID and path denied; root URL 404 with trusted TLS; direct
origin HTTPS unavailable from the test host; WARP disconnection fails closed;
reconnection and dedicated service restart recover; existing services stay active.
The test host retained its existing TUN, so direct-origin unavailability alone
does not identify the packet-drop layer. Cloud and host source restrictions were
also independently read back.

Six isolated-core checks passed: TXT lookup, empty AAAA response, no UDP response,
observed UDP REJECT rule, observed DoH routing through the node, and DNS failure
with invalid tunnel authentication. These prove behavior of this explicit test
core, not system-wide DNS/IPv6 capture or absence of every possible leak.

A real renewal-timer trigger succeeded; the certificate was not due and no
renewal was attempted. A separate DNS-01 staging renewal dry run succeeded.
Later target-device testing contradicted direct-network readiness: node DNS
failed first, then connections timed out after a reachable bootstrap resolver
was selected. Several isolated core tests above had retained an existing TUN.
Alternative CDN addresses improved repeated physical-interface requests, but
occasional failures remained. Keep successes and failures in the acceptance
record; do not report a passing sample as a stable fix. Compare the same active
profile on both home broadband and cellular access, then test real applications.
Subsequent dual-entry repair was accepted by the user on Windows and Android,
including YouTube and subscription import/update, on 2026-11-07. System-wide
capture and a measured 30-minute playback test are not inferred from this report.
