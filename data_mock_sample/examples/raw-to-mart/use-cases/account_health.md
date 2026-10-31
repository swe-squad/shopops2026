# Does the seller have active penalty events that need attention?

[Back to use-case index](../README.md) · [Complete field reference](../reference.md)

Use this case to answer: **Does the seller have active penalty events that need attention?**

Marts used: `mart.issue_candidates`, `mart.agent_context`. The main calculation is shown below; `issue_candidates` applies the trigger and `agent_context` packages it for the planner.

All measured values below come from the fixed fixture clock, **2026-10-31 00:00 Vietnam time**. Recent window is October 29–30; baseline is October 17–28. The raw/core snippets are representative records; the SQL aggregates use the full source population.

## 1. Source data: what the connector received

The main example uses Shopee shop `1001`. Native order fields are provisional; operational records such as reviews, finance, inventory and health are explicitly labeled demo supplements.

```json
{
  "events": [
    {
      "reason": "Demo: late shipment warning",
      "event_id": "P1",
      "expires_at": "2026-11-30T00:00:00+07:00",
      "occurred_at": "2026-10-30T18:00:00+07:00",
      "penalty_points": 3
    }
  ]
}
```

<details>
<summary>Compare the raw samples from Lazada and Shopify</summary>

### lazada

```json
{
  "events": [
    {
      "reason": "Demo: late shipment warning",
      "event_id": "P1",
      "expires_at": "2026-11-30T00:00:00+07:00",
      "occurred_at": "2026-10-30T18:00:00+07:00",
      "penalty_points": 3
    }
  ]
}
```

### shopify

No health feed in the fixture; absence does not measure zero risk.

</details>

## 2. General core: the normalized business records

The adapters add `shop_key`, retain source IDs, standardize names/statuses, parse timestamps and convert money to exact decimal values. Use shop + entity ID when joining. The following excerpts contain only fields relevant to this case; full rows retain source-document pointers.

```json
{
  "core.account_health": [
    {
      "shop_key": "shopee-open-platform:1001",
      "event_id": "P1",
      "occurred_at": "2026-10-30T11:00:00.000Z",
      "expires_at": "2026-11-29T17:00:00.000Z",
      "penalty_points": 3,
      "reason": "Demo: late shipment warning"
    }
  ]
}
```

## 3. Mart: calculate the measurement

Keep events that occurred before as_of and expire after it. Sum incremental penalty_points, not repeated cumulative balances. The active demo event contributes 3 points.

Run this query against the loaded PostgreSQL database:

```sql
SELECT shop_key,event_id,occurred_at,expires_at,penalty_points,reason
FROM core.account_health CROSS JOIN mart.settings s
WHERE shop_key='shopee-open-platform:1001'
  AND occurred_at<s.as_of
  AND expires_at>s.as_of
ORDER BY event_id;
```

Actual query result:

```json
[
  {
    "shop_key": "shopee-open-platform:1001",
    "event_id": "P1",
    "occurred_at": "2026-10-30T11:00:00.000Z",
    "expires_at": "2026-11-29T17:00:00.000Z",
    "penalty_points": 3,
    "reason": "Demo: late shipment warning"
  }
]
```

## 4. Detection and the input passed to the agent

Trigger: At least 3 active demo penalty points.

Selected fields from the actual `mart.agent_context` packet:

```json
{
  "issue_key": "shopee-open-platform:1001:account_health:shop",
  "shop_key": "shopee-open-platform:1001",
  "platform": "shopee-open-platform",
  "as_of": "2026-10-30T17:00:00+00:00",
  "issue_type": "account_health",
  "entity_key": "shop",
  "severity": "high",
  "metrics": {
    "policy": "Demo alert threshold; not a platform suspension threshold",
    "active_penalty_points": 3
  },
  "decision_mode": "suggest_only"
}
```

The complete packet, including windows and evidence, is available in `cases.json` and `mart.json`. The planner uses these facts to classify the problem and request missing information.

## 5. Plan → seller chooses → execute

The following are illustrative planning options. The data pipeline has not executed them. Current settings, target IDs, seller approval and connector results must be supplied by the next component.

| Option | Expected purpose / required input | Cost and risk | Reversibility |
|---|---|---|---|
| Review the source penalty and its supporting orders | Check whether the event is understood or disputable | Staff time; official policy and order-level penalty evidence must be fetched | Read-only review requires no rollback |
| Prepare an appeal or operational correction for seller review | Address an eligible error or reduce recurrence | Appeal eligibility and success are unknown | An appeal submission may be irreversible |

After the seller chooses an option in Telegram, store the approval under this packet’s `issue_key`, fetch the latest target state, execute idempotently, and retain before/after state and rollback parameters where supported. No numeric impact or success is invented here.

## 6. Verify with new data

Fetch a new account-health observation or event history and confirm source-backed correction, appeal outcome or expiry. Keep expiry separate from evidence that an action caused improvement.

**What to collect next:** Fetch new health records and verify an appeal, correction or expiry in the source.

The frozen fixture contains no post-action success data. Re-querying it proves reproducibility, not action effectiveness.

**Interpretation limits:** The threshold and events are synthetic, and Lazada health is a demo supplement. Shopify is explicitly unsupported. No official suspension threshold is inferred. This case reads core events directly.

Full source → core → mart samples for each platform: [`cases.json`](../cases.json), find `issue_type = "account_health"`. Boundary behavior and unsupported data are explained in the [controls guide](controls.md).
