"""`python -m rubricator`. One line, so the entry point and the CLI cannot drift."""

import sys

from rubricator.cli import main

if __name__ == "__main__":
    sys.exit(main())
