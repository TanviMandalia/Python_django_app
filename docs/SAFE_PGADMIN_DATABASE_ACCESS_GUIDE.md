# Safe pgAdmin Database Access & Least-Privilege Guide

This guide details the secure procedure for administering the production PostgreSQL database using **pgAdmin 4** without exposing the database to the public internet or hard-coding sensitive credentials.

---

## 1. Network Security Architecture

> [!CAUTION]
> **Never open PostgreSQL port 5432 to `0.0.0.0/0` (all IPv4 addresses) or the public internet.** Doing so invites automated brute-force attacks and port scanning.

Render provides two connection endpoints for managed PostgreSQL:
1. **Internal Database URL (`dpg-xxxxxx-a:5432`):** Used strictly by the web service running inside Render's private virtual network. This endpoint is **completely isolated** from the internet.
2. **External Database URL:** If enabled, must be protected by an **IP Access Control List (Allowlist)**.

---

## 2. Option A: Secure SSH Bastion Tunnel (Recommended)

When connecting pgAdmin from your workstation to an internal PostgreSQL database, use an SSH tunnel through a secure bastion host or VPN.

```
[Workstation / pgAdmin] 
         │ (Encrypted SSH Tunnel : Port 22)
         ▼
[Bastion Host / Jump Server] 
         │ (Private Internal Network : Port 5432)
         ▼
[Render Managed PostgreSQL Database]
```

### pgAdmin Configuration Steps:

1. Open **pgAdmin 4**.
2. Right-click **Servers** > **Register** > **Server...**
3. In the **General** tab:
   - **Name:** `Physio-Rehab-Prod-Tunnel`
4. In the **Connection** tab:
   - **Host name/address:** `localhost` *(or `127.0.0.1`)*
   - **Port:** `5433` *(local port mapped by the tunnel)*
   - **Maintenance database:** `physio_db` *(or your DB name from environment variables)*
   - **Username:** `physio_viewer` *(or your dedicated application/admin user)*
   - **Password:** Leave blank or check "Save Password" if using an OS-level encrypted keychain.
5. In the **SSH Tunnel** tab:
   - Check **Use SSH Tunneling**: `Yes`
   - **Tunnel host:** `<YOUR_BASTION_OR_VPN_SERVER_IP>`
   - **Tunnel port:** `22`
   - **Username:** `<YOUR_SSH_USERNAME>`
   - **Authentication:** `Identity file` *(Recommended: Ed25519 or RSA private key)*
   - **Identity file:** Path to your private key (e.g., `~/.ssh/id_ed25519`)
   - **Remote host:** `<INTERNAL_DB_HOSTNAME>` *(from Render dashboard: `dpg-xxxxxx-a`)*
   - **Remote port:** `5432`
6. Click **Save** and connect.

---

## 3. Option B: Render IP Allowlist (If using External URL)

If you must connect directly via the external connection URL without an SSH bastion:

1. Log in to the **Render Dashboard**.
2. Select your PostgreSQL database instance (`physio-db`).
3. Scroll to **Access Control** / **IP Allowlist**.
4. Click **Add IP Address**:
   - Find your current public IP address (e.g. from `https://ipv4.icanhazip.com`).
   - Add your specific IP in CIDR format: `YOUR_IP/32` (e.g. `203.0.113.45/32`).
   - Give it a description: `Admin Workstation - Dhvani`.
5. Under pgAdmin:
   - **Host:** External host provided by Render (e.g., `oregon-postgres.render.com`)
   - **Port:** `5432`
   - **SSL mode:** `Require` or `Verify-Full`

---

## 4. Least-Privilege Database Role Creation

Never run general day-to-day administrative viewing or application tasks using the `postgres` superuser. Use the following SQL commands to create a dedicated read/write application user and a read-only viewer user.

### 4.1 Application User (`physio_app_user`)
```sql
-- Run as superuser/owner initially:
CREATE USER physio_app_user WITH PASSWORD '<STRONG_RANDOMLY_GENERATED_PASSWORD>';

-- Grant connection to the application database:
GRANT CONNECT ON DATABASE physio_db TO physio_app_user;

-- Grant schema usage:
GRANT USAGE ON SCHEMA public TO physio_app_user;

-- Grant data manipulation privileges:
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO physio_app_user;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO physio_app_user;

-- Ensure future tables created by migrations also grant permissions:
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO physio_app_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO physio_app_user;
```

### 4.2 Read-Only Viewer Role (`physio_viewer` for pgAdmin viewing)
```sql
CREATE USER physio_viewer WITH PASSWORD '<STRONG_VIEWER_PASSWORD>';

GRANT CONNECT ON DATABASE physio_db TO physio_viewer;
GRANT USAGE ON SCHEMA public TO physio_viewer;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO physio_viewer;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO physio_viewer;
```

---

## 5. Security Checklist
- [x] Passwords are never committed into Git, bash scripts, or documentation.
- [x] SSL mode is set to `Require` (`sslmode=require`).
- [x] Access is constrained to localhost via SSH tunnel or restricted `/32` IP allowlist.
- [x] pgAdmin operates under a least-privilege role (`physio_viewer` for auditing or `physio_app_user`).
