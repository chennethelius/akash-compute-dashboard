"""Decode already archived evidence, preserving partial coverage explicitly."""

from datetime import datetime, timezone
from sqlalchemy import text

from compute_market.db.models import BlockProjection, RawBlock
from compute_market.db.session import SessionLocal
from compute_market.ingestion.chain.projector import project_actions


def decode_archived(chain_id: str, start: int, end: int) -> dict:
    from compute_market.ingestion.chain.decoder import DECODER_VERSION, decode_block

    if start < 1 or end < start:
        raise ValueError("Expected a positive bounded height range")
    summary = {"complete_blocks": 0, "partial_blocks": 0, "actions": 0}
    for height in range(start, end + 1):
        with SessionLocal.begin() as session:
            if session.bind.dialect.name == "postgresql":
                session.execute(
                    text("SELECT pg_advisory_xact_lock(hashtext(:name))"),
                    {"name": f"projection:{chain_id}"},
                )
            raw = session.get(RawBlock, (chain_id, height))
            if raw is None:
                raise ValueError(
                    f"Block {height} is not archived; archive it before decoding"
                )
            result = decode_block(
                chain_id, height, raw.block_payload, raw.results_payload
            )
            issues = list(result["issues"])
            issues.extend(
                project_actions(session, chain_id, result["actions"], DECODER_VERSION)
            )
            status = (
                "partial" if issues or result["status"] != "complete" else "complete"
            )
            report = session.get(BlockProjection, (chain_id, height, DECODER_VERSION))
            if report is None:
                report = BlockProjection(
                    chain_id=chain_id, height=height, decoder_version=DECODER_VERSION
                )
                session.add(report)
            report.status = status
            report.issues = issues
            report.event_count = len(result["actions"])
            report.projected_at = datetime.now(timezone.utc)
            raw.decoder_version = DECODER_VERSION
            summary[f"{status}_blocks"] += 1
            summary["actions"] += len(result["actions"])
    return summary
