FROM node:22-alpine AS build
WORKDIR /app

COPY package*.json ./
COPY spa-bff/package*.json ./spa-bff/
COPY spa-web/package*.json ./spa-web/
RUN npm ci --include-workspace-root

COPY spa-bff/tsconfig.json ./spa-bff/tsconfig.json
COPY spa-bff/src ./spa-bff/src
WORKDIR /app/spa-bff
RUN npm run build
RUN cd /app && npm prune --omit=dev --workspace spa-bff

FROM node:22-alpine
WORKDIR /app

ENV NODE_ENV=production

COPY --from=build /app/package.json ./package.json
COPY --from=build /app/spa-bff/package*.json ./spa-bff/
COPY --from=build /app/node_modules ./node_modules
COPY --from=build /app/spa-bff/dist ./dist

EXPOSE 3001

CMD ["node", "dist/src/server.js"]

