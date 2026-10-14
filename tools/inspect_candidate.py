"""Private read-only development inspection; candidates are not registered editors."""

import argparse
import json
from koei_editor.research.arland_plus_vita import inspector as vita
from koei_editor.research.gundam2_ps3 import inspector as gundam


def main():
    parser = argparse.ArgumentParser(
        description="Inspect one explicit unregistered copied-save research profile."
    )
    parser.add_argument(
        "--profile", required=True, choices=tuple(vita.PROFILES) + ("gundam2_ps3",)
    )
    parser.add_argument("copy")
    arguments = parser.parse_args()
    try:
        if arguments.profile == "gundam2_ps3":
            report = gundam.inspect(gundam.read_save(arguments.copy))
        else:
            report = vita.inspect(vita.read_save(arguments.copy, arguments.profile))
        print(json.dumps(report, indent=2, ensure_ascii=True))
    except (OSError, ValueError) as error:
        parser.exit(1, "Read-only research inspection failed: " + str(error) + "\n")


if __name__ == "__main__":
    main()
