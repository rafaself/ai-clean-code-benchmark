FROM node@sha256:c3de60bf2f9dd0ac6370e6117950ff62d6e339527e7472301c9c78a017978392
RUN apt-get update -qq && apt-get install -y --no-install-recommends openssl ca-certificates git ripgrep \
    && rm -rf /var/lib/apt/lists/* \
    && npm install --global pnpm@10.34.5 @openai/codex@0.158.0 \
    && npm cache clean --force
RUN mkdir -p /home/node/.codex && chown node:node /home/node/.codex
WORKDIR /workspace/packages/hoppscotch-backend
ENV TZ=UTC
USER node
# Pin the built image ID in the execution manifest; this recipe contains no subject/evaluator/auth artifacts.
