FROM node:20-alpine AS build
WORKDIR /src
# Save to GitHub tidak menyertakan yarn.lock, jadi salinan lock disimpan di deploy/frontend-yarn-lock.txt
COPY frontend/package.json frontend/yarn.loc[k] deploy/frontend-yarn-lock.txt ./
RUN [ -f yarn.lock ] || cp frontend-yarn-lock.txt yarn.lock; yarn install --frozen-lockfile --ignore-engines --network-timeout 600000
COPY frontend/ ./
ARG REACT_APP_BACKEND_URL
ARG REACT_APP_RECAPTCHA_SITE_KEY
ENV REACT_APP_BACKEND_URL=$REACT_APP_BACKEND_URL REACT_APP_RECAPTCHA_SITE_KEY=$REACT_APP_RECAPTCHA_SITE_KEY CI=false GENERATE_SOURCEMAP=false NODE_OPTIONS=--max-old-space-size=2048
ENV REACT_APP_CONTACT_EMAIL=cvmaiharta@gmail.com REACT_APP_CONTACT_COMPOSE_URL=https://mail.google.com/mail/
RUN yarn build

FROM caddy:2-alpine
COPY --from=build /src/build /srv
COPY deploy/Caddyfile /etc/caddy/Caddyfile
