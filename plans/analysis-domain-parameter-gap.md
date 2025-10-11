# Analysis: Domain Parameter Mismatch

**Date**: 2025-10-11
**Issue**: Services deployed via API are not accessible via domain (only via direct IP)

## Root Cause Analysis

### Problem Discovery

SSH inspection of deployed services showed NO Traefik labels:
```bash
$ docker service inspect portainer_portainer --format '{{json .Spec.TaskTemplate.ContainerSpec.Labels}}'
{
    "com.docker.stack.namespace": "portainer"
    # ❌ Missing Traefik labels!
}
```

Expected labels (when domain is configured):
```json
{
    "traefik.enable": "true",
    "traefik.http.routers.portainer.rule": "Host(`ptn.lab.livchat.ai`)",
    "traefik.http.services.portainer.loadbalancer.server.port": "9000",
    "traefik.http.routers.portainer.tls.certresolver": "letsencryptresolver"
}
```

### Parameter Name Mismatch

**The Bug**: Inconsistent parameter naming across the stack

**API Endpoint** → `domain`
```python
# src/api/routes/apps.py:209
params={
    "domain": request.domain  # ✅ API accepts "domain"
}
```

**Infrastructure Executor** → `domain` (WRONG!)
```python
# src/job_executors/infrastructure_executors.py:60
if domain:
    config["domain"] = domain  # ❌ Passes as "domain"
```

**Server Setup** → expects `dns_domain` (CORRECT!)
```python
# src/server_setup.py:604
if "dns_domain" in config:  # ❌ Looks for "dns_domain"
    config["portainer_domain"] = config["dns_domain"]
```

**Result**: `dns_domain` is not found, so `PORTAINER_DOMAIN` remains empty, causing Traefik labels to use default: `portainer.localhost`

### Flow Comparison

**Working Flow** (E2E Direct Test):
```
test_complete_e2e_workflow.py
  ↓ passes: config["dns_domain"] = "ptn.lab.livchat.ai" ✅
  ↓
orchestrator.deploy_portainer()
  ↓
server_setup.deploy_portainer()
  ↓ finds: config["dns_domain"] ✅
  ↓ maps: config["portainer_domain"] = config["dns_domain"]
  ↓
deploy_infrastructure_from_yaml()
  ↓ substitutes: ${PORTAINER_DOMAIN} → "ptn.lab.livchat.ai" ✅
  ↓
Traefik labels: Host(`ptn.lab.livchat.ai`) ✅
```

**Broken Flow** (E2E API Test):
```
test_api_e2e_workflow.py
  ↓ POST /api/apps/portainer/deploy {"domain": "ptn.lab.livchat.ai"}
  ↓
infrastructure_executor.py
  ↓ passes: config["domain"] = "ptn.lab.livchat.ai" ❌ Wrong key!
  ↓
orchestrator.deploy_portainer()
  ↓
server_setup.deploy_portainer()
  ↓ searches: if "dns_domain" in config ❌ NOT FOUND!
  ↓ result: portainer_domain is NEVER set
  ↓
deploy_infrastructure_from_yaml()
  ↓ substitutes: ${PORTAINER_DOMAIN:-portainer.localhost} → "portainer.localhost" ❌
  ↓
Traefik labels: Host(`portainer.localhost`) ❌
```

## Consistency Check

Parameter usage across codebase:

| Component | Uses `dns_domain` | Uses `domain` |
|-----------|-------------------|---------------|
| E2E Direct Test | ✅ Yes (line 285, 361) | No |
| server_setup.py | ✅ Yes (line 604) | No |
| API models | No | ✅ Yes (request field) |
| infrastructure_executors.py | ❌ **BUG** Should use! | ✅ Currently uses |
| app_executors.py | ❌ **BUG** Should use! | ✅ Currently uses |

**Conclusion**:
- Internal system uses `dns_domain` ✅
- API accepts `domain` ✅
- **Executors must translate `domain` → `dns_domain`** ❌ Currently missing!

## Solution

### Option 1: Fix Executors (RECOMMENDED)

Change executors to translate `domain` → `dns_domain`:

```python
# src/job_executors/infrastructure_executors.py:60
if domain:
    config["dns_domain"] = domain  # ✅ Use correct internal name
```

```python
# src/job_executors/app_executors.py:49
if domain:
    config["dns_domain"] = domain  # ✅ Use correct internal name
```

**Pros**:
- Minimal change (2 lines)
- Keeps API interface clean (`domain` is user-friendly)
- Aligns with internal convention (`dns_domain` is accurate)

**Cons**:
- None

### Option 2: Change server_setup.py

Change `server_setup.py` to accept `domain` instead of `dns_domain`

**Pros**:
- None

**Cons**:
- Breaks existing working code (E2E direct test)
- `dns_domain` is more descriptive for internal use
- Would require changing all callers

### Option 3: Accept Both

```python
domain_value = config.get("dns_domain") or config.get("domain")
```

**Pros**:
- Maximum compatibility

**Cons**:
- Ambiguous - which one takes precedence?
- Technical debt - duplicate ways to do same thing

## Decision

**✅ Implement Option 1** - Fix executors to translate `domain` → `dns_domain`

Rationale:
- API layer uses user-friendly `domain`
- Internal layer uses precise `dns_domain`
- Executors are the translation layer (already translate other params)
- Minimal risk, clear semantics

## Implementation Plan (TDD)

### 1. Write Unit Tests
- Test infrastructure executor with domain
- Test app executor with domain
- Verify correct parameter translation

### 2. Fix Implementation
- Update `infrastructure_executors.py:60`
- Update `app_executors.py:49`

### 3. Update E2E API Test
- Add DNS configuration step (like E2E direct)
- Pass `domain` to Portainer deployment
- Add N8N deployment (like E2E direct)
- Verify services accessible via domain

### 4. Verify
- Run unit tests
- Run E2E API test
- SSH to server, verify Traefik labels present
- Test domain access

## Files to Modify

1. `src/job_executors/infrastructure_executors.py` - Line 60
2. `src/job_executors/app_executors.py` - Line 49
3. `tests/unit/job_executors/test_infrastructure_executors.py` - Add test
4. `tests/unit/job_executors/test_app_executors.py` - Add test
5. `tests/e2e/test_api_e2e_workflow.py` - Add DNS setup + N8N deployment

## Success Criteria

- [ ] Unit tests pass with domain translation
- [ ] E2E API test configures DNS
- [ ] E2E API test deploys N8N
- [ ] Services accessible via domain (not just IP)
- [ ] SSH inspection shows Traefik labels present
- [ ] All tests pass (27 unit + E2E)
