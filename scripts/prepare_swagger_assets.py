from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Optional


def _find_assets_dir(package_dir: Path) -> Optional[Path]:
    if not package_dir.is_dir():
        return None

    for js_file in package_dir.rglob("swagger-ui-bundle.js"):
        candidate = js_file.parent
        if (candidate / "swagger-ui.css").is_file():
            return candidate
    return None


def main() -> int:
    strict = os.getenv("PREPARE_SWAGGER_ASSETS_STRICT", "0") == "1"
    repo_root = Path(__file__).resolve().parents[1]
    dst_dir = repo_root / "static" / "swagger-ui"
    dst_dir.mkdir(parents=True, exist_ok=True)

    try:
        import swagger_ui_bundle  # type: ignore
    except Exception as exc:
        print(f"[prepare_swagger_assets] swagger_ui_bundle import failed: {exc}")
        return 1 if strict else 0

    package_dir = Path(swagger_ui_bundle.__file__).resolve().parent
    src_dir = _find_assets_dir(package_dir)
    if src_dir is None:
        print(f"[prepare_swagger_assets] assets not found under: {package_dir}")
        return 1 if strict else 0

    copied = []
    for name in ("swagger-ui-bundle.js", "swagger-ui.css", "favicon-32x32.png"):
        src = src_dir / name
        if src.is_file():
            dst = dst_dir / name
            shutil.copy2(src, dst)
            copied.append(name)

    if "swagger-ui-bundle.js" not in copied or "swagger-ui.css" not in copied:
        print(f"[prepare_swagger_assets] required files missing in source dir: {src_dir}")
        return 1 if strict else 0

    print(f"[prepare_swagger_assets] copied to {dst_dir}: {', '.join(copied)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
