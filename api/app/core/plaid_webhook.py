import hashlib
import time
from typing import Any, cast

import jwt
from cryptography.hazmat.primitives.asymmetric.ec import EllipticCurvePublicKey
from jwt.algorithms import ECAlgorithm

from app.core.exceptions import ForbiddenError
from app.ingestion.connectors.plaid.client import PlaidClient

_ALGORITHM = "ES256"
# Plaid's own documented tolerance -- a webhook JWT older than this is
# treated as a replay, not a late delivery.
_MAX_CLOCK_SKEW_SECONDS = 5 * 60


def verify_plaid_webhook(
    *, body: bytes, verification_header: str | None, plaid_client: PlaidClient
) -> dict[str, Any]:
    """Verifies a Plaid webhook's `Plaid-Verification` JWT per Plaid's
    documented process: fetch the signing key by `kid`, verify the ES256
    signature, reject a stale `iat` (replay protection), and confirm the
    claimed body hash matches the actual raw request body. Returns the
    verified claims. Raises ForbiddenError (403) on any failure -- there is
    no partial trust here, a webhook that fails any one of these checks is
    not trusted at all.
    """
    if not verification_header:
        raise ForbiddenError("Missing Plaid-Verification header.")

    try:
        unverified_header = jwt.get_unverified_header(verification_header)
    except jwt.PyJWTError as exc:
        raise ForbiddenError("Malformed Plaid-Verification header.") from exc

    if unverified_header.get("alg") != _ALGORITHM:
        raise ForbiddenError("Unexpected Plaid webhook JWT algorithm.")
    key_id = unverified_header.get("kid")
    if not key_id:
        raise ForbiddenError("Plaid-Verification header is missing a key id.")

    verification_key = plaid_client.get_webhook_verification_key(key_id)
    # Plaid's endpoint only ever returns a public verification key -- the
    # union with private-key types is from_jwk's generic JWK-parsing
    # signature, not a real possibility here.
    public_key = cast(EllipticCurvePublicKey, ECAlgorithm.from_jwk(verification_key.jwk))

    try:
        claims = jwt.decode(verification_header, key=public_key, algorithms=[_ALGORITHM])
    except jwt.PyJWTError as exc:
        raise ForbiddenError("Plaid webhook signature verification failed.") from exc

    issued_at = claims.get("iat")
    if not isinstance(issued_at, int | float) or time.time() - issued_at > _MAX_CLOCK_SKEW_SECONDS:
        raise ForbiddenError("Plaid webhook JWT is stale -- possible replay.")

    expected_hash = hashlib.sha256(body).hexdigest()
    if claims.get("request_body_sha256") != expected_hash:
        raise ForbiddenError("Plaid webhook body hash does not match the signed claim.")

    return claims
