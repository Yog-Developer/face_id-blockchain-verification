
import hashlib
import json


def canonicalize(record: dict) -> str:
    """
    Convert a dictionary into deterministic JSON.

    The same record must always produce the exact same string.
    """

    return json.dumps(
        record,
        sort_keys=True,
        separators=(",", ":"),
    )


def fingerprint(record: dict) -> str:
    """
    Create a SHA-256 hash of the canonicalized record.
    """

    canonical_record = canonicalize(record)

    return hashlib.sha256(
        canonical_record.encode("utf-8")
    ).hexdigest()

