FROM node:18-alpine AS builder

WORKDIR /app
COPY package*.json .
RUN npm ci
COPY . .
RUN npm run build

# Production stage — nginx serves the built assets
FROM nginx:alpine

COPY --from=builder /app/dist /usr/share/nginx/html

# SPA fallback: all routes serve index.html
RUN printf 'server {\n  listen 3000;\n  root /usr/share/nginx/html;\n  index index.html;\n  location / { try_files $uri $uri/ /index.html; }\n  gzip on;\n  gzip_types text/plain text/css application/javascript application/json;\n}\n' > /etc/nginx/conf.d/default.conf

EXPOSE 3000
CMD ["nginx", "-g", "daemon off;"]
