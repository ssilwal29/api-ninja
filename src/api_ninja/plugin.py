import logging
import os
import pathlib
import sys

import pytest
import requests
import yaml

from api_ninja.color import Colors
from api_ninja.core import APINinja

NOISY_LOGGERS = [
    "httpx",
    "httpcore",
    "openai",
    "openai._base_client",
    "uvicorn",
]


def _silence_noisy_loggers():
    for logger_name in NOISY_LOGGERS:
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.WARNING)


# Optional: Setup APINinja logger to go to stdout cleanly
def _setup_apininja_logger():
    logger = logging.getLogger("APINinja")
    logger.setLevel(logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("[APINinja] %(message)s"))

    # Avoid duplicate handlers
    if not any(isinstance(h, logging.StreamHandler) for h in logger.handlers):
        logger.addHandler(handler)


@pytest.hookimpl(tryfirst=True)
def pytest_configure(config):
    _silence_noisy_loggers()
    _setup_apininja_logger()


def pytest_addoption(parser):
    parser.addoption(
        "--config",
        action="store",
        default="config.yaml",
        help="Path to your APINinja config YAML",
    )
    parser.addoption(
        "--openapi-spec-url",
        action="store",
        help="URL to fetch OpenAPI spec from",
    )
    parser.addoption(
        "--openapi-spec-path",
        action="store",
        type=pathlib.Path,
        help="Path to local OpenAPI JSON/YAML file",
    )
    parser.addoption(
        "--base-url",
        action="store",
        help="Base URL for the API (overrides config.yaml)",
    )


def pytest_collect_file(parent, path):
    config_file = parent.config.getoption("config")
    candidate = os.path.abspath(str(path))
    target = os.path.abspath(config_file)
    # path.ext is the extension, including the leading dot
    if candidate == target and path.ext in (".yaml", ".yml"):
        path = pathlib.Path(str(path))
        return APINinjaFile.from_parent(
            parent,
            path=path,
        )


class APINinjaFile(pytest.File):
    """Treat the config YAML as a virtual pytest File."""

    def collect(self):
        cfg = yaml.safe_load(self.path.open("r"))
        openapi_spec_url = self.config.getoption("openapi_spec_url", default=None)
        openapi_spec_path = self.config.getoption("openapi_spec_path", default=None)
        base_url = self.config.getoption("base_url", default=None)

        # Fetch OpenAPI spec from URL or local path
        spec = {}
        if openapi_spec_url:
            spec = requests.get(openapi_spec_url).json()
        elif openapi_spec_path:
            with open(openapi_spec_path, "r") as f:
                spec = (
                    yaml.safe_load(f) if openapi_spec_path.suffix in (".yaml", ".yml") else f.read()
                )

        ninja = APINinja(openapi_spec=spec, api_base_url=base_url)
        defaults = cfg.get("defaults", [])
        for coll_name, coll in cfg["collections"].items():
            for flow_id in coll["flows"]:
                flow = dict(cfg["flows"][flow_id])
                flow.update(
                    flow_id=flow_id,
                    collection=coll_name,
                    collection_description=coll.get("description", ""),
                    defaults=defaults,
                )
                yield APINinjaItem.from_parent(
                    self,
                    name=flow_id,
                    flow=flow,
                    ninja=ninja,
                )


class APINinjaItem(pytest.Item):
    """Runs one APINinja flow as a pytest test."""

    def __init__(self, name, parent, *, flow, ninja):
        super().__init__(name, parent)
        self.flow = flow
        self.ninja = ninja

    def runtest(self):
        # Raises AssertionError on failure
        self.ninja.plan_and_run(self.flow)

    def repr_failure(self, excinfo):
        if excinfo.errisinstance(AssertionError):
            return f"{Colors.RED}\nFlow {self.name!r} failed\n" f"  {excinfo.value}\n{Colors.RESET}"
        return super().repr_failure(excinfo)

    def reportinfo(self):
        # Show the config path and flow name
        return str(self.fspath), 0, f"APINinja flow: {self.name}"
