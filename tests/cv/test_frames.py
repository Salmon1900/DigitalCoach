"""Tests for frame sampling helpers (pure, no video file needed)."""

from __future__ import annotations

import numpy as np

from app.cv.frames import fit_within


def _img(height: int, width: int) -> np.ndarray:
    return np.zeros((height, width, 3), dtype=np.uint8)


def test_downscales_landscape_to_max_dim() -> None:
    out = fit_within(_img(1080, 1920), max_dim=720)
    h, w = out.shape[:2]
    assert max(h, w) == 720
    # Aspect ratio preserved (16:9).
    assert abs((w / h) - (1920 / 1080)) < 0.02


def test_downscales_portrait_to_max_dim() -> None:
    out = fit_within(_img(1920, 1080), max_dim=720)
    h, w = out.shape[:2]
    assert max(h, w) == 720
    assert abs((h / w) - (1920 / 1080)) < 0.02


def test_does_not_upscale_small_frame() -> None:
    src = _img(480, 640)
    out = fit_within(src, max_dim=720)
    assert out.shape == src.shape


def test_disabled_when_max_dim_zero() -> None:
    src = _img(1080, 1920)
    out = fit_within(src, max_dim=0)
    assert out.shape == src.shape
