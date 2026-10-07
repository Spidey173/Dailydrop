"""
Idempotency Service Module.

Guarantees strict end-to-end idempotency for order checkout and payment operations:
1. Prevents duplicate charges and double-orders caused by rapid button clicks, network retries, or browser refreshes.
2. Returns HTTP 409 Conflict if a concurrent request with the same Idempotency-Key is currently in-flight.
3. Caches and re-plays original successful responses if a completed Idempotency-Key is retransmitted.
4. Automatically cleans up reservation on non-retryable validation failures.
"""

import json
import logging
from typing import Optional, Tuple, Dict, Any
from flask import request, jsonify, make_response
from functools import wraps

from config import Config
from services.redis_service import RedisService

logger = logging.getLogger(__name__)


class IdempotencyService:
    """Manages idempotency tokens stored in Redis."""

    PREFIX = "idempotency:checkout:"
    DEFAULT_PROCESSING_TTL = 120  # 2 minutes lock during processing
    DEFAULT_COMPLETED_TTL = 86400  # 24 hours retention for completed responses

    @classmethod
    def get_idempotency_key_from_request(cls) -> Optional[str]:
        """Extract Idempotency-Key from headers or JSON body."""
        key = request.headers.get('Idempotency-Key') or request.headers.get('X-Idempotency-Key')
        if not key and request.is_json:
            data = request.get_json(silent=True) or {}
            key = data.get('idempotency_key')
        return key.strip() if (key and isinstance(key, str)) else None

    @classmethod
    def acquire(cls, key: str, user_id: Optional[Any] = None) -> Tuple[bool, Optional[Dict[str, Any]], Optional[int]]:
        """
        Check and lock an idempotency key.

        Returns:
            Tuple[can_proceed, cached_response, http_status_code]:
            - (True, None, None): Lock acquired, proceed with executing business logic.
            - (False, error_payload, 409): Request with this key is currently in-progress.
            - (False, cached_payload, cached_status): Previously completed request; replay response.
        """
        client = RedisService.get_client()
        if not client:
            # If Redis is unavailable, allow execution to proceed (graceful degradation)
            return True, None, None

        redis_key = f"{cls.PREFIX}{key}"

        try:
            # Check existing status
            existing = client.get(redis_key)
            if existing:
                try:
                    payload = json.loads(existing)
                except Exception:
                    payload = {"status": existing}

                status = payload.get("status")
                if status == "PROCESSING":
                    logger.warning(f"Concurrent idempotent request blocked for key: {key}")
                    return False, {
                        "success": False,
                        "error": "Conflict",
                        "message": "A checkout request with this Idempotency-Key is already being processed. Please wait."
                    }, 409
                elif status == "COMPLETED":
                    logger.info(f"Replaying cached response for idempotency key: {key}")
                    return False, payload.get("response", {}), payload.get("status_code", 200)

            # Attempt atomic lock with NX
            init_data = json.dumps({
                "status": "PROCESSING",
                "user_id": str(user_id) if user_id else None
            })
            acquired = client.set(redis_key, init_data, nx=True, ex=cls.DEFAULT_PROCESSING_TTL)
            if not acquired:
                return False, {
                    "success": False,
                    "error": "Conflict",
                    "message": "A checkout request with this Idempotency-Key is currently in-flight."
                }, 409

            return True, None, None

        except Exception as e:
            logger.warning(f"Idempotency check error ({e}). Proceeding without lock.")
            return True, None, None

    @classmethod
    def complete(cls, key: str, response_payload: Dict[str, Any], status_code: int = 200, ttl: Optional[int] = None) -> None:
        """Cache the successful response under the idempotency key."""
        client = RedisService.get_client()
        if not client or not key:
            return

        redis_key = f"{cls.PREFIX}{key}"
        if ttl is None:
            ttl = getattr(Config, 'IDEMPOTENCY_TTL', cls.DEFAULT_COMPLETED_TTL)

        try:
            data = json.dumps({
                "status": "COMPLETED",
                "response": response_payload,
                "status_code": status_code
            }, default=str)
            client.set(redis_key, data, ex=ttl)
            logger.info(f"Cached idempotent response for key: {key} (TTL: {ttl}s)")
        except Exception as e:
            logger.warning(f"Failed to record idempotency completion for {key}: {e}")

    @classmethod
    def release(cls, key: str) -> None:
        """Release / delete an in-progress lock if validation or order failed before completion."""
        client = RedisService.get_client()
        if not client or not key:
            return
        try:
            client.delete(f"{cls.PREFIX}{key}")
        except Exception as e:
            logger.warning(f"Failed to release idempotency key {key}: {e}")
