from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


class WheelData(BaseModel):
    fl: float
    fr: float
    rl: float
    rr: float


class CornerSummary(BaseModel):
    corner_index: int
    corner_name: Optional[str]
    entry_speed_kmh: float
    min_speed_kmh: float
    exit_speed_kmh: float
    brake_point_distance_m: float
    brake_duration_ms: int
    max_brake_input: float
    abs_intervention_peak: float
    abs_intervention_count: int
    throttle_application_distance_m: float
    tc_intervention_peak: float
    tc_intervention_count: int
    max_rear_wheel_slip: float
    lockup_detected: bool


class LapSummary(BaseModel):
    session_id: str
    lap_number: int
    lap_time_ms: int
    is_valid: bool
    circuit: str
    car_model: str
    recorded_at: datetime
    sector_times_ms: list[int]
    corners: list[CornerSummary]
    tyre_core_temp_avg: WheelData
    tyre_pressure_avg: WheelData
    tyre_wear_delta: WheelData
    fuel_start_litres: float
    fuel_end_litres: float
    fuel_used_litres: float
    abs_total_frames: int
    tc_total_frames: int
    lockup_events: int
    track_grip_status: str
    rain_intensity: str
    air_temp_c: Optional[float]
    track_temp_c: Optional[float]


class SessionSummary(BaseModel):
    session_id: str
    session_type: str
    circuit: str
    car_model: str
    started_at: datetime
    laps: list[LapSummary]


class AnalysisRequest(BaseModel):
    session_id: str
    reference_lap_id: Optional[str] = None
    focus_areas: Optional[list[str]] = None


class CornerFeedback(BaseModel):
    corner_index: int
    corner_name: Optional[str]
    time_loss_estimate_ms: Optional[int]
    issues: list[str]
    recommendations: list[str]


class AnalysisResult(BaseModel):
    session_id: str
    generated_at: datetime
    overall_summary: str
    top_weaknesses: list[str]
    corner_feedback: list[CornerFeedback]
    positive_observations: list[str]
    focus_for_next_stint: str
    raw_llm_response: str


class CornerDelta(BaseModel):
    i: int
    n: Optional[str] = None
    t_d: int
    bp_d: float
    bd_d: int
    mb_d: float
    ms_d: float
    xs_d: float
    th_d: float
    abs_d: float
    tc_d: float
    slip: float
    lock: bool = False
    tags: list[
        Literal[
            "late_brake",
            "early_brake",
            "over_brake",
            "under_brake",
            "early_throttle",
            "late_throttle",
            "lockup",
            "abs_heavy",
            "tc_heavy",
            "apex_slow",
            "apex_fast",
            "exit_slow",
            "wide_exit",
            "trail_short",
            "trail_long",
        ]
    ] = Field(default_factory=list)


class LapDeltaHeader(BaseModel):
    track: str
    car: str
    ref_t: int
    drv_t: int
    tot_d: int
    sec_d: list[int]
    abs_f_d: int
    tc_f_d: int
    lock_d: int
    env_note: Optional[str] = None


class TailAggregate(BaseModel):
    n_corners: int
    t_d_sum: int
    dominant_tags: list[str]


class DeltaReport(BaseModel):
    v: int = 1
    hdr: LapDeltaHeader
    top: list[CornerDelta]
    tail: Optional[TailAggregate] = None
    recent_laps_ms: list[int] = Field(default_factory=list)
