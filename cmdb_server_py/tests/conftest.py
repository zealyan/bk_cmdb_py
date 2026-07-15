"""pytest 共享夹具：以 importlib 加载顶层 app.py（避免 cmdb_server_py/ 下
``app/`` 包与 ``app.py`` 模块同名遮蔽导致 ``from app import app`` 失败）。
"""
import importlib.util
import os
import sys

import pytest

CMDB_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_PATH = os.path.join(CMDB_ROOT, "app.py")


def _load_app():
    spec = importlib.util.spec_from_file_location("appmodule", APP_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["appmodule"] = module
    spec.loader.exec_module(module)
    return module.app


@pytest.fixture(scope="session")
def app():
    return _load_app()


@pytest.fixture()
def client(app):
    return app.test_client()
