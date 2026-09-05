from blockchain.solana_client import store_record, verify_on_chain
from datetime import datetime, timezone
from typing import Any

from hashing.fingerprint import fingerprint
from search.face_search_client import (
    search_by_face,
    FaceSearchError,
)
from utils.logger import get_logger


logger = get_logger(__name__)


# ============================================================
# CONFIGURATION
# ============================================================

SIMILARITY_THRESHOLD = 0.80


# ============================================================
# TEAMMATE A - TEMPORARY MOCKS
# Replace these with real imports when teammate A's code is ready.
# ============================================================

def get_embedding(image_path: str):
    """
    Temporary mock.

    Real interface:
        get_embedding(image_path) -> np.ndarray | None
    """

    logger.info("MOCK: Generating input embedding.")

    # Temporary value so we can test orchestration.
    return "mock_embedding"


def verify_candidate(
    input_embedding,
    candidate_url: str,
) -> dict | None:
    """
    Temporary mock.

    Real interface:
        verify_candidate(input_embedding, candidate_url) -> dict | None
    """

    logger.info(
        "MOCK: Verifying candidate: %s",
        candidate_url,
    )

    return {
        "similarity_score": 0.90,
        "caption": "Mock caption",
        "image_url": candidate_url,
    }


# ============================================================
# TEAMMATE B - TEMPORARY MOCKS
# Replace these with real imports when teammate B's code is ready.
# ============================================================

# ============================================================
# HELPER
# ============================================================

def _extract_similarity_score(
    verification: dict[str, Any],
) -> float | None:
    """
    Extract similarity score from teammate A's verification result.
    """

    score = verification.get("similarity_score")

    if score is None:
        return None

    try:
        return float(score)

    except (TypeError, ValueError):
        return None


# ============================================================
# MAIN ORCHESTRATION
# ============================================================

def run_pipeline(
    input_image_path: str,
    testing_mode: bool = True,
) -> dict[str, Any]:
    """
    Run the complete Face ID + Blockchain Verification pipeline.

    Flow:
        1. Get embedding
        2. Search by face
        3. Verify candidates
        4. Pick highest match above threshold
        5. Build record
        6. Fingerprint record
        7. Store hash on Solana
        8. Verify hash on-chain
    """

    logger.info("Pipeline started.")

    # --------------------------------------------------------
    # A. GET INPUT EMBEDDING
    # --------------------------------------------------------

    logger.info("Generating input embedding.")

    input_embedding = get_embedding(input_image_path)

    if input_embedding is None:
        logger.error("Could not generate input embedding.")

        return {
            "status": "FAILED",
            "reason": "Could not generate face embedding.",
        }

    # --------------------------------------------------------
    # B. FACE SEARCH
    # --------------------------------------------------------

    logger.info("Searching for face candidates.")

    try:
        candidates = search_by_face(
            input_image_path,
            testing_mode=testing_mode,
        )

    except FaceSearchError as error:

        logger.error("Face search failed: %s", error)

        return {
            "status": "FAILED",
            "reason": f"Face search failed: {error}",
        }

    if not candidates:

        logger.info("No face-search candidates found.")

        return {
            "status": "NO_MATCH",
            "reason": "No face-search candidates found.",
        }

    logger.info(
        "Found %d candidates.",
        len(candidates),
    )

    # --------------------------------------------------------
    # C + D. VERIFY CANDIDATES AND PICK BEST MATCH
    # --------------------------------------------------------

    best_match = None
    best_score = -1.0

    for candidate in candidates:

        candidate_url = candidate.get("url")

        if not candidate_url:

            logger.warning(
                "Skipping candidate without URL."
            )

            continue

        try:

            verification = verify_candidate(
                input_embedding,
                candidate_url,
            )

        except Exception as error:

            logger.warning(
                "Verification failed for %s: %s",
                candidate_url,
                error,
            )

            continue

        if verification is None:

            logger.info(
                "Candidate was not verified: %s",
                candidate_url,
            )

            continue

        similarity_score = _extract_similarity_score(
            verification
        )

        if similarity_score is None:

            logger.warning(
                "Candidate returned no valid similarity score."
            )

            continue

        logger.info(
            "Candidate score %.4f: %s",
            similarity_score,
            candidate_url,
        )

        if similarity_score > best_score:

            best_score = similarity_score

            best_match = {
                "candidate": candidate,
                "verification": verification,
                "similarity_score": similarity_score,
            }

    # --------------------------------------------------------
    # NO VERIFIED MATCH
    # --------------------------------------------------------

    if best_match is None:

        logger.info("No verified match found.")

        return {
            "status": "NO_MATCH",
            "reason": "No verified match found.",
        }

    # --------------------------------------------------------
    # THRESHOLD CHECK
    # --------------------------------------------------------

    if best_match["similarity_score"] < SIMILARITY_THRESHOLD:

        logger.info(
            "Best score %.4f is below threshold %.4f.",
            best_match["similarity_score"],
            SIMILARITY_THRESHOLD,
        )

        return {
            "status": "NO_MATCH",
            "reason": "No verified match found.",
            "best_similarity_score":
                best_match["similarity_score"],
        }

    logger.info(
        "Verified match selected with score %.4f.",
        best_match["similarity_score"],
    )

    # --------------------------------------------------------
    # E. BUILD RECORD
    # --------------------------------------------------------

    candidate = best_match["candidate"]
    verification = best_match["verification"]
    similarity_score = best_match["similarity_score"]

    record = {
        "source_platform": candidate.get(
            "platform",
            "unknown",
        ),
        "post_url": candidate["url"],
        "image_url": (
            verification.get("image_url")
            or candidate.get("thumbnail_url")
            or candidate["url"]
        ),
        "caption": verification.get("caption"),
        "search_timestamp": datetime.now(
            timezone.utc
        ).isoformat(),
        "face_similarity_score": similarity_score,
    }

    # --------------------------------------------------------
    # FINGERPRINT
    # IMPORTANT:
    # content_hash is NOT included while calculating itself.
    # --------------------------------------------------------

    logger.info("Generating content fingerprint.")

    content_hash = fingerprint(record)

    record["content_hash"] = content_hash

    logger.info(
        "Content hash generated successfully."
    )

    # --------------------------------------------------------
    # F. STORE ON SOLANA
    # --------------------------------------------------------

    try:

        blockchain_result = store_record(
            content_hash=content_hash,
            post_url=record["post_url"],
            similarity_score=similarity_score,
        )

    except Exception as error:

        logger.error(
            "Blockchain storage failed: %s",
            error,
        )

        return {
            "status": "FAILED",
            "reason": f"Blockchain storage failed: {error}",
            "record": record,
        }

    record_address = blockchain_result.get(
        "record_address"
    )

    tx_hash = blockchain_result.get("tx_hash")

    if not record_address:

        logger.error(
            "store_record did not return record_address."
        )

        return {
            "status": "FAILED",
            "reason":
                "Blockchain storage did not return record_address.",
            "record": record,
        }

    # --------------------------------------------------------
    # G. VERIFY ON CHAIN
    # --------------------------------------------------------

    try:

        chain_status = verify_on_chain(
            record_address,
            content_hash,
        )

    except Exception as error:

        logger.error(
            "On-chain verification failed: %s",
            error,
        )

        return {
            "status": "FAILED",
            "reason":
                f"On-chain verification failed: {error}",
            "record": record,
            "record_address": record_address,
            "tx_hash": tx_hash,
        }

    # --------------------------------------------------------
    # FINAL RESULT
    # --------------------------------------------------------

    logger.info(
        "Pipeline finished with status: %s",
        chain_status,
    )

    return {
        "status": chain_status,
        "record": record,
        "record_address": record_address,
        "tx_hash": tx_hash,
        "verified_match": {
            "url": record["post_url"],
            "similarity_score": similarity_score,
        },
    }


# ============================================================
# LOCAL TEST
# ============================================================

if __name__ == "__main__":

    result = run_pipeline(
        input_image_path="back.jpg",
        testing_mode=True,
    )

    print("\nFINAL PIPELINE RESULT:")
    print(result)

