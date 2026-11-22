# DigitalOcean launch runbook

This is the production path. Contabo and Hostinger notes are not the launch deploy.

Text interviews only. Do not add the voice Compose profile until LiveKit is configured for a public droplet.

## Server

- Ubuntu 24.04 LTS droplet, 2 vCPU / 4 GB RAM, 80 GB disk
- DNS `A` record: `app.example.com` → the droplet IPv4
- Firewall, on the droplet and in the DigitalOcean cloud firewall:

```bash
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw --force enable
```

Do not open `8000`, `27017`, or the LiveKit ports.

## First boot

```bash
sudo apt update && sudo apt upgrade -y
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker "$USER"
```

Log in again so the `docker` group applies.

```bash
git clone https://github.com/mangatohjunior/devops-interview-ai.git
cd devops-interview-ai
cp backend/.env.example backend/.env
```

Edit `backend/.env` on the server. Set a real `GROQ_API_KEY` and a `JWT_SECRET_KEY` of at least 32 random characters. Leave Mongo on the Compose network; the production file does not publish it.

Create the operator before the DNS name is shared:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build mongodb backend
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec backend \
  env ADMIN_EMAIL=you@example.com ADMIN_USERNAME=operator ADMIN_PASSWORD='a long password' \
  python create_admin.py
```

`create_admin.py` is added with the production auth changes. Until that revision is on `main`, create the admin after that code is deployed.

## Start

From the repo root, with the public hostname:

```bash
export SITE_ADDRESS=app.example.com
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

Caddy obtains the certificate and redirects port 80 to HTTPS. The browser uses one origin, so the auth cookies stay on `SameSite=lax`.

Check:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps
curl -fsS "https://${SITE_ADDRESS}/api/ready"
```

`/api/ready` should return `{"status":"ready"}`. MongoDB and the API are only reachable on the Compose network.

## Update

```bash
cd ~/devops-interview-ai
git pull origin main
export SITE_ADDRESS=app.example.com
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

If the image build fails, the existing containers keep serving. Do not run `docker compose down` as the deploy step.

## Rollback

```bash
git checkout <previous-sha>
export SITE_ADDRESS=app.example.com
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```
