FROM node:20-alpine

WORKDIR /app

COPY cliente-node/package*.json ./
RUN npm install --omit=dev

COPY cliente-node/src/ ./src/

CMD ["npm", "run", "test:integration"]
