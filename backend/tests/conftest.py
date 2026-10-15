"""Shared fixtures."""
import pytest

from app.config import get_settings


@pytest.fixture
def offline(monkeypatch):
    """No network: embeddings disabled and no NVIDIA key (pipeline + log extraction)."""
    monkeypatch.setattr(get_settings(), "embeddings_enabled", False)
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
