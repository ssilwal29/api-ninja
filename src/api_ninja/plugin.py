import pathlib
import os
import pytest
import yaml
import requests

from api_ninja.core import APINinja


def pytest_addoption(parser):
    parser.addoption(
        "--config",
        action="store",
        default="config.yaml",
        help="Path to your APINinja config YAML",
    )


def pytest_collect_file(parent, path):
    config_file = parent.config.getoption("config")
    candidate = os.path.abspath(str(path))
    target = os.path.abspath(config_file)
    # path.ext is the extension, including the leading dot
    if candidate == target and path.ext in (".yaml", ".yml"):
        path = pathlib.Path(str(path))
        return APINinjaFile.from_parent(parent, path=path)


class APINinjaFile(pytest.File):
    """Treat the config YAML as a virtual pytest File."""

    def collect(self):
        cfg = yaml.safe_load(self.path.open("r"))

        # Optional OpenAPI fetch
        spec_uri = cfg.get("api", {}).get("openapi_spec")
        spec = requests.get(spec_uri).json() if spec_uri else {}

        ninja = APINinja(openapi_spec=spec, api_base_url=cfg["api"]["base_url"])

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
            return f"\n[APINinja] flow {self.name!r} failed:\n" f"  {excinfo.value}\n"
        return super().repr_failure(excinfo)

    def reportinfo(self):
        # Show the config path and flow name
        return str(self.fspath), 0, f"APINinja flow: {self.name}"
