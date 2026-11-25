# Deploying Bento

One Linux server runs the whole stack with Docker Compose, behind Caddy for HTTPS. This guide uses
**Oracle Cloud Always Free** (4 CPUs and 24 GB of memory on ARM, free permanently) and a **free domain
from the GitHub Student Developer Pack**, but any Ubuntu server with 4 GB+ and any domain work the same.

What runs where:

```
browser ──https──► Caddy (80/443, automatic certificates)
                     └─► frontend (nginx) ──/api──► api-gateway ──► workers, Postgres, TimescaleDB, Redis, Ollama
                                                     (none of these are reachable from the internet)
```

## 1. Get a domain (free with the Student Pack)

1. Open **https://education.github.com/pack** and sign in with GitHub (verify your student status if asked).
2. Find the **Namecheap** offer (a free `.me` domain for a year) or **name.com / .TECH**, and claim a
   domain, e.g. `yourname.me`.
3. Keep its DNS settings page open: you'll add one record in step 3.

## 2. Create the server (Oracle Cloud Always Free)

1. Sign up at **https://www.oracle.com/cloud/free/** (a card is used for verification only). Pick a home
   region close to your users; Always Free capacity is per region.
2. **Compute → Instances → Create instance**:
   - **Image:** Canonical Ubuntu 24.04
   - **Shape:** *Change shape* → **Ampere** → `VM.Standard.A1.Flex`, **4 OCPUs, 24 GB memory**
     (if it says *out of capacity*, try another availability domain or retry later)
   - **SSH keys:** *Generate a key pair for me* and **download the private key**, or upload your own
     (`ssh-keygen -t ed25519` on your laptop creates one).
   - Create. Note the **public IP address** shown on the instance page.
3. Open the web ports: on the instance page → **Subnet** → **Security list** → **Add ingress rules**:
   source `0.0.0.0/0`, TCP, destination port **80**; repeat for **443**.

## 3. Point the domain at the server

In your domain's DNS settings, add an **A record**: host `bento` (or `@` for the bare domain), value =
the server's public IP. Your Bento address is then `bento.yourname.me`. DNS can take a few minutes.

## 4. Prepare the server

```bash
ssh -i path/to/private.key ubuntu@<public-ip>
curl -fsSL https://raw.githubusercontent.com/shak5hi/bento/main/deploy/server-setup.sh | bash
exit            # log out and back in so Docker works without sudo
ssh -i path/to/private.key ubuntu@<public-ip>
```

This installs Docker, opens ports 80/443 in Ubuntu's own firewall (Oracle images block them by default)
and puts Bento in `~/bento` with an empty `backend/.env`.

## 5. Fill in the settings

```bash
nano ~/bento/backend/.env
```

- `BENTO_DOMAIN`: e.g. `bento.yourname.me`
- `POSTGRES_PASSWORD`, `JWT_SECRET`: run `openssl rand -hex 32` once for each and paste the output
- `GITHUB_*`: the same values as on your laptop (copy them over yourself)
- `RESEND_API_KEY`, `EMAIL_FROM`: see step 8

## 6. Start Bento

```bash
cd ~/bento/backend
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

The first start builds everything and downloads Pickle's model, which takes 5 to 15 minutes. Then open
`https://bento.yourname.me`. Caddy fetches the HTTPS certificate on the first visit.

Check on it with `docker compose ps` and `docker compose logs -f caddy api-gateway`.

## 7. Point the GitHub App at the new address

In **https://github.com/settings/apps** → your app → **General**, replace `http://localhost:8080` (and the
tunnel address) with `https://bento.yourname.me` in:

| Field | Value |
|---|---|
| Homepage URL | `https://bento.yourname.me` |
| Callback URL | `https://bento.yourname.me/api/auth/github/callback` |
| Setup URL | `https://bento.yourname.me/api/auth/github/callback` |
| Webhook URL | `https://bento.yourname.me/api/webhooks/github` |

No more cloudflared tunnel: the webhook address never changes now.

## 8. Email to anyone (Resend)

1. In **https://resend.com/domains**, add your domain and add the DNS records it shows (SPF and DKIM) at
   your domain's DNS settings. Wait for *Verified*.
2. In `backend/.env`, set `EMAIL_FROM=Bento <alerts@yourname.me>` and your `RESEND_API_KEY`.
3. `docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d`

## Day to day

```bash
cd ~/bento && git pull
cd backend && docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build   # update
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs -f api-gateway             # logs
```

**Backups:** a compressed dump of both databases is written every day to the `bento_backups` volume, and
the last 7 are kept. To copy them off the server:
`docker run --rm -v bento_bento_backups:/b -v "$PWD":/out alpine cp -r /b /out/backups`.
To restore one: `gunzip -c bento-YYYY-MM-DD.sql.gz | docker exec -i bento-postgres psql -U bento -d bento`.

**Pickle's model:** the template uses `qwen2.5:3b`, which the 24 GB server runs comfortably. Set
`PICKLE_MODEL` to any Ollama model, or `OLLAMA_URL=` (empty) to use rule-based text only.
