# Shopify connector fixture

`raw/1001_orders.json` uses a selected GraphQL response shape, with full global IDs, `nodes` connections and decimal MoneyBag values. The selection uses fields inspected in the official GraphQL reference; it is not a response captured from a live shop.

```graphql
query DemoOrders($after: String) {
  orders(first: 50, after: $after) {
    nodes {
      id createdAt updatedAt currencyCode cancelledAt
      displayFinancialStatus displayFulfillmentStatus discountCodes
      totalDiscountsSet { shopMoney { amount currencyCode } }
      lineItems(first: 100) {
        nodes {
          id sku quantity
          originalUnitPriceSet { shopMoney { amount currencyCode } }
        }
        pageInfo { hasNextPage endCursor }
      }
    }
    pageInfo { hasNextPage endCursor }
  }
}
```

This query is an integration starting point. The synthetic order batch deliberately exceeds a real page; fixture orders each have one line, and nested pagination metadata is omitted from the fixture. A live adapter must fetch all order and line-item pages and pin its API version.

`FULFILLED` maps to `shipped`; it is not evidence of delivery. All discounts in this demo are merchant-funded. The adapter preserves global order IDs when linking supplemental settlement/return records.

`raw/1001_supplement.json` supplies catalog/costs, reviews, returns, inventory, promotions, payment-provider settlements and shipping policy. These are local contracts, not native Shopify response objects. Penalty-point support is explicitly `unsupported`, with no health events. No Shopify Payments availability in Vietnam is assumed.

See [normalized core rows](core/), [adapter logic](../scripts/normalize.py), and [sources H1–H5](../SOURCES.md).
