"""Validate the entire snapshot before opening a publication transaction."""

from collections import defaultdict
from datetime import datetime

from pydantic import TypeAdapter, ValidationError, create_model

from app.api.common import APIError
from app.pipeline.connectors import TABLES, normalize_shop
from app.source.entities import RESOURCES, Record
from app.source.models import Snapshot


def invalid() -> APIError:
    return APIError(422, "INVALID_SNAPSHOT", "Source snapshot failed validation")


def key(resource, row: dict) -> tuple:
    return tuple(row[column] for column in resource.keys)


def normalize(value: dict) -> dict:
    try:
        snapshot = Snapshot.model_validate(value).model_dump(mode="json")
        if snapshot["source_revision"] < 0:
            raise ValueError("Negative revision")
        TypeAdapter(datetime).validate_python(snapshot["as_of"])
        core = {table: [] for table in TABLES}
        merchants = {r["merchant_id"] for r in snapshot["access"]["merchants"]}
        groups = defaultdict(list)
        document_ids = set()
        for doc in snapshot["documents"]:
            captured = datetime.fromisoformat(doc["captured_at"])
            if captured.tzinfo is None or doc["resource_revision"] > snapshot["source_revision"]:
                raise ValueError("Invalid document revision/time")
            if doc["document_id"] in document_ids or doc["merchant_id"] not in merchants:
                raise ValueError("Duplicate or unowned document")
            document_ids.add(doc["document_id"])
            groups[doc["platform"], doc["shop_id"]].append(doc)
        for (platform, _), docs in groups.items():
            required = {"orders", "supplement"}
            if platform == "lazada":
                required.add("order_items")
            if len(docs) != len(required) or {d["resource"] for d in docs} != required:
                raise ValueError("Incomplete shop documents")
            result = normalize_shop(platform, docs, docs[0]["merchant_id"])
            for table, rows in result.items():
                core[table].extend(rows)
        rows_by_name, indexes = {}, {}
        for name, resource in RESOURCES.items():
            source = snapshot["access"] if resource.admin else core
            rows = source[resource.table]
            validated = []
            for row in rows:
                data = resource.model.model_validate(
                    {k: v for k, v in row.items() if k in resource.model.model_fields}
                ).model_dump()
                data.pop("native_status", None)
                data.update({k: v for k, v in row.items() if k.endswith("source_document_id")})
                validated.append(data)
            source[resource.table] = validated
            rows_by_name[name] = validated
            indexes[name] = {key(resource, row) for row in validated}
            if len(indexes[name]) != len(validated):
                raise ValueError("Duplicate key")
        if snapshot["counts"] != {name: len(rows) for name, rows in rows_by_name.items()}:
            raise ValueError("Count mismatch")
        for name, resource in RESOURCES.items():
            for row in rows_by_name[name]:
                for columns, target, _target_columns in resource.refs:
                    values = tuple(row[c] for c in columns)
                    if None not in values and values not in indexes[target]:
                        raise ValueError("Missing reference")
        seen_markers = set()
        for marker in snapshot["tombstones"]:
            resource = RESOURCES[marker["resource"]]
            model = create_model(
                "DeletionKey",
                __base__=Record,
                **{k: (resource.model.model_fields[k].annotation, ...) for k in resource.keys},
            )
            marker["record_key"] = model.model_validate(marker["record_key"]).model_dump()
            if (
                marker["tombstone_id"] <= 0
                or marker["tombstone_id"] in seen_markers
                or not 0 < marker["revision"] <= snapshot["source_revision"]
            ):
                raise ValueError("Invalid deletion identity")
            seen_markers.add(marker["tombstone_id"])
            if not resource.admin:
                if (
                    marker["scope"].get("merchant_id") not in merchants
                    or marker["scope"].get("shop_key") != marker["record_key"]["shop_key"]
                    or key(resource, marker["record_key"]) in indexes[resource.name]
                ):
                    raise ValueError("Invalid deletion scope")
        return {"snapshot": snapshot, "core": core, "access": snapshot["access"]}
    except ValueError, KeyError, TypeError, OverflowError, ValidationError:
        raise invalid() from None
