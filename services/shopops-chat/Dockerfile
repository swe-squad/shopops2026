FROM node:24-alpine AS builder
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .

RUN npm run build

FROM nginx:1.29-alpine
ENV WORKSPACE_VIEWER_URL=""
COPY --chmod=755 require-env.sh /docker-entrypoint.d/15-require-env.sh
COPY nginx.conf /etc/nginx/templates/default.conf.template
COPY --from=builder /app/dist /usr/share/nginx/html
EXPOSE 80
