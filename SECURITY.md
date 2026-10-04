# Security policy

## Reporting

Please report vulnerabilities through
[GitHub private vulnerability reporting](https://github.com/jturbide/niri-fx/security/advisories/new)
when it is available for this repository. If that page is unavailable, open an
issue containing **only a request for a private reporting channel**, with no
vulnerability details, credentials or sensitive logs. Do not disclose an exploit
in a public issue while arranging private contact.

Include the affected version/commit, a minimal reproduction, expected impact and
whether the issue involves Studio, registry handling or the experimental Niri
patch. Remove personal data and live session tokens. This is a volunteer prototype;
there is no guaranteed response time. Fixes target the current development branch
and latest release; older prototype versions have no separate maintenance branches.

## Security boundaries

Studio binds to loopback and requires a per-session token and matching Origin for
write operations. It accepts validated effect parameters, not arbitrary shader
source or filesystem destinations. It writes the configured iNiR registry with
backup/atomic replacement and does not activate the saved preset. The separate
Library Review/Apply endpoints use conflict-aware configuration snapshots and
validate the resulting Niri config. Paths and executable choices are fixed at
launch; browser requests cannot supply them. Restore refuses external edits.
Hosted/offline Studio has no local activation endpoints. The editor
does not fetch external page resources. Treat its session URL as a local secret;
do not forward its port or embed it on an untrusted site.

The compositor patch is experimental code with access to rendered window content.
Keep it in the supplied nested demo until its capture, damage, scaling and
interruption behavior has broader validation. The supported stock effects do not
require that patch, a privileged service or an always-running daemon.

These controls and automated checks are not a formal security audit. For ordinary
rendering bugs, use the bug template and [troubleshooting guide](docs/troubleshooting.md).
