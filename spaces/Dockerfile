FROM node:24-alpine
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --omit=dev
COPY server.mjs engine.mjs matching.mjs adaptation.mjs identity.mjs room-function.mjs ./
COPY public ./public
ENV NODE_ENV=production
EXPOSE 8080
CMD ["node", "server.mjs"]
