from datetime import datetime
from typing import Any, Optional


def _format_timestamp(value: Optional[datetime]) -> str:
    if value is None:
        return "-"
    return value.isoformat().replace("+00:00", "Z")


def _elapsed_ms(start: datetime, end: datetime) -> float:
    if start.tzinfo is None and end.tzinfo is not None:
        start = start.replace(tzinfo=end.tzinfo)
    elif start.tzinfo is not None and end.tzinfo is None:
        end = end.replace(tzinfo=start.tzinfo)
    return (end - start).total_seconds() * 1000.0


def _format_value(value: Any) -> str:
    return str(getattr(value, "value", value))


def print_point_generation_timing(
    task: Any,
    point_generation_start_time: datetime,
    point_generated_time: datetime,
    point_type: str,
    point_count: Optional[int] = None,
) -> None:
    task_dispatch_time = getattr(task, "create_time", None) or getattr(task, "start_time", None)
    dispatch_to_point_ms = None
    if task_dispatch_time is not None:
        dispatch_to_point_ms = _elapsed_ms(task_dispatch_time, point_generated_time)
    generation_elapsed_ms = _elapsed_ms(point_generation_start_time, point_generated_time)

    count_text = f" point_count={point_count}" if point_count is not None else ""
    dispatch_elapsed_text = "-" if dispatch_to_point_ms is None else f"{dispatch_to_point_ms:.3f}"
    print(
        "[PointGenerationTiming] "
        f"task_id={getattr(task, 'task_id', '-')}"
        f" task_type={_format_value(getattr(task, 'task_type', '-'))}"
        f" point_type={point_type}"
        f"{count_text}"
        f" task_dispatch_time={_format_timestamp(task_dispatch_time)}"
        f" point_generation_start_time={_format_timestamp(point_generation_start_time)}"
        f" point_generated_time={_format_timestamp(point_generated_time)}"
        f" generation_elapsed_ms={generation_elapsed_ms:.3f}"
        f" dispatch_to_point_ms={dispatch_elapsed_text}"
    )
