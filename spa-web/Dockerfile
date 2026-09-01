FROM node:22-alpine AS deps
WORKDIR /app
COPY package*.json ./
COPY spa-bff/package*.json ./spa-bff/
COPY spa-web/package*.json ./spa-web/
RUN npm ci --include-workspace-root

FROM node:22-alpine AS build
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY spa-web/ ./spa-web/
WORKDIR /app/spa-web
RUN npm run build

FROM node:22-alpine AS runtime
WORKDIR /app/spa-web
ENV NODE_ENV=production
ENV PORT=3000

COPY --from=build /app/package.json /app/package.json
COPY --from=build /app/spa-web/package*.json ./
COPY --from=build /app/spa-web/.next ./.next
COPY --from=build /app/spa-web/public ./public
COPY --from=build /app/node_modules /app/node_modules

EXPOSE 3000

CMD ["npm", "run", "start"]

