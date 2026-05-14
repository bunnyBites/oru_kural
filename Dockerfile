# Stage 1 — Builder
FROM rust:1.86-slim AS builder

WORKDIR /app
COPY backend/ ./backend/

WORKDIR /app/backend
RUN cargo build --release --bin oru-kural-backend

# Stage 2 — Runtime
FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y ca-certificates && rm -rf /var/lib/apt/lists/*

COPY --from=builder /app/backend/target/release/oru-kural-backend /usr/local/bin/server

EXPOSE 8080
CMD ["server"]
