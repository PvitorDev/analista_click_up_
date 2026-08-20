FROM node:20-alpine

WORKDIR /app
RUN corepack enable && corepack prepare pnpm@9 --activate

COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

COPY . .

EXPOSE 3000
# O volume client_node_modules cobre /app/node_modules e pode ficar
# com pacotes do client antigo. Instalar de novo na subida alinha o volume.
CMD ["sh", "-c", "CI=true pnpm install --frozen-lockfile && pnpm run dev"]
