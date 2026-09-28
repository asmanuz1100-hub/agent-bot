# ASMAN Agent Bot — VPS migration

This migration keeps the current Render service untouched until the final cutover.
The VPS stack contains the Python bot/backend, PostgreSQL 16 and Caddy for automatic HTTPS.

## Recommended server

Ubuntu 24.04 LTS, 2 vCPU and 4 GB RAM is a comfortable starting point.
Use a public IPv4 address and a domain/subdomain such as `bot.example.com`.

## 1. Prepare DNS before cutover

Create an A record:

```
bot.example.com -> VPS_PUBLIC_IP
```

Wait until the hostname resolves to the VPS. Telegram webhooks and the Mini Apps require HTTPS.

## 2. Install the base packages

```bash
sudo apt update
sudo apt install -y git ca-certificates curl postgresql-client ufw

curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker "$USER"
```

Log out and back in once after adding the user to the Docker group.

Firewall:

```bash
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

PostgreSQL and the app ports are bound to 127.0.0.1 only by docker-compose.

## 3. Clone and configure

```bash
git clone https://github.com/asmanuz1100-hub/agent-bot.git
cd agent-bot
cp .env.example .env
chmod 600 .env
```

Fill in `.env`:

- `BOT_TOKEN`
- `ADMIN_IDS`
- `APP_DOMAIN`
- a long random `POSTGRES_PASSWORD`
- a stable random `WEBHOOK_SECRET`
- `OPENAI_API_KEY` if OCR is used

Do not copy secrets into GitHub.

## 4. Start only the new database first

```bash
docker compose up -d db
docker compose ps
```

Do not start the `app` service yet. Starting it with `WEBHOOK_BASE_URL` switches Telegram's webhook to the VPS.

## 5. Back up only the ASMAN bot schema from Render

The current Render PostgreSQL database is shared; the bot uses `DB_SCHEMA=agentbot`.
Back up only that schema, not the entire database.

Install/copy the current Render external PostgreSQL URL into the shell only for this command:

```bash
export SOURCE_DATABASE_URL='postgresql://...render...'
export DB_SCHEMA=agentbot
bash scripts/backup_render_schema.sh
unset SOURCE_DATABASE_URL
```

The script creates and validates a custom-format dump under `backups/`.

## 6. Final cutover without losing new operations

For the final migration window:

1. Temporarily stop/suspend the current Render backend so no new writes reach the old database.
2. Take one final `agentbot` schema backup with `backup_render_schema.sh`.
3. Restore that final dump on the VPS:
   ```bash
   bash scripts/restore_to_vps.sh backups/<final-dump>.dump
   ```
4. Start the full VPS stack:
   ```bash
   docker compose up -d --build
   ```
5. Watch startup:
   ```bash
   docker compose ps
   docker compose logs -f --tail=100 app caddy
   ```

Caddy obtains the TLS certificate automatically. The Python app then uses
`https://$APP_DOMAIN` as `WEBHOOK_BASE_URL` and registers the new Telegram webhook.

## 7. Verify the new backend

```bash
curl -fsS "https://$APP_DOMAIN/health"
```

Expected response:

```
Internal Agent Bot OK
```

Also verify:

- Telegram bot commands and menus
- one test client read/write
- cashier page
- Rahbar Mini App
- Agent Mini App
- map/client photo links

## 8. Switch the two static Mini Apps

At the moment the static Mini Apps are intentionally still hosted on Render.
Their API endpoints are hardcoded to the old backend and must be changed only after
the VPS domain is known and verified.

Manager branch/file:

```
branch: manager-miniapp-test
file: manager-miniapp/index.html
old: https://asman-agent-test.onrender.com/api/manager
new: https://$APP_DOMAIN/api/manager
```

Agent branch/file:

```
branch: agent-miniapp-test
file: agent-miniapp/index.html
old: https://asman-agent-test.onrender.com/api/agent
new: https://$APP_DOMAIN/api/agent
```

The backend already accepts the current Render static-site origins, so the static sites
can remain on Render while only the backend/database move to the VPS.

## 9. Automatic local database backups

Run a backup manually:

```bash
bash scripts/backup_local_postgres.sh
```

For a daily 03:20 backup:

```bash
crontab -e
```

Add:

```
20 3 * * * cd /opt/agent-bot && /usr/bin/bash scripts/backup_local_postgres.sh >> /var/log/asman-agent-backup.log 2>&1
```

The script keeps 14 days by default. Copy important backups to a second server or
object storage as well; a backup stored only on the same VPS is not disaster recovery.

## 10. Update and restart later

```bash
git pull --ff-only
docker compose up -d --build
docker compose ps
```

Docker uses `restart: unless-stopped`, so the bot, database and Caddy return after a reboot.

## Rollback

Keep the Render backend and its database intact until the VPS has been verified.
If rollback is required before new production writes are accepted on the VPS:

1. Stop the VPS app: `docker compose stop app`.
2. Point the two Mini App API URLs back to the Render backend.
3. Restart/resume the Render backend so it registers its old webhook again.

If the VPS has already accepted new sales, payments, clients or cashier operations,
do not simply roll back to the old database. First export/synchronize those new writes.
