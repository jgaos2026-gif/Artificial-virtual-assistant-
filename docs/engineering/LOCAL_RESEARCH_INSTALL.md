# Local Research Foundation Install

**Status:** limited foundation installer, not a complete AVA/OASIS deployment.

## Scope

The Windows and Linux scripts create a Python virtual environment in a separate runtime directory and install this repository in editable mode. They install no service, network listener, firewall rule, model, privileged component, authority service, or autonomous recovery mechanism. The installer refuses a non-empty runtime directory. It does not delete, reset, or migrate an existing runtime.

Requirements: Python 3.11 or newer, local source checkout, and pip/setuptools available to the interpreter. The package currently declares no runtime dependencies.

## Windows

From the repository root in PowerShell:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\install.ps1
```

Optional explicit paths:

```powershell
.\scripts\install.ps1 -Source "C:\Users\JaysG\JGA\oasis" -Runtime "C:\Users\JaysG\JGA\OASIS-Research-Runtime"
```

## Linux

From the repository root:

```bash
bash scripts/install.sh "$HOME/JGA/OASIS-Research-Runtime"
```

## Read-only diagnostics

```powershell
.\.venv\Scripts\python.exe -m ava_military.doctor --source . --runtime "$env:USERPROFILE\JGA\OASIS-Research-Runtime"
```

The doctor reports package/environment facts only. It does not verify OS isolation, network policy, keys, witness independence, storage durability, backup restorability, or integrated OASIS behavior.

## What this install does not provide

- AVA process lifecycle, UI, model adapter, authenticated IPC, or three running rooms.
- Universal Braid live handshake or Clip Brick adapter runtime.
- Production SB688 quarantine/recovery, external monotonic anchor, or independently operated SB712 quorum.
- Windows Job Object enforcement, Linux MAC/seccomp/cgroup policy, or strict-offline host enforcement.
- COLD/WARM/HOT integrated memory stores, encrypted/off-device backup, or a restore drill.
- Signed release, lockfile, SBOM, release provenance, installer upgrade/rollback/uninstall, or independent security review.

Those remain explicit release gates. A successful foundation install must not be described as AVA/OASIS production readiness.
