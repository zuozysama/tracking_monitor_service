from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Callable


class DdsAdapter(ABC):
    @abstractmethod
    def publish(self, topic: str, payload: dict) -> None:
        raise NotImplementedError

    @abstractmethod
    def subscribe(self, topic: str, handler: Callable[[dict], None]) -> None:
        raise NotImplementedError

    @abstractmethod
    def start(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def stop(self) -> None:
        raise NotImplementedError
