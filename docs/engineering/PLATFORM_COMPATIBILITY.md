# Multi-Platform and Linux Distribution Compatibility

**Status:** compatibility architecture and qualification plan. No distribution is certified or installer-supported by this document.

## 1. Compatibility objective

AVA's reference package should remain portable across supported Python 3 environments. The eventual OASIS node should support multiple Linux distribution families without embedding package-manager assumptions in the application core.

Compatibility is not the same as a universal installer. Kernel, init system, mandatory-access-control framework, firewall tooling, libc, filesystem, boot mode, and package manager differ. Each target must pass the same acceptance suite using a distribution-specific adapter.

## 2. Platform support classes

| Platform | Intended role | Current status |
|---|---|---|
| Ubuntu LTS (systemd, glibc) | First Linux qualification target | NOT QUALIFIED |
| Debian stable (systemd, glibc) | First Linux qualification target | NOT QUALIFIED |
| Fedora (systemd, glibc) | Secondary Linux qualification target | NOT QUALIFIED |
| RHEL-compatible distributions (systemd, glibc) | Secondary Linux qualification target | NOT QUALIFIED |
| openSUSE Leap / Tumbleweed (systemd, glibc) | Candidate Linux qualification target | NOT QUALIFIED |
| Arch Linux (systemd, glibc) | Community/developer candidate, rolling-release qualification required | NOT QUALIFIED |
| Alpine Linux (OpenRC commonly; musl) | Separate compatibility target; requires musl and init-system testing | NOT QUALIFIED |
| Windows | Development/operator workstation only | Existing CI coverage must be established before claiming compatibility |
| macOS | Development/operator workstation only | Existing CI coverage must be established before claiming compatibility |

The current repository has no installer, service, runtime, or OS enforcement layer. The table is a qualification plan, not a claim that these platforms already work.

## 3. Portability rules for the application core

1. Keep application logic in Python and standard-library interfaces wherever practical.
2. Do not call apt, dpkg, dnf, rpm, zypper, pacman, apk, systemctl, ufw, firewalld, nft, or iptables from core application modules.
3. Put OS-specific operations behind small, typed platform adapters with explicit capability detection.
4. Detect the platform from structured OS metadata and executable/capability checks. Never infer it from a display name alone.
5. Treat unknown distributions, unsupported init systems, missing security controls, and ambiguous capabilities as unsupported. Fail closed for security-critical setup.
6. Do not silently substitute a weaker control. For example, absence of SELinux/AppArmor must be reported, not treated as equivalent enforcement.
7. Keep configuration, data, cache, logs, runtime sockets, and secrets in separate paths with explicit ownership and permissions.
8. Do not assume /bin/bash, GNU-only command flags, a particular filesystem, or a writable system Python environment.
9. Use a dedicated virtual environment or a reproducible package artifact. Never modify the host's system Python packages.
10. Keep the Windows development environment separate from the Linux target's security boundary.

## 4. Distribution adapter contract

The future installer and host-hardening layer must expose capability-based adapters for:

- Package installation and verification.
- Service manager lifecycle (systemd first; OpenRC only after separate implementation and tests).
- Firewall and egress policy.
- Mandatory access control (SELinux, AppArmor, or an explicitly documented unsupported state).
- User/group and filesystem permission management.
- Storage and filesystem capability checks.
- CPU, memory, process, and disk quotas.
- Boot-time activation and recovery.
- Package removal, rollback, and post-install health checks.

Each adapter must declare detected capabilities, supported operations, required privileges, side effects, rollback behavior, and evidence artifacts. A distro name must never imply that every control is active.

## 5. Qualification matrix

A platform is not supported until all applicable gates pass on a clean VM or physical target:

| Gate | Required evidence |
|---|---|
| Runtime | Python version, architecture, libc, kernel, init system, filesystem, and OS release captured |
| Install | Clean install succeeds from a versioned artifact with no manual repair |
| Least privilege | Service account, groups, file ownership, and permission-denial tests pass |
| Service lifecycle | Start, stop, restart, reboot persistence, crash recovery, and uninstall pass |
| Network | Host-level default-deny/allow-list behavior verified; packet capture shows no unauthorized egress |
| MAC / sandbox | Actual SELinux/AppArmor/seccomp state recorded and negative tests pass; unsupported controls remain explicit |
| Resources | CPU, RAM, PID, and disk limits enforced and exhaustion behavior tested |
| Storage | Disk-full, read-only, corruption, and interrupted-write tests pass on the target filesystem |
| Recovery | Upgrade, rollback, backup restore, and clean-host recovery pass |
| Security | Dependency scan, static checks, secret scan, and platform-specific configuration review pass |
| Evidence | Raw logs, package hashes, configuration snapshots, test results, and target details retained |

A successful Ubuntu run does not qualify Debian, Fedora, Alpine, or another distribution. Each distribution family requires its own run; each materially different init, libc, or MAC path requires separate evidence.

## 6. Build and release strategy

- Keep one platform-neutral Python package and a common acceptance-test contract.
- Build separate, reproducible installation artifacts only where native packaging requires them.
- Use distribution-specific packaging adapters rather than branching the application core.
- Pin dependencies and build inputs; generate an SBOM and sign release artifacts.
- Publish an explicit support matrix with tested distro version, architecture, kernel, Python version, filesystem, and known exclusions.
- Keep the first release scope small: one Debian-family target and one Red Hat-family target. Expand only after both pass the complete gate.
- Treat Alpine/musl and non-systemd support as separate engineering work, not a checkbox.

## 7. Current blockers

The repository currently has no OASIS service, installer, OS adapter, firewall integration, MAC profile, container build, backup/restore utility, or platform qualification tests. The existing 98-test result is reference-component evidence only and does not establish multi-OS compatibility.

The first implementation milestone should add:
1. A platform inventory command that is read-only and reports capabilities without changing the host.
2. A common installer interface with explicit dry-run and plan output.
3. Debian-family and Red Hat-family adapters, each independently tested.
4. A systemd service only after the runtime entry point and service account are defined.
5. A clean-VM matrix with install, lifecycle, denial, rollback, and uninstall evidence.

Do not write or execute a privileged installer until the runtime paths, service identity, package contents, upgrade semantics, and rollback boundary are frozen and reviewed.
