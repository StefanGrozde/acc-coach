from sqlalchemy import Boolean, Column, DateTime, Index, Integer, String, Text, UniqueConstraint  # noqa: F401
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    pass


class Session(Base):
    __tablename__ = "sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    session_id = Column(Text, unique=True, nullable=False)
    session_type = Column(Text)
    circuit = Column(Text)
    car_model = Column(Text)
    started_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Lap(Base):
    __tablename__ = "laps"
    __table_args__ = (UniqueConstraint("session_id", "lap_number"),)

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    session_id = Column(Text, nullable=False)
    lap_number = Column(Integer, nullable=False)
    lap_time_ms = Column(Integer)
    is_valid = Column(Boolean)
    circuit = Column(Text)
    car_model = Column(Text)
    recorded_at = Column(DateTime(timezone=True))
    summary = Column(JSONB, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Analysis(Base):
    __tablename__ = "analyses"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    session_id = Column(Text, nullable=False)
    generated_at = Column(DateTime(timezone=True), server_default=func.now())
    result = Column(JSONB, nullable=False)
    model_used = Column(Text)
    prompt_tokens = Column(Integer)
    completion_tokens = Column(Integer)


class ReferenceLap(Base):
    __tablename__ = "reference_laps"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    circuit = Column(Text, nullable=False)
    car_model = Column(Text, nullable=False)
    lap_time_ms = Column(Integer)
    source = Column(Text)
    summary = Column(JSONB, nullable=False)
    added_at = Column(DateTime(timezone=True), server_default=func.now())


Index("idx_laps_session", Lap.session_id)
Index("idx_laps_circuit_car", Lap.circuit, Lap.car_model)
Index("idx_analyses_session", Analysis.session_id)
