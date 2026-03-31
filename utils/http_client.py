from typing import Optional, Dict, Any

import requests


class HttpClientError(Exception):
    pass


def http_get_json(
    url: str,
    timeout_sec: float,
    params: Optional[Dict[str, Any]] = None,
) -> dict:
    try:
        response = requests.get(url, params=params, timeout=timeout_sec)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        raise HttpClientError(str(e))


def http_post_json(
    url: str,
    timeout_sec: float,
    payload: Optional[Dict[str, Any]] = None,
) -> dict:
    try:
        response = requests.post(url, json=payload or {}, timeout=timeout_sec)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        raise HttpClientError(str(e))