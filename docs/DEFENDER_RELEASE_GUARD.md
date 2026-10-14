# Defender verification and the withdrawn 2.0 release

Version 2.0 was withdrawn after a user reported
`Trojan:Win32/Sabsik.TE.A!ml` while downloading its standalone executable.
Its SHA-256 is
`2be5de88e333a3d7e839ae6cd4183d866cf063c8ae6542000b7a472d53cccc0c`.
The draft retains the original assets for investigation; they are not offered
as public downloads. The flagged executable is inspected statically, never run.

## Evidence and limits

The source changes, dependencies and exact executable were reviewed against
1.91. The native DLL/PYD blobs and runtime hooks are identical. Standard-library
module contents are identical; new application modules correspond to the
documented game adapters. The executable bootloader's code matches the official
hash-verified PyInstaller wheel. Both old releases are unsigned.

These findings do not determine why Defender's classifier flagged the download
and do not establish that its verdict is a false positive. Functional tests,
package privacy checks and matching download hashes are not antivirus scans.

Version 2.01 uses `--onedir --noupx`: the launcher loads its complete adjacent
runtime rather than unpacking a runtime into a temporary directory. The Windows
ZIP must be extracted completely, keeping `_internal` beside the launcher.
This is a distribution change, not an exception to antivirus protection.

Version 2.02 provides both the complete portable Windows ZIP and a separate
self-contained EXE. Both modes use `--noupx`, the same 90 profiles, and the same
required embedded notices. The direct EXE needs no side files and unpacks its
runtime temporarily when launched. The Windows ZIP contains only its versioned
application folder; users extract that entire folder, keeping `_internal`
beside its launcher. The Source ZIP retains developer documentation.

## Required Windows release checks

GitHub's Windows image installs Defender but disables protections and excludes
the C: and D: drives. The release scanner therefore verifies observed readiness;
installation or a successful preference write alone never establishes a scan.
On the isolated build runner it enables protection, removes inherited
exclusions, updates signatures and validates Microsoft cloud connectivity.

The scanner requires an active Normal-mode service/engine, real-time,
behavior, IOAV, script and archive protection, cloud reporting and signatures
updated within two days. The selected `MpCmdRun.exe` must have a valid Microsoft
Authenticode signature. Unavailable protection, cloud failure, stale signatures,
scan errors or detections block candidate publication.

Version 2.1 records and retries recognized Defender RPC startup failures during
preparation only. At most two complete configuration attempts share a bounded
120-second service/query settling budget. The report records the failed command,
exception codes and observed state. A pending service waits; only a stopped
service is started. During query settling after a recognized RPC restart,
Defender initialization response `0x800106BA` remains pending within the same
budget; it never permits a failed configuration or scan to qualify. After
successful queries, the complete protection and
signature configuration is replayed, followed by the same strict readiness,
Microsoft scanner signature, cloud, scan and unchanged-input requirements.
Persistent and nontransient failures still block publication.

Custom scans use `-Scan -ScanType 3 -File ... -DisableRemediation`. Microsoft
documents that this flag ignores file exclusions, scans archives and reports
detections without custom-scan remediation. Real-time protection remains active.
No exclusion is added, no protection is disabled, and no quarantined file is
restored. Native output and exit code are retained; code 2 can mean a detection
or a scan error and is never described automatically as a malware finding.

The complete portable runtime and standalone EXE must both pass their scans
before either binary is executed, including smoke tests and copied-save checks.
After packaging, the exact final direct EXE and both downloadable ZIPs are
scanned. Complete before/after file inventories and SHA-256 hashes must match
through every stage. Publication independently checks that successful reports,
all three downloadable asset hashes, application version and tested commit
agree. The downloadable `DefenderScan-v2.1.json` records that evidence only
after actual native scans pass. See [VALIDATION.md](VALIDATION.md) for the current
qualification status. Scanner diagnostics are retained
even if the build fails; an old-baseline diagnostic never qualifies a candidate.

All Windows build wheels are version- and hash-locked. CI force-reinstalls the
lock, then installs the local source without build isolation so an unpinned
build dependency is not fetched before qualification. Python is pinned to
3.14.7. Source/private-input and complete-runtime integrity checks remain active.

Defender results reflect the recorded engine, signatures, cloud state and files.
They cannot guarantee every future verdict or establish Microsoft's internal
classification rationale. If the reported detection persists, Microsoft can
review the exact public file/hash through its submission portal. Users should
not need an antivirus exclusion or disabled protection to use the release.

## References

- [Microsoft Defender command-line scan options](https://learn.microsoft.com/en-us/defender-endpoint/command-line-arguments-microsoft-defender-antivirus)
- [Block at first sight and cloud configuration](https://learn.microsoft.com/en-us/defender-endpoint/configure-block-at-first-sight-microsoft-defender-antivirus)
- [Detection investigation](https://learn.microsoft.com/en-us/defender-endpoint/defender-endpoint-false-positives-negatives)
- [Microsoft file submission](https://www.microsoft.com/en-us/wdsi/filesubmission)
- [Hosted runner Defender configuration](https://github.com/actions/runner-images/blob/main/images/windows/scripts/build/Configure-WindowsDefender.ps1)
- [PyInstaller operating modes](https://github.com/pyinstaller/pyinstaller/blob/v6.22.3/doc/operating-mode.rst)
