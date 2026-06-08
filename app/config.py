"""Env-backed application settings (single source of configuration)."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    log_level: str = "INFO"

    # --- Computer vision ---
    # Reject videos longer than this (seconds).
    max_video_seconds: int = 120
    # Frames per second sampled for pose estimation.
    analysis_sample_fps: int = 10
    # MediaPipe Pose model complexity: 0 (fast), 1 (balanced), 2 (accurate).
    model_complexity: int = 1
    # Per-landmark visibility below this is treated as "not seen".
    min_pose_visibility: float = 0.5
    # If fewer than this fraction of sampled frames yield a usable pose, we bail out.
    min_pose_detected_ratio: float = 0.6
    # Cap total analysed frames to keep latency bounded on long clips.
    max_analyzed_frames: int = 600
    # Downscale each sampled frame so its longer side is at most this many pixels
    # before buffering. MediaPipe Pose runs low-res internally and returns normalized
    # landmarks, so this slashes memory (a 1080p frame is ~6 MB; at 720px ~0.9 MB)
    # with no accuracy impact. 0 disables downscaling.
    max_frame_dim: int = 720

    # --- Supabase (only needed for the by-reference input path) ---
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_role_key: str = ""
    supabase_video_bucket: str = "workout-videos"

    # --- Hosting ---
    port: int = 8080


@lru_cache
def get_settings() -> Settings:
    """Cached settings accessor (used as a FastAPI dependency)."""
    return Settings()
