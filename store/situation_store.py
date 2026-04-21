from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from typing import Dict, Optional

from domain.models import OwnShipState, TargetState
from utils.time_utils import utc_now


@dataclass(frozen=True)
class TargetSyncResult:
    accepted: bool
    mode: str
    input_count: int
    total_count: int
    revision: int
    ignored_stale_revision: bool = False


class SituationStore:
    def __init__(self) -> None:
        self._lock = RLock()
        self._ownship: Optional[OwnShipState] = None
        self._targets: Dict[str, TargetState] = {}
        self._target_revision: int = 0
        self._targets_last_update_time = None
        self._targets_last_source_id: Optional[str] = None

    def update_ownship(self, ownship: OwnShipState) -> None:
        with self._lock:
            self._ownship = ownship

    def get_ownship(self) -> Optional[OwnShipState]:
        with self._lock:
            return self._ownship

    def _normalize_target_id(self, target: TargetState) -> str:
        if target.target_id:
            return target.target_id
        return f"target-{target.target_batch_no}"

    def _should_reject_revision(self, revision: Optional[int]) -> bool:
        return revision is not None and revision <= self._target_revision

    def _bump_revision(self, revision: Optional[int]) -> int:
        if revision is None:
            self._target_revision += 1
        else:
            self._target_revision = revision
        return self._target_revision

    def _sync_result(
        self,
        *,
        accepted: bool,
        mode: str,
        input_count: int,
        ignored_stale_revision: bool = False,
    ) -> TargetSyncResult:
        return TargetSyncResult(
            accepted=accepted,
            mode=mode,
            input_count=input_count,
            total_count=len(self._targets),
            revision=self._target_revision,
            ignored_stale_revision=ignored_stale_revision,
        )

    def update_targets(
        self,
        targets: list[TargetState],
        revision: Optional[int] = None,
        source_id: Optional[str] = None,
    ) -> TargetSyncResult:
        with self._lock:
            if self._should_reject_revision(revision):
                return self._sync_result(
                    accepted=False,
                    mode="merge",
                    input_count=len(targets),
                    ignored_stale_revision=True,
                )

            for target in targets:
                self._targets[self._normalize_target_id(target)] = target
            self._bump_revision(revision)
            self._targets_last_update_time = utc_now()
            self._targets_last_source_id = source_id
            return self._sync_result(accepted=True, mode="merge", input_count=len(targets))

    def replace_targets(
        self,
        targets: list[TargetState],
        revision: Optional[int] = None,
        source_id: Optional[str] = None,
    ) -> TargetSyncResult:
        with self._lock:
            if self._should_reject_revision(revision):
                return self._sync_result(
                    accepted=False,
                    mode="replace",
                    input_count=len(targets),
                    ignored_stale_revision=True,
                )

            replaced: Dict[str, TargetState] = {}
            for target in targets:
                replaced[self._normalize_target_id(target)] = target
            self._targets = replaced
            self._bump_revision(revision)
            self._targets_last_update_time = utc_now()
            self._targets_last_source_id = source_id
            return self._sync_result(accepted=True, mode="replace", input_count=len(targets))

    def get_target(self, target_id: str) -> Optional[TargetState]:
        with self._lock:
            return self._targets.get(target_id)

    def get_all_targets(self) -> list[TargetState]:
        with self._lock:
            return list(self._targets.values())

    def get_target_revision(self) -> int:
        with self._lock:
            return self._target_revision

    def get_situation_snapshot(self) -> dict:
        with self._lock:
            return {
                "ownship": self._ownship,
                "targets": list(self._targets.values()),
                "revision": self._target_revision,
                "last_update_time": self._targets_last_update_time,
                "last_source_id": self._targets_last_source_id,
            }

    def remove_targets(self, target_ids: list[str], revision: Optional[int] = None) -> list[str]:
        with self._lock:
            if self._should_reject_revision(revision):
                return []
            removed = []
            for target_id in target_ids:
                if target_id in self._targets:
                    del self._targets[target_id]
                    removed.append(target_id)
            if removed:
                self._bump_revision(revision)
                self._targets_last_update_time = utc_now()
            return removed

    def reset(self) -> None:
        with self._lock:
            self._ownship = None
            self._targets.clear()
            self._target_revision = 0
            self._targets_last_update_time = None
            self._targets_last_source_id = None


situation_store = SituationStore()
