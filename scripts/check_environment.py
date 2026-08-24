"""课程环境自检：在仓库根目录运行 `python scripts/check_environment.py`。"""

from __future__ import annotations

import importlib
import platform
import sys
from dataclasses import dataclass


@dataclass
class Check:
    name: str
    ok: bool
    detail: str


PACKAGES = {
    "numpy": "NumPy",
    "pandas": "Pandas",
    "geopandas": "GeoPandas",
    "shapely": "Shapely",
    "pyproj": "PyProj",
    "matplotlib": "Matplotlib",
    "sklearn": "Scikit-learn",
    "libpysal": "libpysal",
    "esda": "esda",
    "networkx": "NetworkX",
}


def check_imports() -> list[Check]:
    checks: list[Check] = []
    for module_name, label in PACKAGES.items():
        try:
            module = importlib.import_module(module_name)
            version = getattr(module, "__version__", "version unavailable")
            checks.append(Check(label, True, str(version)))
        except Exception as exc:  # noqa: BLE001 - diagnostic script records all failures
            checks.append(Check(label, False, f"{type(exc).__name__}: {exc}"))
    return checks


def check_spatial_operation() -> Check:
    try:
        import geopandas as gpd
        from shapely.geometry import Point

        sample = gpd.GeoDataFrame(
            {"place": ["Nanjing", "Shanghai"]},
            geometry=[Point(118.7969, 32.0603), Point(121.4737, 31.2304)],
            crs="EPSG:4326",
        )
        projected = sample.to_crs("EPSG:3857")
        assert projected.crs is not None and not projected.crs.is_geographic
        assert projected.geometry.is_valid.all()
        return Check("CRS transform", True, str(projected.crs))
    except Exception as exc:  # noqa: BLE001
        return Check("CRS transform", False, f"{type(exc).__name__}: {exc}")


def main() -> int:
    print("=== Urban Data Environment Check ===")
    print(f"Python version : {sys.version.split()[0]}")
    print(f"Python path    : {sys.executable}")
    print(f"Platform       : {platform.platform()}")
    print()

    checks = [*check_imports(), check_spatial_operation()]
    width = max(len(check.name) for check in checks)
    for check in checks:
        mark = "PASS" if check.ok else "FAIL"
        print(f"[{mark}] {check.name:<{width}}  {check.detail}")

    failed = [check for check in checks if not check.ok]
    print()
    if failed:
        print(f"Environment check failed: {len(failed)} item(s).")
        print("Confirm that urban-data is active and VS Code uses the same interpreter.")
        return 1

    print("Environment check passed. You can continue to Chapter 7.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
