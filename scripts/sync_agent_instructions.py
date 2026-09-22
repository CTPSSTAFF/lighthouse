"""Mirror the shared baseline into Copilot's portable repository entry point."""

import argparse
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Fail if the copy is stale")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    source = root / "AGENTS.md"
    target = root / ".github" / "copilot-instructions.md"
    expected = source.read_bytes()
    if args.check:
        if not target.exists() or target.read_bytes() != expected:
            parser.exit(1, "Copilot instructions are stale; run this script without --check.\n")
        print("Agent instructions are synchronized.")
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(expected)
    print("Updated .github/copilot-instructions.md from AGENTS.md.")


if __name__ == "__main__":
    main()
