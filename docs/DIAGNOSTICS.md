# Toolkit diagnostics

Open **Help → Toolkit diagnostics**, or search for it with **Ctrl+K**. The panel
collects a small local support report without opening saves, scanning installed
games or contacting a service. **Refresh** recollects the report. **Copy report**
copies the visible JSON; **Export new JSON…** writes it to a new filename without
overwriting an existing file. Choose an existing folder; file and directory
aliases are refused. Review the report before sharing it.

The same report is available through the [CLI](CLI.md):

```text
universal-koei-toolkit diagnostics --json
```

The report contains the Toolkit and Python versions, source/frozen mode, OS family,
architecture, registered profile/platform/route counts and five asset-preview
dependency versions. Missing optional dependency metadata is reported explicitly;
metadata presence does not prove that a native decoder can load. It records no
personal paths, installation folders, usernames, account identifiers, environment
variables, exception text, save contents or logs. Nothing is uploaded.

Save Vault and Playthrough Profiles require Windows even from source. A supported
platform indication is not a filesystem readiness certificate: destination-specific
checks still apply. This report does not certify CNG, codec behavior, edited saves
or converted saves loading in a game. See [validation](VALIDATION.md).
