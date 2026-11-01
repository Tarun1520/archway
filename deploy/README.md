# Deploying Archway

```text
 visitors ──https──> Vercel (the frontend; /api/* is forwarded) ──https──> your server (Oracle Cloud Always Free)
                                                                           Caddy  -> backend (FastAPI + LangGraph)
                                                                                     -> Laya (decision model, on CPU)
```

- **Frontend:** Vercel (free Hobby plan). `/api/*` is forwarded to the server, so the sign-in cookie stays on the
  Vercel address (first-party, `__Host-` cookie).
- **Backend + Laya:** one Oracle Cloud *Always Free* Ampere server (2 CPUs, 12 GB RAM, persistent disk: free,
  always on). Caddy gets the HTTPS certificate by itself. The whole app also works directly at the server's address.

## Live setup (2026-10-29): Azure for Students

The server running now is an **Azure for Students** VM (no card; free 750 h/month of B2ats v2 for 12 months,
renewed yearly while a student). Laya is off: the VM has 1 GB RAM (see `docker-compose.yml`).

- Subscription "Azure for Students", resource group `archway-rg`, VM `archway-vm`, region **indiasouthcentral**
  (the student subscription only allows eastasia, indiasouthcentral, malaysiawest, uaenorth, koreacentral).
- Ubuntu 24.04, `Standard_B2ats_v2`, 64 GB Premium SSD (the free P6 size), user `ubuntu`, key `~/.ssh/archway_oracle`.
- IP `172.198.71.34`, domain `172-198-71-34.sslip.io`; ports 80/443 opened with `az vm open-port`.
- Created from Azure Cloud Shell:
  ```bash
  az group create -n archway-rg -l indiasouthcentral
  az vm create -g archway-rg -n archway-vm --image Ubuntu2404 --size Standard_B2ats_v2 --admin-username ubuntu \
    --ssh-key-values "<contents of archway_oracle.pub>" --public-ip-sku Standard --os-disk-size-gb 64 --storage-sku Premium_LRS
  az vm open-port -g archway-rg -n archway-vm --port 80,443 --priority 900
  ```
- Then steps 4–5 below, and `sh deploy/deploy.sh ubuntu@172.198.71.34 172-198-71-34.sslip.io`.
- **Voice input** needs a WebSocket, which Vercel rewrites do not forward. The page gets a one-time pass through
  Vercel and connects straight to `VOICE_SOCKET_URL=wss://172-198-71-34.sslip.io` (in the server's backend.env;
  `frontend/vercel.json` allows that address in `connect-src`). See LEARNING_GUIDE topic 73.

### Switching Laya on: resize to 4 GB (paid from the $100 credit)

The free hours cover only `Standard_B2ats_v2` (1 GB). `Standard_B2als_v2` (2 CPUs, 4 GB) costs about $0.025/hour
(about $18/month), so the credit lasts about 5 months. The disk, the IP and the data stay the same.

1. In Azure Cloud Shell (portal → the `>_` icon):
   ```bash
   az vm resize -g archway-rg -n archway-vm --size Standard_B2als_v2
   ```
   (About 2 minutes, with a restart. If that size is not offered, `az vm list-vm-resize-options -g archway-rg -n archway-vm -o table` lists the ones that are.)
2. From the repository root on the Mac:
   ```bash
   COMPOSE_PROFILES=laya sh deploy/deploy.sh ubuntu@172.198.71.34 172-198-71-34.sslip.io
   ```
   Laya downloads its model (about 1 GB) the first time; decisions then show **LAYA**.

Back to free: run the normal deploy (without `COMPOSE_PROFILES`; it stops Laya), then
`az vm resize -g archway-rg -n archway-vm --size Standard_B2ats_v2`.

The Oracle steps below still apply if the app ever moves to Oracle Cloud.

## 1. The server (once)

1. Sign up at <https://www.oracle.com/cloud/free/> (a card is asked for identity only; Always Free is not charged).
   Pick a home region close to you; it cannot be changed later.
2. **Create instance**: image **Canonical Ubuntu 24.04**, shape **VM.Standard.A1.Flex** with **2 OCPUs, 12 GB**,
   a public IPv4 address, and under *Add SSH keys* paste the contents of `~/.ssh/archway_oracle.pub`.
   (If it says "out of capacity", try another availability domain, or again later.)
3. In the instance's **Virtual cloud network → Security list**, add ingress rules: TCP **80** and **443** from
   `0.0.0.0/0`.
4. From this folder:
   ```bash
   scp -i ~/.ssh/archway_oracle deploy/setup-server.sh ubuntu@<server-ip>:
   ssh -i ~/.ssh/archway_oracle ubuntu@<server-ip> sh setup-server.sh
   ```
5. Create `~/archway/deploy/backend.env` **on the server** with the secrets and settings (it never leaves the
   server and is never committed). Start from `backend/.env`, and set:
   ```text
   ALLOWED_ORIGINS=https://<your-vercel-domain>,https://<server-domain>
   ADMIN_EMAIL=<your email>
   JEV_MODE=live
   ```
   `<server-domain>` is the IP with dashes plus `.sslip.io`, e.g. `152-67-1-2.sslip.io` (free; sslip.io answers
   with that IP, so Caddy can get a certificate for it).

## 2. Deploy (every update)

```bash
sh deploy/deploy.sh ubuntu@<server-ip> <server-domain>
```

It builds the frontend, copies only the code (never `.env`, databases or virtual environments), and rebuilds and
restarts the containers. The database and Laya's model files live in Docker volumes and survive every deploy.

## 3. Vercel

`frontend/vercel.json` forwards `/api/*` to `https://<server-domain>/api/*`. Then, from `frontend/`:

```bash
vercel login
vercel deploy --prod
```

## Checks after deploying

- `https://<vercel-domain>` shows the welcome page; Sign in / Create account work.
- `https://<server-domain>/docs` answers 404 (the API docs are off on HTTPS).
- A research run shows live progress; decisions show **LAYA**.
- securityheaders.com gives the site an A.

See [docs/security.md](../docs/security.md) for what protects the deployed app.
