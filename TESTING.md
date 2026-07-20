# Test environment — bring-up & reproduce

How to run the local Roundcube instance with the **Air** skin and demo data, and
how to get it all back after a **PC restart**.

## What it is

`docker-compose.yml` runs two throwaway containers:

| Container | Image | Ports (host) | Purpose |
|-----------|-------|--------------|---------|
| `am-roundcube` | `roundcube/roundcubemail:latest` | `8095 → 80` | webmail, Air skin mounted live, read-only |
| `am-greenmail` | `greenmail/standalone:2.1.0` | `3025` SMTP, `3143` IMAP | throwaway mail server, **auth disabled** (any login works) |

- Web UI: **http://localhost:8095** — login `demo@localhost`, password **anything**.
- The skins in `skins/air` and `skins/airblue` are bind-mounted, so editing the
  LESS and recompiling the CSS shows on refresh (no rebuild of the container).

> **Important:** GreenMail has **no volume** — all mail lives in memory and is
> **lost whenever the container restarts** (including a PC reboot). Roundcube
> likewise re-runs its installer on each start. So after a reboot the containers
> come back empty and you **re-seed** the demo data (step 4 below).

## Prerequisites (one-time, already set up on this machine)

- **Docker Engine runs inside WSL2** (`Ubuntu-24.04`), *not* Docker Desktop.
  `docker.service` is `enabled` (auto-starts with the distro) and the user is in
  the `docker` group (no `sudo` needed).
- `python3` in WSL (for the seed script). No third-party Python packages required.
- WSL networking is `networkingMode=Mirrored` (in `~/.wslconfig`). `localhost`
  published by Docker is reachable from Windows once the distro is up — **no
  firewall rule is needed** (the Hyper-V firewall's default-block does not affect
  loopback).

## Reproduce after a PC restart

Open a **WSL / Ubuntu terminal** (this boots the distro; `docker.service` starts
automatically and the containers' `restart: unless-stopped` brings them back on
their own). Then:

```bash
cd /mnt/c/Users/skive/Claude/Projects/roundcube-skin

# 1. make sure the containers are up (idempotent — starts them if not already)
docker compose up -d

# 2. wait for Roundcube to finish its first-boot installer (~1–2 min), i.e. HTTP 200
until curl -s -o /dev/null -w '%{http_code}' http://localhost:8095/ | grep -q 200; do
  echo "waiting for roundcube..."; sleep 5
done; echo "roundcube up"

# 3. (re)seed the demo mailbox — 132 inbox messages + 30 work folders
python3 tools/seed-demo.py
```

Then open **http://localhost:8095** (login `demo@localhost` / any password).

## Seed data (`tools/seed-demo.py`)

Idempotent — it **purges** the INBOX and the 30 work folders before filling, so
it is safe to re-run. It produces:

- **132 messages in the INBOX.** The **newest** one carries **10 attachments**
  of varied types (PDF, XLSX, DOCX, PNG, CSV, TXT, JSON, ZIP, ICS, MD).
- A realistic mix for exercising the skin: read/unread (bold), flagged,
  attachment paperclips, HTML newsletters with inline images, `Re:`/`Fwd:`
  threads, dates spread over ~2.5 months.
- **30 subscribed work folders** (Cyrillic names, IMAP UTF-7 encoded), each
  lightly populated with 2–5 messages incl. one unread (so the sidebar shows
  unread badges).

Usage: `python3 tools/seed-demo.py [host] [imap_port] [user]`
(defaults `127.0.0.1 3143 demo@localhost`).

Other seed helpers: `tools/seed-mail.py` / `tools/seed-mail-extra.py` (send a few
messages over SMTP) and `tools/make-folders.py` (create the special
Sent/Drafts/Junk/Trash/Archive folders).

## Editing the skin

Styles are LESS compiled to committed CSS. After editing any `.less` under
`skins/air/styles/`:

```bash
cd skins/air && make css     # recompiles styles.css / print.css / embed.css
```

Refresh the browser (the CSS is mounted live).

## Troubleshooting

- **`localhost:8095` refuses / “connection refused”** — usually the Roundcube
  container is still running its installer right after start; wait 1–2 min (the
  `until` loop above). If it persists, make sure the WSL distro is awake (run any
  `wsl` command / keep a terminal open) and `docker ps` shows both containers
  `Up`.
- **Mail is gone / folders empty after a reboot** — expected (GreenMail is
  throwaway). Re-run `python3 tools/seed-demo.py`.
- **Stop everything:** `docker compose down`. **Start again:** `docker compose up -d`.
- **From Windows PowerShell** instead of a WSL terminal, prefix commands with
  `wsl -e bash -lc "cd /mnt/c/Users/skive/Claude/Projects/roundcube-skin && ..."`.
