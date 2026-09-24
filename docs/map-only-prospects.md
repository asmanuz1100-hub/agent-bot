# Map-only prospective customers — implementation specification

## Agent flow
- In **🏪 Мижоз қўшиш**, collect the location, photo, up to three phone numbers, name, shop, address and comment as before.
- At the first product-selection step offer **🗺 Товарсиз харитага сақлаш**. A confirmation must persist the customer even with an empty product basket.
- Mark these newly created customers as `map_only=1`; leave historic customers visible as they were.
- Do not write a delivery, inventory transaction, sale or receivable for a map-only customer.
- Show a prospect's name, location, assigned agent and a prospect marker in the agent's and admin's customer maps; the prospect does not appear in the normal **👥 Мижозлар** list.
- Provide a signed agent-owned **📦 Товар бериш** map action so the assigned agent can revisit and give products later, with the existing live-GPS and permissions checks.
- When a real delivery is recorded, set `map_only=0`; the customer then appears in the normal customer list and retains the original record.
- Do not expose payment or return quick actions for a customer who has never received products.

## Where to change
- `core.py`: add and migrate `clients.map_only INTEGER NOT NULL DEFAULT 0` for SQLite/Postgres; clear it only after a successful delivery record.
- `bot.py`: add the product-free branch to the customer-creation wizard and confirmation; change the customer-list query and search for customer-view; count map-only customers when offering the map; add a signed delivery deep link.
- `reports.py`: include map-only customers in the agent/admin map queries, label prospect markers and expose the delivery deep link only to the assigned agent.
- Add regression tests for prospect save (zero debt and stock movement), both maps, list exclusion, conversion on first delivery, and authorization of deep links.

**Status:** design only. This branch does not contain deployed code changes.
