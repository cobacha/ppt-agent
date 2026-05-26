FROM node:20-slim

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm ci

COPY . .
RUN npm run build

EXPOSE 8877

CMD ["npm", "start", "--", "--port", "8877"]
