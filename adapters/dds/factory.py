from __future__ import annotations

from adapters.dds.base import DdsAdapter
from adapters.dds.config import load_dds_runtime_config
from adapters.dds.mock_adapter import MockDdsAdapter
from adapters.dds.real_adapter import RealLjdssAdapter

_dds_adapter: DdsAdapter | None = None


def get_dds_adapter() -> DdsAdapter:
    global _dds_adapter
    if _dds_adapter is not None:
        return _dds_adapter

    cfg = load_dds_runtime_config()
    if cfg.mode == "real":
        _dds_adapter = RealLjdssAdapter(cfg)
    else:
        _dds_adapter = MockDdsAdapter()
    _dds_adapter.start()
    return _dds_adapter
