"""Prevent native extension ABI drift between Docker build and runtime."""
from pathlib import Path


def test_docker_uses_same_python_base_for_builder_and_runtime():
    source = (Path(__file__).resolve().parents[1] / 'Dockerfile').read_text()
    assert 'FROM python:3.14-slim AS python-base' in source
    assert 'FROM python-base AS builder' in source
    assert 'FROM python-base AS runtime' in source
    assert 'USER 65532:65532' in source
