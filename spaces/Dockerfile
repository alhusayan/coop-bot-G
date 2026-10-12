FROM node:24-alpine
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --omit=dev
COPY trial-quota.mjs localized-render.mjs catalog-first.mjs store-details.mjs product-data.mjs dimensions.mjs recommendation.mjs room-preview.mjs availability.mjs stock.mjs server.mjs engine.mjs matching.mjs adaptation.mjs identity.mjs room-function.mjs sourcing.mjs ./
COPY public ./public
ENV NODE_ENV=production
EXPOSE 8080
CMD ["node", "server.mjs"]
