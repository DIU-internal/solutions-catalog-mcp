# Deploy on NVIDIA DGX-1 / Ubuntu 20.04

This deployment targets a DGX-1 with Ubuntu 20.04.6 LTS and host-installed nginx. The MCP uses CPU
ONNX inference because the complete catalog has only 137 records; enabling the eight V100 GPUs would
add CUDA and NVIDIA Container Toolkit dependencies without a useful latency benefit.

## Architecture

```text
Codex / MCP client
        |
        | HTTP :8080 (trusted network) or HTTPS :443
        v
host nginx
        |
        | http://127.0.0.1:8001
        v
Docker container: FastMCP /mcp
        |
        +-- embedded Qdrant (137 records)
        +-- local BGE ONNX model cache
```

Only nginx is network-facing. Embedded Qdrant is not a separate service and exposes no database port.

## 1. Copy the repository to the DGX

```bash
git clone YOUR_REPOSITORY_URL solutions-catalog-mcp
cd solutions-catalog-mcp
```

Confirm Docker Compose is available:

```bash
docker --version
docker compose version
sudo systemctl enable --now docker
```

If the DGX has the standalone Compose binary instead of the plugin, replace `docker compose` with
`docker-compose` in the commands below.

The container does not require `nvidia-docker`, `--gpus`, CUDA, or a GPU driver mount.

## 2. Configure and build the service

```bash
cd deploy/dgx
cp .env.example .env
openssl rand -hex 32
```

Put the generated secret in `DIU_MCP_API_KEY` inside `.env`, then build and start:

```bash
docker compose up -d --build
docker compose ps
docker compose logs --tail=100 diu-catalog-mcp
```

The first image build needs outbound HTTPS access to PyPI and Hugging Face. It embeds the dependencies,
model, CSV, and Qdrant index in the resulting image; normal container starts are offline and fast.

Verify from the DGX host:

```bash
curl http://127.0.0.1:8001/health
curl http://127.0.0.1:8001/ready
```

Expected readiness includes `"indexed_records":137`.

## 3. Configure host nginx for IP:port access

This option exposes `http://DGX_IP:8080/mcp`, suitable for a trusted LAN or VPN.
Because bearer tokens are not encrypted by plain HTTP, do not route this endpoint across an
untrusted network; use the HTTPS configuration below instead.

From the repository root:

```bash
sudo cp deploy/dgx/nginx-ip-port.conf /etc/nginx/sites-available/diu-catalog-mcp
sudo ln -s /etc/nginx/sites-available/diu-catalog-mcp /etc/nginx/sites-enabled/diu-catalog-mcp
sudo nginx -t
sudo systemctl reload nginx
```

If the symlink already exists, do not recreate it; update the file and reload nginx.

Restrict port 8080 to the client IP or trusted network. Examples:

```bash
sudo ufw allow from CLIENT_IP to any port 8080 proto tcp
# or for a private LAN/VPN range:
sudo ufw allow from 10.0.0.0/8 to any port 8080 proto tcp
sudo ufw status
```

Do not run `ufw enable` remotely until SSH access is explicitly allowed and you have confirmed the
DGX's existing firewall policy.

Verify through nginx:

```bash
curl http://DGX_IP:8080/health
curl http://DGX_IP:8080/ready
```

## 4. Connect Codex

On the machine running Codex, export the same token stored on the DGX:

```bash
export DIU_CATALOG_MCP_TOKEN="YOUR_DGX_SECRET"
```

Add this to `~/.codex/config.toml`:

```toml
[mcp_servers.diu_catalog]
url = "http://DGX_IP:8080/mcp"
bearer_token_env_var = "DIU_CATALOG_MCP_TOKEN"
required = true
startup_timeout_sec = 30
tool_timeout_sec = 60
```

Restart Codex and confirm the `diu_catalog` MCP server reports seven tools. Official Codex MCP
configuration documentation: <https://developers.openai.com/codex/mcp/>.

## 5. Connect another Streamable HTTP client

Use this MCP endpoint:

```text
http://DGX_IP:8080/mcp
```

Send the token as:

```text
Authorization: Bearer YOUR_DGX_SECRET
```

If the client uses a JSON connection definition, the equivalent shape is generally:

```json
{
  "url": "http://DGX_IP:8080/mcp",
  "headers": {
    "Authorization": "Bearer YOUR_DGX_SECRET"
  }
}
```

Exact configuration keys vary by client; Streamable HTTP and the bearer header are the interoperable
pieces.

## Public Internet or ChatGPT

Use HTTPS for any connection that crosses the public Internet. Assign a DNS name to the DGX, obtain a
trusted certificate, and adapt `nginx-https.conf.example`. The resulting MCP URL is:

```text
https://mcp.example.com/mcp
```

ChatGPT requires a publicly reachable HTTPS Streamable HTTP endpoint for a public connection. Follow
the official connection guide: <https://developers.openai.com/apps-sdk/deploy/connect-chatgpt/>.

## Operations

Status and logs:

```bash
cd deploy/dgx
docker compose ps
docker compose logs -f diu-catalog-mcp
curl http://127.0.0.1:8001/ready
sudo tail -f /var/log/nginx/diu-catalog-mcp.error.log
```

Rebuild after catalog or code changes:

```bash
git pull --ff-only
cd deploy/dgx
docker compose up -d --build
```

Stop without deleting the built image:

```bash
docker compose down
```

## Troubleshooting

- **502 from nginx:** Run `docker compose ps`, check container logs, and verify
  `curl http://127.0.0.1:8001/ready` on the DGX.
- **401 from `/mcp`:** Confirm the client sends the same bearer token as `DIU_MCP_API_KEY` in `.env`.
- **Connection timeout:** Check nginx is listening with `sudo ss -ltnp | grep -E ':8001|:8080'`, then
  verify the host firewall and upstream network ACLs.
- **Container marked unhealthy:** Read container logs. Readiness requires the embedded Qdrant index
  and model cache to load successfully.
- **Image build cannot download the model:** Build on another amd64 Docker host, push the image to a
  registry, or transfer it with `docker save` / `docker load`.
- **Multiple Uvicorn workers fail:** Keep one process per container. Embedded Qdrant uses an exclusive
  local storage lock.
