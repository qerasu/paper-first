FROM node:20-alpine

WORKDIR /app

COPY package.json package-lock.json /app/
RUN npm ci

COPY . /app

EXPOSE 5173

CMD ["npm", "run", "dev"]
