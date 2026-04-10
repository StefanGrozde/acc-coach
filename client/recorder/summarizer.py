from __future__ import annotations

import json
from datetime import datetime, timezone
from statistics import fmean
from typing import Any

from shared.models import CornerSummary, LapSummary, WheelData

DEFAULT_SECTOR_COUNT = 3
CORNER_BRAKE_THRESHOLD = 0.05
LOCKUP_SLIP_THRESHOLD = 0.3
LOCKUP_BRAKE_THRESHOLD = 0.2
THROTTLE_ON_THRESHOLD = 0.8
THROTTLE_FALLBACK_THRESHOLD = 0.5
MIN_CORNER_PROMINENCE_KMH = 8.0


def summarize_lap(
    frames: list[dict],
    session_id: str,
    lap_number: int,
    circuit: str,
    car_model: str,
    sector_count: int | None = None,
) -> LapSummary:
    if sector_count is not None:
        for frame in frames:
            if isinstance(frame, dict) and frame.get("sector_count") is None:
                frame["sector_count"] = sector_count

    samples = [_normalize_frame(frame, index) for index, frame in enumerate(frames)]
    samples.sort(key=_sample_sort_key)

    lap_time_ms = _lap_time_ms(samples)
    corners = segment_corners(frames)

    tyre_core_temp_avg = _average_wheel_series(
        samples,
        (
            "tyre_temp",
            "tyreTemp",
            "tyre_core_temp",
            "tyreCoreTemperature",
        ),
    )
    tyre_pressure_avg = _average_wheel_series(
        samples,
        (
            "tyre_pressure",
            "tyrePressure",
            "wheelsPressure",
            "tyre_pressure_avg",
        ),
    )
    tyre_wear_delta = _delta_wheel_series(
        samples,
        (
            "tyre_wear",
            "tyreWear",
            "tyre_wear_delta",
        ),
    )

    fuel_start, fuel_end = _first_last_float(samples, ("fuel", "fuel_litres", "fuelLitres"))
    abs_total_frames = _count_positive(samples, ("abs_active", "abs"))
    tc_total_frames = _count_positive(samples, ("tc_active", "tc"))
    lockup_events = _count_lockup_events(samples)
    env = _environment_snapshot(samples)

    payload = {
        "session_id": session_id,
        "lap_number": lap_number,
        "lap_time_ms": lap_time_ms,
        "is_valid": not _has_penalty(samples),
        "circuit": circuit,
        "car_model": car_model,
        "recorded_at": datetime.now(timezone.utc),
        "sector_times_ms": _derive_sector_times(samples, lap_time_ms),
        "corners": corners,
        "tyre_core_temp_avg": tyre_core_temp_avg,
        "tyre_pressure_avg": tyre_pressure_avg,
        "tyre_wear_delta": tyre_wear_delta,
        "fuel_start_litres": fuel_start,
        "fuel_end_litres": fuel_end,
        "fuel_used_litres": max(0.0, fuel_start - fuel_end),
        "abs_total_frames": abs_total_frames,
        "tc_total_frames": tc_total_frames,
        "lockup_events": lockup_events,
        "track_grip_status": env["track_grip_status"],
        "rain_intensity": env["rain_intensity"],
        "air_temp_c": env["air_temp_c"],
        "track_temp_c": env["track_temp_c"],
    }
    return LapSummary.model_validate(payload)


def segment_corners(
    frames: list[dict],
    threshold_kmh: float = 180,
    min_sep_m: float = 50,
) -> list[CornerSummary]:
    samples = [_normalize_frame(frame, index) for index, frame in enumerate(frames)]
    samples = [sample for sample in samples if sample["distance_m"] is not None and sample["speed_kmh"] is not None]
    samples.sort(key=_sample_sort_key)
    if len(samples) < 3:
        return []

    speeds = [sample["speed_kmh"] for sample in samples]
    smoothed = _rolling_mean(speeds, window=5)
    candidate_indices = _find_corner_apices(samples, smoothed, threshold_kmh)
    apex_indices = _merge_close_apices(samples, candidate_indices, min_sep_m)

    if not apex_indices:
        return []

    corners: list[CornerSummary] = []
    for corner_index, apex_index in enumerate(apex_indices):
        start_index = 0 if corner_index == 0 else _midpoint_index(samples, apex_indices[corner_index - 1], apex_index)
        end_index = len(samples) - 1 if corner_index == len(apex_indices) - 1 else _midpoint_index(samples, apex_index, apex_indices[corner_index + 1])
        if end_index < start_index:
            start_index, end_index = end_index, start_index

        segment = samples[start_index : end_index + 1]
        if not segment:
            continue

        apex_sample = min(segment, key=lambda sample: (sample["speed_kmh"] if sample["speed_kmh"] is not None else float("inf"), sample["timestamp_ms"] or 0))
        entry_speed = float(segment[0]["speed_kmh"] or 0.0)
        exit_speed = float(segment[-1]["speed_kmh"] or 0.0)
        min_speed = float(apex_sample["speed_kmh"] or 0.0)
        apex_distance = float(apex_sample["distance_m"] or 0.0)

        brake_point_distance = _first_brake_distance(segment, apex_distance)
        brake_duration_ms = _brake_duration_ms([sample for sample in segment if _coerce_float(sample.get("brake")) > CORNER_BRAKE_THRESHOLD])
        max_brake_input = max((_coerce_float(sample.get("brake")) for sample in segment), default=0.0)
        abs_intervention_peak = max((_coerce_float(sample.get("abs_active")) for sample in segment), default=0.0)
        abs_intervention_count = sum(1 for sample in segment if _coerce_float(sample.get("abs_active")) > 0.0)
        tc_intervention_peak = max((_coerce_float(sample.get("tc_active")) for sample in segment), default=0.0)
        tc_intervention_count = sum(1 for sample in segment if _coerce_float(sample.get("tc_active")) > 0.0)
        max_rear_wheel_slip = max((_rear_wheel_slip(sample) for sample in segment), default=0.0)
        throttle_application_distance = _throttle_application_distance(segment, segment.index(apex_sample))
        lockup_detected = any(
            _coerce_float(sample.get("brake")) > LOCKUP_BRAKE_THRESHOLD
            and _rear_wheel_slip(sample) > LOCKUP_SLIP_THRESHOLD
            for sample in segment
        )

        corners.append(
            CornerSummary.model_validate(
                {
                    "corner_index": corner_index,
                    "corner_name": None,
                    "entry_speed_kmh": entry_speed,
                    "min_speed_kmh": min_speed,
                    "exit_speed_kmh": exit_speed,
                    "brake_point_distance_m": brake_point_distance,
                    "brake_duration_ms": brake_duration_ms,
                    "max_brake_input": max_brake_input,
                    "abs_intervention_peak": abs_intervention_peak,
                    "abs_intervention_count": abs_intervention_count,
                    "throttle_application_distance_m": throttle_application_distance,
                    "tc_intervention_peak": tc_intervention_peak,
                    "tc_intervention_count": tc_intervention_count,
                    "max_rear_wheel_slip": max_rear_wheel_slip,
                    "lockup_detected": lockup_detected,
                }
            )
        )

    return corners


def _normalize_frame(frame: dict[str, Any], index: int) -> dict[str, Any]:
    payload: dict[str, Any] = {}

    raw_json = frame.get("raw_json")
    if isinstance(raw_json, dict):
        payload.update(raw_json)
    elif isinstance(raw_json, (str, bytes)):
        try:
            decoded = json.loads(raw_json)
        except (TypeError, ValueError, json.JSONDecodeError):
            decoded = None
        if isinstance(decoded, dict):
            payload.update(decoded)

    if isinstance(frame, dict):
        for key, value in frame.items():
            if value is not None:
                payload[key] = value

    payload["__index__"] = index
    payload["timestamp_ms"] = _coerce_int(payload.get("timestamp_ms"))
    payload["distance_m"] = _coerce_float(_first_present(payload, ("distance_m", "distance_traveled")))
    payload["speed_kmh"] = _coerce_float(_first_present(payload, ("speed_kmh", "speedKmh")))
    payload["brake"] = _coerce_float(_first_present(payload, ("brake",)))
    payload["throttle"] = _coerce_float(_first_present(payload, ("throttle",)))
    payload["abs_active"] = _coerce_float(_first_present(payload, ("abs_active", "abs", "absInAction")))
    payload["tc_active"] = _coerce_float(_first_present(payload, ("tc_active", "tc", "tcInAction")))
    payload["fuel"] = _coerce_float(_first_present(payload, ("fuel", "fuel_litres", "fuelLitres")))
    payload["track_grip_status"] = _first_present(payload, ("track_grip_status", "trackGripStatus", "trackStatus"))
    payload["rain_intensity"] = _first_present(payload, ("rain_intensity", "rainIntensity"))
    payload["air_temp_c"] = _coerce_optional_float(_first_present(payload, ("air_temp_c", "airTemp")))
    payload["track_temp_c"] = _coerce_optional_float(_first_present(payload, ("track_temp_c", "roadTemp")))
    payload["sector_count"] = _coerce_int(_first_present(payload, ("sector_count", "sectorCount")))
    payload["current_sector_index"] = _coerce_int(_first_present(payload, ("currentSectorIndex", "current_sector_index")))
    payload["last_sector_time"] = _coerce_int(_first_present(payload, ("lastSectorTime", "last_sector_time")))
    payload["tyre_temp"] = _normalize_wheel_values(
        _first_present(payload, ("tyre_temp", "tyreTemp", "tyreCoreTemperature", "tyre_core_temperature"))
    )
    payload["tyre_pressure"] = _normalize_wheel_values(
        _first_present(payload, ("tyre_pressure", "tyrePressure", "wheelsPressure", "mfdTyrePressure"))
    )
    payload["tyre_wear"] = _normalize_wheel_values(
        _first_present(payload, ("tyre_wear", "tyreWear"))
    )
    payload["wheel_slip"] = _normalize_wheel_values(
        _first_present(payload, ("wheel_slip", "wheelSlip", "slipRatio"))
    )
    return payload


def _first_present(frame: dict[str, Any], aliases: tuple[str, ...]) -> Any:
    for key in aliases:
        if key in frame and frame[key] is not None:
            return frame[key]
    return None


def _sample_sort_key(sample: dict[str, Any]) -> tuple[float, int]:
    distance = sample.get("distance_m")
    timestamp_ms = sample.get("timestamp_ms")
    if distance is not None:
        return (float(distance), int(timestamp_ms or 0))
    return (float(sample.get("__index__", 0)), int(timestamp_ms or 0))


def _lap_time_ms(samples: list[dict[str, Any]]) -> int:
    timestamps = [sample["timestamp_ms"] for sample in samples if sample.get("timestamp_ms") is not None]
    if not timestamps:
        return 0
    return max(0, int(max(timestamps) - min(timestamps)))


def _has_penalty(samples: list[dict[str, Any]]) -> bool:
    for sample in samples:
        penalty = sample.get("penalty")
        if penalty is None:
            continue
        try:
            if int(penalty) != 0:
                return True
        except (TypeError, ValueError):
            if bool(penalty):
                return True
    return False


def _count_positive(samples: list[dict[str, Any]], aliases: tuple[str, ...]) -> int:
    count = 0
    for sample in samples:
        value = _coerce_float(_first_present(sample, aliases))
        if value is not None and value > 0.0:
            count += 1
    return count


def _count_lockup_events(samples: list[dict[str, Any]]) -> int:
    events = 0
    in_event = False
    for sample in samples:
        locked = _coerce_float(sample.get("brake")) > LOCKUP_BRAKE_THRESHOLD and _rear_wheel_slip(sample) > LOCKUP_SLIP_THRESHOLD
        if locked and not in_event:
            events += 1
        in_event = locked
    return events


def _environment_snapshot(samples: list[dict[str, Any]]) -> dict[str, Any]:
    if not samples:
        return {
            "track_grip_status": "unknown",
            "rain_intensity": "unknown",
            "air_temp_c": None,
            "track_temp_c": None,
        }

    mid_index = len(samples) // 2
    track_grip_status = _nearest_present(samples, mid_index, ("track_grip_status", "trackGripStatus", "trackStatus"))
    rain_intensity = _nearest_present(samples, mid_index, ("rain_intensity", "rainIntensity"))
    air_temp_c = _nearest_present_float(samples, mid_index, ("air_temp_c", "airTemp"))
    track_temp_c = _nearest_present_float(samples, mid_index, ("track_temp_c", "roadTemp"))

    return {
        "track_grip_status": _stringify_snapshot_value(track_grip_status),
        "rain_intensity": _stringify_snapshot_value(rain_intensity),
        "air_temp_c": air_temp_c,
        "track_temp_c": track_temp_c,
    }


def _nearest_present(samples: list[dict[str, Any]], midpoint: int, aliases: tuple[str, ...]) -> Any:
    for offset in range(0, len(samples)):
        left = midpoint - offset
        right = midpoint + offset
        if left >= 0:
            value = _first_present(samples[left], aliases)
            if value is not None:
                return value
        if right < len(samples) and right != left:
            value = _first_present(samples[right], aliases)
            if value is not None:
                return value
    return None


def _nearest_present_float(samples: list[dict[str, Any]], midpoint: int, aliases: tuple[str, ...]) -> float | None:
    value = _nearest_present(samples, midpoint, aliases)
    return _coerce_optional_float(value)


def _stringify_snapshot_value(value: Any) -> str:
    if value is None:
        return "unknown"
    if isinstance(value, str):
        text = value.strip()
        return text or "unknown"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(int(value)) if float(value).is_integer() else str(value)
    return str(value)


def _derive_sector_times(samples: list[dict[str, Any]], lap_time_ms: int) -> list[int]:
    sector_count = _resolve_sector_count(samples)
    sector_indices = [
        _coerce_int(_first_present(sample, ("currentSectorIndex", "current_sector_index", "sector_index")))
        for sample in samples
    ]
    sector_indices = [index for index in sector_indices if index is not None and index >= 0]

    if sector_indices:
        sector_count = max(sector_count, max(sector_indices) + 1)
        boundaries: list[int] = []
        for sector_idx in range(sector_count):
            sector_samples = [
                sample
                for sample in samples
                if _coerce_int(_first_present(sample, ("currentSectorIndex", "current_sector_index", "sector_index"))) == sector_idx
                and sample.get("timestamp_ms") is not None
            ]
            if not sector_samples:
                boundaries.append(0)
                continue
            first_ts = min(int(sample["timestamp_ms"]) for sample in sector_samples)
            last_ts = max(int(sample["timestamp_ms"]) for sample in sector_samples)
            boundaries.append(max(0, last_ts - first_ts))
        if any(boundaries):
            return _normalize_sector_times(boundaries, lap_time_ms, sector_count)

    distances = [sample["distance_m"] for sample in samples if sample.get("distance_m") is not None and sample.get("timestamp_ms") is not None]
    timestamps = [int(sample["timestamp_ms"]) for sample in samples if sample.get("timestamp_ms") is not None]
    if not distances or not timestamps:
        return _split_evenly(lap_time_ms, sector_count)

    total_distance = max(distances)
    if total_distance <= 0:
        return _split_evenly(lap_time_ms, sector_count)

    split_distances = [total_distance * i / sector_count for i in range(1, sector_count)]
    boundary_timestamps: list[int] = []
    for target_distance in split_distances:
        boundary_timestamps.append(_interpolated_timestamp_at_distance(samples, target_distance))

    first_ts = min(timestamps)
    last_ts = max(timestamps)
    boundaries = [max(0, boundary_timestamps[0] - first_ts)]
    for earlier, later in zip(boundary_timestamps, boundary_timestamps[1:]):
        boundaries.append(max(0, later - earlier))
    boundaries.append(max(0, last_ts - boundary_timestamps[-1]))
    return _normalize_sector_times(boundaries, lap_time_ms, sector_count)


def _resolve_sector_count(samples: list[dict[str, Any]]) -> int:
    for sample in samples:
        sector_count = _coerce_int(_first_present(sample, ("sector_count", "sectorCount")))
        if sector_count is not None and sector_count > 0:
            return sector_count
    return DEFAULT_SECTOR_COUNT


def _interpolated_timestamp_at_distance(samples: list[dict[str, Any]], target_distance: float) -> int:
    points = [
        (float(sample["distance_m"]), int(sample["timestamp_ms"]))
        for sample in samples
        if sample.get("distance_m") is not None and sample.get("timestamp_ms") is not None
    ]
    points.sort(key=lambda item: item[0])
    if not points:
        return 0
    if target_distance <= points[0][0]:
        return points[0][1]
    if target_distance >= points[-1][0]:
        return points[-1][1]

    for (left_distance, left_timestamp), (right_distance, right_timestamp) in zip(points, points[1:]):
        if right_distance < target_distance:
            continue
        if right_distance == left_distance:
            return right_timestamp
        fraction = (target_distance - left_distance) / (right_distance - left_distance)
        return int(round(left_timestamp + fraction * (right_timestamp - left_timestamp)))

    return points[-1][1]


def _split_evenly(total_ms: int, count: int) -> list[int]:
    if count <= 0:
        return []
    base = total_ms // count
    remainder = total_ms % count
    result = [base + (1 if index < remainder else 0) for index in range(count)]
    if result and sum(result) != total_ms:
        result[-1] += total_ms - sum(result)
    return result


def _normalize_sector_times(times: list[int], lap_time_ms: int, fallback_count: int = DEFAULT_SECTOR_COUNT) -> list[int]:
    normalized = [max(0, int(value)) for value in times if value is not None]
    if not normalized:
        return _split_evenly(lap_time_ms, fallback_count)
    total = sum(normalized)
    if total == lap_time_ms or lap_time_ms <= 0:
        return normalized
    if total == 0:
        return _split_evenly(lap_time_ms, len(normalized))
    scaled = [int(round(value * lap_time_ms / total)) for value in normalized]
    drift = lap_time_ms - sum(scaled)
    if scaled:
        scaled[-1] += drift
    return [max(0, value) for value in scaled]


def _average_wheel_series(samples: list[dict[str, Any]], aliases: tuple[str, ...]) -> WheelData:
    series = [_wheel_series_from_sample(sample, aliases) for sample in samples]
    return _wheel_data_from_series(series)


def _delta_wheel_series(samples: list[dict[str, Any]], aliases: tuple[str, ...]) -> WheelData:
    start = None
    end = None
    for sample in samples:
        values = _wheel_series_from_sample(sample, aliases)
        if values is None:
            continue
        if start is None:
            start = values
        end = values
    if start is None or end is None:
        return WheelData(fl=0.0, fr=0.0, rl=0.0, rr=0.0)
    return WheelData(
        fl=float(end[0] - start[0]),
        fr=float(end[1] - start[1]),
        rl=float(end[2] - start[2]),
        rr=float(end[3] - start[3]),
    )


def _wheel_series_from_sample(sample: dict[str, Any], aliases: tuple[str, ...]) -> list[float] | None:
    value = _first_present(sample, aliases)
    return _normalize_wheel_values(value)


def _wheel_data_from_series(series: list[list[float] | None]) -> WheelData:
    per_wheel: list[list[float]] = [[], [], [], []]
    for values in series:
        if values is None:
            continue
        for index, value in enumerate(values[:4]):
            per_wheel[index].append(float(value))

    def _avg(values: list[float]) -> float:
        return float(fmean(values)) if values else 0.0

    return WheelData(
        fl=_avg(per_wheel[0]),
        fr=_avg(per_wheel[1]),
        rl=_avg(per_wheel[2]),
        rr=_avg(per_wheel[3]),
    )


def _normalize_wheel_values(value: Any) -> list[float] | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return [float(value), float(value), float(value), float(value)]
    if isinstance(value, (list, tuple)):
        values = [_coerce_float(item) or 0.0 for item in value[:4]]
        while len(values) < 4:
            values.append(values[-1] if values else 0.0)
        return values[:4]
    return None


def _first_last_float(samples: list[dict[str, Any]], aliases: tuple[str, ...]) -> tuple[float, float]:
    values = [_coerce_optional_float(_first_present(sample, aliases)) for sample in samples]
    values = [value for value in values if value is not None]
    if not values:
        return 0.0, 0.0
    return float(values[0]), float(values[-1])


def _rolling_mean(values: list[float], window: int) -> list[float]:
    if window <= 1 or len(values) <= 2:
        return [float(value) for value in values]
    radius = window // 2
    smoothed: list[float] = []
    for index in range(len(values)):
        start = max(0, index - radius)
        end = min(len(values), index + radius + 1)
        smoothed.append(float(fmean(values[start:end])))
    return smoothed


def _find_corner_apices(samples: list[dict[str, Any]], smoothed: list[float], threshold_kmh: float) -> list[int]:
    candidates: list[int] = []
    for index in range(1, len(smoothed) - 1):
        speed = smoothed[index]
        if speed >= threshold_kmh:
            continue
        if speed > smoothed[index - 1] or speed > smoothed[index + 1]:
            continue
        left_window = smoothed[max(0, index - 3) : index]
        right_window = smoothed[index + 1 : min(len(smoothed), index + 4)]
        if not left_window or not right_window:
            continue
        prominence = max(max(left_window) - speed, max(right_window) - speed)
        if prominence < MIN_CORNER_PROMINENCE_KMH:
            continue
        candidates.append(index)
    return candidates


def _merge_close_apices(samples: list[dict[str, Any]], candidate_indices: list[int], min_sep_m: float) -> list[int]:
    if not candidate_indices:
        return []

    merged: list[int] = []
    cluster: list[int] = [candidate_indices[0]]
    for index in candidate_indices[1:]:
        previous = cluster[-1]
        previous_distance = float(samples[previous]["distance_m"] or 0.0)
        current_distance = float(samples[index]["distance_m"] or 0.0)
        if current_distance - previous_distance <= min_sep_m:
            cluster.append(index)
            continue
        merged.append(_best_apex_in_cluster(samples, cluster))
        cluster = [index]
    merged.append(_best_apex_in_cluster(samples, cluster))
    return merged


def _best_apex_in_cluster(samples: list[dict[str, Any]], cluster: list[int]) -> int:
    return min(
        cluster,
        key=lambda index: (
            float(samples[index].get("speed_kmh") or float("inf")),
            int(samples[index].get("timestamp_ms") or 0),
        ),
    )


def _midpoint_index(samples: list[dict[str, Any]], left_index: int, right_index: int) -> int:
    left_distance = float(samples[left_index].get("distance_m") or 0.0)
    right_distance = float(samples[right_index].get("distance_m") or 0.0)
    target_distance = (left_distance + right_distance) / 2.0
    return min(
        range(len(samples)),
        key=lambda index: abs(float(samples[index].get("distance_m") or 0.0) - target_distance),
    )


def _first_brake_distance(segment: list[dict[str, Any]], fallback_distance: float) -> float:
    for sample in segment:
        brake = _coerce_float(sample.get("brake"))
        if brake is not None and brake > CORNER_BRAKE_THRESHOLD:
            distance = sample.get("distance_m")
            return float(distance if distance is not None else fallback_distance)
    return fallback_distance


def _brake_duration_ms(brake_samples: list[dict[str, Any]]) -> int:
    timestamps = [int(sample["timestamp_ms"]) for sample in brake_samples if sample.get("timestamp_ms") is not None]
    if len(timestamps) < 2:
        return 0
    return max(0, max(timestamps) - min(timestamps))


def _throttle_application_distance(segment: list[dict[str, Any]], apex_local_index: int) -> float:
    if apex_local_index >= len(segment):
        return float(segment[-1].get("distance_m") or 0.0)

    after_apex = segment[apex_local_index + 1 :]
    for index in range(len(after_apex)):
        throttle = _coerce_float(after_apex[index].get("throttle"))
        if throttle is None or throttle < THROTTLE_ON_THRESHOLD:
            continue
        if index + 1 < len(after_apex) and _coerce_float(after_apex[index + 1].get("throttle")) is not None and _coerce_float(after_apex[index + 1].get("throttle")) >= THROTTLE_ON_THRESHOLD:
            return float(after_apex[index].get("distance_m") or 0.0)
    for sample in after_apex:
        throttle = _coerce_float(sample.get("throttle"))
        if throttle is not None and throttle >= THROTTLE_FALLBACK_THRESHOLD:
            return float(sample.get("distance_m") or 0.0)
    return float(segment[-1].get("distance_m") or 0.0)


def _rear_wheel_slip(sample: dict[str, Any]) -> float:
    values = _normalize_wheel_values(sample.get("wheel_slip"))
    if values is None:
        return 0.0
    return float(max(values[2], values[3]))


def _coerce_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _coerce_float(value: Any) -> float:
    if value is None:
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _coerce_optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


if __name__ == "__main__":
    demo_frames = [
        {
            "timestamp_ms": 0,
            "distance_m": 0.0,
            "speed_kmh": 220.0,
            "brake": 0.0,
            "throttle": 0.2,
            "fuel": 100.0,
            "tyre_temp": [85.0, 86.0, 84.0, 85.5],
            "tyre_pressure": [26.0, 26.1, 25.9, 26.2],
            "tyre_wear": [0.0, 0.0, 0.0, 0.0],
            "abs_active": 0.0,
            "tc_active": 0.0,
            "wheel_slip": [0.0, 0.0, 0.0, 0.0],
        },
        {
            "timestamp_ms": 1000,
            "distance_m": 180.0,
            "speed_kmh": 95.0,
            "brake": 0.82,
            "throttle": 0.0,
            "fuel": 99.4,
            "tyre_temp": [88.0, 89.0, 87.0, 88.5],
            "tyre_pressure": [26.1, 26.2, 26.0, 26.3],
            "tyre_wear": [0.1, 0.1, 0.1, 0.1],
            "abs_active": 0.5,
            "tc_active": 0.0,
            "wheel_slip": [0.2, 0.25, 0.4, 0.38],
            "penalty": 0,
        },
        {
            "timestamp_ms": 2000,
            "distance_m": 320.0,
            "speed_kmh": 230.0,
            "brake": 0.0,
            "throttle": 0.95,
            "fuel": 98.8,
            "tyre_temp": [90.0, 91.0, 89.0, 90.5],
            "tyre_pressure": [26.2, 26.2, 26.1, 26.4],
            "tyre_wear": [0.2, 0.2, 0.2, 0.2],
            "abs_active": 0.0,
            "tc_active": 0.1,
            "wheel_slip": [0.0, 0.0, 0.0, 0.0],
            "track_grip_status": "optimum",
            "rain_intensity": "dry",
            "air_temp_c": 24.0,
            "track_temp_c": 32.0,
        },
    ]

    summary = summarize_lap(demo_frames, "session-1", 1, "spa", "mclaren_720s_gt3")
    print(summary.model_dump())
