"""Load checked-in public chain evidence into a migrated development database.

No network calls, no synthetic rows, and no automatic database creation.
"""

import argparse
import hashlib
import json
from pathlib import Path

from compute_market.db.models import RawBlock
from compute_market.db.session import SessionLocal
from compute_market.ingestion.chain.projector import instant
from compute_market.jobs.decode import decode_archived


def load_sample(directory: Path) -> dict:
    manifest = json.loads((directory / "manifest.json").read_text())
    for entry in manifest["files"]:
        path = (directory / entry["path"]).resolve()
        if not path.is_relative_to(directory.resolve()):
            raise ValueError("Fixture path escapes source directory")
        if hashlib.sha256(path.read_bytes()).hexdigest() != entry["sha256"]:
            raise ValueError(f"Fixture hash mismatch: {entry['path']}")
    verified = {entry["path"] for entry in manifest["files"]}
    heights = []
    for name in sorted(verified):
        if not name.startswith("block-") or not name.endswith(".json"):
            continue
        block = json.loads((directory / name).read_text())
        header = block["result"]["block"]["header"]
        chain_id, height = header["chain_id"], int(header["height"])
        if chain_id != manifest["chain_id"] or name != f"block-{height}.json":
            raise ValueError("Fixture block identity mismatch")
        result_name = f"results-{height}.json"
        if result_name not in verified:
            raise ValueError("Block result is missing from verified manifest")
        results = json.loads((directory / result_name).read_text())
        if int(results["result"]["height"]) != height:
            raise ValueError("Result height mismatch")
        with SessionLocal.begin() as session:
            existing = session.get(RawBlock, (chain_id, height))
            if existing:
                if (
                    existing.block_payload != block
                    or existing.results_payload != results
                ):
                    raise ValueError("Archived evidence conflicts with fixture")
            else:
                session.add(
                    RawBlock(
                        chain_id=chain_id,
                        height=height,
                        timestamp=instant(header["time"]),
                        block_payload=block,
                        results_payload=results,
                    )
                )
        heights.append(height)
    summary = {"complete_blocks": 0, "partial_blocks": 0, "actions": 0}
    for height in sorted(heights):
        result = decode_archived(manifest["chain_id"], height, height)
        for key in summary:
            summary[key] += result[key]
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, required=True)
    args = parser.parse_args()
    print(load_sample(args.directory))


if __name__ == "__main__":
    main()
