# Lab 3 – Revisions & Traffic Splitting

## Objectives

- Understand Azure Container Apps **revision** concepts
- Enable **Multiple** revision mode on the Account API
- Deploy a code change to create a **new revision**
- Use **traffic splitting** to canary-test the new revision
- **Roll back** by shifting traffic to the previous revision

## Architecture

Lab 3 keeps the same three-service architecture from Lab 2. The change is operational: the Account API is switched to **Multiple revision mode**, allowing two revisions to coexist and share traffic.

```
                    ┌─────────────────────────────────┐
                    │  Azure Container Apps Environment │
                    │                                   │
                    │  ┌─────────────────────────────┐  │
                    │  │      Account API             │  │
  Internet ──────►  │  │  ┌──────────┐ ┌──────────┐  │  │
                    │  │  │ Rev 1    │ │ Rev 2    │  │  │
                    │  │  │ (v1 – no │ │ (v2 –    │  │  │
                    │  │  │ /version)│ │ /version)│  │  │
                    │  │  └──────────┘ └──────────┘  │  │
                    │  │     80%           20%        │  │
                    │  └─────────────────────────────┘  │
                    │                                   │
                    │  ┌──────────────┐ ┌────────────┐  │
                    │  │ Transaction  │ │  Payment   │  │
                    │  │     API      │ │    API     │  │
                    │  └──────────────┘ └────────────┘  │
                    └─────────────────────────────────┘
```

## Concepts

| Concept | Description |
|---------|-------------|
| **Revision** | An immutable snapshot of a container app version. Every deployment creates a new revision. |
| **Single mode** | Only one revision receives traffic at a time (default). Old revisions are deactivated. |
| **Multiple mode** | Multiple revisions can coexist. You control the traffic percentage each one receives. |
| **Traffic splitting** | Route a percentage of requests to different revisions — perfect for canary releases. |
| **Revision label** | A friendly name you can assign to a revision for stable URLs (e.g., `green`, `blue`). |

## Files in this Lab (delta from Lab 2)

| File | Status | Purpose |
|------|--------|---------|
| `infra/app/account.bicep` | Modified | Sets `revisionMode: 'Multiple'` for the Account API |
| `app/business-api/python/account/main.py` | Modified | Adds `/api/version` endpoint to identify which revision is serving |

> **Note:** The shared module `infra/shared/host/container-app-upsert.bicep` already accepts a `revisionMode` parameter (default `'Single'`), so no shared module changes are needed.

## Prerequisites

- Labs 1 and 2 completed and deployed
- Working project at the repository root

---

## Step 1 – Apply Lab 3 Files

From the repository root:

```bash
./setup-lab.sh 3
```

This copies the modified `infra/app/account.bicep` and `app/business-api/python/account/main.py` into your workspace.

## Step 2 – Review the Changes

### Infrastructure: `revisionMode` support

The shared module `infra/shared/host/container-app-upsert.bicep` already accepts a `revisionMode` parameter:

```bicep
@allowed([ 'Single', 'Multiple' ])
@description('Controls whether the container app runs in single or multiple revision mode.')
param revisionMode string = 'Single'
```

The default value `'Single'` means Labs 1 and 2 continue to work without changes. In this lab, we override it to `'Multiple'`.

### Account Bicep: Multiple revision mode

Open `infra/app/account.bicep`. The module call now includes:

```bicep
revisionMode: 'Multiple'
```

### Code: Version endpoint

Open `app/business-api/python/account/main.py`. A new endpoint identifies the revision:

```python
@app.get("/api/version")
async def get_version():
    return {
        "version": API_VERSION,
        "revision": REVISION_LABEL,
        "service": "account-api"
    }
```

## Step 3 – Deploy the Updated Account API

```bash
azd up
```

This will:
1. Build a new container image with the `/api/version` endpoint
2. Enable **Multiple** revision mode on the Account API
3. Create a **new revision** (the old revision from Lab 2 still exists)

## Step 4 – Verify the New Revision

```bash
# Get the Account API URL
ACCOUNT_URL=$(azd env get-value ACCOUNT_API_URL)

# Test the new version endpoint
curl $ACCOUNT_URL/api/version
```

Expected response:
```json
{"version": "2.0.0", "revision": "green", "service": "account-api"}
```

## Step 5 – List Revisions

```bash
# Get the container app name
ACCOUNT_APP=$(az containerapp list \
  --resource-group $(azd env get-value AZURE_RESOURCE_GROUP) \
  --query "[?contains(name,'account')].name" -o tsv)

# List all revisions
az containerapp revision list \
  --name $ACCOUNT_APP \
  --resource-group $(azd env get-value AZURE_RESOURCE_GROUP) \
  --output table
```

You should see at least two revisions: the original (from Lab 2) and the new one (with the version endpoint).

## Step 6 – Split Traffic

Distribute traffic: **80%** to the new revision, **20%** to the previous one:

```bash
# Get revision names
REVISIONS=$(az containerapp revision list \
  --name $ACCOUNT_APP \
  --resource-group $(azd env get-value AZURE_RESOURCE_GROUP) \
  --query "[].name" -o tsv)

# The latest revision (last in list)
NEW_REV=$(echo "$REVISIONS" | tail -1)
# The previous revision
OLD_REV=$(echo "$REVISIONS" | head -1)

echo "Old revision: $OLD_REV"
echo "New revision: $NEW_REV"

# Split traffic: 80% new, 20% old
az containerapp ingress traffic set \
  --name $ACCOUNT_APP \
  --resource-group $(azd env get-value AZURE_RESOURCE_GROUP) \
  --revision-weight "$NEW_REV=80" "$OLD_REV=20"
```

## Step 7 – Test Traffic Splitting

Call the version endpoint multiple times. About 80% of requests should return the version response, and 20% should return a 404 (the old revision doesn't have `/api/version`):

```bash
for i in {1..10}; do
  echo "Request $i:"
  curl -s -o /dev/null -w "HTTP %{http_code}" $ACCOUNT_URL/api/version
  echo ""
done
```

You should see a mix of `HTTP 200` and `HTTP 404` responses, roughly in an 80/20 ratio.

## Step 8 – Promote the New Revision (100%)

Once you're confident the new revision is working correctly, send all traffic to it:

```bash
az containerapp ingress traffic set \
  --name $ACCOUNT_APP \
  --resource-group $(azd env get-value AZURE_RESOURCE_GROUP) \
  --revision-weight "$NEW_REV=100"
```

Verify:
```bash
# All requests should return 200 now
for i in {1..5}; do
  curl -s $ACCOUNT_URL/api/version
  echo ""
done
```

## Step 9 – (Optional) Roll Back

If you needed to roll back, you would simply shift traffic back:

```bash
az containerapp ingress traffic set \
  --name $ACCOUNT_APP \
  --resource-group $(azd env get-value AZURE_RESOURCE_GROUP) \
  --revision-weight "$OLD_REV=100"
```

## Key Takeaways

- **Revisions are immutable** — every deployment creates a new one
- **Multiple revision mode** must be enabled before you can split traffic
- **Traffic splitting** lets you do canary releases with fine-grained control
- You can **roll back instantly** by shifting traffic to a previous revision — no redeployment needed
- The shared `container-app-upsert.bicep` already accepts `revisionMode`, making it reusable for any service

## What's Next

In **[Lab 4](../lab-04/README.md)**, you'll enable **Azure Monitor OpenTelemetry** for structured logging, deploy an **Application Insights Dashboard**, and learn to query your services with **KQL**.
