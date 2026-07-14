"""
Terminal output beautification utilities.

Provides styled console helpers built on top of ``rich`` for consistent,
colorful, and structured terminal output across the project.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.traceback import install as install_rich_traceback

# ── Single shared Console instance ──────────────────────────────────────
console = Console(stderr=False, highlight=True)


# ── Styled print helpers ────────────────────────────────────────────────

def info(label: str, msg: str = "", **extra: Any) -> None:
    """Print an info-level (cyan) styled message."""
    _rich_print("info", label, msg, extra)


def success(label: str, msg: str = "", **extra: Any) -> None:
    """Print a success (green) styled message."""
    _rich_print("success", label, msg, extra)


def warning(label: str, msg: str = "", **extra: Any) -> None:
    """Print a warning (yellow) styled message."""
    _rich_print("warning", label, msg, extra)


def error(label: str, msg: str = "", **extra: Any) -> None:
    """Print an error (red) styled message."""
    _rich_print("error", label, msg, extra)


def debug(label: str, msg: str = "", **extra: Any) -> None:
    """Print a debug (dim) styled message."""
    _rich_print("debug", label, msg, extra)


# ── Structured output helpers ───────────────────────────────────────────

def print_panel(title: str, content: str, style: str = "cyan") -> None:
    """Print a bordered panel with a title."""
    console.print(Panel(content, title=title, border_style=style))


def print_table(title: str, columns: list[str], rows: list[list[str]]) -> None:
    """Print a table with automatic column sizing."""
    table = Table(title=title, title_style="bold cyan")
    for col in columns:
        table.add_column(col, style="cyan", no_wrap=False)
    for row in rows:
        table.add_row(*row)
    console.print(table)
    console.print()


def print_rule(title: str = "", style: str = "dim") -> None:
    """Print a horizontal rule (line separator)."""
    console.rule(title, style=style)


# ── Logging setup ───────────────────────────────────────────────────────

def setup_logging(level: str = "INFO") -> None:
    """Configure Python's ``logging`` to use Rich-formatted output.

    Call once at application startup (e.g. in ``app.py`` lifespan).
    Installs rich traceback handler for prettier exception rendering.
    """
    install_rich_traceback(show_locals=True, width=120)

    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(message)s",
        datefmt="[%X]",
        handlers=[
            RichHandler(
                rich_tracebacks=True,
                show_path=False,
                omit_repeated_times=False,
            )
        ],
    )

    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)

    _rich_print("info", "Logging", f"level={level.upper()}", {})


# ── Domain-specific beautification helpers ──────────────────────────────

def _compact_json(data: dict, max_values: int = 30) -> str:
    """Render a dict as compact ``{key=val, ...}`` for one-line display.

    Only keeps the first *max_values* entries; nested dicts/lists are
    shortened to a count or ellipsis.
    """
    items: list[str] = []
    for k, v in list(data.items())[:max_values]:
        if isinstance(v, dict):
            v = "{...}" if v else "{}"
        elif isinstance(v, list):
            v = f"[{len(v)} items]" if v else "[]"
        elif isinstance(v, float):
            v = f"{v:.4f}"
        elif isinstance(v, str) and len(v) > 64:
            v = v[:60] + "..."
        items.append(f"{k}={v}")
    if len(data) > max_values:
        items.append("...")
    return "{" + ", ".join(items) + "}"


def _compact_task_type(task_type) -> str:
    """Return a short Chinese-friendly label for the task type."""
    mapping = {
        "patrol": "巡逻",
        "escort": " escort",
        "intercept": " intercept",
        "expel": " expel",
        "underwater_search": "水下搜索",
        "fixed_tracking": "定点跟踪",
        "preplan": "预规划",
    }
    t = str(task_type).lower() if task_type else ""
    return mapping.get(t, t)


def print_received_task(task_summary: dict) -> None:
    """Print all fields when a task is received from upstream."""
    print_rule(style="cyan")
    task_id = task_summary.get("task_id", "-")
    compact = _compact_json(task_summary)
    msg = f"收到任务 {task_id} {compact}"
    _rich_print("info", "TaskIn", msg, {})


def print_publish_dds(topic_label: str, payload: dict, **annotations: Any) -> None:
    """Print a one-line summary when publishing a DDS topic."""
    compact = _compact_json(payload)
    msg = f"发布DDS [{topic_label}] {compact}"
    _rich_print("info", "DDSOut", msg, annotations)


def print_dispatch_to(module: str, summary: dict) -> None:
    """Print a one-line summary when dispatching a plan to an external module."""
    compact = _compact_json(summary)
    msg = f"下发{module} {compact}"
    _rich_print("info", "Dispatch", msg, {})


def print_dispatch_response(module: str, result: dict) -> None:
    """Print the HTTP response from an external module dispatch."""
    filtered = {k: v for k, v in result.items() if k != "data"}
    data = result.get("data")
    if isinstance(data, dict) and data.get("task_id"):
        filtered["task_id"] = data["task_id"]
    compact = _compact_json(filtered)
    msg = f"{module} 响应 {compact}"
    _rich_print("info", "DispatchRsp", msg, {})


def print_ownship_situation(ownship: Any) -> None:
    """Print a one-line situation summary for ownship navigation data."""
    if ownship is None:
        return
    lon = getattr(ownship, "longitude", "?")
    lat = getattr(ownship, "latitude", "?")
    speed_mps = getattr(ownship, "speed_mps", "?")
    heading_deg = getattr(ownship, "heading_deg", "?")
    msg = f"本船 pos=({lon}, {lat})  heading_deg={heading_deg}  speed_mps={speed_mps}"
    _rich_print("info", "Situation", msg, {})


def print_targets_situation(target_count: int, targets: list) -> None:
    """Print a one-line summary of current target situation."""
    if not targets:
        _rich_print("info", "Situation", "目标: 0 个活跃", {})
        return

    # Sort by distance for consistent display
    sorted_targets = sorted(
        targets,
        key=lambda t: getattr(t, "target_distance_m", float("inf")) or float("inf"),
    )
    items: list[str] = [f"目标: {target_count} 个活跃"]
    for t in sorted_targets[:5]:  # Show up to 5 targets
        target_batch_no = getattr(t, "target_batch_no", "?")
        target_distance_m = getattr(t, "target_distance_m", "?")
        target_absolute_heading_deg = getattr(t, "target_absolute_heading_deg", "?")
        target_absolute_speed_mps = getattr(t, "target_absolute_speed_mps", "?")
        target_type_code = getattr(t, "target_type_code", "?")
        threat_level = getattr(t, "threat_level", "?")
        items.append(f"target_batch_no={target_batch_no}  target_type_code={target_type_code}  target_distance_m={target_distance_m}  target_absolute_heading_deg={target_absolute_heading_deg}  target_absolute_speed_mps={target_absolute_speed_mps}  threat_level={threat_level}")
    if target_count > 5:
        items.append(f"... 还有 {target_count - 5} 个")
    _rich_print("info", "Situation", " | ".join(items), {})


def print_task_status_summary(tasks: list) -> None:
    """Print a compact summary of all current tasks."""
    if not tasks:
        _rich_print("info", "TaskStatus", "当前无活跃任务", {})
        return

    for t in tasks:
        tid = getattr(t, "task_id", "-")
        ttype = _compact_task_type(getattr(t, "task_type", ""))
        status = getattr(t, "status", "?").value if hasattr(getattr(t, "status", None), "value") else getattr(t, "status", "?")
        phase = getattr(t, "execution_phase", "?")
        target_batch = getattr(t, "current_target_batch_no", None)
        msg = f"任务 {tid}  [{ttype}]  status={status}  phase={phase}"
        extras = {}
        if target_batch is not None:
            extras["target_batch"] = target_batch
        _rich_print("info", "TaskStatus", msg, extras)


# ── Internal helpers ────────────────────────────────────────────────────

_STYLES: dict[str, str] = {
    "info": "bold cyan",
    "success": "bold green",
    "warning": "bold yellow",
    "error": "bold red",
    "debug": "dim white",
}


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%H:%M:%S.%f")[:-3]


def _rich_print(level: str, label: str, msg: str, extra: dict[str, Any]) -> None:
    styled_label = Text(f"[{label}]", style=_STYLES.get(level, "bold"))
    ts = Text(f"{_timestamp()}", style="dim")
    parts = [ts, " ", styled_label]
    if msg:
        parts.append(Text(f" {msg}", style="white"))
    for k, v in extra.items():
        parts.append(Text(f"  {k}=", style="bright_black"))
        parts.append(Text(f"{v}", style="bright_white"))
    console.print(*parts)
