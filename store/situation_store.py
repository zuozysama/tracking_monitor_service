from typing import Dict, Optional

from domain.models import OwnShipState, TargetState


class SituationStore:
    def __init__(self) -> None:
        self._ownship: Optional[OwnShipState] = None
        self._targets: Dict[str, TargetState] = {}

    def update_ownship(self, ownship: OwnShipState) -> None:
        self._ownship = ownship

    def get_ownship(self) -> Optional[OwnShipState]:
        return self._ownship

    def update_targets(self, targets: list[TargetState]) -> int:
        for target in targets:
            self._targets[target.target_id] = target
        return len(targets)

    def get_target(self, target_id: str) -> Optional[TargetState]:
        return self._targets.get(target_id)

    def get_all_targets(self) -> list[TargetState]:
        return list(self._targets.values())

    def remove_targets(self, target_ids: list[str]) -> list[str]:
        removed = []
        for target_id in target_ids:
            if target_id in self._targets:
                del self._targets[target_id]
                removed.append(target_id)
        return removed

    def reset(self) -> None:
        self._ownship = None
        self._targets.clear()


situation_store = SituationStore()