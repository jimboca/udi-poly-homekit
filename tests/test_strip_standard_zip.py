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


def _stripped(path: Path) -> str:
    return strip_professional_blocks(path.read_text(encoding='utf-8'))


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


def test_standard_zip_includes_paths_module() -> None:
    exclude = (ROOT / 'zip_exclude_professional.lst').read_text(encoding='utf-8')
    assert 'homekit_hub/paths.py' not in exclude.splitlines()
