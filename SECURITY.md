# Security policy

## Reporting

Please report vulnerabilities through
[GitHub private vulnerability reporting](https://github.com/jturbide/niri-fx/security/advisories/new)
when it is available for this repository. If that page is unavailable, open an
issue containing **only a request for a private reporting channel**, with no
vulnerability details, credentials or sensitive logs. Do not disclose an exploit
in a public issue while arranging private contact.

Include the affected version/commit, a minimal reproduction, expected impact and
whether the issue involves Studio, configuration handling or the NiriFX
compositor. Remove personal data and live session tokens. This is a volunteer project;
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
Current source limits imported recipe documents to 32 KiB (16 KiB in 0.20).
Continuous-fragment recipes contain validated numeric controls and fixed choices,
not shader source, SVG paths or executable content.
Hosted/offline Studio has no local activation endpoints. The editor
does not fetch external page resources. Treat its session URL as a local secret;
do not forward its port or embed it on an untrusted site.

The NiriFX compositor has access to rendered window content. Its
[managed session](docs/native-session.md) keeps a separate compositor and
configuration, with reviewed selection and rollback. Live Apply in that session
requires a verified matching renderer; build identity alone does not
establish capture privacy. Physical capture, mixed-output and recovery acceptance
remain incomplete; see the [native validation limits](docs/validation.md).
Keep stock Niri available as a recovery path. Stock effects do not require the
NiriFX compositor, a privileged service or an always-running daemon.

These controls and automated checks are not a formal security audit. For ordinary
rendering bugs, use the bug template and [troubleshooting guide](docs/troubleshooting.md).
