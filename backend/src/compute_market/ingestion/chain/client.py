"""Archive RPC responses without assuming message versions or event semantics."""

from typing import Any
import httpx


class ChainClient:
    def __init__(self, base_url: str, client: httpx.Client):
        self.base_url = base_url.rstrip("/")
        self.client = client

    def request(self, method: str, height: int | None = None) -> dict[str, Any]:
        response = self.client.get(
            f"{self.base_url}/{method}",
            params={"height": str(height)} if height is not None else {},
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("error") or not isinstance(payload.get("result"), dict):
            raise ValueError(
                f"RPC {method} failed: {payload.get('error', 'missing result')}"
            )
        return payload

    def latest_height(self) -> int:
        return int(self.request("status")["result"]["sync_info"]["latest_block_height"])

    def block_pair(self, chain_id: str, height: int) -> tuple[dict, dict]:
        block = self.request("block", height)
        results = self.request("block_results", height)
        header = block["result"]["block"]["header"]
        if (
            header["chain_id"] != chain_id
            or int(header["height"]) != height
            or int(results["result"]["height"]) != height
        ):
            raise ValueError("RPC returned mismatched chain or height")
        txs = block["result"]["block"].get("data", {}).get("txs") or []
        tx_results = results["result"].get("txs_results") or []
        if len(txs) != len(tx_results):
            raise ValueError(
                "Block transactions and execution results do not reconcile"
            )
        return block, results
