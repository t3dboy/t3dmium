# T3dmium sync server container.
#
# The reference server is pure Python standard library, so any recent Python
# base works. We use 3.12-slim for the container even though local development
# targets 3.9 (the code is 3.9-compatible).
#
# NOTE ON TLS: this container serves PLAIN HTTP. Terminating TLS is the
# operator's responsibility — run your own reverse proxy (Caddy / nginx /
# Traefik) in front and keep this bound to loopback. See README.md.

FROM python:3.12-slim

# Run as a non-root user.
RUN useradd --create-home --uid 10001 t3dsync
WORKDIR /app

# Only the server and its (empty) requirements are needed at runtime. No
# third-party packages are installed because the reference server needs none.
COPY server/ /app/server/
COPY requirements.txt /app/requirements.txt

# Persisted SQLite database lives here (mounted as a volume in compose).
RUN mkdir -p /data && chown -R t3dsync:t3dsync /app /data
USER t3dsync

VOLUME ["/data"]
EXPOSE 8787

# Bind to all interfaces INSIDE the container; the compose file publishes the
# port only on the host's 127.0.0.1 so it is never directly internet-facing.
ENTRYPOINT ["python3", "server/app.py", "--host", "0.0.0.0", "--port", "8787", "--db", "/data/data.db"]
