"""Version-limited decoding of archived successful Akash execution events.

Schemas: akash-network/chain-sdk commit 452904e69a35d80291bc7c24fda6477ed64c9445
proto/node/akash/{market/v1/event.proto,
deployment/v1/event.proto,deployment/v1beta{3,4}/deploymentmsg.proto}.
Resource extraction reads the original protobuf bytes, not current chain state.
Unknown event/message versions remain explicit coverage issues.
"""

import base64
import hashlib
import json
import re
from decimal import Decimal

DECODER_VERSION = "akash-typed-v1-resources-v1"
EVENTS = {
    "akash.market.v1.EventOrderCreated": "order_created",
    "akash.market.v1.EventOrderClosed": "order_closed",
    "akash.market.v1.EventBidCreated": "bid_created",
    "akash.market.v1.EventBidClosed": "bid_closed",
    "akash.market.v1.EventLeaseCreated": "lease_created",
    "akash.market.v1.EventLeaseClosed": "lease_closed",
    "akash.deployment.v1.EventDeploymentCreated": "deployment_created",
    "akash.deployment.v1.EventDeploymentClosed": "deployment_closed",
    "akash.deployment.v1.EventGroupClosed": "group_closed",
}
CREATE_TYPES = {
    f"/akash.deployment.{v}.MsgCreateDeployment" for v in ("v1beta3", "v1beta4")
}


class WireFields(dict):
    """Wire types retained so known fields cannot be interpreted as another type."""

    def __init__(self):
        super().__init__()
        self.encodings = {}


def wire(data: bytes) -> dict[int, list]:
    """Read protobuf wire fields, rejecting truncation and unsupported wire types."""
    if not isinstance(data, bytes):
        raise ValueError("Protobuf message must be length-delimited bytes")
    fields = WireFields()
    position = 0

    def integer():
        nonlocal position
        result = 0
        for shift in range(0, 70, 7):
            if position >= len(data):
                raise ValueError("Truncated protobuf varint")
            byte = data[position]
            position += 1
            result |= (byte & 127) << shift
            if byte < 128:
                if result >= 2**64:
                    raise ValueError("Protobuf varint exceeds uint64")
                return result
        raise ValueError("Oversized protobuf varint")

    while position < len(data):
        tag = integer()
        number, encoding = tag >> 3, tag & 7
        if number == 0 or number >= 2**29:
            raise ValueError("Invalid protobuf field zero")
        if encoding == 0:
            value = integer()
        elif encoding in (1, 2, 5):
            length = integer() if encoding == 2 else (8 if encoding == 1 else 4)
            if position + length > len(data):
                raise ValueError("Truncated protobuf field")
            value = data[position : position + length]
            position += length
        else:
            raise ValueError(f"Unsupported protobuf wire encoding {encoding}")
        fields.setdefault(number, []).append(value)
        fields.encodings.setdefault(number, []).append(encoding)
    return fields


def one(fields, number, default=b""):
    expected = 0 if isinstance(default, int) else 2
    if number in fields and any(
        value != expected for value in fields.encodings[number]
    ):
        raise ValueError(f"Wrong protobuf wire type for field {number}")
    values = fields.get(number, [default])
    if len(values) != 1:
        raise ValueError(f"Duplicate singular protobuf field {number}")
    return values[0]


def repeated(fields, number):
    if any(encoding != 2 for encoding in fields.encodings.get(number, [])):
        raise ValueError(f"Wrong protobuf wire type for repeated field {number}")
    return fields.get(number, [])


def attributes(values):
    return [
        {"key": one(wire(v), 1).decode(), "value": one(wire(v), 2).decode()}
        for v in values
    ]


def resource_value(data):
    value = one(wire(data), 1).decode()
    if not re.fullmatch(r"[0-9]+", value):
        raise ValueError("Resource value is not a nonnegative integer")
    return int(value)


def deployment_message(data):
    message = wire(data)
    ident = wire(one(message, 1))
    groups = []
    for raw_group in repeated(message, 2):
        group = wire(raw_group)
        totals = dict(gpu_count=0, cpu_units=0, memory_bytes=0, storage_bytes=0)
        units = []
        models = set()
        gpu_model_unknown = False
        for raw_unit in repeated(group, 3):
            unit = wire(raw_unit)
            count = one(unit, 2, 0)
            if not isinstance(count, int) or count <= 0:
                raise ValueError("Resource replica count must be positive")
            resource = wire(one(unit, 1))
            evidence = {"count": count, "id": one(resource, 1, 0)}
            for field, name in (
                (2, "cpu_units"),
                (3, "memory_bytes"),
                (5, "gpu_count"),
            ):
                part = wire(one(resource, field))
                value = resource_value(one(part, 1)) if part else 0
                totals[name] += count * value
                evidence[name] = value
                evidence[name + "_attributes"] = attributes(repeated(part, 2))
                if name == "gpu_count" and value:
                    requested = set()
                    for attr in evidence[name + "_attributes"]:
                        match = re.fullmatch(
                            r"vendor/[^/]+/model/([^/]+)(?:/.*)?", attr["key"]
                        )
                        if match and attr["value"].lower() == "true":
                            requested.add((attr["key"].split("/")[1], match[1]))
                    if len(requested) != 1:
                        gpu_model_unknown = True
                    models.update(requested)
            storage = []
            for raw_volume in repeated(resource, 4):
                volume = wire(raw_volume)
                size = resource_value(one(volume, 2))
                totals["storage_bytes"] += count * size
                storage.append(
                    {
                        "name": one(volume, 1).decode(),
                        "size": size,
                        "attributes": attributes(repeated(volume, 3)),
                    }
                )
            evidence["storage"] = storage
            units.append(evidence)
        requirements = wire(one(group, 2))
        # PlacementRequirements attributes are field 2; preserve raw bytes too.
        totals["gpu_model"] = (
            next(iter(models))[1]
            if len(models) == 1 and not gpu_model_unknown
            else None
        )
        totals["attributes"] = {
            "group_name": one(group, 1).decode(),
            "resource_units": units,
            "requirements_protobuf_base64": base64.b64encode(one(group, 2)).decode(),
            "requirements": attributes(repeated(requirements, 2)),
        }
        groups.append(totals)
    return {
        "owner": one(ident, 1).decode(),
        "dseq": str(one(ident, 2, 0)),
        "groups": groups,
    }


def transaction_messages(raw):
    body = wire(one(wire(raw), 1))
    result = []
    for index, encoded in enumerate(repeated(body, 1)):
        item = wire(encoded)
        type_url = one(item, 1).decode()
        result.append((index, type_url, one(item, 2)))
    return result


def event_attributes(event):
    result = {}
    for attr in event.get("attributes", []):
        key, value = attr["key"], attr["value"]
        # Older RPCs encode attributes as base64. Only accept known decoded keys.
        if key not in {"id", "price", "reason", "msg_index", "hash", "action"}:
            try:
                decoded = base64.b64decode(key, validate=True).decode()
                if decoded in {"id", "price", "reason", "msg_index", "hash", "action"}:
                    key, value = (
                        decoded,
                        base64.b64decode(value, validate=True).decode(),
                    )
            except (ValueError, UnicodeDecodeError):
                pass
        if key in result:
            raise ValueError(f"Duplicate event attribute {key}")
        result[key] = value
    return result


def decode_block(
    chain_id, height, block_payload, results_payload, decoded_transactions=None
):
    block = block_payload["result"]["block"]
    header = block["header"]
    results = results_payload["result"]
    if (
        header["chain_id"] != chain_id
        or int(header["height"]) != height
        or int(results["height"]) != height
    ):
        raise ValueError("Block/result identity mismatch")
    txs = block.get("data", {}).get("txs") or []
    executions = results.get("txs_results") or []
    if len(txs) != len(executions):
        raise ValueError("Block transaction/result count mismatch")
    actions, issues = [], []

    def decode_events(events, tx_index, tx_hash, deployments):
        for event_index, event in enumerate(events):
            event_type = event.get("type", "")
            kind = EVENTS.get(event_type)
            if not kind:
                if event_type.startswith(
                    ("akash.market.", "akash.deployment.", "akash.provider.")
                ) or event_type in {"akash.v1", "akash.v1beta1"}:
                    issues.append(
                        {
                            "tx_index": tx_index,
                            "event_index": event_index,
                            "reason": "unsupported_event",
                            "event_type": event_type,
                            "event": event,
                        }
                    )
                continue
            try:
                attrs = event_attributes(event)
                identity = json.loads(attrs["id"])
                if (
                    not isinstance(identity, dict)
                    or not identity.get("owner")
                    or "dseq" not in identity
                ):
                    raise ValueError("Incomplete event identity")
                for key in ("dseq", "gseq", "oseq", "bseq"):
                    if key in identity and (
                        isinstance(identity[key], bool)
                        or not isinstance(identity[key], (str, int))
                        or re.fullmatch(r"[0-9]+", str(identity[key])) is None
                        or int(identity[key]) >= 2 ** (64 if key == "dseq" else 32)
                    ):
                        raise ValueError("Invalid event sequence")
                required = (
                    ("gseq", "oseq")
                    if kind.startswith(("order_", "bid_", "lease_"))
                    else ("gseq",)
                    if kind == "group_closed"
                    else ()
                )
                if any(key not in identity for key in required):
                    raise ValueError("Missing order sequence")
                if kind.startswith(("bid_", "lease_")) and not identity.get("provider"):
                    raise ValueError("Missing provider")
                payload = {"id": identity, "raw_event": event}
                if kind in ("bid_created", "lease_created"):
                    price = json.loads(attrs["price"])
                    amount = Decimal(price["amount"])
                    if not amount.is_finite() or amount < 0 or not price.get("denom"):
                        raise ValueError("Invalid native price")
                    payload["price"] = {"amount": str(amount), "denom": price["denom"]}
                if kind == "order_created":
                    deployment = deployments.get(
                        (identity["owner"], str(identity["dseq"]))
                    )
                    if deployment and 0 < int(identity["gseq"]) <= len(
                        deployment["groups"]
                    ):
                        payload["resources"] = deployment["groups"][
                            int(identity["gseq"]) - 1
                        ]
                    else:
                        issues.append(
                            {
                                "tx_index": tx_index,
                                "event_index": event_index,
                                "reason": "order_resources_unavailable",
                                "id": identity,
                            }
                        )
                if "reason" in attrs:
                    payload["close_reason"] = json.loads(attrs["reason"])
                actions.append(
                    {
                        "event_id": f"{chain_id}:{height}:{tx_index}:{event_index}",
                        "kind": kind,
                        "height": height,
                        "timestamp": header["time"],
                        "tx_hash": tx_hash,
                        "tx_index": tx_index if isinstance(tx_index, int) else None,
                        "phase": "transaction"
                        if isinstance(tx_index, int)
                        else tx_index.removesuffix("_events"),
                        "msg_index": int(attrs["msg_index"])
                        if "msg_index" in attrs
                        else None,
                        "event_index": event_index,
                        "payload": payload,
                    }
                )
            except (ValueError, TypeError, KeyError, ArithmeticError) as exc:
                issues.append(
                    {
                        "tx_index": tx_index,
                        "event_index": event_index,
                        "reason": "invalid_event",
                        "error": str(exc),
                        "event": event,
                    }
                )

    decode_events(
        results.get("begin_block_events") or [], "begin_block_events", None, {}
    )
    for index, (encoded, execution) in enumerate(zip(txs, executions)):
        if int(execution.get("code", -1)) != 0:
            continue
        deployments = {}
        try:
            raw = base64.b64decode(encoded, validate=True)
            tx_hash = hashlib.sha256(raw).hexdigest().upper()
            for msg_index, type_url, value in transaction_messages(raw):
                if type_url in CREATE_TYPES:
                    deployment = deployment_message(value)
                    deployments[(deployment["owner"], deployment["dseq"])] = deployment
                elif type_url.startswith("/akash.deployment.") and type_url.endswith(
                    ".MsgCreateDeployment"
                ):
                    issues.append(
                        {
                            "tx_index": index,
                            "msg_index": msg_index,
                            "reason": "unsupported_deployment_version",
                            "type_url": type_url,
                        }
                    )
                elif type_url == "/cosmos.authz.v1beta1.MsgExec":
                    issues.append(
                        {
                            "tx_index": index,
                            "msg_index": msg_index,
                            "reason": "authz_resource_decoding_unsupported",
                        }
                    )
        except (
            ValueError,
            TypeError,
            KeyError,
            UnicodeDecodeError,
            AttributeError,
        ) as exc:
            issues.append(
                {
                    "tx_index": index,
                    "reason": "invalid_transaction_resources",
                    "error": str(exc),
                }
            )
            tx_hash = hashlib.sha256(base64.b64decode(encoded)).hexdigest().upper()
        decode_events(execution.get("events") or [], index, tx_hash, deployments)
    # Consensus-generated closes may occur outside transactions.
    for label in ("end_block_events", "finalize_block_events"):
        decode_events(results.get(label) or [], label, None, {})
    return {
        "actions": actions,
        "issues": issues,
        "status": "partial" if issues else "complete",
    }
