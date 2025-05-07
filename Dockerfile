FROM python:3.12-bookworm

# Install uv.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy the application into the container.
COPY . /app

# Install the application dependencies.
WORKDIR /app
RUN uv venv
RUN uv sync --locked
RUN chmod +x run.sh

ENTRYPOINT ["./run.sh"]