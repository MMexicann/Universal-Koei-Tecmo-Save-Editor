"""Private read-only development inspection; candidates are not registered editors."""

import argparse
import json
from koei_editor.research import imports


def main():
    parser = argparse.ArgumentParser(
        description="Inspect one explicit unregistered copied-save research profile."
    )
    parser.add_argument(
        "--profile", required=True, choices=tuple(imports.PROFILES)
    )
    parser.add_argument("copy")
    arguments = parser.parse_args()
    try:
        result = imports.inspect_copy(arguments.profile, arguments.copy)
        print(json.dumps(json.loads(result.report_json), indent=2, ensure_ascii=True))
    except (OSError, ValueError) as error:
        parser.exit(1, "Read-only research inspection failed: " + str(error) + "\n")


if __name__ == "__main__":
    main()
