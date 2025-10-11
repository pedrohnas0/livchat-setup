# E2E API Test Enhancements - DNS and N8N Support

**Objective**: Update E2E API test to match E2E direct test functionality

## Changes Needed

### 1. Add DNS Configuration (After STEP 3, before STEP 3.5)

Add between lines 344-348 (after setup completes, before Portainer):

```python
# ===========================================
# STEP 3.25: Configure DNS via Cloudflare (if available)
# ===========================================
dns_configured = False
zone_name = config['test_domain']  # "livchat.ai"
subdomain = config['test_subdomain']  # "api-test"

if cloudflare_email and cloudflare_key:
    print(f"\n🌐 [STEP 3.25/8] Configuring DNS via Cloudflare...")
    print(f"   Zone: {zone_name}")
    print(f"   Subdomain: {subdomain}")

    # Note: API doesn't have direct DNS endpoint yet
    # We need to use orchestrator directly for this
    from src.api.dependencies import get_orchestrator
    orch = get_orchestrator()

    # Setup DNS
    import asyncio
    dns_result = asyncio.run(orch.setup_dns_for_server(
        server_name=server_name,
        zone_name=zone_name,
        subdomain=subdomain
    ))

    if dns_result.get('success'):
        dns_configured = True
        print(f"✅ DNS configured successfully!")
        print(f"   Records created:")
        print(f"     - ptn.{subdomain}.{zone_name}")
        print(f"     - edt.{subdomain}.{zone_name}")
    else:
        print(f"⚠️ DNS configuration failed: {dns_result.get('error')}")
else:
    print(f"\n⏭️ [STEP 3.25/8] Skipping DNS (Cloudflare not configured)")
```

### 2. Update Portainer Deployment (Line 353-358)

Change from:
```python
response = api_client.post(
    "/api/apps/portainer/deploy",
    json={
        "server_name": server_name,
        "environment": {}
    }
)
```

To:
```python
portainer_config = {
    "server_name": server_name,
    "environment": {}
}

# Add domain if DNS is configured
if dns_configured:
    portainer_domain = f"ptn.{subdomain}.{zone_name}"
    portainer_config["domain"] = portainer_domain
    print(f"   Using domain: {portainer_domain}")

response = api_client.post(
    "/api/apps/portainer/deploy",
    json=portainer_config
)
```

### 3. Add N8N Deployment (After Redis, before STEP 7)

Add after line 357 (after Redis deployment):

```python
# ===========================================
# STEP 6.5: Deploy N8N via API
# ===========================================
print(f"\n🔄 [STEP 6.5/8] Deploying N8N workflow automation via API...")
print(f"   Dependencies: PostgreSQL, Redis")

n8n_config = {
    "server_name": server_name,
    "environment": {
        "N8N_BASIC_AUTH_USER": "admin",
        "N8N_BASIC_AUTH_PASSWORD": "n8npass123"
    }
}

# Add domain if DNS is configured
if dns_configured:
    n8n_domain = f"edt.{subdomain}.{zone_name}"
    n8n_config["domain"] = n8n_domain
    print(f"   Using domain: {n8n_domain}")

response = api_client.post(
    "/api/apps/n8n/deploy",
    json=n8n_config
)

if response.status_code == 202:
    deploy_data = response.json()
    job_id = deploy_data["job_id"]
    print(f"✅ N8N deployment job started: {job_id}")

    # Monitor deployment
    try:
        job_result = self.poll_job_until_complete(
            api_client,
            job_id,
            "N8N deployment"
        )
        apps_deployed.append("n8n")
        print(f"✅ N8N deployed successfully!")
        if dns_configured:
            print(f"   URL: https://{n8n_domain}")
        print(f"   Credentials: admin / n8npass123")
    except AssertionError as e:
        print(f"⚠️ N8N deployment failed: {e}")
else:
    print(f"⚠️ N8N deployment skipped: {response.status_code}")
```

### 4. Update Assertions (Line 454-457)

Change from:
```python
assert "portainer" in apps_deployed, "Portainer must be deployed (required for app deployments)"
assert "postgres" in apps_deployed, "PostgreSQL must be deployed successfully"
assert "redis" in apps_deployed, "Redis must be deployed successfully"
```

To:
```python
assert "portainer" in apps_deployed, "Portainer must be deployed (required for app deployments)"
assert "postgres" in apps_deployed, "PostgreSQL must be deployed successfully"
assert "redis" in apps_deployed, "Redis must be deployed successfully"
# N8N is optional (requires DNS)
if dns_configured:
    assert "n8n" in apps_deployed, "N8N must be deployed when DNS is configured"
```

### 5. Update Step Numbers

Since we added steps 3.25 and 6.5, update total from "STEP X/7" to "STEP X/8" throughout:
- STEP 1/8
- STEP 2/8
- STEP 3/8
- STEP 3.25/8 (NEW)
- STEP 3.5/8
- STEP 4/8
- STEP 5/8
- STEP 6/8
- STEP 6.5/8 (NEW)
- STEP 7/8 (was 7/7)

## Implementation Steps

1. ✅ Fix domain parameter translation (DONE - infrastructure_executors.py, app_executors.py)
2. ✅ Update E2E API test with DNS support (DONE - added STEP 3.25)
3. ✅ Update E2E API test with N8N deployment (DONE - added STEP 6.5)
4. ✅ Update all step numbers (DONE - 1/8 through 7/8)
5. ✅ Update final assertions (DONE - N8N conditional on DNS)
6. ⏳ Run full E2E API test to verify domain access works (READY TO RUN)
7. ⏳ SSH to server to verify Traefik labels are present (AWAITING TEST RUN)

## Expected Outcome

After these changes:
- Portainer, PostgreSQL, Redis, N8N all deployed
- Services accessible via domain (not just IP)
- Traefik labels present on all services
- Test verifies complete workflow matching E2E direct test
