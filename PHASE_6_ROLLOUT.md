# Phase 6: End-to-End Testing & Rollout

**Timeline:** Week 3, Days 4-5 - Week 4
**Goal:** Production-ready deployment with gradual rollout

## Overview

Final validation through E2E testing in dev environment, then controlled production rollout using feature flags with monitoring and rollback capability.

## Prerequisites

- ✅ Phase 5 completed
- ✅ All components implemented (processor, API, UI)
- ✅ Unit and integration tests passing

## Tasks

### 1. E2E Testing in Dev Environment

**Objective:** Validate complete flow from agent execution to UI display

**Setup dev environment:**
```bash
# Deploy all components to dev
./deploy-dev.sh

# Components:
# - Python SDK with LangGraphCollapsingSpanProcessor
# - Backend API with upsert logic
# - Frontend with SignalR subscription
```

**Create E2E test script:**

**File:** `tests/e2e/test_complete_flow.py`

```python
"""
E2E test for LangGraph span simplification.

Flow:
1. Run LangGraph agent with processor enabled
2. Verify spans exported to API
3. Verify UI receives SignalR updates
4. Verify final state in UI matches expected
"""

import asyncio
import requests
from playwright.async_api import async_playwright
from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
import os

# Dev environment config
API_BASE_URL = "https://llmops-dev.uipath.com/api"
UI_BASE_URL = "https://llmops-dev.uipath.com"
API_KEY = os.getenv("UIPATH_API_KEY_DEV")

@tool
def calculator(expression: str) -> float:
    """Evaluate mathematical expression."""
    return eval(expression)  # Safe for test

async def test_e2e_langgraph_simplification():
    """Complete E2E test."""

    print("🧪 Starting E2E test...")

    # Step 1: Enable simplification
    os.environ["UIPATH_LANGGRAPH_SIMPLIFY"] = "true"

    # Step 2: Run agent
    print("📝 Running LangGraph agent...")

    llm = ChatOpenAI(model="gpt-4o-mini")
    agent = create_react_agent(llm, [calculator])

    result = agent.invoke({
        "messages": [("user", "What is 25 * 4 + 10?")]
    })

    # Extract trace ID (need to add instrumentation to capture this)
    trace_id = get_current_trace_id()  # Helper function
    print(f"✅ Agent completed. Trace ID: {trace_id}")

    # Step 3: Wait for spans to be exported
    await asyncio.sleep(2)

    # Step 4: Verify spans in API
    print("🔍 Verifying spans in API...")

    response = requests.get(
        f"{API_BASE_URL}/traces/{trace_id}/spans",
        headers={"Authorization": f"Bearer {API_KEY}"}
    )
    spans = response.json()

    # Validate span structure
    synthetic_spans = [s for s in spans if s["name"] == "Agent run - Agent"]
    node_spans = [s for s in spans if s["name"] in ["agent", "action"]]
    llm_spans = [s for s in spans
                 if s.get("attributes", {}).get("openinference.span.kind") == "LLM"]
    tool_spans = [s for s in spans
                  if s.get("attributes", {}).get("openinference.span.kind") == "TOOL"]

    assert len(synthetic_spans) == 2, f"Expected 2 synthetic spans, got {len(synthetic_spans)}"
    assert len(node_spans) == 0, f"Expected 0 node spans, got {len(node_spans)}"
    assert len(llm_spans) > 0, "Expected LLM spans"
    assert len(tool_spans) > 0, "Expected tool spans"

    print(f"  ✅ Synthetic spans: {len(synthetic_spans)}")
    print(f"  ✅ Node spans (filtered): {len(node_spans)}")
    print(f"  ✅ LLM spans: {len(llm_spans)}")
    print(f"  ✅ Tool spans: {len(tool_spans)}")

    # Step 5: Verify UI displays correctly
    print("🖥️  Verifying UI...")

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()

        # Navigate to trace viewer
        await page.goto(f"{UI_BASE_URL}/traces/{trace_id}")

        # Wait for trace to load
        await page.wait_for_selector(".span-tree")

        # Check for synthetic span
        agent_span = await page.query_selector('text="Agent run - Agent"')
        assert agent_span is not None, "Synthetic span not found in UI"

        # Check for completed state (no "Running..." badge)
        running_badge = await page.query_selector('text="Running..."')
        assert running_badge is None, "Span still showing as running"

        # Check for duration
        duration_badge = await page.query_selector('.duration-badge')
        assert duration_badge is not None, "Duration not displayed"

        # Check span count (should be simplified)
        span_nodes = await page.query_selector_all('.span-node')
        assert len(span_nodes) < 10, f"Too many spans displayed: {len(span_nodes)}"

        print(f"  ✅ UI displays {len(span_nodes)} spans (simplified)")

        await browser.close()

    print("\n🎉 E2E test PASSED!")

if __name__ == "__main__":
    asyncio.run(test_e2e_langgraph_simplification())
```

**Run:**
```bash
export UIPATH_LANGGRAPH_SIMPLIFY=true
export UIPATH_API_KEY_DEV="..."
export OPENAI_API_KEY="..."

python tests/e2e/test_complete_flow.py
```

### 2. Feature Flag Setup

**Objective:** Configure LaunchDarkly for gradual rollout

**Create feature flag:**

**LaunchDarkly configuration:**
```json
{
  "name": "langgraph-simplification-enabled",
  "key": "langgraph-simplification-enabled",
  "description": "Enable LangGraph span simplification for cleaner traces",
  "kind": "boolean",
  "variations": [
    { "value": false, "name": "Off" },
    { "value": true, "name": "On" }
  ],
  "temporary": false,
  "tags": ["observability", "performance", "ux"]
}
```

**Targeting rules (for rollout):**

**Phase 1: Alpha (Week 3, Day 5)**
```
Rule: "Alpha Test Orgs"
IF organization_id IN ["org-test-1", "org-test-2"]
THEN serve: true
ELSE serve: false (default)
```

**Phase 2: Beta (Week 4, Days 1-2)**
```
Rule: "Beta Test Orgs"
IF organization_id IN ["org-beta-1", "org-beta-2", ..., "org-beta-10"]
THEN serve: true
ELSE serve: false (default)
```

**Phase 3: Gradual Rollout (Week 4, Days 3-5)**
```
Rule: "Percentage Rollout"
Percentage: 10% → 25% → 50% → 100%
Serve: true for selected percentage
Default: false
```

**Integrate in CLI:**

**Modify:** `src/uipath_langchain/_cli/cli_run.py`

```python
from launchdarkly import LDClient, Config, Context

def _should_enable_langgraph_simplification(org_id: str) -> bool:
    """
    Check feature flag for LangGraph simplification.

    Priority:
    1. Environment variable (local override)
    2. LaunchDarkly feature flag (production)
    3. Default: false
    """

    # Check env var first (local development)
    env_override = os.getenv("UIPATH_LANGGRAPH_SIMPLIFY", "").lower()
    if env_override in ["true", "1"]:
        return True
    if env_override in ["false", "0"]:
        return False

    # Check LaunchDarkly in production
    try:
        ld_client = LDClient(Config(sdk_key=os.getenv("LAUNCHDARKLY_SDK_KEY")))

        context = Context.builder(org_id).kind("organization").build()

        enabled = ld_client.variation(
            "langgraph-simplification-enabled",
            context,
            False  # Default
        )

        ld_client.close()
        return enabled

    except Exception as e:
        logger.warning(f"Failed to check feature flag: {e}")
        return False  # Fail safe
```

### 3. Alpha Testing

**Objective:** Enable for 1-2 test orgs, monitor closely

**Setup:**
```bash
# Configure LaunchDarkly
# Add test org IDs to alpha rule

# Monitor logs
kubectl logs -f deployment/llmops-api -n dev | grep "langgraph"
kubectl logs -f deployment/llmops-sdk -n dev | grep "simplification"
```

**Test checklist:**
- [ ] Alpha org can run agents with simplification
- [ ] Spans correctly simplified (verified via API)
- [ ] UI shows running → completed transition
- [ ] No errors in logs
- [ ] Latency within acceptable range (<100ms for processor)
- [ ] Memory usage stable

**Metrics to monitor:**
```sql
-- Span processing latency
SELECT
  AVG(processing_time_ms) as avg_latency,
  P95(processing_time_ms) as p95_latency
FROM span_processor_metrics
WHERE feature = 'langgraph_simplification'
  AND timestamp > NOW() - INTERVAL '1 hour';

-- Span count reduction
SELECT
  COUNT(*) FILTER (WHERE simplified = false) as original_count,
  COUNT(*) FILTER (WHERE simplified = true) as simplified_count
FROM spans
WHERE created_at > NOW() - INTERVAL '1 hour';

-- Error rate
SELECT
  COUNT(*) FILTER (WHERE error = true) as errors,
  COUNT(*) as total
FROM span_processor_logs
WHERE timestamp > NOW() - INTERVAL '1 hour';
```

### 4. Gradual Rollout

**Objective:** Increase coverage progressively with monitoring

**Rollout schedule:**

**Day 1: 10%**
- Enable for 10% of organizations
- Monitor for 24 hours
- Check: error rate < 0.1%, latency < 100ms

**Day 2: 25%**
- Increase to 25%
- Monitor for 24 hours
- Gather user feedback

**Day 3: 50%**
- Increase to 50%
- Monitor for 24 hours
- Performance testing under load

**Day 4: 100%**
- Full rollout
- Continue monitoring for 48 hours
- Declare success or rollback

**Rollback criteria:**
- Error rate > 1%
- P95 latency > 200ms
- >5 user complaints
- Data loss detected
- Memory leak detected

**Rollback procedure:**
```bash
# 1. Disable feature flag immediately
# LaunchDarkly console: Set default to false

# 2. Verify rollback
curl -H "Authorization: Bearer $API_KEY" \
  https://api.launchdarkly.com/api/v2/flags/production/langgraph-simplification-enabled

# 3. Monitor that new spans use old format
kubectl logs -f deployment/llmops-sdk | grep -v "simplification enabled"

# 4. No database rollback needed (backward compatible)
```

### 5. Success Metrics

**Track and validate:**

| Metric | Target | Actual | Status |
|--------|--------|--------|--------|
| Span count reduction | 60%+ | TBD | ⏳ |
| Processing latency P95 | <100ms | TBD | ⏳ |
| Error rate | <0.1% | TBD | ⏳ |
| UI render time | <500ms | TBD | ⏳ |
| User satisfaction | 8/10+ | TBD | ⏳ |
| Support tickets | 50%↓ | TBD | ⏳ |

**User feedback survey:**
```
After using the simplified traces for 1 week:

1. Are traces easier to understand?
   ⭐⭐⭐⭐⭐ (1-5 scale)

2. Do you prefer the new view?
   ☐ Yes, much better
   ☐ Yes, slightly better
   ☐ No difference
   ☐ No, prefer old view

3. Additional comments:
   [Free text]
```

## Success Criteria

- ✅ E2E test passes in dev environment
- ✅ Alpha testing successful (no issues)
- ✅ Gradual rollout completes without rollback
- ✅ All metrics meet targets
- ✅ Positive user feedback (8/10+)
- ✅ No critical bugs reported

## Deliverables

1. E2E test suite (`tests/e2e/test_complete_flow.py`)
2. LaunchDarkly feature flag configuration
3. Monitoring dashboard for rollout metrics
4. Rollout plan and runbook
5. User feedback analysis
6. Final report with metrics

## Timeline

- **Day 4:** E2E testing in dev, fix any issues
- **Day 5:** Alpha testing (2 orgs)
- **Week 4, Day 1:** Beta testing (10 orgs)
- **Week 4, Day 2:** 10% rollout
- **Week 4, Day 3:** 25% rollout
- **Week 4, Day 4:** 50% rollout
- **Week 4, Day 5:** 100% rollout, final validation

## Monitoring Dashboard

**Create Grafana dashboard:**

```yaml
# grafana-dashboard.json
{
  "dashboard": {
    "title": "LangGraph Simplification Rollout",
    "panels": [
      {
        "title": "Span Count Reduction",
        "targets": [{
          "expr": "rate(spans_total{simplified=\"true\"}[5m]) / rate(spans_total[5m])"
        }]
      },
      {
        "title": "Processing Latency P95",
        "targets": [{
          "expr": "histogram_quantile(0.95, span_processor_duration_seconds)"
        }]
      },
      {
        "title": "Error Rate",
        "targets": [{
          "expr": "rate(span_processor_errors_total[5m])"
        }]
      },
      {
        "title": "Feature Flag Coverage",
        "targets": [{
          "expr": "sum(langgraph_simplification_enabled) / sum(organizations_total)"
        }]
      }
    ]
  }
}
```

## Communication Plan

**Announce to users:**

**Email template:**
```
Subject: Improved Trace Viewing Experience

Hi [Organization],

We're excited to announce an enhancement to the UiPath LLM Observability trace viewer!

What's New:
✨ Simplified LangGraph traces - 60% fewer spans
🎯 Clearer execution view - single "Agent run" parent
⚡ Real-time updates - see agent progress live

This improvement is now enabled for your organization. No action needed on your part.

Questions? Contact support@uipath.com

- UiPath LLM Ops Team
```

## Post-Rollout

**After 100% rollout:**
- [ ] Collect final metrics
- [ ] Analyze user feedback
- [ ] Write retrospective document
- [ ] Plan Phase 2 improvements (if any)
- [ ] Archive feature flag (set permanent=true)
