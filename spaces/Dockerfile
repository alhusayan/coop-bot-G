FROM node:24-bookworm-slim
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --omit=dev
COPY design-billing.mjs availability.mjs stock.mjs server.mjs engine.mjs matching.mjs adaptation.mjs identity.mjs room-function.mjs sourcing.mjs shopify.mjs findzia-engine.mjs original-client.mjs search-scheduler.mjs inventory.mjs inventory-pipeline.mjs original-page.mjs product-details.mjs ./
COPY public ./public
COPY scripts ./scripts
RUN node scripts/apply-credit-copy.mjs
ENV NODE_ENV=production
EXPOSE 8080
CMD ["node", "server.mjs"]

