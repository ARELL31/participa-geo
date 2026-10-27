# PARTICIPA-GEO web image.
#
# Pinned Node 24 LTS builds the Vite bundle; the runtime is a pinned nginx image
# that only serves static assets and proxies `/api/` to the internal API service.
# The `test` and `e2e` stages keep Vitest/Playwright inside Docker (no host
# Node install, no committed node_modules or browser download).

FROM node:24-bookworm-slim@sha256:55fb5f5a527ea2c5c4a95f963e48ef90aa38c7b346054fdc8ee9957a2b55d205 AS deps
WORKDIR /app
COPY apps/web/package.json apps/web/package-lock.json ./
RUN npm ci --no-audit --no-fund

FROM deps AS test
COPY apps/web/ ./
CMD ["npm", "run", "test", "--", "--run"]

FROM test AS e2e
RUN npx playwright install --with-deps chromium
CMD ["npx", "playwright", "test"]

FROM deps AS build
COPY apps/web/ ./
RUN npm run build

FROM nginx:1.29-bookworm@sha256:8adbdcb969e2676478ee2c7ad333956f0c8e0e4c5a7463f4611d7a2e7a7ff5dc AS runtime
COPY infrastructure/docker/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
# The local Inter webfonts are OFL-1.1; keep the license with the distributed build.
COPY --from=deps /app/node_modules/@fontsource/inter/LICENSE /usr/share/nginx/html/licenses/inter-OFL.txt
EXPOSE 80
