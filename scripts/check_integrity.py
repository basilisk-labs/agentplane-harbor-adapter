from __future__ import annotations

import json
import sys
from pathlib import Path

FORBIDDEN_NAMES = {
    "oracle",
    "solution",
    "solutions",
    "tests",
    "hidden_tests",
    "reward",
}


def main() -> int:
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    proof_files = list(root.rglob("proof.json"))
    if not proof_files:
        print("no proof.json files found", file=sys.stderr)
        return 1

    failed = False
    for proof_file in proof_files:
        data = json.loads(proof_file.read_text())
        integrity = data.get("integrity", {})
        for key, value in integrity.items():
            ok = value is True if key == "generic_policy_only" else value is False
            if not ok:
                print(f"integrity flag failed: {proof_file}: {key}={value}", file=sys.stderr)
                failed = True

    for path in root.rglob("*"):
        lowered = path.name.lower()
        if lowered in FORBIDDEN_NAMES and ".agentplane-harbor" in path.parts:
            print(f"forbidden artifact name in proof bundle: {path}", file=sys.stderr)
            failed = True

    if failed:
        return 1

    print(f"checked {len(proof_files)} proof bundle(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
