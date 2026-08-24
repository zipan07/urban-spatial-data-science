"""验证中国八城市课程数据包并生成机器可读质量报告。

检查覆盖文件完整性、GeoJSON结构、主键唯一性、表格—空间对象一一对应、
GeoTIFF空间参考标签、元数据计数和SHA-256校验值。任何关键或高风险问题
都会令脚本以非零状态退出，便于在GitHub Actions中阻止不合格数据发布。
"""

from __future__ import annotations

import csv
import hashlib
import json
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = ROOT / "data" / "china_city_cases"
CITY_IDS = ["beijing", "shanghai", "nanjing", "guangzhou", "chengdu", "wuhan", "xian", "hangzhou"]
VECTOR_SPECS = {
    "boundary.geojson": ("uc_id", 1),
    "facilities.geojson": ("facility_id", 1),
    "network_nodes.geojson": ("node_id", 1),
    "network_edges.geojson": ("edge_id", 1),
    "analysis_grid.geojson": ("cell_id", 64),
}
REQUIRED_FILES = [
    *VECTOR_SPECS,
    "grid_indicators.csv",
    "elevation_250m.tif",
    "city_profile.csv",
    "metadata.json",
]
GLOBAL_FILES = [
    "catalog.csv",
    "catalog.json",
    "city_profiles.csv",
    "all_grid_indicators.csv",
    "data_inventory.csv",
    "china_eight_city_course_data.zip",
    "checksums.sha256",
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def walk_coordinates(value: Any) -> Iterable[tuple[float, float]]:
    """递归读取GeoJSON坐标数组中的二维坐标。"""
    if (
        isinstance(value, list)
        and len(value) >= 2
        and isinstance(value[0], (int, float))
        and isinstance(value[1], (int, float))
    ):
        yield float(value[0]), float(value[1])
        return
    if isinstance(value, list):
        for child in value:
            yield from walk_coordinates(child)


def validate() -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    checks: list[dict[str, Any]] = []

    def finding(severity: str, check: str, message: str, city_id: str | None = None) -> None:
        findings.append({"severity": severity, "check": check, "city_id": city_id, "message": message})

    def checked(check: str, status: str, detail: str, city_id: str | None = None) -> None:
        checks.append({"check": check, "status": status, "city_id": city_id, "detail": detail})

    for filename in GLOBAL_FILES:
        path = DATA_ROOT / filename
        if path.exists() and path.stat().st_size > 0:
            checked("global_file", "pass", f"{filename}: {path.stat().st_size} bytes")
        else:
            finding("critical", "global_file", f"缺少全局文件或文件为空：{filename}")

    for city_id in CITY_IDS:
        city_dir = DATA_ROOT / city_id
        if not city_dir.is_dir():
            finding("critical", "city_directory", "缺少城市目录", city_id)
            continue

        city_required = [*REQUIRED_FILES, f"{city_id}_course_data.zip"]
        missing = [filename for filename in city_required if not (city_dir / filename).is_file()]
        if missing:
            finding("critical", "required_files", "缺少文件：" + ", ".join(missing), city_id)
            continue
        checked("required_files", "pass", f"{len(city_required)}个文件齐全", city_id)

        try:
            with zipfile.ZipFile(city_dir / f"{city_id}_course_data.zip") as archive:
                bad_members = archive.testzip()
                member_names = archive.namelist()
                names = set(member_names)
            expected_names = {f"{city_id}/{filename}" for filename in REQUIRED_FILES}
            duplicate_names = len(member_names) - len(names)
            if bad_members or not expected_names.issubset(names) or duplicate_names:
                finding(
                    "high",
                    "city_zip",
                    f"压缩包缺项、重复或损坏：bad_member={bad_members}, duplicates={duplicate_names}",
                    city_id,
                )
            else:
                checked("city_zip", "pass", f"{len(names)}个成员可解压", city_id)
        except Exception as error:
            finding("critical", "city_zip", f"城市压缩包无法读取：{error}", city_id)

        feature_ids: dict[str, set[str]] = {}
        for filename, (id_field, expected_minimum) in VECTOR_SPECS.items():
            path = city_dir / filename
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                features = payload.get("features", [])
            except Exception as error:
                finding("critical", "geojson_parse", f"{filename}无法解析：{error}", city_id)
                continue
            if payload.get("type") != "FeatureCollection":
                finding("critical", "geojson_type", f"{filename}不是FeatureCollection", city_id)
            if len(features) < expected_minimum:
                finding("high", "feature_count", f"{filename}仅有{len(features)}条，最低要求{expected_minimum}条", city_id)
            ids = [str(feature.get("properties", {}).get(id_field, "")) for feature in features]
            if not all(ids) or len(ids) != len(set(ids)):
                finding("high", "primary_key", f"{filename}的{id_field}存在空值或重复", city_id)
            feature_ids[filename] = set(ids)
            invalid_coordinates = 0
            coordinate_count = 0
            for feature in features:
                geometry = feature.get("geometry") or {}
                for lon, lat in walk_coordinates(geometry.get("coordinates")):
                    coordinate_count += 1
                    if not (-180 <= lon <= 180 and -90 <= lat <= 90):
                        invalid_coordinates += 1
            if coordinate_count == 0:
                finding("critical", "geometry", f"{filename}没有可读取的坐标", city_id)
            elif invalid_coordinates:
                finding("critical", "coordinate_range", f"{filename}含{invalid_coordinates}个越界坐标", city_id)
            else:
                checked("geojson", "pass", f"{filename}: {len(features)} features, {coordinate_count} coordinates", city_id)

        grid_table = read_csv(city_dir / "grid_indicators.csv")
        grid_table_ids = [row.get("cell_id", "") for row in grid_table]
        if len(grid_table) != 64:
            finding("high", "grid_rows", f"grid_indicators.csv应有64行，实际{len(grid_table)}行", city_id)
        if len(grid_table_ids) != len(set(grid_table_ids)) or not all(grid_table_ids):
            finding("high", "grid_primary_key", "grid_indicators.csv的cell_id存在空值或重复", city_id)
        if set(grid_table_ids) != feature_ids.get("analysis_grid.geojson", set()):
            finding("high", "grid_join", "网格CSV与GeoJSON的cell_id不能一一对应", city_id)
        else:
            checked("grid_join", "pass", "64个cell_id一一对应", city_id)

        profile_rows = read_csv(city_dir / "city_profile.csv")
        if len(profile_rows) != 1 or profile_rows[0].get("city_id") != city_id:
            finding("high", "city_profile", "city_profile.csv应仅含一条本城市记录", city_id)
        else:
            checked("city_profile", "pass", "单行城市摘要与目录一致", city_id)

        raster_path = city_dir / "elevation_250m.tif"
        try:
            with Image.open(raster_path) as raster:
                tags = raster.tag_v2
                missing_tags = [tag for tag in (33550, 33922, 34735, 42113) if tag not in tags]
                if raster.size != (24, 24):
                    finding("high", "raster_dimensions", f"栅格应为24×24，实际{raster.size}", city_id)
                if missing_tags:
                    finding("critical", "raster_georeference", f"GeoTIFF缺少标签：{missing_tags}", city_id)
                else:
                    checked("raster", "pass", f"24×24；WGS84 GeoTIFF标签齐全；mode={raster.mode}", city_id)
        except Exception as error:
            finding("critical", "raster_open", f"GeoTIFF无法读取：{error}", city_id)

        try:
            metadata = json.loads((city_dir / "metadata.json").read_text(encoding="utf-8"))
        except Exception as error:
            finding("critical", "metadata_parse", f"metadata.json无法解析：{error}", city_id)
            continue
        counts = metadata.get("record_counts", {})
        observed_counts = {
            "boundary": len(feature_ids.get("boundary.geojson", set())),
            "facilities": len(feature_ids.get("facilities.geojson", set())),
            "network_nodes": len(feature_ids.get("network_nodes.geojson", set())),
            "network_edges": len(feature_ids.get("network_edges.geojson", set())),
            "analysis_grid": len(feature_ids.get("analysis_grid.geojson", set())),
            "grid_indicators": len(grid_table),
        }
        if counts != observed_counts:
            finding("high", "metadata_counts", f"元数据计数{counts}与观测计数{observed_counts}不一致", city_id)
        else:
            checked("metadata_counts", "pass", "元数据计数与文件一致", city_id)
        hash_mismatches = []
        for filename, info in metadata.get("files", {}).items():
            path = city_dir / filename
            if not path.exists() or info.get("sha256") != sha256(path) or info.get("bytes") != path.stat().st_size:
                hash_mismatches.append(filename)
        if hash_mismatches:
            finding("high", "checksums", "校验值或文件大小不符：" + ", ".join(hash_mismatches), city_id)
        else:
            checked("checksums", "pass", f"{len(metadata.get('files', {}))}个文件校验通过", city_id)

    if (DATA_ROOT / "catalog.csv").exists():
        catalog = read_csv(DATA_ROOT / "catalog.csv")
        ids = [row.get("city_id") for row in catalog]
        if len(catalog) != 8 or set(ids) != set(CITY_IDS):
            finding("critical", "catalog_city_coverage", f"目录应覆盖八城，实际：{ids}")
        else:
            checked("catalog_city_coverage", "pass", "八城目录完整")
    if (DATA_ROOT / "city_profiles.csv").exists():
        profiles = read_csv(DATA_ROOT / "city_profiles.csv")
        if len(profiles) != 8:
            finding("high", "profile_rows", f"city_profiles.csv应有8行，实际{len(profiles)}行")
        else:
            checked("profile_rows", "pass", "八条城市摘要完整")
    if (DATA_ROOT / "all_grid_indicators.csv").exists():
        grid_rows = read_csv(DATA_ROOT / "all_grid_indicators.csv")
        if len(grid_rows) != 512:
            finding("high", "all_grid_rows", f"all_grid_indicators.csv应有512行，实际{len(grid_rows)}行")
        else:
            checked("all_grid_rows", "pass", "8×64=512条网格记录完整")

    full_zip = DATA_ROOT / "china_eight_city_course_data.zip"
    if full_zip.exists():
        try:
            with zipfile.ZipFile(full_zip) as archive:
                bad_member = archive.testzip()
                member_names = archive.namelist()
                names = set(member_names)
            expected_names = {
                f"{city_id}/{filename}"
                for city_id in CITY_IDS
                for filename in REQUIRED_FILES
            }
            expected_names.update(
                {
                    "catalog.csv",
                    "catalog.json",
                    "city_profiles.csv",
                    "all_grid_indicators.csv",
                    "data_inventory.csv",
                }
            )
            duplicate_names = len(member_names) - len(names)
            missing_names = sorted(expected_names - names)
            if bad_member or duplicate_names or missing_names:
                finding(
                    "high",
                    "full_zip",
                    "八城合集缺项、重复或损坏："
                    f"bad_member={bad_member}, duplicates={duplicate_names}, missing={missing_names}",
                )
            else:
                checked("full_zip", "pass", f"{len(names)}个成员可解压且名称唯一")
        except Exception as error:
            finding("critical", "full_zip", f"八城合集无法读取：{error}")

    checksum_manifest = DATA_ROOT / "checksums.sha256"
    if checksum_manifest.exists():
        checksum_errors: list[str] = []
        manifest_rows = [line.strip() for line in checksum_manifest.read_text(encoding="utf-8").splitlines() if line.strip()]
        for line in manifest_rows:
            try:
                expected_hash, relative_path = line.split(maxsplit=1)
                target = DATA_ROOT / relative_path.strip()
            except ValueError:
                checksum_errors.append(f"无法解析：{line}")
                continue
            if not target.is_file() or sha256(target) != expected_hash:
                checksum_errors.append(relative_path.strip())
        if len(manifest_rows) != 9:
            checksum_errors.append(f"清单应有9条，实际{len(manifest_rows)}条")
        if checksum_errors:
            finding("high", "download_checksums", "下载校验失败：" + ", ".join(checksum_errors))
        else:
            checked("download_checksums", "pass", "八个单城ZIP与八城合集SHA-256全部一致")

    severity_counts = {severity: sum(item["severity"] == severity for item in findings) for severity in ("critical", "high", "medium", "low")}
    publishable = severity_counts["critical"] == 0 and severity_counts["high"] == 0
    return {
        "report_title": "中国八城市课程数据包质量审计",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "data_root": str(DATA_ROOT.relative_to(ROOT)),
        "city_count_expected": 8,
        "status": "PASS" if publishable else "FAIL",
        "publishable": publishable,
        "risk_policy": "critical/high findings block publication; medium/low findings require review",
        "severity_counts": severity_counts,
        "check_count": len(checks),
        "checks": checks,
        "findings": findings,
        "limitations": [
            "OSM对象由志愿者维护，八城之间的设施完整性不可直接解释为真实服务供给差异。",
            "课程裁剪覆盖中心点附近约5—7 km范围，不代表城市行政区全域。",
            "accessibility_proxy为教学推导指标，不能替代正式的出行时间或规划评价。",
            "GHSL、OSM与SRTM保留各自的来源和许可条件。",
        ],
    }


def main() -> None:
    DATA_ROOT.mkdir(parents=True, exist_ok=True)
    report = validate()
    report_path = DATA_ROOT / "quality_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("status", "publishable", "severity_counts", "check_count")}, ensure_ascii=False, indent=2))
    print(f"质量报告：{report_path}")
    if not report["publishable"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
