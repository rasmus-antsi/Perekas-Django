import hashlib
import os
import time
import uuid
from typing import Any, Dict, List, Optional

import requests


class MetaCapiConfigError(Exception):
    """Raised when required Meta CAPI configuration is missing."""


class MetaCapiSendError(Exception):
    """Raised when Meta CAPI responds with an error."""


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise MetaCapiConfigError(f"Missing required environment variable: {name}")
    return value


def hash_email(email: str) -> str:
    normalized = email.strip().lower()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def build_user_data(email: Optional[str], ip: Optional[str], ua: Optional[str]) -> Dict[str, Any]:
    user_data: Dict[str, Any] = {}
    if ua:
        user_data["client_user_agent"] = ua
    if ip:
        user_data["client_ip_address"] = ip
    if email:
        user_data["em"] = [hash_email(email)]
    return user_data


def build_event_payload(
    *,
    event_name: str,
    event_time: int,
    event_source_url: str,
    action_source: str,
    event_id: str,
    user_data: Dict[str, Any],
    custom_data: Optional[Dict[str, Any]] = None,
    attribution_data: Optional[Dict[str, Any]] = None,
    original_event_data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "event_name": event_name,
        "event_time": event_time,
        "event_source_url": event_source_url,
        "action_source": action_source,
        "event_id": event_id,
        "user_data": user_data,
    }
    if custom_data:
        payload["custom_data"] = custom_data
    if attribution_data:
        payload["attribution_data"] = attribution_data
    if original_event_data:
        payload["original_event_data"] = original_event_data
    return payload


def send_events_to_meta(
    events: List[Dict[str, Any]],
    *,
    test_event_code: Optional[str] = None,
    timeout_seconds: int = 10,
) -> Dict[str, Any]:
    pixel_id = _require_env("META_PIXEL_ID")
    access_token = _require_env("META_ACCESS_TOKEN")
    api_version = os.getenv("META_API_VERSION", "v19.0")

    url = f"https://graph.facebook.com/{api_version}/{pixel_id}/events"
    params = {"access_token": access_token}
    if test_event_code:
        params["test_event_code"] = test_event_code

    response = requests.post(url, params=params, json={"data": events}, timeout=timeout_seconds)
    try:
        body = response.json()
    except Exception:
        body = {"error": response.text}

    if not response.ok:
        raise MetaCapiSendError(body)

    return body


def default_event_id() -> str:
    return str(uuid.uuid4())


def default_event_time(provided: Optional[int] = None) -> int:
    try:
        if provided:
            return int(provided)
    except (TypeError, ValueError):
        pass
    return int(time.time())
