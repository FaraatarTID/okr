FROM node:22-alpine AS deps
WORKDIR /app/spa-web
COPY package.json /app/package.json
COPY spa-web/package*.json ./
RUN npm ci

FROM node:22-alpine AS build
WORKDIR /app/spa-web
COPY --from=deps /app/spa-web/node_modules ./node_modules
COPY spa-web/ .
RUN npm run build

FROM node:22-alpine AS runtime
WORKDIR /app
ENV NODE_ENV=production
ENV PORT=3000

COPY --from=build /app/spa-web/package*.json ./
COPY --from=build /app/spa-web/.next ./.next
COPY --from=build /app/spa-web/public ./public
COPY --from=build /app/spa-web/node_modules ./node_modules

EXPOSE 3000

CMD ["npm", "run", "start"]

