# Cloudflare Tunnel Setup Guide for Local Development

This guide explains how to expose your local development services securely over HTTPS using Cloudflare Tunnel, mapped to subdomains of your own domain (e.g., `dev.petetreadaway.com` and `api.petetreadaway.com`).
You only need to set this up once per machine, and you can easily add or remove local services as needed.

---

## 1. Initial Setup

### Prerequisites
- You own a domain managed by Cloudflare (e.g., `petetreadaway.com`).
- You have a Cloudflare account and access to your domain’s dashboard.
- You have Homebrew installed on your Mac.

### Steps

#### 1.1. Install Cloudflare Tunnel CLI

```
brew install cloudflared
```

#### 1.2. Authenticate with Cloudflare

```bash
couldflared login
```
- This opens a browser window. Select your domain and complete authentication.

### 1.3. Create a Tunnel

```bash
couldflared tunnel create dev-tunnel
```
- This creates a tunnel named `dev-tunnel` and stores credentials locally.

### 1.4. Add DNS Records for Your Subdomains

For each subdomain you want to use (e.g., `dev.petetreadaway.com`, `api.petetreadaway.com`):

```bash
couldflared tunnel route dns dev-tunnel dev.petetreadaway.com
couldflared tunnel route dns dev-tunnel api.petetreadaway.com
```
- This creates CNAME records in Cloudflare DNS pointing to your tunnel.

### 1.5. Create/Edit the Tunnel Config File

Create or edit `~/.cloudflared/config.yml`:

```yaml
tunnel: <your-tunnel-id>
credentials-file: /Users/<your-username>/.cloudflared/<your-tunnel-id>.json

ingress:
  - hostname: dev.petetreadaway.com
    service: http://localhost:8080
  - hostname: api.petetreadaway.com
    service: http://localhost:8443
  - service: http_status:404
```
- Replace `<your-tunnel-id>` and `<your-username>` with your actual values.
- Adjust the `service:` URLs and `hostname:` entries as needed for your setup.

#### 1.6. Start the Tunnel

```bash
cloudflared tunnel run dev-tunnel
```
- Keep this terminal window open while you are developing.

#### 1.7. Test

- Visit `https://dev.petetreadaway.com` and `https://api.petetreadaway.com` in your browser.
- You should see your local apps, served securely via Cloudflare.

---

## 2. Maintenance

### 2.1. Starting and Stopping the Tunnel

- **Start:**  
  ```bash
cloudflared tunnel run dev-tunnel
```
- **Stop:**  
  Press `Ctrl+C` in the terminal running the tunnel.

### 2.2. Adding More Local Services/Subdomains

- Add a new DNS route:
  ```bash
cloudflared tunnel route dns dev-tunnel newsub.petetreadaway.com
```
- Add a new ingress rule to `~/.cloudflared/config.yml`:
  ```yaml
- hostname: newsub.petetreadaway.com
  service: http://localhost:XXXX
```
- Restart the tunnel.

### 2.3. Updating or Removing Services

- **To update:** Edit the corresponding `service:` or `hostname:` in `config.yml` and restart the tunnel.
- **To remove:** Remove the relevant ingress rule from `config.yml`, delete the DNS record in Cloudflare dashboard if desired, and restart the tunnel.

### 2.4. Tunnel Credentials

- Credentials are stored in `~/.cloudflared/`.
- If you need to revoke a tunnel, delete it:
  ```bash
cloudflared tunnel delete dev-tunnel
```
  (You may also want to remove associated DNS records.)

### 2.5. Troubleshooting

- To check the status of the tunnel, run:
  ```bash
cloudflared tunnel info dev-tunnel
```
- Ensure your local dev servers are running on the ports specified in `config.yml`.
- Check the terminal output for errors when starting the tunnel.
- Verify DNS records in the Cloudflare dashboard if subdomains do not resolve.

---

## References

- [Cloudflare Tunnel Docs](https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/)
- [Cloudflare Tunnel Configuration](https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/configuration/)

---

**Enjoy secure, reliable local development with real HTTPS and your own domain!**
```

