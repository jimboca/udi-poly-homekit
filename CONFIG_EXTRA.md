# HomeKit Hub — advanced configuration

Rarely-changed **Custom Configuration Parameters** (MQTT, WebSocket, mDNS/zeroconf). Typical installs leave these at shipped defaults — runtime behavior is unchanged even when they are not shown in the PG3 Configuration table.

For normal setup (pairing, typed tables, and the three flat params shown in the UI), see [CONFIG.md](CONFIG.md).

## When to read this

- **Multiple hubs on one MQTT broker** — set a unique **`mqtt_hub_slug`** per hub (must match downstream plugins such as **udi-poly-ecobee**).
- **Custom MQTT or WebSocket bind** — non-default broker host/port or WebSocket listen address.
- **mDNS / DISCOVER troubleshooting** — `zeroconf_*` tuning when **DISCOVER** finds nothing and **Extra Discovery Networks** are already correct.

## How to set an advanced param

1. Open the Node Server **Configuration** page → **Custom Configuration Parameters**.
2. **Add** a row; the **key** must match the table below exactly (e.g. `mqtt_hub_slug`).
3. Enter the value and **Save**. The hub restarts the bridge when transport-related params change.

After upgrading to **2.0.13**, a **one-time** cleanup may have removed advanced params that were still at shipped defaults. Re-adding a key manually is never auto-removed again.

## UI-seeded params (CONFIG.md)

These three flat params are always shown in the PG3 Custom Configuration Parameters table:

| Parameter | Default | Summary |
|-----------|---------|---------|
| `generic_nodes_enable` | `false` | **Professional:** master switch for generic IoX child nodes. |
| `change_node_names` | `true` | When `true`, IoX renames paired-device nodes to track discover/pairing names. |
| `hk_heat_cool_min_delta` | `3` | **Professional:** minimum heat/cool gap (°F) when writing thermostat thresholds. |

## Advanced flat parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `mqtt_enable` | `true` | `true` / `false` (string). When `true`, the hub connects to the LAN MQTT broker (see `PROTOCOL.md`). |
| `mqtt_host` | `localhost` | MQTT broker hostname or IP. |
| `mqtt_port` | `1884` | MQTT broker port (Polisy/eISY general MQTT / PG3-style broker). |
| `mqtt_username` | *(empty)* | Optional broker username. |
| `mqtt_password` | *(empty)* | Optional broker password. |
| `mqtt_hub_slug` | `default` | Topic segment after `udi/homekit/hubs/` for this hub instance. Use a **unique** slug when multiple hubs share one broker. |
| `ws_host` | `127.0.0.1` | WebSocket bind address. |
| `ws_port` | `8163` | WebSocket port. |
| `ws_token` | *(empty)* | Optional shared secret for the WebSocket API. When set, clients must send it on `hello` (see `PROTOCOL.md`). **Does not apply to MQTT** (v1: use broker ACLs). |
| `zeroconf_unicast` | `on` | `on` (default), `auto`, or `off`. **`on`** uses python-zeroconf unicast mode (typical on eISY where UDP **5353** is shared). **`auto`** tries multicast first, then falls back. **`off`** forces multicast only. |
| `zeroconf_interfaces` | *(empty)* | `default`, `all`, or leave empty. Optional narrowing for BSD/macOS unicast quirks (errno **49**). |
| `zeroconf_ip_version` | *(empty)* | `v4`, `v6`, `all`, or leave empty. |

**Zeroconf tuning:** On a normal Polisy / eISY deployment you can ignore the three `zeroconf_*` keys. Run controller command **ZEROCONF_DIAG** for a support snapshot. After changing `zeroconf_*` or WebSocket bind settings, save configuration; the hub restarts the asyncio bridge automatically.

## Environment variable overrides

Override Custom Params `zeroconf_*` for the Node Server process (typical users do not set these):

| Variable | Values | Purpose |
|----------|--------|---------|
| `HOMEKIT_HUB_ZEROCONF_UNICAST` | `1` / `true` / `yes` / `on` or `0` / `false` / `off` | Force unicast or multicast. |
| `HOMEKIT_HUB_ZEROCONF_INTERFACES` | `default` / `all` | Interface selection for zeroconf. |
| `HOMEKIT_HUB_ZEROCONF_IP_VERSION` | `v4` / `v6` / `all` | IP stack for zeroconf. |

## Security / MQTT auth

WebSocket binds to `127.0.0.1` by default. **MQTT (v1):** no application-level secret like **`ws_token`**; use broker authentication, ACLs, and a private LAN. See `PROTOCOL.md` for the wire format.

## Multiple WebSocket clients

Other Node Servers (e.g. **udi-poly-ecobee**) connect as clients. The hub fan-outs HAP events; each client filters by `device_id`. **`hello` `ack`** and **`list_devices`** include accessory **category** metadata (e.g. **9** = thermostat).
