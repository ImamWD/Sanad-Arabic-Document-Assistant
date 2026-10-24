"""Print the OpenAPI spec without starting a server.

Usage: `python -m sanad.api.openapi > openapi.json`
"""

import json
import sys

from sanad.api.main import app


def main() -> None:
    json.dump(app.openapi(), sys.stdout, ensure_ascii=False, indent=2, sort_keys=True)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
