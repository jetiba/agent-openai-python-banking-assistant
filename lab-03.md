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

From the previous lab, the following files will be modified to enable multiple revision mode and traffic splitting:

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

Open `infra/app/account.bicep` and look for the `revisionMode` parameter — you'll see it is now set to `'Multiple'`:

```bicep
revisionMode: 'Multiple'
```

### Code: Version endpoint

Open `app/business-api/python/account/main.py` — a new `/api/version` endpoint has been added that will be used to identify which revision is currently serving the request:

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

Now that we understand the changes made, let's push them to Azure.

```bash
azd up
```

This will:
1. Build a new container image with the `/api/version` endpoint
2. Enable **Multiple** revision mode on the Account API
3. Create a **new revision** (the old revision from Lab 2 still exists)

## Step 4 – Verify the New Revision

Let's confirm that the new revision is running by calling the `/api/version` endpoint we just added. This endpoint will tell us which version and revision is currently serving our request.

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

Now let's see all the revisions that exist for the Account API. Since we enabled Multiple revision mode, the previous revision from Lab 2 is still around alongside the new one.

> **Tip:** If you get an error about the `Microsoft.App` provider not being registered, run:
> ```bash
> az provider register -n Microsoft.App --wait
> ```

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

This is where the power of Multiple revision mode comes in. Instead of sending all traffic to the new revision right away, we'll do a **canary release** — routing most traffic (80%) to the new revision while keeping a small portion (20%) on the previous one. This lets you test the new version with real traffic while minimizing risk. If something goes wrong, you can quickly shift traffic back.

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

Call the version endpoint multiple times. About 80% of requests should return the version response, and 20% should return a 404:

```bash
for i in {1..10}; do
  echo "Request $i:"
  curl -s -o /dev/null -w "HTTP %{http_code}" $ACCOUNT_URL/api/version
  echo ""
done
```

You should see a mix of `HTTP 200` and `HTTP 404` responses, roughly in an 80/20 ratio. The `200` responses come from the **new revision** which has the `/api/version` endpoint, while the `404` responses come from the **old revision** — proving that traffic is being split between the two revisions.

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

## Next Steps 

In **[Lab 4](lab-04.md)**, you'll enable **Azure Monitor OpenTelemetry** for structured logging, deploy an **Application Insights Dashboard**, and learn to query your services with **KQL**.
