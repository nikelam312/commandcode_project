"""Shared modules for the CommandCode crawler workspace.

One home for the proxy, config, fetch, alerting and DB helpers that the
collectors (hk-event-collector, jetso-monitor, maphk-restaurants),
the NordVPN HTTP bridge and the Apple watcher all use, so each tool stays
thin and behavior is defined once.
"""