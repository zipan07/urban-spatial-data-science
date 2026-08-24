"""生成可重复执行的八城市数据质量审计Notebook。"""

from pathlib import Path

import nbformat as nbf


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "notebooks" / "00_china_city_data_quality.ipynb"


def markdown(text: str):
    return nbf.v4.new_markdown_cell(text.strip())


def code(text: str):
    return nbf.v4.new_code_cell(text.strip())


notebook = nbf.v4.new_notebook()
notebook["metadata"] = {
    "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
    "language_info": {"name": "python", "version": "3"},
}
notebook["cells"] = [
    markdown(
        """
        # 中国八城市课程数据包：质量审计

        ## tl;dr

        本Notebook是教材数据发布前的可执行审计记录。它检查八个城市的数据文件是否齐全，
        GeoJSON与CSV主键能否一一连接，GeoTIFF是否保留空间参考，元数据计数与校验值是否一致。
        `critical`或`high`级问题会阻止发布。
        """
    ),
    markdown(
        """
        ## Context & Methods

        数据包服务于第6—16章的课堂练习。每城采用相同的数据契约，但研究范围是城市中心附近的
        小尺度教学裁剪。检查脚本只验证文件结构、连接关系与发布完整性；它无法证明OpenStreetMap
        在不同城市中的设施覆盖程度完全一致，因此跨城市比较时必须把平台覆盖差异列为限制。
        """
    ),
    code(
        """
        from pathlib import Path
        import json
        import subprocess
        import sys
        import pandas as pd

        ROOT = Path.cwd()
        DATA = ROOT / "data" / "china_city_cases"
        subprocess.run([sys.executable, "scripts/validate_china_city_cases.py"], check=True)
        """
    ),
    markdown("## Data"),
    code(
        """
        catalog = pd.read_csv(DATA / "catalog.csv")
        profiles = pd.read_csv(DATA / "city_profiles.csv")
        grids = pd.read_csv(DATA / "all_grid_indicators.csv")
        inventory = pd.read_csv(DATA / "data_inventory.csv")
        report = json.loads((DATA / "quality_report.json").read_text(encoding="utf-8"))

        catalog[["city_name_zh", "facility_count", "network_edge_count", "grid_count", "extract_date"]]
        """
    ),
    markdown("## Results"),
    code(
        """
        audit_summary = pd.DataFrame([
            {
                "status": report["status"],
                "publishable": report["publishable"],
                "checks": report["check_count"],
                **report["severity_counts"],
            }
        ])
        audit_summary
        """
    ),
    code(
        """
        coverage = (
            grids.groupby(["city_id", "city_name_zh"], as_index=False)
            .agg(
                grid_cells=("cell_id", "nunique"),
                facilities=("facility_count", "sum"),
                road_length_km=("road_length_m", lambda values: values.sum() / 1000),
                elevation_min_m=("elevation_m", "min"),
                elevation_max_m=("elevation_m", "max"),
            )
        )
        coverage
        """
    ),
    code(
        """
        # 关键一致性断言：失败时Notebook执行会停止。
        assert report["publishable"] is True
        assert set(catalog["city_id"]) == set(profiles["city_id"])
        assert len(catalog) == 8
        assert len(grids) == 8 * 64
        assert grids["cell_id"].is_unique
        assert inventory.groupby("city_id")["dataset_id"].nunique().eq(3).all()
        print("全部发布门槛均已通过。")
        """
    ),
    markdown(
        """
        ## Takeaways

        - 八个城市均具备矢量、栅格和统计表三类课堂数据。
        - 每城64个分析网格可由`cell_id`无损连接到指标表。
        - GeoTIFF保留WGS84空间参考与无数据值；道路、设施和高程文件均记录来源。
        - OSM覆盖差异、中心城区裁剪和教学推导指标仍是实质性限制，使用者应在研究报告中说明。
        """
    ),
]

OUTPUT.parent.mkdir(parents=True, exist_ok=True)
nbf.write(notebook, OUTPUT)
print(f"Notebook written to {OUTPUT}")
