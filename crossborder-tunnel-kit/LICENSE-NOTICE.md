# License and third-party notice

This package is authored and maintained by JoyZhang666 and released under the [MIT License](LICENSE).

Hysteria, sing-box, Xray-core and Mihomo are separately distributed upstream projects with their own licenses. This package contains original instructions, configuration templates and Python helpers; it does not bundle upstream source code or executables. Official links and version scope are listed in [sources](references/sources.md). No upstream endorsement is claimed.

Operational design was informed by 233boy/sing-box (GPL-3.0), reviewed at commit
6082f1bf70ed4550a5fbd5c9fe147ba5228189d5. No source code from that project is
copied or bundled. The management helpers here were independently implemented
against official component interfaces. See references/cdn-warp.md for provenance.

Caddy, OpenSSL and Cloudflare WARP are external dependencies with their own
licenses or service terms; they are not bundled or relicensed here. The explicit
integration-test downloader fetches fixed official Hysteria and Mihomo binaries
into a separate temporary directory and verifies their SHA-256 values. Downloaded
binaries and generated test certificates are excluded from the Skill archive.
