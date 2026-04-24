from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from threading import RLock
from typing import Dict, Optional

from domain.models import OwnShipState, TargetState
from utils.config_utils import get_dds_target_stale_timeout_sec
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
        self._targets: Dict[int, TargetState] = {}
        self._target_last_seen_at: Dict[int, datetime] = {}
        self._target_stale_timeout_sec: float = get_dds_target_stale_timeout_sec()
        self._target_revision: int = 0
        self._targets_last_update_time = None
        self._targets_last_source_id: Optional[str] = None

    def update_ownship(self, ownship: OwnShipState) -> None:
        with self._lock:
            self._ownship = ownship

    def get_ownship(self) -> Optional[OwnShipState]:
        with self._lock:
            return self._ownship

    @staticmethod
    def _normalize_target_batch_no(target: TargetState) -> Optional[int]:
        try:
            return int(target.target_batch_no)
        except Exception:
            return None

    @staticmethod
    def _parse_target_batch_no(value: object) -> Optional[int]:
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            return None
        try:
            return int(text)
        except Exception:
            pass
        lower = text.lower()
        for prefix in ("target-", "batch-"):
            if lower.startswith(prefix):
                suffix = text[len(prefix) :]
                try:
                    return int(suffix)
                except Exception:
                    pass
        digits = "".join(ch for ch in text if ch.isdigit())
        if digits:
            return int(digits)
        return None

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

    def _prune_stale_targets(self, now: datetime) -> list[int]:
        stale_batch_nos: list[int] = []
        for batch_no, last_seen_at in self._target_last_seen_at.items():
            age_sec = (now - last_seen_at).total_seconds()
            if age_sec > self._target_stale_timeout_sec:
                stale_batch_nos.append(batch_no)

        for batch_no in stale_batch_nos:
            self._target_last_seen_at.pop(batch_no, None)
            self._targets.pop(batch_no, None)

        return stale_batch_nos

    def _prune_stale_targets_and_mark(self, now: datetime) -> list[int]:
        removed = self._prune_stale_targets(now)
        if removed:
            self._bump_revision(None)
            self._targets_last_update_time = now
        return removed

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
                    mode="dynamic",
                    input_count=len(targets),
                    ignored_stale_revision=True,
                )

            now = utc_now()
            valid_input_count = 0
            for target in targets:
                batch_no = self._normalize_target_batch_no(target)
                if batch_no is None:
                    continue
                self._targets[batch_no] = target
                self._target_last_seen_at[batch_no] = now
                valid_input_count += 1

            self._prune_stale_targets(now)
            self._bump_revision(revision)
            self._targets_last_update_time = now
            self._targets_last_source_id = source_id
            return self._sync_result(accepted=True, mode="dynamic", input_count=valid_input_count)

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

            now = utc_now()
            replaced: Dict[int, TargetState] = {}
            replaced_last_seen: Dict[int, datetime] = {}
            valid_input_count = 0
            for target in targets:
                batch_no = self._normalize_target_batch_no(target)
                if batch_no is None:
                    continue
                replaced[batch_no] = target
                replaced_last_seen[batch_no] = now
                valid_input_count += 1

            self._targets = replaced
            self._target_last_seen_at = replaced_last_seen
            self._bump_revision(revision)
            self._targets_last_update_time = now
            self._targets_last_source_id = source_id
            return self._sync_result(accepted=True, mode="replace", input_count=valid_input_count)

    def get_target_by_batch_no(self, target_batch_no: Optional[int]) -> Optional[TargetState]:
        if target_batch_no is None:
            return None
        batch_no = int(target_batch_no)
        with self._lock:
            self._prune_stale_targets_and_mark(utc_now())
            return self._targets.get(batch_no)

    def get_target(self, target_id: str) -> Optional[TargetState]:
        batch_no = self._parse_target_batch_no(target_id)
        with self._lock:
            self._prune_stale_targets_and_mark(utc_now())
            if batch_no is not None:
                return self._targets.get(batch_no)
            for item in self._targets.values():
                if item.target_id == target_id:
                    return item
            return None

    def get_all_targets(self) -> list[TargetState]:
        with self._lock:
            self._prune_stale_targets_and_mark(utc_now())
            return list(self._targets.values())

    def get_target_revision(self) -> int:
        with self._lock:
            return self._target_revision

    def get_situation_snapshot(self) -> dict:
        with self._lock:
            self._prune_stale_targets_and_mark(utc_now())
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
                batch_no = self._parse_target_batch_no(target_id)
                if batch_no is not None:
                    if batch_no in self._targets:
                        del self._targets[batch_no]
                        self._target_last_seen_at.pop(batch_no, None)
                        removed.append(target_id)
                    continue
                to_delete = None
                for key, item in self._targets.items():
                    if item.target_id == target_id:
                        to_delete = key
                        break
                if to_delete is not None:
                    del self._targets[to_delete]
                    self._target_last_seen_at.pop(to_delete, None)
                    removed.append(target_id)
            if removed:
                self._bump_revision(revision)
                self._targets_last_update_time = utc_now()
            return removed

    def reset(self) -> None:
        with self._lock:
            self._ownship = None
            self._targets.clear()
            self._target_last_seen_at.clear()
            self._target_revision = 0
            self._targets_last_update_time = None
            self._targets_last_source_id = None


situation_store = SituationStore()
