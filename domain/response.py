from typing import Any


def ok(data: Any = None, message: str = "success") -> dict:
    return {
        "code": 0,
        "message": message,
        "data": data
    }


def err(code: int, message: str, data: Any = None) -> dict:
    return {
        "code": code,
        "message": message,
        "data": data
    }