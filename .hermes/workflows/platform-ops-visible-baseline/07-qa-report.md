# QA Report — platform-ops-visible-baseline

Role: QA
Timestamp: 2026-05-07T12:27:05+08:00
Verdict: **PASS**

## Scope

Live API/browser/SelfCheck QA for `platform-ops-visible-baseline` against:

- Platform backend: `http://127.0.0.1:8195`
- Platform frontend: `http://127.0.0.1:5173`
- Ecommerce backend: `http://127.0.0.1:8396`

I did not edit product code. I used the local dev admin credential only for browser/API authentication and did not print password or token values.

## 1. API / static checks

### Health / frontend reachability

Command:

```bash
set -o pipefail
for url in \
  http://127.0.0.1:8195/health \
  http://127.0.0.1:8195/api/v1/health \
  http://127.0.0.1:8396/health \
  http://127.0.0.1:8396/api/v1/health \
  http://127.0.0.1:5173/ \
  http://127.0.0.1:5173/login; do
  code=$(curl -sS -o /tmp/qa_curl_body -w '%{http_code}' "$url" || true)
  bytes=$(wc -c </tmp/qa_curl_body)
  printf '%s -> HTTP %s (%s bytes)\n' "$url" "$code" "$bytes"
done
```

Result:

```text
http://127.0.0.1:8195/health -> HTTP 404 (18 bytes)
http://127.0.0.1:8195/api/v1/health -> HTTP 404 (18 bytes)
http://127.0.0.1:8396/health -> HTTP 404 (18 bytes)
http://127.0.0.1:8396/api/v1/health -> HTTP 404 (18 bytes)
http://127.0.0.1:5173/ -> HTTP 200 (634 bytes)
http://127.0.0.1:5173/login -> HTTP 200 (634 bytes)
```

Follow-up with actual service health routes found in router code:

```bash
set -o pipefail
for url in \
  http://127.0.0.1:8195/healthz \
  http://127.0.0.1:8195/readyz \
  http://127.0.0.1:8396/healthz \
  http://127.0.0.1:8396/readyz \
  http://127.0.0.1:8396/api/v1/health \
  http://127.0.0.1:5173/ \
  http://127.0.0.1:5173/login; do
  echo "--- $url"
  curl -sS -i --max-time 5 "$url" | sed -n '1,12p'
done
```

Result:

```text
--- http://127.0.0.1:8195/healthz
HTTP/1.1 200 OK
Content-Type: application/json; charset=utf-8
X-Request-Id: 31034577-c08b-4187-85b9-ba2fcc22b991
X-Trace-Id: e3616103a5b36ba585b65e5c93a10bf7
Date: Thu, 07 May 2026 04:21:54 GMT
Content-Length: 162

{"code":0,"message":"success","timestamp":1778127714382,"request_id":"31034577-c08b-4187-85b9-ba2fcc22b991","data":{"service":"v-platform-backend","status":"ok"}}
--- http://127.0.0.1:8195/readyz
HTTP/1.1 404 Not Found
Content-Type: text/plain
X-Request-Id: b0f0894a-c616-48e8-ac35-48bfe438f398
X-Trace-Id: 706f7ce5b5b61373bb0a098baf27a1c6
Date: Thu, 07 May 2026 04:21:54 GMT
Content-Length: 18

404 page not found
--- http://127.0.0.1:8396/healthz
HTTP/1.1 200 OK
Access-Control-Allow-Credentials: true
Access-Control-Allow-Headers: Authorization, Content-Type, X-Request-ID, X-Trace-ID
Access-Control-Allow-Methods: GET, POST, PUT, PATCH, DELETE, OPTIONS
Content-Type: application/json; charset=utf-8
X-Request-Id: req_1778127714396306725
X-Trace-Id: 76ac2dac5ee9f083f9fdbccdc7dd10f5
Date: Thu, 07 May 2026 04:21:54 GMT
Content-Length: 194

{"code":0,"message":"success","timestamp":1778127714396,"request_id":"req_1778127714396306725","data":{"platform_base_url":"http://127.0.0.1:8195","service":"v-ecommerce-backend","status":"ok"}}
--- http://127.0.0.1:8396/readyz
HTTP/1.1 200 OK
Access-Control-Allow-Credentials: true
Access-Control-Allow-Headers: Authorization, Content-Type, X-Request-ID, X-Trace-ID
Access-Control-Allow-Methods: GET, POST, PUT, PATCH, DELETE, OPTIONS
Content-Type: application/json; charset=utf-8
X-Request-Id: req_1778127714402983621
X-Trace-Id: 2489083770b6cdadef88407b2b210883
Date: Thu, 07 May 2026 04:21:54 GMT
Content-Length: 193

{"code":0,"message":"success","timestamp":1778127714411,"request_id":"req_1778127714402983621","data":{"checks":{"database":"ok","redis":"ok"},"service":"v-ecommerce-backend","status":"ready"}}
--- http://127.0.0.1:8396/api/v1/health
HTTP/1.1 404 Not Found
Access-Control-Allow-Credentials: true
Access-Control-Allow-Headers: Authorization, Content-Type, X-Request-ID, X-Trace-ID
Access-Control-Allow-Methods: GET, POST, PUT, PATCH, DELETE, OPTIONS
Content-Type: text/plain
X-Request-Id: req_1778127714418835474
X-Trace-Id: 111c1bf6483198bdd079b7236be00eeb
Date: Thu, 07 May 2026 04:21:54 GMT
Content-Length: 18

404 page not found
--- http://127.0.0.1:5173/
HTTP/1.1 200 OK
Vary: Origin
Content-Type: text/html
Cache-Control: no-cache
Etag: W/"27a-MWAnHplOn3B+BD2bTt68UZ9mSSk"
Date: Thu, 07 May 2026 04:21:54 GMT
Connection: keep-alive
Keep-Alive: timeout=5
Content-Length: 634

<!doctype html>
<html lang="en">
--- http://127.0.0.1:5173/login
HTTP/1.1 200 OK
Vary: Origin
Content-Type: text/html
Cache-Control: no-cache
Etag: W/"27a-MWAnHplOn3B+BD2bTt68UZ9mSSk"
Date: Thu, 07 May 2026 04:21:54 GMT
Connection: keep-alive
Keep-Alive: timeout=5
Content-Length: 634

<!doctype html>
<html lang="en">
```

Interpretation: platform backend health is exposed at `/healthz`; ecommerce backend health/readiness are exposed at `/healthz` and `/readyz`; frontend root and login route are reachable. Non-canonical `/health`, `/api/v1/health`, and platform `/readyz` returned 404 and are not treated as failures because the implemented health route is `/healthz`.

### SelfCheck validate

Command:

```bash
cd /root/work/agentic-selfcheck
python3 -m selfcheck validate --root .
```

Result:

```text
PASS: no issues
```

### SelfCheck audit

Command:

```bash
cd /root/work/agentic-selfcheck
python3 -m selfcheck audit --root .
```

Result:

```text
PASS: no issues
```

### Project API smoke

Command:

```bash
cd /root/work/agentic-selfcheck
scripts/project_api_smoke.sh v-workspace platform-ops-visible-baseline
```

Result:

```json
{
  "project": "v-workspace",
  "feature": "platform-ops-visible-baseline",
  "status": "PASS",
  "scope": "platform-ops-visible-baseline",
  "expectations": {
    "platform_login_token": true,
    "template_sync_request_ok": true,
    "template_sync_upserted_non_empty": true,
    "template_ops_persisted_projection_visible": true,
    "template_ops_ecommerce_non_empty": true,
    "template_ops_projection_fields": true,
    "catalog_product_ecommerce_exists": true,
    "catalog_skus_minimum": true,
    "catalog_packages_minimum": true,
    "catalog_billable_items_minimum": true,
    "catalog_rate_cards_minimum": true,
    "wallet_assets_minimum": true,
    "quota_policies_minimum": true,
    "offerings_payload_ecommerce": true
  },
  "checks": {
    "platform_login": {
      "url": "http://127.0.0.1:8195/api/v1/auth/login",
      "status": 200,
      "ok": true,
      "duration_ms": 359
    },
    "template_ops_sync": {
      "url": "http://127.0.0.1:8195/api/v1/template-ops/sync?product_code=ecommerce&locale=zh",
      "status": 200,
      "ok": true,
      "duration_ms": 538,
      "upserted_total": 146
    },
    "template_ops_catalog": {
      "ok": true,
      "status": 200,
      "total": 146,
      "item_count": 146,
      "sample_refs": [
        "ecommerce:tpl_s2_t02",
        "ecommerce:tpl_s2_t01",
        "ecommerce:tpl_s1_t02",
        "ecommerce:tpl_s1_t01",
        "ecommerce:tpl_m6_t11"
      ]
    },
    "catalog_products": {
      "ok": true,
      "status": 200,
      "count": 2,
      "ecommerce_product_id": "beba4339-225d-462f-abe4-a6a6031d18cb"
    },
    "catalog_skus": {
      "ok": true,
      "status": 200,
      "count": 5
    },
    "catalog_packages": {
      "ok": true,
      "status": 200,
      "count": 5
    },
    "catalog_billable_items": {
      "ok": true,
      "status": 200,
      "count": 1,
      "codes": [
        "ecommerce.image.generate"
      ]
    },
    "catalog_rate_cards": {
      "ok": true,
      "status": 200,
      "count": 6,
      "target_types": [
        "billable_item",
        "sku"
      ]
    },
    "catalog_offerings": {
      "ok": true,
      "status": 200,
      "has_payload": true
    },
    "wallet_assets": {
      "ok": true,
      "status": 200,
      "count": 4,
      "asset_codes": [
        "ECOMMERCE_CASH",
        "ECOMMERCE_MONTHLY_ALLOWANCE",
        "ECOMMERCE_PROMO_CREDIT",
        "ECOMMERCE_CREDIT"
      ]
    },
    "quota_policies": {
      "ok": true,
      "status": 200,
      "count": 5
    },
    "token_obtained": true
  },
  "notes": [
    "Password/token values are used only in memory and are never printed.",
    "Gate requires the Ecommerce Template Ops sync HTTP request to succeed and report non-empty upserts; persisted projection visibility is tracked separately and cannot mask sync failure."
  ]
}
```

Key smoke confirmations: `status = PASS`; sync returned HTTP `200`; `template_ops_sync.upserted_total = 146`; Template Ops catalog has 146 Ecommerce projections; Catalog API has Ecommerce product, 5 SKUs, 5 packages, 1 billable item, 6 rate cards, 4 wallet assets, and 5 quota policies.

## 2. Browser checks

### Login

- Opened `http://127.0.0.1:5173/login`.
- Confirmed login screen rendered with email/password inputs and `Sign in` button.
- Logged in as local dev platform admin. Password/token are intentionally omitted.
- Post-login dashboard rendered with sidebar navigation and `Platform Admin` identity label.

### Template Ops

Clicked interaction path:

1. From authenticated console, clicked sidebar `Template Ops`.
2. Observed `Template Ops Center` page and `Unified catalog` section.
3. Confirmed page shows a populated table/list, not an empty state.

Visible summary:

- Ecommerce rows are visible in Template Ops.
- First visible rows include:
  - `家居家装套图` / `ecommerce:tpl_s2_t02` / business domain `ecommerce`
  - `3C数码标准套图` / `ecommerce:tpl_s2_t01` / business domain `ecommerce`
  - `女装亚马逊合规套装` / `ecommerce:tpl_s1_t02` / business domain `ecommerce`
- Capability tags such as `workflow_suite / product_photo_package / workflow` and recommendation scores are visible.
- No empty-state message or blank catalog was visible.

Screenshot evidence:

MEDIA:/root/.hermes/cache/screenshots/browser_screenshot_863ebb263aa64047b4b2ab800a6f5921.png

### Catalog & Assets

Clicked interaction path:

1. Clicked sidebar `Catalog & Assets`.
2. Confirmed `Product List` shows current workspace `Agent Ecommerce (ecommerce) · agent-ecommerce`.
3. Confirmed Product row: code `ecommerce`, name `Agent Ecommerce`, owner team `agent-ecommerce`, status `Active`.
4. Observed default `SKU` tab with 5 visible Ecommerce SKU rows, including subscription/resource/promo examples.
5. Clicked `Package` tab and observed 5 package rows.
6. Clicked `Billable Item` tab and observed `ecommerce.image.generate` / `Ecommerce Image Generation` active row.
7. Clicked `Rate Card` tab and observed 6 active rate card rows with `sku:*` and `billable_item:*` targets and current prices.

Visible commercial-data summary:

- Product: `Agent Ecommerce (ecommerce)` visible and active.
- SKU: examples visible included `ecommerce.sku.sub.basic.monthly`, `ecommerce.sku.sub.pro.monthly`, `ecommerce.sku.sub.growth.monthly`, `ecommerce.sku.pack.permanent.basic`, `ecommerce.sku.pack.promo.basic`.
- Package: examples visible included `ecommerce.pkg.sub.basic.monthly`, `ecommerce.pkg.sub.pro.monthly`, `ecommerce.pkg.sub.growth.monthly`, `ecommerce.pkg.pack.permanent.basic`, `ecommerce.pkg.pack.promo.basic`.
- Billable Item: `ecommerce.image.generate` visible and active.
- Rate Card: examples visible included `ecommerce.sku.sub.basic.monthly.v1`, `ecommerce.sku.sub.pro.monthly.v1`, `ecommerce.sku.sub.growth.monthly.v1`, `ecommerce.sku.pack.permanent.basic.v1`, `ecommerce.sku.pack.promo.basic.v1`, and `ecommerce.image.generate.overage.v1`.
- No empty-state message or blank commercial-data section was visible.

Screenshot evidence:

MEDIA:/root/.hermes/cache/screenshots/browser_screenshot_792be3354f1045b385c67d45348822f2.png

### Browser console

Command via browser console collection:

```text
browser_console(clear=false)
```

Result:

```text
console_messages:
- [vite] connecting...
- [vite] connected.
- Download the React DevTools for a better development experience: https://react.dev/link/react-devtools
js_errors: []
total_errors: 0
```

## 3. Unverified items / limitations

- No product code was edited or repaired during QA.
- I did not run broad backend/frontend unit test suites because this QA scope requested live runtime/API/browser/SelfCheck checks.
- Platform `/readyz` and non-canonical `/health` or `/api/v1/health` paths returned 404; implemented `/healthz` returned 200 and was used as the platform health check.
- Screenshots intentionally avoid exposing passwords or tokens.

## Final verdict

**PASS** — Live API/static checks, SelfCheck validate/audit, project smoke gate, and authenticated browser visibility all satisfy the acceptance criteria for `platform-ops-visible-baseline`.
