FROM node:22-alpine AS build
WORKDIR /app/spa-bff

COPY package.json /app/package.json
COPY spa-bff/package*.json ./
RUN npm ci

COPY spa-bff/tsconfig.json ./
COPY spa-bff/src ./src
RUN npm run build
RUN npm prune --omit=dev

FROM node:22-alpine
WORKDIR /app

ENV NODE_ENV=production

COPY --from=build /app/spa-bff/package*.json ./
COPY --from=build /app/spa-bff/node_modules ./node_modules
COPY --from=build /app/spa-bff/dist ./dist

EXPOSE 3001

CMD ["node", "dist/src/server.js"]

