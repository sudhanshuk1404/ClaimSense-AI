import json
from pathlib import Path


def main() -> None:
    output = [
        {
            "claim_id": "CLM-2026-00391",
            "carc": "50",
            "procedure": "72148",
            "diagnosis": ["M54.5", "M51.16"],
            "recoverability_label": "needs_review",
        },
        {
            "claim_id": "CLM-2026-00412",
            "carc": "29",
            "procedure": "99213",
            "diagnosis": ["I10"],
            "recoverability_label": "not_recoverable",
        },
    ]
    destination = Path("data/synthetic/claims.json")
    destination.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(f"Wrote {destination}")


if __name__ == "__main__":
    main()

