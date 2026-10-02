"""Captured chain evidence plus controlled malformed/failed execution cases."""

import copy
import json
from pathlib import Path

import pytest

from compute_market.ingestion.chain.decoder import decode_block, wire

FIXTURES = Path(__file__).parent / "fixtures" / "akash"


def captured():
    return tuple(
        json.loads((FIXTURES / f"{name}-28879982.json").read_text())
        for name in ("block", "results")
    )


def test_captured_deployment_resources_and_failed_tx_exclusion():
    block, results = captured()
    decoded = decode_block("akashnet-2", 28879982, block, results)
    order = next(a for a in decoded["actions"] if a["kind"] == "order_created")
    resources = order["payload"]["resources"]
    assert resources["gpu_model"] == "p40"
    assert resources["gpu_count"] == 1
    assert resources["cpu_units"] == 8000
    assert resources["memory_bytes"] == 68719476736
    assert resources["storage_bytes"] == 64424509440
    assert (
        order["tx_hash"]
        == "EA06BDB6F60044FCC15D816B9D570776AAD3FC0BA9D6128F843AA0E5DC6BFD8E"
    )
    assert all(a["tx_index"] != 3 for a in decoded["actions"])
    assert decoded["status"] == "complete"
    for tx in FIXTURES.glob("tx-EA06*.json"):
        rest = json.loads(tx.read_text())
        group = rest["tx"]["body"]["messages"][0]["groups"][0]
        assert resources["gpu_count"] == int(
            group["resources"][0]["resource"]["gpu"]["units"]["val"]
        )


def event(kind, identity, price=None):
    attrs = [
        {"key": "id", "value": json.dumps(identity)},
        {"key": "msg_index", "value": "0"},
    ]
    if price:
        attrs.append(
            {"key": "price", "value": json.dumps({"amount": price, "denom": "uact"})}
        )
    return {"type": "akash.market.v1.Event" + kind, "attributes": attrs}


def test_event_order_exact_price_selected_provider_and_failed_events():
    block, results = captured()
    results = copy.deepcopy(results)
    identity = dict(owner="owner", dseq="10", gseq=1, oseq=2, provider="winner", bseq=3)
    expected_price = "0.123456789012345678"
    lifecycle = [
        event("BidCreated", identity, expected_price),
        event("LeaseCreated", identity, expected_price),
        event("LeaseClosed", identity),
    ]
    results["result"]["txs_results"][0]["events"] = lifecycle
    results["result"]["txs_results"][3]["events"] = [
        event("BidCreated", dict(identity, provider="failed"), "1")
    ]
    decoded = decode_block("akashnet-2", 28879982, block, results)
    assert [a["kind"] for a in decoded["actions"]] == [
        "bid_created",
        "lease_created",
        "lease_closed",
    ]
    assert decoded["actions"][1]["payload"]["id"]["provider"] == "winner"
    assert decoded["actions"][1]["payload"]["id"]["bseq"] == 3
    assert decoded["actions"][1]["payload"]["price"]["amount"] == expected_price


def test_invalid_price_and_unknown_versions_report_partial():
    block, results = captured()
    identity = dict(owner="o", dseq="1", gseq=1, oseq=1, provider="p")
    results["result"]["txs_results"][0]["events"] = [
        event("BidCreated", identity, "NaN"),
        {"type": "akash.market.v9.EventNewThing", "attributes": []},
    ]
    decoded = decode_block("akashnet-2", 28879982, block, results)
    assert decoded["status"] == "partial"
    assert decoded["actions"] == []
    assert {i["reason"] for i in decoded["issues"]} == {
        "invalid_event",
        "unsupported_event",
    }


def test_identity_mismatch_and_truncated_protobuf_fail():
    block, results = captured()
    with pytest.raises(ValueError, match="identity"):
        decode_block("other-chain", 28879982, block, results)
    for raw in (b"\x0a\x08abc", b"\x80", b"\x00", b"\x0b"):
        with pytest.raises(ValueError):
            wire(raw)


def test_captured_real_selected_lease_and_close_lifecycle():
    def decode_height(height):
        payloads = [
            json.loads((FIXTURES / f"{name}-{height}.json").read_text())
            for name in ("block", "results")
        ]
        return decode_block("akashnet-2", height, *payloads)

    lease = next(
        a for a in decode_height(28879989)["actions"] if a["kind"] == "lease_created"
    )
    assert lease["payload"]["price"] == {
        "amount": "4.000000000000000000",
        "denom": "uact",
    }
    assert lease["payload"]["id"]["provider"].startswith("akash1")
    closes = decode_height(28879984)
    assert {a["kind"] for a in closes["actions"]} >= {
        "deployment_closed",
        "group_closed",
        "order_closed",
        "bid_closed",
        "lease_closed",
    }
    assert closes["status"] == "complete"


def test_close_reason_phase_and_group_identity_validation():
    block, results = captured()
    identity = dict(owner="o", dseq="1", gseq=1, oseq=1, provider="p", bseq=0)
    closed = event("LeaseClosed", identity)
    closed["attributes"].append(
        {"key": "reason", "value": '"lease_closed_reason_owner"'}
    )
    results["result"]["begin_block_events"] = [closed]
    group = {
        "type": "akash.deployment.v1.EventGroupClosed",
        "attributes": [{"key": "id", "value": json.dumps({"owner": "o", "dseq": "1"})}],
    }
    results["result"]["end_block_events"] = [group]
    decoded = decode_block("akashnet-2", 28879982, block, results)
    first = decoded["actions"][0]
    assert first["phase"] == "begin_block"
    assert first["tx_index"] is None
    assert first["payload"]["close_reason"] == "lease_closed_reason_owner"
    assert any(i["reason"] == "invalid_event" for i in decoded["issues"])


def test_malformed_transaction_resource_bytes_are_visible():
    import base64

    block, results = captured()
    block["result"]["block"]["data"]["txs"][0] = base64.b64encode(
        b"\x0a\x08abc"
    ).decode()
    decoded = decode_block("akashnet-2", 28879982, block, results)
    assert decoded["status"] == "partial"
    assert any(
        i["reason"] == "invalid_transaction_resources" for i in decoded["issues"]
    )
    order = next(a for a in decoded["actions"] if a["kind"] == "order_created")
    assert "resources" not in order["payload"]


def test_replica_weighting_and_ambiguous_models_stay_unknown():
    from compute_market.ingestion.chain.decoder import deployment_message

    def varint(value):
        output = bytearray()
        while value >= 128:
            output.append((value & 127) | 128)
            value >>= 7
        output.append(value)
        return bytes(output)

    def field(number, value):
        if isinstance(value, int):
            return varint(number << 3) + varint(value)
        if isinstance(value, str):
            value = value.encode()
        return varint(number << 3 | 2) + varint(len(value)) + value

    def attribute(model):
        return field(1, "vendor/nvidia/model/" + model) + field(2, "true")

    def unit(models, count):
        gpu = field(1, field(1, "2")) + b"".join(
            field(2, attribute(model)) for model in models
        )
        resource = field(5, gpu)
        return field(1, resource) + field(2, count)

    group = field(1, "group") + field(3, unit(["h100", "a100"], 3))
    message = field(1, field(1, "owner") + field(2, 1)) + field(2, group)
    parsed = deployment_message(message)["groups"][0]
    assert parsed["gpu_count"] == 6
    assert parsed["gpu_model"] is None
    assert len(parsed["attributes"]["resource_units"][0]["gpu_count_attributes"]) == 2


def test_captured_gpu_auction_two_bids_and_actual_selected_lease():
    actions = []
    for height in range(28860258, 28860262):
        payloads = [
            json.loads((FIXTURES / f"{name}-{height}.json").read_text())
            for name in ("block", "results")
        ]
        decoded = decode_block("akashnet-2", height, *payloads)
        assert decoded["status"] == "complete"
        actions.extend(decoded["actions"])
    order = next(a for a in actions if a["kind"] == "order_created")
    resources = order["payload"]["resources"]
    assert (
        resources["gpu_model"],
        resources["gpu_count"],
        resources["cpu_units"],
        resources["memory_bytes"],
        resources["storage_bytes"],
    ) == ("rtx3090", 1, 4000, 17179869184, 53687091200)
    bids = [a for a in actions if a["kind"] == "bid_created"]
    assert [b["payload"]["price"]["amount"] for b in bids] == [
        "282.496994000000000000",
        "265.753915000000000000",
    ]
    assert all(b["payload"]["price"]["denom"] == "uact" for b in bids)
    lease = next(a for a in actions if a["kind"] == "lease_created")
    assert (
        lease["payload"]["id"]["provider"]
        == "akash1p5qkxeu3hcxzx9nvfvva93pyvxcyqduly9udz9"
    )
    assert lease["payload"]["price"]["amount"] == "265.753915000000000000"
    assert lease["height"] == 28860261
