# Lab 4 – Logging & Monitoring

## Objectives

- Understand the **observability stack** provided by Azure Container Apps (Log Analytics + Application Insights)
- Enable **Azure Monitor OpenTelemetry** in each Python service so traces, metrics, and logs flow to Application Insights
- Deploy an **Application Insights Dashboard** for a single-pane-of-glass view of your services
- Explore **structured logs** in the Azure Portal and query them with **KQL** (Kusto Query Language)
- View **live metrics** and **end-to-end transaction traces** across services

## Architecture

Lab 4 keeps the same four-service architecture from Labs 2-3. The additions are all about observability: each Python API now sends telemetry to Application Insights via OpenTelemetry, and a portal dashboard visualises the data.

```
                    ┌─────────────────────────────────────────┐
                    │  Azure Container Apps Environment        │
                    │                                          │
                    │  ┌───────────┐  ┌──────────────┐        │
  Internet ──────►  │  │  Account  │  │ Transaction  │        │
                    │  │   API     │  │     API      │        │
                    │  └─────┬─────┘  └──────┬───────┘        │
                    │        │               │                │
                    │  ┌─────┴─────┐  ┌──────┴───────┐        │
                    │  │  Payment  │  │     Web      │        │
                    │  │   API     │  │   Frontend   │        │
                    │  └───────────┘  └──────────────┘        │
                    └────────┬────────────────┬───────────────┘
                             │                │
                    ┌────────▼────────────────▼───────────────┐
                    │        Azure Monitor                     │
                    │  ┌──────────────┐  ┌─────────────────┐  │
                    │  │ Log Analytics│  │ App Insights    │  │
                    │  │  (platform   │  │ (app telemetry: │  │
                    │  │   logs)      │  │  traces, logs,  │  │
                    │  │              │  │  metrics)       │  │
                    │  └──────────────┘  └────────┬────────┘  │
                    │                             │           │
                    │                   ┌─────────▼────────┐  │
                    │                   │    Dashboard     │  │
                    │                   │ (Portal view)    │  │
                    │                   └──────────────────┘  │
                    └─────────────────────────────────────────┘
```

## Concepts

| Concept | Description |
|---------|-------------|
| **Log Analytics workspace** | Central store for all platform and application logs. Already deployed since Lab 1. |
| **Application Insights** | APM (Application Performance Management) service built on Log Analytics. Provides request tracing, dependency tracking, failure analysis, and live metrics. Already deployed since Lab 1. |
| **Azure Monitor OpenTelemetry Distro** | A Python package (`azure-monitor-opentelemetry`) that auto-instruments your app — captures HTTP requests, outgoing calls, and Python log records, then sends them to Application Insights. |
| **Connection string** | The `APPLICATIONINSIGHTS_CONNECTION_STRING` environment variable tells the SDK where to send telemetry. Already injected into each container app since Lab 1. |
| **KQL (Kusto Query Language)** | SQL-like language for querying Log Analytics tables such as `traces`, `requests`, `dependencies`, and `ContainerAppConsoleLogs_CL`. |
| **Application Insights Dashboard** | An Azure Portal dashboard that provides at-a-glance visualisations: request rates, failure rates, response times, and more. |
| **Live Metrics** | Real-time view of incoming requests, outgoing calls, and exceptions — useful for live debugging. |

## Files in this Lab (delta from Labs 1-3)

| File | Status | Purpose |
|------|--------|---------|
| `infra/main.bicep` | Modified | Adds `applicationInsightsDashboardName` parameter to monitoring module call — triggers dashboard deployment |
| `app/business-api/python/account/logging_config.py` | Modified | Enables Azure Monitor OpenTelemetry auto-instrumentation via `configure_azure_monitor()` |
| `app/business-api/python/account/pyproject.toml` | Modified | Adds `azure-monitor-opentelemetry` dependency |
| `app/business-api/python/transaction/logging_config.py` | Modified | Same OpenTelemetry enhancement as account |
| `app/business-api/python/transaction/pyproject.toml` | Modified | Adds `azure-monitor-opentelemetry` dependency |
| `app/business-api/python/payment/logging_config.py` | Modified | Same OpenTelemetry enhancement as payment |
| `app/business-api/python/payment/pyproject.toml` | Modified | Adds `azure-monitor-opentelemetry` dependency |

> **Note:** No changes to `main.parameters.json` — the dashboard name defaults automatically using the naming convention.

## Prerequisites

- Labs 1-3 completed and deployed
- Working project at the repository root

---

## Step 1 – Apply Lab 4 Files

From the repository root:

```bash
./setup-lab.sh 4
```

This copies the updated `logging_config.py`, `pyproject.toml`, and `infra/main.bicep` into your workspace.

## Step 2 – Review the Changes

### Application Code: OpenTelemetry Instrumentation

Open `app/business-api/python/account/logging_config.py`. The `configure_logging()` function now checks for the `APPLICATIONINSIGHTS_CONNECTION_STRING` environment variable:

```python
from azure.monitor.opentelemetry import configure_azure_monitor

configure_azure_monitor(
    connection_string=connection_string,
    logger_name="",               # instrument the root logger
    enable_live_metrics=True,
)
```

Key points:
- **`configure_azure_monitor()`** is an all-in-one call that sets up OpenTelemetry tracing, metrics, and logging exporters
- **`logger_name=""`** instruments the root logger, so all `logging.info()` / `logging.warning()` calls across the app are captured
- **`enable_live_metrics=True`** enables the Application Insights Live Metrics stream
- If the connection string is missing (e.g., local dev), it falls back to the original `logging.basicConfig()` — your app still works offline

### Dependencies: `pyproject.toml`

Each service's `pyproject.toml` now includes:

```toml
"azure-monitor-opentelemetry",
```

This single dependency pulls in the full OpenTelemetry SDK plus Azure Monitor exporters.

### Infrastructure: Application Insights Dashboard

Open `infra/main.bicep`. The monitoring module call now includes an additional parameter:

```bicep
module monitoring './shared/monitor/monitoring.bicep' = {
  name: 'monitoring'
  scope: resourceGroup
  params: {
    // ...existing params...
    applicationInsightsDashboardName: !empty(applicationInsightsDashboardName)
      ? applicationInsightsDashboardName
      : '${abbrs.portalDashboards}${resourceToken}'
  }
}
```

This triggers the deployment of `applicationinsights-dashboard.bicep` — a full Azure Portal dashboard with widgets for:
- Server requests & response time
- Failed requests
- Server exceptions
- Dependency calls & duration
- Browser page load time
- Availability

## Step 3 – Deploy

```bash
azd up
```

This will:
1. Rebuild all three API container images (with the new `azure-monitor-opentelemetry` dependency)
2. Deploy the updated monitoring stack (adding the Application Insights dashboard)
3. Redeploy the container apps (no config change needed — `APPLICATIONINSIGHTS_CONNECTION_STRING` was already injected)

> **Tip:** If you only want to redeploy the APIs without reprovisioning infrastructure:
> ```bash
> azd deploy account && azd deploy transaction && azd deploy payment
> ```
> To deploy just the dashboard:
> ```bash
> azd provision
> ```

## Step 4 – Generate Some Traffic

Send a few requests to generate telemetry data:

```bash
ACCOUNT_URL=$(azd env get-value ACCOUNT_API_URL)

# Hit the accounts endpoint several times
for i in {1..20}; do
  curl -s "$ACCOUNT_URL/api/accounts" > /dev/null
done

# Also hit the version endpoint (from Lab 3)
curl -s "$ACCOUNT_URL/api/version"
```

If you have the frontend deployed, open it in a browser and click around to generate additional traffic.

## Step 5 – View Container App Logs (Platform Logs)

Azure Container Apps automatically sends platform logs (stdout/stderr) to Log Analytics. View them in the Azure Portal:

1. Go to **Azure Portal** → your **Resource Group** → your **Log Analytics workspace**
2. Click **Logs** in the left nav
3. Run this KQL query:

```kql
ContainerAppConsoleLogs_CL
| where ContainerAppName_s contains "account"
| project TimeGenerated, Log_s, ContainerAppName_s, RevisionName_s
| order by TimeGenerated desc
| take 50
```

You should see log lines from your services, including the `"Azure Monitor OpenTelemetry configured successfully"` startup message.

## Step 6 – Explore Application Insights

1. Go to **Azure Portal** → your **Resource Group** → **Application Insights** resource
2. Explore the following sections:

### Live Metrics
Click **Live Metrics** in the left nav. You'll see real-time incoming requests, outgoing calls, and exceptions streaming in. Send a few more `curl` requests to see them appear.

### Application Map
Click **Application Map**. This auto-discovers your services and their dependencies, showing request rates and failure percentages between components.

### Transaction Search
Under  **Transaction search**. Filter by time range and search for specific requests. Click on a request to see the **end-to-end transaction detail** — including correlated logs, dependencies, and timing.

### Failures
Click **Failures** to see any failed requests grouped by operation, response code, and exception type.

## Step 7 – Query Application Logs with KQL

In Application Insights → **Logs**, try these queries:

### All Traces (Application Logs)
```kql
traces
| where timestamp > ago(1h)
| project timestamp, message, severityLevel, cloud_RoleName
| order by timestamp desc
| take 50
```

### Request Performance by Service
```kql
requests
| where timestamp > ago(1h)
| summarize
    avgDuration = avg(duration),
    p95Duration = percentile(duration, 95),
    requestCount = count(),
    failedCount = countif(success == false)
  by cloud_RoleName
| order by requestCount desc
```

### Slow Requests (> 500ms)
```kql
requests
| where timestamp > ago(1h)
| where duration > 500
| project timestamp, name, duration, resultCode, cloud_RoleName
| order by duration desc
```

### Dependency Calls Between Services
```kql
dependencies
| where timestamp > ago(1h)
| project timestamp, name, target, duration, success, cloud_RoleName
| order by timestamp desc
| take 30
```

## Step 8 – Explore the Dashboard

1. Go to **Home** → **Dashboard** -> **Browse all Dashboards** → **Shared Dashboard**
2. Find the dashboard named with your environment prefix (e.g., `dash-<token>`)
3. The dashboard shows at-a-glance widgets:
   - **Server Requests** — total count and trend
   - **Response Time** — average and percentiles
   - **Failed Requests** — error rate
   - **Dependency Duration** — outgoing call latency
   - **Browser Page Load Time** — (when frontend is generating telemetry)

> **Tip:** You can customise the dashboard in the portal — add tiles, change time ranges, or pin additional charts from Application Insights.

## Step 9 – (Optional) Structured Logging in Code

The OpenTelemetry instrumentation captures all Python `logging.*` calls. You can add structured context with the `extra` parameter:

```python
import logging

logger = logging.getLogger(__name__)

# This log message will appear in Application Insights 'traces' table
# with custom dimensions for account_id and operation
logger.info(
    "Processing account request",
    extra={"account_id": "12345", "operation": "get_balance"},
)
```

In KQL, query custom dimensions:

```kql
traces
| where message == "Processing account request"
| extend accountId = tostring(customDimensions.account_id)
| project timestamp, message, accountId, cloud_RoleName
```

## Key Takeaways

- **Platform logs** (stdout/stderr) flow to Log Analytics automatically via the ACA Environment — no SDK needed
- **Application telemetry** (traces, metrics, logs) requires the `azure-monitor-opentelemetry` SDK — a single `configure_azure_monitor()` call instruments everything
- The **`APPLICATIONINSIGHTS_CONNECTION_STRING`** env var was already injected since Lab 1 — Lab 4 adds the SDK to use it
- **Application Insights** provides Application Map, Live Metrics, Transaction Search, and Failures views out of the box
- **KQL** gives you full query power over your logs and metrics
- **Dashboards** provide a sharable, at-a-glance view of your application's health

## Next Steps 

In **[Lab 5](lab-05.md)**, you'll add **built-in authentication** (Easy Auth) to your container apps and integrate **Azure Key Vault** to manage application secrets securely.
