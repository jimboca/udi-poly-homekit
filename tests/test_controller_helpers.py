"""Tests for controller helpers (no Polyglot / bridge loop)."""

from __future__ import annotations

from unittest.mock import MagicMock


from homekit_hub.bridge import (
    DATA_KEY_DISCOVER_ZEROCONF_AUTO_APPLIED,
    DATA_KEY_LAST_HAP_DISCOVER,
    TYPED_PAIRING_SLOTS_KEY,
)
from node_funcs import generic_node_address
from nodes.Controller import (
    ERR_ASYNC_LOOP_DEAD,
    Controller,
    _DATA_KEY_CUSTOM_PARAMS_DEFAULT_PRUNE_DONE,
    _DEFAULT_BRIDGE_PARAMS,
    _UI_SEED_CUSTOM_PARAMS,
)
from nodes.SensorNode import SensorNode


class FakeTypedData:
    def __init__(self, store: dict):
        self._store = dict(store)
        self.loads: list[tuple[dict, bool]] = []

    def get(self, key, default=None):
        return self._store.get(key, default)

    def keys(self):
        return list(self._store.keys())

    def __getitem__(self, k):
        return self._store[k]

    def load(self, data, save=True):
        self.loads.append((dict(data), save))
        self._store = dict(data)


class FakeData:
    def __init__(self, d: dict | None = None):
        self._d = dict(d or {})
        self.loads: list[tuple[dict, bool]] = []

    def get(self, key, default=None):
        return self._d.get(key, default)

    def __setitem__(self, key, value):
        self._d[key] = value

    def keys(self):
        return self._d.keys()

    def __getitem__(self, key):
        return self._d[key]

    def load(self, data, save=True):
        self.loads.append((dict(data), save))
        self._d = dict(data)


class FakeParams:
    def __init__(self, d: dict | None = None):
        self._d = dict(d or {})
        self.loads: list[tuple[dict, bool]] = []

    def get(self, key, default=None):
        return self._d.get(key, default)

    def __contains__(self, key):
        return key in self._d

    def __setitem__(self, key, value):
        self._d[key] = value

    def keys(self):
        return self._d.keys()

    def __getitem__(self, key):
        return self._d[key]

    def delete(self, key):
        self._d.pop(key, None)

    def load(self, data, save=True):
        self.loads.append((dict(data), save))
        self._d = dict(data)


def _bare_controller():
    c = Controller.__new__(Controller)
    c.report_error = MagicMock()
    c._maybe_restart_on_config_change = MagicMock()
    c.ready = False
    c.setDriver = MagicMock()
    c.handler_params_st = None
    c.handler_data_st = None
    c.handler_typedparams_st = None
    c.handler_typed_data_st = None
    c._generic_nodes = {}
    c._sensor_by_key = {}
    c._motion_sensor_by_device = {}
    c._thermostat_control_aid = {}
    c._existing_sensor_addnode_retried = set()
    c.n_queue = []
    return c


def test_refresh_change_node_names_default_true():
    c = _bare_controller()
    c.Params = FakeParams({})
    c._refresh_change_node_names_flag()
    assert c.change_node_names is True


def test_refresh_change_node_names_custom_param_false():
    c = _bare_controller()
    c.Params = FakeParams({"change_node_names": "false"})
    c._refresh_change_node_names_flag()
    assert c.change_node_names is False


def test_ensure_default_custom_params_seeds_missing_keys():
    c = _bare_controller()
    c.Params = FakeParams({"ws_host": "127.0.0.1"})
    c._ensure_default_custom_params()
    for key in _UI_SEED_CUSTOM_PARAMS:
        assert key in c.Params
    assert c.Params.get("change_node_names") == "true"
    assert "ws_port" not in c.Params


def test_bridge_get_params_returns_defaults_for_unseeded_keys():
    c = _bare_controller()
    c.Params = FakeParams({"generic_nodes_enable": "false"})
    c.TypedData = FakeTypedData({})
    c.poly = MagicMock()
    c.poly.network_interface = {}
    out = c._bridge_get_params()
    assert out["ws_port"] == _DEFAULT_BRIDGE_PARAMS["ws_port"]
    assert out["mqtt_hub_slug"] == "default"


def test_prune_default_custom_params_removes_advanced_at_default():
    c = _bare_controller()
    c.handler_data_st = True
    c.handler_params_st = True
    c.Params = FakeParams(
        {
            "ws_host": "127.0.0.1",
            "mqtt_hub_slug": "default",
            "generic_nodes_enable": "false",
            "change_node_names": "true",
            "hk_heat_cool_min_delta": "3",
        }
    )
    c.Data = FakeData({})
    c._maybe_prune_default_custom_params_once()
    assert "ws_host" not in c.Params
    assert "mqtt_hub_slug" not in c.Params
    assert c.Data.get(_DATA_KEY_CUSTOM_PARAMS_DEFAULT_PRUNE_DONE) == "true"


def test_prune_default_custom_params_keeps_customized():
    c = _bare_controller()
    c.handler_data_st = True
    c.handler_params_st = True
    c.Params = FakeParams({"mqtt_port": "9999", "generic_nodes_enable": "false"})
    c.Data = FakeData({})
    c._maybe_prune_default_custom_params_once()
    assert c.Params.get("mqtt_port") == "9999"
    assert c.Data.get(_DATA_KEY_CUSTOM_PARAMS_DEFAULT_PRUNE_DONE) == "true"


def test_prune_default_custom_params_skipped_when_flag_set():
    c = _bare_controller()
    c.handler_data_st = True
    c.handler_params_st = True
    c.Params = FakeParams({"ws_host": "127.0.0.1"})
    c.Data = FakeData({_DATA_KEY_CUSTOM_PARAMS_DEFAULT_PRUNE_DONE: "true"})
    c._maybe_prune_default_custom_params_once()
    assert "ws_host" in c.Params


def test_prune_default_custom_params_never_prunes_ui_seed():
    c = _bare_controller()
    c.handler_data_st = True
    c.handler_params_st = True
    c.Params = FakeParams(
        {
            "generic_nodes_enable": "false",
            "change_node_names": "true",
            "hk_heat_cool_min_delta": "3",
            "ws_host": "127.0.0.1",
        }
    )
    c.Data = FakeData({})
    c._maybe_prune_default_custom_params_once()
    for key in _UI_SEED_CUSTOM_PARAMS:
        assert key in c.Params


def test_custom_handlers_have_run_false_until_all_set():
    c = _bare_controller()
    assert c._custom_handlers_have_run() is False
    c.handler_params_st = True
    c.handler_data_st = False
    c.handler_typedparams_st = True
    c.handler_typed_data_st = True
    assert c._custom_handlers_have_run() is True


def test_typed_update_needs_discover_false_when_no_pin():
    c = _bare_controller()
    c.TypedData = FakeTypedData({TYPED_PAIRING_SLOTS_KEY: [{"hap_pin": "", "accessory_id": ""}]})
    c.Data = FakeData({})
    assert c._typed_update_needs_discover() is False


def test_typed_update_needs_discover_true_when_pin_no_filter_and_no_last():
    c = _bare_controller()
    c.TypedData = FakeTypedData(
        {
            TYPED_PAIRING_SLOTS_KEY: [
                {"hap_pin": "12345678", "accessory_id": "", "accessory_name": ""}
            ]
        }
    )
    c.Data = FakeData({DATA_KEY_LAST_HAP_DISCOVER: []})
    assert c._typed_update_needs_discover() is True


def test_typed_update_needs_discover_false_when_last_populated():
    c = _bare_controller()
    c.TypedData = FakeTypedData(
        {
            TYPED_PAIRING_SLOTS_KEY: [
                {"hap_pin": "12345678", "accessory_id": "", "accessory_name": ""}
            ]
        }
    )
    c.Data = FakeData({DATA_KEY_LAST_HAP_DISCOVER: [{"id": "x", "paired": False}]})
    assert c._typed_update_needs_discover() is False


def test_typed_update_needs_discover_false_when_filter_set():
    c = _bare_controller()
    c.TypedData = FakeTypedData(
        {
            TYPED_PAIRING_SLOTS_KEY: [
                {"hap_pin": "12345678", "accessory_id": "aa:bb", "accessory_name": ""}
            ]
        }
    )
    c.Data = FakeData({})
    assert c._typed_update_needs_discover() is False


def test_append_pairing_rows_for_discover_merge_fill_append():
    c = _bare_controller()
    c.TypedData = FakeTypedData(
        {
            TYPED_PAIRING_SLOTS_KEY: [
                {
                    "slot": "1",
                    "hap_pin": "11111111",
                    "accessory_id": "aa:bb:cc",
                    "accessory_name": "",
                    "discover_endpoint": "",
                },
                {"slot": "2", "hap_pin": "", "accessory_id": "", "accessory_name": ""},
            ],
            "other_key": "keep",
        }
    )
    discover_rows = [
        {"id": "AA:BB:CC", "name": "MergedName", "paired": False, "host": "10.0.0.1", "port": 99},
        {"id": "dd:ee:ff", "name": "FillDev", "paired": False, "host": "10.0.0.2", "port": 100},
        {"id": "11:22:33", "name": "Appended", "paired": False},
    ]
    n_app, n_fill, n_merge = c._append_pairing_rows_for_discover(discover_rows)
    assert (n_app, n_fill, n_merge) == (1, 1, 1)
    assert len(c.TypedData.loads) == 1
    saved, _save = c.TypedData.loads[0]
    assert saved["other_key"] == "keep"
    rows = saved[TYPED_PAIRING_SLOTS_KEY]
    by_id = {(r.get("accessory_id") or "").lower(): r for r in rows}
    assert by_id["aa:bb:cc"]["accessory_name"] == "MergedName"
    assert by_id["aa:bb:cc"]["discover_endpoint"] == "10.0.0.1:99"
    assert by_id["dd:ee:ff"]["accessory_id"] == "dd:ee:ff"
    assert by_id["dd:ee:ff"]["accessory_name"] == "FillDev"
    assert by_id["11:22:33"]["accessory_name"] == "Appended"
    assert "slot" in by_id["11:22:33"]
    assert by_id["dd:ee:ff"]["generic_nodes"] == "false"
    assert by_id["11:22:33"]["generic_nodes"] == "false"


def test_ensure_pairing_row_generic_nodes_default_seeds_blank_rows():
    c = _bare_controller()
    c.TypedData = FakeTypedData(
        {
            TYPED_PAIRING_SLOTS_KEY: [
                {"hap_pin": "123-45-678", "generic_nodes": ""},
                {"hap_pin": "111-11-111", "generic_nodes": "true"},
            ]
        }
    )
    assert c._ensure_pairing_row_generic_nodes_default() is True
    rows = c.TypedData.loads[0][0][TYPED_PAIRING_SLOTS_KEY]
    assert rows[0]["generic_nodes"] == "false"
    assert rows[1]["generic_nodes"] == "true"


def test_ensure_pairing_row_generic_nodes_default_noop_when_set():
    c = _bare_controller()
    c.TypedData = FakeTypedData(
        {TYPED_PAIRING_SLOTS_KEY: [{"generic_nodes": "false"}]}
    )
    assert c._ensure_pairing_row_generic_nodes_default() is False
    assert not c.TypedData.loads


def test_append_pairing_rows_for_discover_empty():
    c = _bare_controller()
    c.TypedData = FakeTypedData({TYPED_PAIRING_SLOTS_KEY: []})
    assert c._append_pairing_rows_for_discover([]) == (0, 0, 0)


def test_check_asyncio_loop_thread_health_noop_when_alive():
    c = _bare_controller()
    c.ready = True
    alive = MagicMock()
    alive.is_alive.return_value = True
    c._loop_thread = alive
    c._check_asyncio_loop_thread_health()
    c.report_error.assert_not_called()
    assert c.ready is True


def test_check_asyncio_loop_thread_health_noop_when_dead_but_not_ready():
    c = _bare_controller()
    c.ready = False
    dead = MagicMock()
    dead.is_alive.return_value = False
    c._loop_thread = dead
    c._check_asyncio_loop_thread_health()
    c.report_error.assert_not_called()


def test_check_asyncio_loop_thread_health_reports_when_dead_and_ready():
    c = _bare_controller()
    c.ready = True
    c._async_loop_death_reported = False
    dead = MagicMock()
    dead.is_alive.return_value = False
    c._loop_thread = dead
    c._check_asyncio_loop_thread_health()
    c.report_error.assert_called_once()
    args, kwargs = c.report_error.call_args
    assert args[0] == ERR_ASYNC_LOOP_DEAD
    assert kwargs.get("set_st_error") is True
    assert c.ready is False
    c.setDriver.assert_not_called()
    c.report_error.reset_mock()
    c._check_asyncio_loop_thread_health()
    c.report_error.assert_not_called()


def test_append_pairing_rows_for_discover_load_failure():
    class BadTypedData(FakeTypedData):
        def load(self, data, save=True):
            raise RuntimeError("save failed")

    c = _bare_controller()
    c.TypedData = BadTypedData({TYPED_PAIRING_SLOTS_KEY: []})
    out = c._append_pairing_rows_for_discover(
        [{"id": "aa:bb", "name": "X", "paired": False}],
    )
    assert out == (0, 0, 0)
    c.report_error.assert_called()


def test_handler_stop_clears_generic_nodes_without_deleting():
    c = _bare_controller()
    c._generic_nodes = {'ge3811269468c9': MagicMock(address='ge3811269468c9')}
    c._sensor_by_key = {('aa:bb', 3): MagicMock()}
    c._motion_sensor_by_device = {'aa:bb': MagicMock()}
    c._thermostat_control_aid = {'aa:bb': 2}
    c._paired_nodes = {'c': MagicMock()}
    c.poly = MagicMock()
    c.bridge = None
    c.mainloop = None
    c._mqtt_transport_driver = 0
    c.handler_stop()
    assert c._generic_nodes == {}
    assert c._sensor_by_key == {}
    assert c._motion_sensor_by_device == {}
    assert c._thermostat_control_aid == {}
    assert c._paired_nodes == {}
    c.poly.delNode.assert_not_called()


def test_thermostat_must_self_parent_when_parented_to_controller():
    c = _bare_controller()
    node = MagicMock(id='HKHubEcobeeThermostat', primary='controller', address='ge3811269468c9')
    assert c._thermostat_must_self_parent(node, 'ge3811269468c9') is True


def test_thermostat_must_self_parent_ok_when_self_parented():
    c = _bare_controller()
    node = MagicMock(id='HKHubThermostat', primary='ge3811269468c9', address='ge3811269468c9')
    assert c._thermostat_must_self_parent(node, 'ge3811269468c9') is False


def test_thermostat_profile_fresh_when_rev_not_recorded_and_no_pg3_row():
    c = _bare_controller()
    c.TypedData = FakeTypedData({})
    c.poly = MagicMock()
    c.poly.getNodesFromDb.return_value = []
    node = MagicMock(id='HKHubThermostat', address='ge3811269468c9')
    assert c._thermostat_profile_stale(node, 'ge3811269468c9') is False


def test_thermostat_profile_stale_when_pg3_hint_wrong():
    c = _bare_controller()
    c.TypedData = FakeTypedData({'thermostat_profile_rev': 1})
    c.poly = MagicMock()
    c.poly.getNodesFromDb.return_value = [
        {'address': 'ge3811269468c9', 'nodeDefId': 'HKHubThermostat', 'hint': '0x0'}
    ]
    node = MagicMock(id='HKHubThermostat', address='ge3811269468c9')
    assert c._thermostat_profile_stale(node, 'ge3811269468c9') is True


def test_thermostat_profile_fresh_when_rev_one_but_pg3_metadata_ok():
    c = _bare_controller()
    c.TypedData = FakeTypedData({'thermostat_profile_rev': 1})
    c.poly = MagicMock()
    c.poly.getNodesFromDb.return_value = [
        {
            'address': 'ge3811269468c9',
            'nodeDefId': 'HKHubThermostat',
            'nodeType': '140',
            'hint': '0x010c0100',
        }
    ]
    node = MagicMock(id='HKHubThermostat', address='ge3811269468c9')
    assert c._thermostat_profile_stale(node, 'ge3811269468c9') is False


def test_thermostat_profile_fresh_when_rev_and_hint_ok():
    c = _bare_controller()
    c.TypedData = FakeTypedData({'thermostat_profile_rev': 2})
    c.poly = MagicMock()
    c.poly.getNodesFromDb.return_value = [
        {
            'address': 'ge3811269468c9',
            'nodeDefId': 'HKHubThermostat',
            'nodeType': '140',
            'hint': '0x010c0100',
        }
    ]
    node = MagicMock(id='HKHubThermostat', address='ge3811269468c9')
    assert c._thermostat_profile_stale(node, 'ge3811269468c9') is False


def test_thermostat_sensor_child_addresses_from_pg3():
    c = _bare_controller()
    c.poly = MagicMock()
    c.poly.getNodesFromDb.return_value = [
        {'address': 'ge3811269468c9', 'primaryNode': 'ge3811269468c9'},
        {'address': 'gsensor1', 'primaryNode': 'ge3811269468c9', 'nodeDefId': 'HKHubSensor'},
        {'address': 'other', 'primaryNode': 'controller'},
    ]
    assert c._thermostat_sensor_child_addresses('ge3811269468c9') == ['gsensor1']


def test_delete_thermostat_for_recreation_deletes_children_first():
    c = _bare_controller()
    c.poly = MagicMock()
    child = MagicMock(
        id='HKHubSensor',
        primary='ge3811269468c9',
        device_id='aa:bb',
        role='sensor',
        address='gsensor1',
    )
    therm = MagicMock(
        id='HKHubEcobeeThermostat',
        primary='ge3811269468c9',
        device_id='aa:bb',
        address='ge3811269468c9',
    )
    c._generic_nodes = {'gsensor1': child, 'ge3811269468c9': therm}
    c._sensor_by_key = {('aa:bb', 3): child}
    c._existing_sensor_addnode_retried = {'gsensor1'}
    calls: list[str] = []

    def del_node(addr):
        calls.append(addr)

    c.poly.delNode = del_node
    c.poly.getNodesFromDb.side_effect = [
        [
            {'address': 'gsensor1', 'primaryNode': 'ge3811269468c9'},
            {'address': 'ge3811269468c9', 'primaryNode': 'ge3811269468c9'},
        ],
        None,
    ]
    assert c._delete_thermostat_for_recreation(
        'ge3811269468c9', 'aa:bb', reason='140E profile'
    ) is True
    assert calls == ['gsensor1', 'ge3811269468c9']
    assert 'gsensor1' not in c._generic_nodes
    assert 'ge3811269468c9' not in c._generic_nodes
    assert 'gsensor1' not in c._existing_sensor_addnode_retried


def test_mark_thermostat_profile_rev_skipped_when_stale():
    c = _bare_controller()
    c.TypedData = FakeTypedData({})
    c.poly = MagicMock()
    stale = MagicMock(id='HKHubThermostat', address='ge3811269468c9')
    c._generic_nodes = {'ge3811269468c9': stale}
    c.poly.getNodesFromDb.return_value = [
        {'address': 'ge3811269468c9', 'nodeDefId': 'HKHubThermostat', 'hint': '0x0'}
    ]
    c._mark_thermostat_profile_rev()
    assert c.TypedData.loads == []
    assert c.TypedData.get('thermostat_profile_rev') is None


def test_mark_thermostat_profile_rev_recorded_when_fresh():
    c = _bare_controller()
    c.TypedData = FakeTypedData({})
    c.poly = MagicMock()
    fresh = MagicMock(id='HKHubThermostat', address='ge3811269468c9')
    c._generic_nodes = {'ge3811269468c9': fresh}
    c.poly.getNodesFromDb.return_value = [
        {
            'address': 'ge3811269468c9',
            'nodeDefId': 'HKHubThermostat',
            'nodeType': '140',
            'hint': '0x010c0100',
        }
    ]
    c._mark_thermostat_profile_rev()
    assert c.TypedData.get('thermostat_profile_rev') == 2


def test_ensure_fresh_thermostat_pg3_node_deletes_when_pg3_row_stale():
    c = _bare_controller()
    c.TypedData = FakeTypedData({'thermostat_profile_rev': 1})
    c.poly = MagicMock()
    c.poly.getNodesFromDb.return_value = [
        {
            'address': 'ge3811269468c9',
            'nodeDefId': 'HKHubEcobeeThermostat',
            'nodeType': '140',
            'hint': '0x0',
        }
    ]
    c._delete_thermostat_for_recreation = MagicMock(return_value=True)
    c._ensure_fresh_thermostat_pg3_node(
        'ge3811269468c9', '44:be:73:09:47:20', 'HKHubEcobeeThermostat'
    )
    c._delete_thermostat_for_recreation.assert_called_once_with(
        'ge3811269468c9',
        '44:be:73:09:47:20',
        reason='140E profile (hint/icon/name)',
    )


def test_ensure_fresh_thermostat_pg3_node_skips_when_pg3_row_fresh():
    c = _bare_controller()
    c.TypedData = FakeTypedData({'thermostat_profile_rev': 1})
    c.poly = MagicMock()
    c.poly.getNodesFromDb.return_value = [
        {
            'address': 'ge3811269468c9',
            'nodeDefId': 'HKHubEcobeeThermostat',
            'nodeType': '140',
            'hint': '0x010c0100',
        }
    ]
    c._delete_thermostat_for_recreation = MagicMock(return_value=True)
    c._ensure_fresh_thermostat_pg3_node(
        'ge3811269468c9', '44:be:73:09:47:20', 'HKHubEcobeeThermostat'
    )
    c._delete_thermostat_for_recreation.assert_not_called()


def test_ensure_sensor_node_addnode_when_pg3_ghost_row_only():
    c = _bare_controller()
    c.edition = 'Professional'
    c.is_professional = lambda: True
    c._generic_nodes = {}
    c._sensor_by_key = {}
    c._motion_sensor_by_device = {}
    c._thermostat_control_aid = {'44:be:73:09:47:20': 2}
    c._pairing_display_name = lambda _did: 'Ecobee'
    c._sensor_parent_address = lambda _did: 'ge3811269468c9'
    c._generic_node_address = lambda did, row: generic_node_address(
        did, int(row['aid']), str(row['role'])
    )
    c._schedule_refresh_generic_node = MagicMock()
    c._purge_stale_pg3_node = MagicMock()
    c.add_node = MagicMock(side_effect=lambda node, wait=True: node)
    c.poly = MagicMock()
    c.poly.getNode.return_value = None
    c.poly.db_getNodeDrivers.return_value = []
    c.poly.getNodesFromDb.return_value = [
        {'address': 'g4470f9aa21fa7', 'nodeDefId': 'HKHubSensorDry'}
    ]
    c.address = 'controller'
    node = c._ensure_sensor_node(
        '44:be:73:09:47:20',
        3,
        char_bindings={},
        role='sensor',
        accessory_name='Master Bedroom',
        register_only=False,
    )
    assert node is not None
    c._purge_stale_pg3_node.assert_called_once()
    c.add_node.assert_called_once()


def test_pg3_primary_mismatch_when_controller_parent():
    c = _bare_controller()
    c.poly = MagicMock()
    c.poly.getNodesFromDb.return_value = [
        {
            'address': 'ge3811269468c9',
            'nodeDefId': 'HKHubEcobeeThermostat',
            'primaryNode': 'controller',
            'isPrimary': 0,
        }
    ]
    node = MagicMock(
        id='HKHubEcobeeThermostat',
        address='ge3811269468c9',
        primary='ge3811269468c9',
    )
    assert c._pg3_primary_mismatch(node) is True


def test_pg3_primary_mismatch_false_when_self_parented():
    c = _bare_controller()
    c.poly = MagicMock()
    c.poly.getNodesFromDb.return_value = [
        {
            'address': 'ge3811269468c9',
            'nodeDefId': 'HKHubEcobeeThermostat',
            'primaryNode': 'ge3811269468c9',
            'isPrimary': 1,
        }
    ]
    node = MagicMock(
        id='HKHubEcobeeThermostat',
        address='ge3811269468c9',
        primary='ge3811269468c9',
    )
    assert c._pg3_primary_mismatch(node) is False


def test_add_node_purges_when_pg3_primary_wrong():
    c = _bare_controller()
    c.poly = MagicMock()
    c.poly.getNodesFromDb.return_value = [
        {
            'address': 'ge3811269468c9',
            'primaryNode': 'controller',
            'isPrimary': 0,
        }
    ]
    c.poly.addNode.return_value = MagicMock()
    c._purge_stale_pg3_node = MagicMock()
    c.wait_for_node_done = MagicMock()
    node = MagicMock(
        id='HKHubEcobeeThermostat',
        address='ge3811269468c9',
        primary='ge3811269468c9',
    )
    c.add_node(node)
    c._purge_stale_pg3_node.assert_called_once_with(
        'ge3811269468c9',
        reason='primary migration',
    )
    c.poly.addNode.assert_called_once_with(node)
    c.wait_for_node_done.assert_called_once()


def test_node_queue_unblocks_wait_for_node_done():
    c = _bare_controller()
    c.n_queue = []

    def _release() -> None:
        c.node_queue({'address': 'ge3811269468c9'})

    from threading import Timer

    Timer(0.05, _release).start()
    c.wait_for_node_done()
    assert c.n_queue == []


def test_handler_add_node_done_enqueues_address():
    c = _bare_controller()
    c.node_queue = MagicMock()
    c.handler_add_node_done({'address': 'g4470f9aa21fa7'})
    c.node_queue.assert_called_once_with({'address': 'g4470f9aa21fa7'})


def test_ensure_sensor_node_adds_when_missing():
    c = _bare_controller()
    c.edition = 'Professional'
    c.is_professional = lambda: True
    c._generic_nodes = {}
    c._sensor_by_key = {}
    c._motion_sensor_by_device = {}
    c._thermostat_control_aid = {'44:be:73:09:47:20': 2}
    c._pairing_display_name = lambda _did: 'Ecobee'
    c._sensor_parent_address = lambda _did: 'hkp_c'
    c._generic_node_address = lambda did, row: generic_node_address(
        did, int(row['aid']), str(row['role'])
    )
    c._schedule_refresh_generic_node = MagicMock()
    c.add_node = MagicMock(side_effect=lambda node, wait=True: node)
    c.poly = MagicMock()
    c.poly.getNode.return_value = None
    c.poly.db_getNodeDrivers.return_value = []
    c.poly.getNodesFromDb.return_value = []
    c.address = 'controller'
    node = c._ensure_sensor_node(
        '44:be:73:09:47:20',
        3,
        char_bindings={},
        role='sensor',
        accessory_name='Master Bedroom',
        register_only=False,
    )
    assert node is not None
    c.add_node.assert_called_once()
    key = ('44:be:73:09:47:20', 3)
    assert key in c._sensor_by_key


def test_retry_existing_sensor_recreates_when_pg3_uoms_stale():
    c = _bare_controller()
    c._existing_sensor_addnode_retried = set()
    c._generic_nodes = {}
    c._motion_sensor_by_device = {}
    c._sensor_by_key = {}
    c.poly = MagicMock()
    addr = 'ga31a1dfbd9b71'
    node = MagicMock(
        address=addr,
        role='motion_sensor',
        device_id='44:be:73:09:47:20',
        aid=1,
        primary='ge3811269468c9',
    )
    node.apply_driver_schema = MagicMock()
    c.poly.getNodesFromDb.return_value = [{'address': addr, 'nodeDefId': 'HKHubSensor'}]
    c.poly.db_getNodeDrivers.return_value = [
        {'driver': 'GV2', 'value': 0, 'uom': 25, 'name': 'Contact'},
        {'driver': 'BATLOW', 'value': 0, 'uom': 25, 'name': 'Low battery'},
        {'driver': 'ST', 'value': 82, 'uom': 17, 'name': 'Temperature'},
        {'driver': 'GV1', 'value': 0, 'uom': 25, 'name': 'Motion/Occupancy'},
        {'driver': 'BATLVL', 'value': 0, 'uom': 22, 'name': 'Battery'},
        {'driver': 'CLIHUM', 'value': 30, 'uom': 22, 'name': 'Humidity'},
    ]
    c._recreate_stale_sensor_node = MagicMock()
    c._retry_existing_sensor_addnode(node, addr)
    c._recreate_stale_sensor_node.assert_called_once_with(node, addr)


def test_motion_sensor_schema_includes_clihum_not_battery():
    schema = SensorNode._drivers_for_role('motion_sensor')
    keys = {s['driver'] for s in schema}
    assert 'CLIHUM' in keys
    assert 'BATLVL' not in keys
    assert 'BATLOW' not in keys


def test_apply_driver_schema_skips_deferred_zeros():
    poly = MagicMock()
    poly.db_getNodeDrivers.return_value = [
        {'driver': 'ST', 'value': 74},
        {'driver': 'CLIHUM', 'value': 0},
        {'driver': 'BATLVL', 'value': 0},
    ]
    controller = MagicMock(poly=poly)
    node = SensorNode(
        controller,
        'parent',
        'gsensoraddr01',
        'Kitchen',
        device_id='aa:bb:cc:dd:ee:ff',
        aid=3,
        char_bindings={'RELATIVE_HUMIDITY': {'iid': 1, 'aid': 3}},
        role='sensor',
    )
    node.setDriver = MagicMock()
    node.apply_driver_schema(report=True)
    reported = {call.args[0] for call in node.setDriver.call_args_list}
    assert 'ST' in reported
    assert 'CLIHUM' not in reported
    assert 'BATLVL' not in reported


def test_dry_sensor_schema_omits_clihum():
    schema = SensorNode._drivers_for_role('sensor', {})
    keys = {s['driver'] for s in schema}
    assert 'CLIHUM' not in keys
    assert 'BATLVL' in keys


def test_sensor_nodedef_stale_wrong_nodedef():
    c = _bare_controller()
    c.poly = MagicMock()
    node = MagicMock(
        role='motion_sensor',
        char_bindings={},
        id='HKHubMotionSensor',
        address='gsensoraddr02',
    )
    c._pg3_node_meta = MagicMock(return_value=None)
    assert c._sensor_nodedef_stale(node) is False
    c._pg3_node_meta = MagicMock(return_value={'nodeDefId': 'HKHubSensor'})
    assert c._sensor_nodedef_stale(node) is True


def test_refresh_device_generic_nodes_one_snapshot():
    c = _bare_controller()
    c.hub_snapshot_values = MagicMock(
        return_value=[
            {'aid': 2, 'characteristic': 'CurrentTemperature', 'value': 22.0},
            {'aid': 3, 'characteristic': 'CurrentTemperature', 'value': 21.0},
        ]
    )
    therm = MagicMock(device_id='aa:bb:cc:dd:ee:ff', role='', id='HKHubEcobeeThermostat')
    sensor = MagicMock(
        device_id='aa:bb:cc:dd:ee:ff',
        role='sensor',
        id='HKHubSensorDry',
        aid=3,
    )
    sensor.apply_driver_schema = MagicMock()
    other = MagicMock(device_id='11:22:33:44:55:66', role='sensor', id='HKHubSensorDry', aid=1)
    c._generic_nodes = {'t': therm, 's': sensor, 'o': other}
    c.refresh_device_generic_nodes('aa:bb:cc:dd:ee:ff')
    c.hub_snapshot_values.assert_called_once_with('aa:bb:cc:dd:ee:ff')
    sensor.apply_driver_schema.assert_called()


def test_reuse_existing_sensor_node_report_only_when_stale():
    c = _bare_controller()
    c.is_professional = lambda: True
    c._generic_nodes = {}
    c._sensor_by_key = {}
    c._motion_sensor_by_device = {}
    c._retry_existing_sensor_addnode = MagicMock()
    c._schedule_refresh_generic_node = MagicMock()
    c._sensor_driver_schema_stale = MagicMock(return_value=False)
    node = MagicMock(role='sensor', address='gsensoraddr01')
    node.apply_driver_schema = MagicMock()
    c._reuse_existing_sensor_node(
        node,
        device_id='aa:bb:cc:dd:ee:ff',
        aid=3,
        role='sensor',
        char_bindings={},
        register_only=False,
        addr='gsensoraddr01',
    )
    node.apply_driver_schema.assert_called_once_with(report=False)


def test_inventory_notice_only_on_manual_export():
    c = _bare_controller()
    c.Notices = MagicMock()
    c._inventory_export_notice_callback('aa:bb', '/tmp/x.json', 'pair')
    c.Notices.__setitem__.assert_not_called()
    c._inventory_export_notice_callback('aa:bb', '/tmp/x.json', 'manual_export')
    c.Notices.__setitem__.assert_called_once()


def test_persist_zeroconf_probe_params_merges_only_zeroconf_keys():
    c = _bare_controller()
    c.Params = FakeParams({"ws_host": "127.0.0.1", "zeroconf_unicast": "on"})
    c.Data = FakeData({})
    c.Notices = MagicMock()
    c._discover_restart_notice_pending = False
    c._maybe_restart_on_config_change = MagicMock()
    c._persist_zeroconf_probe_params({"zeroconf_interfaces": "all"})
    assert c.Params.get("zeroconf_interfaces") == "all"
    assert c.Params.get("ws_host") == "127.0.0.1"
    assert c.Params.loads and c.Params.loads[0][1] is True
    assert DATA_KEY_DISCOVER_ZEROCONF_AUTO_APPLIED in c.Data._d
    assert c._discover_restart_notice_pending is True
    c.Notices.__setitem__.assert_called()
    c._maybe_restart_on_config_change.assert_called_once()


def test_discover_progress_notice_includes_phase():
    c = _bare_controller()
    c.Notices = {}
    c._set_discover_progress_notice(
        5,
        phase="HomeKit DISCOVER — primary scan",
        detail="Listening for mDNS.",
    )
    assert "primary scan" in c.Notices["discover_progress"]
    assert "5" in c.Notices["discover_progress"]


def test_on_full_restart_done_clears_discover_bridge_restart_notice():
    c = _bare_controller()
    c._discover_restart_notice_pending = True
    c.Notices = {"discover_bridge_restart": "pending", "hap_discover": "results"}
    c.setDriver = MagicMock()
    c._sync_mqtt_status_driver_from_params = MagicMock()
    fut = MagicMock()
    fut.result.return_value = None
    c._on_full_restart_done(fut)
    assert c._discover_restart_notice_pending is False
    assert "discover_bridge_restart" not in c.Notices
    assert "Bridge restart complete" in c.Notices["hap_discover"]

