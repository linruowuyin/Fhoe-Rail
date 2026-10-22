"""Regression for the summary produced by the CLI after a completed route."""
import importlib.util
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock

import pytest


@pytest.fixture
def cli(monkeypatch):
    # Import the real entry point without window, network, or configuration IO.
    services = {
        'pyuac': {},
        'get_width': {'check_mult_screen': Mock()},
        'utils.config.config': {'ConfigurationManager': Mock()},
        'utils.core.log': {'fetch_php_file_content': Mock(), 'log': Mock()},
        'utils.flows.map_operations': {'MapOperations': Mock()},
        'utils.core.map_info': {'MapInfo': Mock()},
        'utils.ui.map_selector': {'choose_map': Mock(), 'choose_map_debug': Mock()},
        'utils.core.notify': {'Notify': Mock(), 'get_error_summary': Mock()},
        'utils.ui.setting': {'Setting': Mock()},
        'utils.core.time_utils': {'TimeUtils': Mock()},
        'utils.drivers.window': {'Window': Mock()},
    }
    for name, attributes in services.items():
        module = ModuleType(name)
        module.__dict__.update(attributes)
        monkeypatch.setitem(sys.modules, name, module)
    spec = importlib.util.spec_from_file_location(
        '_fhoe_notification_test', Path(__file__).resolve().parents[1] / 'fhoe.py'
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, 'time', SimpleNamespace(sleep=Mock()))
    monkeypatch.setattr(module, 'shutdown_computer', Mock())
    monkeypatch.setattr(sys, 'argv', ['fhoe.py', '--map', '1-1_0'])
    module.cfg.load_config.return_value = {}
    module.cfg.read_json_file.return_value = {}
    return module


@pytest.mark.parametrize('counts', [(17, 3, 8.5, 2), (0, 0, 0, 0)])
def test_completed_route_sends_summary_from_counter_owners(cli, counts):
    fights, no_fights, saved_time, stalls = counts
    route = SimpleNamespace(
        map_statu=SimpleNamespace(total_time=99),
        handle=SimpleNamespace(
            combat=SimpleNamespace(total_fight_cnt=fights, total_no_fight_cnt=no_fights),
            movement=SimpleNamespace(tatol_save_time=saved_time, time_error_cnt=stalls),
        ),
        process_map=Mock(),
    )
    cli.MapOperations.return_value = route

    cli.main()

    route.process_map.assert_called_once_with('1-1_0', False, dev=False, single_map=True)
    cli.notify.send_end.assert_called_once_with({
        '总计用时': 99,
        '战斗次数': fights,
        '未战斗次数': no_fights,
        '疾跑节约': saved_time,
        '系统卡顿': stalls,
    })
    cli.log.warning.assert_not_called()


def test_missing_optional_summary_objects_still_sends_end(cli):
    cli.MapOperations.return_value = SimpleNamespace(process_map=Mock())
    cli.main()
    cli.notify.send_end.assert_called_once_with({})
