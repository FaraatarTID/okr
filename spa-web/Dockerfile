FROM node:22-alpine@sha256:c610fcdfb1d5b4740dd70c284ed3cb16bb857e0f7166196e36a5501df7a3aa32 AS deps
WORKDIR /app
COPY package*.json ./
COPY spa-bff/package*.json ./spa-bff/
COPY spa-web/package*.json ./spa-web/
RUN npm ci --include-workspace-root --include=dev

FROM node:22-alpine@sha256:c610fcdfb1d5b4740dd70c284ed3cb16bb857e0f7166196e36a5501df7a3aa32 AS build
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY --from=deps /app/spa-web/node_modules ./spa-web/node_modules
COPY --from=deps /app/package.json ./package.json
COPY spa-web/ ./spa-web/
WORKDIR /app/spa-web
RUN npm run build -- --webpack

FROM node:22-alpine@sha256:c610fcdfb1d5b4740dd70c284ed3cb16bb857e0f7166196e36a5501df7a3aa32 AS runtime
WORKDIR /app/spa-web
ENV NODE_ENV=production
ENV PORT=3000

COPY --from=build /app/package.json /app/package.json
COPY --from=build /app/spa-web/package*.json ./
COPY --from=build /app/spa-web/.next ./.next
COPY --from=build /app/spa-web/public ./public
COPY --from=build /app/node_modules /app/node_modules
COPY --from=build /app/spa-web/node_modules ./node_modules

EXPOSE 3000

CMD ["npm", "run", "start"]

