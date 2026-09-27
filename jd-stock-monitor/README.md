# JD Stock Monitor (website-first)

Read-only hourly monitoring for the JD Hong Kong listing `100414877908`. The monitor does not log in, save an account address, add to cart, or place an order. It selects the requested district only in the temporary public-page browser context.

Current configured target:

- Product: Apple iPhone 18 Pro Max, 256GB, Burgundy Red (the public page showed this selected variant at the initial inspection).
- Area requested: Hong Kong, Wan Chai.
- Page: https://mitem.jd.hk/product/100414877908.html
- Proxy: local HTTP bridge at `http://127.0.0.1:1181` when it is available.

The browser sets `zh-HK`, Hong Kong time, and coarse Wan Chai geolocation, then uses JD's visible address picker to select Hong Kong → Wan Chai District → Wan Chai in that temporary browser context. It does not write an account address or persist browser cookies. Geolocation alone is not treated as the service area. `in_stock`/`out_of_stock` require explicit page text; `unavailable_in_region` is kept distinct; otherwise the result is `unknown`.

## Setup and run

```bash
uv venv .venv --python 3.12
uv pip install --python .venv/bin/python -e '.[test]'
.venv/bin/python -m pytest -q
.venv/bin/python -m jd_stock_monitor --config config.toml
```

The command prints one JSON observation. `unknown` covers missing location/variant confirmation, login/challenge pages, browser errors, and ambiguous availability. It does not attempt a direct-home-IP fallback when the configured proxy fails.

## Hourly schedule and notifications

An hourly Hermes job is not enabled. A one-time, user-approved direct page session selected `港澳中国香港湾仔区湾仔`, but the page showed no explicit stock signal (`unknown`). One proxy IP health request succeeded; JD checks remain unreliable: one returned HTTP 200 but the address picker did not confirm Wan Chai, and a later tunnel failed with a service-credential rejection. NordVPN's own proxy notes say that rejection may be temporary authentication throttling, so do not replace credentials based on that error alone. Re-enable scheduling only after a foreground proxy-only JD baseline confirms both the destination and a usable page response. Intended schedule: minute 0. Delivery remains local-only until a notification destination is specified.

## Safety and limitations

- Uses normal browser rendering and visible page text; it does not replay private/signed JD API requests or evade CAPTCHA/anti-bot controls.
- One check per hour; no retries within a tick.
- Proxy exit location can differ from the requested JD service area. A working proxy does not confirm Hong Kong stock or Wan Chai delivery.
- If JD requires the user to log in or save an address/store, the monitor leaves the observation `unknown`; configure that manually outside this tool if needed.
