# commandcode_project — crawler workspace

Monorepo of crawler/automation tools plus one shared package (`crawler_common`,
installed editable via the root `pyproject.toml`).

| Project | What it does |
|---|---|
| `crawler_common/` | Shared package: config, proxy, fetch, alerts, db (installed with `pip install -e .`) |
| `nordvpn_proxy/` | NordVPN setup + the local HTTP bridge that exposes NordVPN to the collectors |
| `apple-watcher/` | Apple HK pickup/delivery watchers (own Chrome profile, own state/logs) |
| `hk-event-collector/` | HK youth/community event collector (`requests` + Playwright + a urllib Notion call) |
| `jetso-monitor/` | HK deals/coupons + cheap-flight monitor (urllib throughout, Playwright for Flyday/Threads) |
| `maphk-restaurants/` | MapHK restaurant collector + Notion mystery-customer matching |
| `inventory-migration/` | Notion inventory migration tooling |

The recent change wires all outbound HTTP through the NordVPN proxy by default,
so collection traffic exits via a NordVPN datacenter IP instead of the home IP.

## Paths are env-driven

Hard-coded `/home/ubuntu/...` paths were removed. Each project's home is its
own folder unless an env var overrides it — so the same checkout works on
Windows, WSL, and the server:

| Env var | Default | Used for |
|---|---|---|
| `EVENT_COLLECTOR_HOME` | `hk-event-collector/` | CLI + `data/` + venv (telegram wrapper) |
| `JETSO_HOME` | `jetso-monitor/` | `jetso.db`, dev DBs, flight monitor |
| `MAPHK_HOME` | `maphk-restaurants/` | `restaurants.db` and friends |
| `INVENTORY_HOME` | `inventory-migration/` | Notion migration logs/backups |

On the server, export the var to the old absolute path (e.g. `JETSO_HOME=/home/ubuntu/jetso-monitor`)
to preserve the exact production layout. The `flight_deal_monitor.py` shebang
still points at the server's Playwright venv — that one can only live on the
server.

## How the proxy works

`nordvpn_proxy/proxy/http_bridge.py` is an **HTTP CONNECT bridge** run locally
on `http://127.0.0.1:1181`. It:

- accepts plain HTTP CONNECT (all HTTPS traffic) plus a minimal pass-through for
  plain `http://` requests,
- tunnels each connection through a NordVPN SOCKS5 server (credentials from
  `nordvpn_proxy/.env`: `NORDVPN_USER` / `NORDVPN_PASS`),
- **rotates through the NordVPN server list** per connection (round-robin) —
  the same 12-server list used by `nordvpn_proxy/watch/apple_stock_checker.py`
  (override with the env var `NORDVPN_PROXY_HOSTS`, comma-separated).

Why a CONNECT bridge instead of pointing the collectors at `socks5h://…`
directly: neither `urllib` nor `requests` handle SOCKS without the `PySocks`
package, and the credentials would have to live in both collector projects. A
plain-HTTP proxy endpoint works for `urllib`, `requests`, and Playwright with
no new dependencies and no credentials in collector code.

## Running the bridge

```bat
python nordvpn_proxy\proxy\http_bridge.py        :: listens on 127.0.0.1:1181
python nordvpn_proxy\proxy\http_bridge.py 1190   :: override port
```

Verify the exit IP changes:

```bat
python -c "import requests;print(requests.get('https://api.ipify.org?format=json',timeout=30).text)"
python -c "import requests;P='http://127.0.0.1:1181';print(requests.get('https://api.ipify.org?format=json',proxies={'http':P,'https':P},timeout=30).text)"
```

Both values must differ (second shows the NordVPN exit IP).

## Collector wiring

Everything is default-on but overridable with the same two env vars:

| Env var | Default | Meaning |
|---|---|---|
| `PROXY_URL` | `http://127.0.0.1:1181` | Local HTTP bridge endpoint |
| `PROXY_DISABLED` | unset (`0`) | Set to `1` to collect directly from the home IP |
| `NO_PROXY` | `127.0.0.1,localhost` | Loopback bypass (auto-set where relevant) |

### hk-event-collector

- `event_collector/proxyutil.py` — helper (`request_proxies()`, `browser_kwargs()`)
  behind one `enabled()` switch.
- `event_collector/sources.py` — every `requests` call (`get()` and the
  `pioneerelite` tRPC call) passes `proxies=request_proxies()`; both Playwright
  launches (`rendered_get`, `yoplace`) pass `proxy=` via `browser_kwargs()`.
- `event_collector_telegram.py` — sets `HTTP(S)_PROXY` at import so its urllib
  Notion call is covered.
- CLI: `collect-events --direct` ⇒ `PROXY_DISABLED=1`.

### jetso-monitor

- `jetso_monitor.py` — `configure_proxy()` installs an explicit urllib opener
  (and sets `HTTP(S)_PROXY`), so every `urlopen` in the repo is covered. Called
  at the top of `main()`.
- `prd/collect.py` — `_init_proxy_env()` sets the proxy env vars in its
  `__main__` block (all `prd/sources/*` urlopen calls honor them). The `dev/`
  mirror is updated the same way.
- `flight_deal_monitor.py` — `jm.configure_proxy()` in `main()`; the two
  Playwright launches (`fetch_flyday_home`, `fetch_threads_profile`) pass
  `proxy=_pw_proxy()`.

## Disabling / troubleshooting

- Bypass the proxy entirely: `set PROXY_DISABLED=1` (or `--direct` where
  supported) before running a collector.
- **Datacenter IPs get refused by some sites.** The Apple pickup watcher, for
  example, returns HTTP 541 to any non-residential IP (documented in
  `nordvpn_proxy/README.md`). If a collector site starts blocking or returning
  challenges, route that source directly rather than assuming the proxy is the
  fix.
- Bridge won't start: check `NORDVPN_USER` / `NORDVPN_PASS` in
  `nordvpn_proxy/.env` (service credentials, not the account password).
- Rotating server list: the bridge reads `NORDVPN_PROXY_HOSTS` env
  (comma-separated); otherwise it falls back to the built-in 12-server list
  that mirrors `apple_stock_checker.py`.