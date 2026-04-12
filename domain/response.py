from typing import Any


def ok(data: Any = None, message: str = "success", code: int = 200) -> dict:
    return {
        "code": code,
        "message": message,
        "data": data,
    }


def err(code: int, message: str, data: Any = None) -> dict:
    return {
        "code": code,
        "message": message,
        "data": data,
    }
