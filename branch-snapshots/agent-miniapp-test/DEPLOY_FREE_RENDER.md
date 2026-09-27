# ASMAN Agent — Free Render test deployment

This repository is prepared for a zero-cost test deployment on Render.

## Architecture

- Render Free Web Service
- Telegram webhook mode
- Existing Render PostgreSQL database
- Separate PostgreSQL schema: `agentbot`
- Local development still uses SQLite and long polling

The separate schema prevents the agent bot tables from mixing with the accounting bot tables.

## Deploy

1. In Render Dashboard choose **New → Blueprint**.
2. Connect the GitHub repository `asmanuz1100-hub/agent-bot`.
3. Render reads `render.yaml`.
4. Enter these secret values when prompted:
   - `BOT_TOKEN`
   - `ADMIN_IDS`
5. Keep `DB_SCHEMA=agentbot`.
6. Deploy the Blueprint.
7. Open `/health` on the generated service URL. It should return `ASMAN Agent OK`.
8. Open Telegram and send `/start` to the bot.

## Important free-tier limits

Render Free Web Services can sleep after inactivity. Telegram webhook traffic wakes the service again, so the first response after a sleep can be slower.

The currently referenced Render Free PostgreSQL instance is for testing and is time-limited. Before production use, move the bot to a persistent database plan or another persistent PostgreSQL service.

## First functional test

1. Admin: `/start`
2. Add an agent and a cashier
3. Give the agent 12 units of Gruntovka 7/1
4. Agent starts work and shares live location
5. Add a customer
6. Give 4 units to the customer
7. Record 2 units sold and the total sale amount
8. Record customer payment
9. Hand cash to cashier and accept it
10. Generate reconciliation and weekly analysis

Do not commit Telegram tokens, API keys, or database passwords to GitHub.
