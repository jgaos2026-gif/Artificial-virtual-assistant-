# Development Workstation, Source Control, Containers, Supabase, and Backup

**Status:** Stack boundary and implementation plan; no integrations are claimed by this document.

## 1. Intended division of responsibility

| Tool / service | Intended role | Must not become |
|---|---|---|
| **VS Code** | Development workstation for editing, debugging, tests, and reviewed automation | Privileged AVA runtime or authority for protected operations |
| **Git / GitHub** | Version control, code review, CI, tags, and release provenance | Only backup of application data, memory, keys, or operator configuration |
| **Docker / OCI** | Reproducible development/test environments and, if justified, controlled packaging | Substitute for host security controls or reason to run privileged containers |
| **Supabase** | Optional connected-service integration for approved non-sensitive metadata or synchronization | Identity root, key store, authorization authority, COLD archive, or external monotonic anchor |
| **Backup system** | Encrypted, versioned recovery copies of approved application data and configuration | Copy stored only on the same disk or under the same credentials as the source |

## 2. VS Code workstation

The repository currently has no checked-in VS Code workspace, task definitions, launch profiles, or development-container configuration.

Required setup work:
- Create a versioned workspace with explicit source and test folders.
- Define Python interpreter and test discovery settings.
- Add repeatable tasks for test collection, unit tests, formatting/linting, package build, and security checks after the tools are selected and pinned.
- Add debug profiles for unit tests and the local service after the runtime entry point exists.
- Recommend a minimal extension set; do not commit user-specific absolute paths.
- Keep secrets out of workspace settings, launch files, environment files, and source control.
- Document separate workflows for the Windows operator/development workstation and Linux target node.

## 3. Git and GitHub

The repository is public. As of the assessed main commit:
- PRs #13–#16 are merged into main.
- Main CI run #199 passed 98 tests on commit 373b7c8583b34fca06f1dd2966ea50ffb1242821.
- The main branch is not protected and the repository has no rulesets.
- There is no CODEOWNERS, SECURITY.md, or Dependabot configuration.
- There is no published GitHub release.

Required controls:
1. Protect main; disallow force pushes and deletion.
2. Require pull requests and successful required CI checks before merge.
3. Require owner review for security-sensitive changes.
4. Pin GitHub Actions to reviewed immutable commit SHAs and maintain them.
5. Add dependency update and vulnerability review.
6. Enable secret scanning and push protection where available; never commit tokens, keys, service-role secrets, or restricted data.
7. Generate an SBOM and signed release provenance for distributable builds.
8. Use version tags and retain release artifacts with checksums and signatures.
9. Maintain a separate encrypted source mirror. Git history is not a backup of local databases or runtime state.

## 4. Docker / OCI

No Dockerfile, Compose file, image build, or container security profile currently exists.

Recommended sequence:
- First define the actual runtime process and data directories.
- Build a development/test image from a pinned Python base image and a locked dependency set.
- Run as a non-root user; use a read-only root filesystem where practical; drop Linux capabilities; prohibit privileged mode and host networking; apply CPU, memory, PID, and filesystem limits.
- Mount only explicit data directories. Never bake secrets or private keys into images or image layers.
- Add image scanning, SBOM generation, digest pinning, and reproducible build evidence.
- Treat production containerization as a separate design decision. Host firewalling, AppArmor/SELinux, seccomp, cgroups, key custody, and offline enforcement remain host responsibilities.

Do not create a production Compose stack until service boundaries, persistent volumes, network policy, model runtime, and backup semantics are defined.

## 5. Supabase

There is no Supabase project configuration, schema, migration, or integration in this repository.

Before integration, decide whether Supabase is required for local AVA v1. Strict-offline operation must remain functional when Supabase and the internet are unavailable.

If an approved connected-mode use case requires Supabase:
- Use a separate project/environment for development and test.
- Define the exact data classes allowed to leave the local node.
- Use least-privilege access and row-level security for every exposed table.
- Keep service-role keys server-side only; never ship them in a desktop client, container image, repository, or logs.
- Store credentials in an approved secret manager or protected environment injection.
- Log synchronization events without copying protected content into telemetry.
- Treat remote data as untrusted input until local validation and provenance checks complete.
- Define conflict, replay, revocation, deletion, retention, and offline reconciliation semantics before enabling writes.

Supabase must not be the sole authority for AVA identity, signing keys, protected policy, COLD history, checkpoint trust, or independent anti-rollback state.

## 6. Backup and restore

No backup/restore implementation or restore-drill evidence is present in the repository.

The backup design must inventory and classify:
- Application configuration and versioned policy.
- Approved user/application data.
- COLD archive and lineage metadata.
- WARM data only if it is not safely reconstructible.
- Identity and checkpoint metadata.
- Clip Brick manifests, versions, and revocation state.
- Audit and recovery records.
- Database schemas and migrations for any connected service.

Controls:
1. Encrypt backups before they leave the source device.
2. Keep at least one offline copy and one separately controlled off-device copy.
3. Keep encryption and signing keys outside the backup set and outside the same failure domain.
4. Record backup version, source build, timestamp, content manifest, and cryptographic checksums.
5. Verify backups automatically and perform scheduled clean-host restore drills.
6. Restore into quarantine; verify identity, lineage, policy, and checkpoint before protected services resume.
7. Never silently overwrite newer or conflicting history during restore.
8. Document retention, deletion, recovery authorization, and emergency access.

A backup job that has never completed a restore test is not a proven recovery system.

## 7. First reproducible developer environment

The first container should be a **test/build environment**, not a production deployment:
- pinned Python runtime;
- locked development dependencies;
- non-root execution;
- deterministic test command;
- no secrets;
- no outbound network during tests unless a specific test requires it;
- build and test logs retained by CI.

After the local service, storage, and model interfaces are defined, add a separate integration environment. Keep production and development secrets, databases, and signing keys isolated.
