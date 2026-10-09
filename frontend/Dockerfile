FROM node:22-alpine AS build
WORKDIR /app
COPY package.json trial.json ./
COPY scripts ./scripts
COPY source ./source
RUN node scripts/build.mjs

FROM node:22-alpine
ENV NODE_ENV=production PORT=8080
WORKDIR /app
COPY --from=build --chown=node:node /app/public ./public
COPY --chown=node:node package.json server.mjs ./
USER node
EXPOSE 8080
CMD ["node", "server.mjs"]
