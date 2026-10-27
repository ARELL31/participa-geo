# PARTICIPA-GEO API development image.
#
# This image installs the locked dependencies only; the project source is
# mounted at runtime (see compose.yaml) and exposed through PYTHONPATH. This
# keeps the first failing test a "module not found" for the not-yet-written
# product code rather than a premature packaging failure.

FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim@sha256:5d275ca5f0da33c3368ac8fbb85fafabad023b3b8a7cff39a94ac0baecfd9a50

WORKDIR /workspace

# Install locked dependencies (runtime + dev) without installing the project.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --all-groups --no-install-project

ENV PATH="/workspace/.venv/bin:$PATH" \
    PYTHONPATH="/workspace/apps/api" \
    PYTHONDONTWRITEBYTECODE=1

CMD ["uvicorn", "participa_geo.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
