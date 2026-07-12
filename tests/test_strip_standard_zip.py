"""Regression: Standard strip must keep shared hub RPC / bootstrap symbols."""

from __future__ import annotations

import re
from pathlib import Path

from scripts.strip_standard_zip import strip_professional_blocks

ROOT = Path(__file__).resolve().parents[1]
STRIP_FILES = (
    ROOT / 'nodes' / 'Controller.py',
    ROOT / 'homekit_hub' / 'bridge.py',
    ROOT / 'nodes' / '__init__.py',
)
MARKER_BEGIN = '# %% professional-only begin'
MARKER_END = '# %% professional-only end'


def _stripped(path: Path) -> str:
    return strip_professional_blocks(path.read_text(encoding='utf-8'))


def _professional_only_methods(src: str) -> set[str]:
    methods: set[str] = set()
    skip = False
    for line in src.splitlines():
        if MARKER_BEGIN in line:
            skip = True
            continue
        if MARKER_END in line:
            skip = False
            continue
        if not skip:
            continue
        m = re.match(r'\s+(?:async )?def ([A-Za-z_][A-Za-z0-9_]*)\(', line)
        if m:
            methods.add(m.group(1))
    return methods


def _dangling_self_calls(src: str, methods: set[str]) -> dict[str, list[str]]:
    stripped = strip_professional_blocks(src)
    dangling: dict[str, list[str]] = {}
    for name in sorted(methods):
        hits = []
        for i, line in enumerate(stripped.splitlines(), 1):
            if re.search(rf'\bself\.{re.escape(name)}\s*\(', line):
                hits.append(f'L{i}: {line.strip()}')
        if hits:
            dangling[name] = hits
    return dangling


def test_standard_strip_compiles() -> None:
    for path in STRIP_FILES:
        compile(_stripped(path), str(path), 'exec')


def test_standard_strip_keeps_snapshot_rpc() -> None:
    bridge = _stripped(ROOT / 'homekit_hub' / 'bridge.py')
    assert re.search(r'async def fetch_snapshot_values\s*\(', bridge)
    assert re.search(r'async def _handle_snapshot\s*\(', bridge)
    assert 'await self.fetch_snapshot_values(' in bridge
    # Professional-only writes / inventory stay stripped
    assert not re.search(r'async def put_characteristic\s*\(', bridge)
    assert not re.search(r'async def _export_device_inventory\s*\(', bridge)


def test_standard_strip_keeps_config_debug_bootstrap() -> None:
    ctrl = _stripped(ROOT / 'nodes' / 'Controller.py')
    assert 'self._config_debug_export_token = 0' in ctrl
    assert 'from homekit_hub.paths import ensure_persistent_dir' in ctrl
    assert 'from homekit_hub.config_debug import export_config_debug' in ctrl
    assert 'def _schedule_config_debug_export' in ctrl
    assert 'ensure_persistent_dir()' in ctrl
    # Professional edition plumbing stays stripped
    assert 'from dev_settings import' not in ctrl
    assert 'self.edition =' not in ctrl
    assert '_maybe_refresh_generic_sensor_nodes' not in ctrl
    assert '_wait_for_pg3_node_gone' not in ctrl


def test_standard_strip_no_dangling_professional_method_calls() -> None:
    """Shared code must not call methods that exist only inside professional-only blocks."""
    for path in (ROOT / 'nodes' / 'Controller.py', ROOT / 'homekit_hub' / 'bridge.py'):
        src = path.read_text(encoding='utf-8')
        dangling = _dangling_self_calls(src, _professional_only_methods(src))
        assert not dangling, f'{path}: dangling after strip: {dangling}'


def test_standard_zip_includes_paths_module() -> None:
    exclude = (ROOT / 'zip_exclude_professional.lst').read_text(encoding='utf-8')
    assert 'homekit_hub/paths.py' not in exclude.splitlines()


def test_config_debug_tolerates_missing_device_inventory(monkeypatch, tmp_path) -> None:
    """Standard zips omit device_inventory; config snapshot export must still succeed."""
    import homekit_hub.config_debug as config_debug
    import sys
    import types

    class _Ctrl:
        poly = types.SimpleNamespace()
        Params = {}
        Data = {}
        TypedData = {}
        ready = True
        change_node_names = True
        bridge = None
        mainloop = None
        handler_config_done_st = True
        handler_params_st = True
        handler_data_st = True
        handler_typed_params_st = True
        handler_typed_data_st = True

        def getDriver(self, _name):
            return 0

    monkeypatch.chdir(tmp_path)
    # Ensure import fails as on Standard.
    sys.modules.pop('homekit_hub.device_inventory', None)
    real_import = __import__

    def _block_inventory(name, *args, **kwargs):
        if name == 'homekit_hub.device_inventory' or name.startswith(
            'homekit_hub.device_inventory.'
        ):
            raise ImportError(name)
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr('builtins.__import__', _block_inventory)
    path = config_debug.export_config_debug(_Ctrl(), reason='unit-test')
    assert path is not None
    assert path.exists()
