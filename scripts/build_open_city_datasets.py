"""下载、整理并绘制教材使用的开放城市数据。

本脚本生成两个可随教材分发的小型数据包：

1. 欧盟委员会联合研究中心 GHSL Urban Centre Database 2024 中的
   11 个中国代表性城市形态区；
2. OpenStreetMap 中南京中心城区的公共服务与轨道交通节点。

运行方式
--------
在仓库根目录执行：

    python scripts/build_open_city_datasets.py

数据源、许可、查询参数和获取日期会同时写入 metadata.json。脚本只使用
Python 标准库下载与整理数据；绘图需要 matplotlib。
"""

from __future__ import annotations

import csv
import json
import math
import os
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any, Iterable

import matplotlib.pyplot as plt
from matplotlib.colors import Normalize
from matplotlib.patches import Polygon as MplPolygon


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "china_city_open"
FIGURE_DIR = ROOT / "figures"

GHSL_SERVICE = (
    "https://services2.arcgis.com/jUpNdisbWqRpMo35/ArcGIS/rest/services/"
    "Urban_Centers_Database_2024_Socioeconomic/FeatureServer/0/query"
)
GHSL_IDS = [6378, 8006, 8557, 8745, 9127, 10131, 10887, 10933, 11199, 11311, 11345]
GHSL_FIELDS = [
    "ID_UC_G0",
    "GC_UCN_MAI_2025",
    "GC_CNT_GAD_2025",
    "GC_UCA_KM2_2025",
    "GC_POP_TOT_2025",
    "SC_GDP_AVG_1990",
    "SC_GDP_AVG_2000",
    "SC_GDP_AVG_2010",
    "SC_GDP_AVG_2020",
    "SC_GDP_SUM_1990",
    "SC_GDP_SUM_2000",
    "SC_GDP_SUM_2010",
    "SC_GDP_SUM_2020",
    "SC_SEC_HDI_1990",
    "SC_SEC_HDI_2000",
    "SC_SEC_HDI_2010",
    "SC_SEC_HDI_2020",
]
CITY_NAME_ZH = {
    "Beijing": "北京",
    "Shanghai": "上海",
    "Nanjing": "南京",
    "Guangzhou": "广州（珠三角连续城市形态区）",
    "Chengdu": "成都",
    "Wuhan": "武汉",
    "Xi'an": "西安",
    "Hangzhou": "杭州",
    "Chongqing": "重庆",
    "Tianjin": "天津",
    "Suzhou": "苏州",
}

NANJING_BBOX = (31.99, 118.72, 32.09, 118.87)  # south, west, north, east
OVERPASS_SERVICE = "https://overpass-api.de/api/interpreter"
OSM_NODE_SERVICE = "https://api.openstreetmap.org/api/0.6/nodes"
OVERPASS_QUERY = f"""[out:json][timeout:60];
(
  node[amenity~\"^(hospital|clinic|school|kindergarten|library|community_centre)$\"]{NANJING_BBOX};
  node[leisure=\"park\"]{NANJING_BBOX};
  node[railway~\"^(station|halt|subway_entrance)$\"]{NANJING_BBOX};
);
out tags;
"""


def fetch_json(url: str, params: dict[str, str], attempts: int = 4) -> dict[str, Any]:
    """以带标识的请求下载 JSON，并对临时服务错误进行有限重试。"""
    query = urllib.parse.urlencode(params)
    request = urllib.request.Request(
        f"{url}?{query}",
        headers={"User-Agent": "urban-spatial-data-science-textbook/0.10"},
    )
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                return json.load(response)
        except Exception:
            if attempt == attempts:
                raise
            time.sleep(attempt * 2)
    raise RuntimeError("unreachable")


def iter_rings(geometry: dict[str, Any]) -> Iterable[list[list[float]]]:
    """逐一返回 Polygon 或 MultiPolygon 的外环与内环。"""
    if geometry["type"] == "Polygon":
        yield from geometry["coordinates"]
    elif geometry["type"] == "MultiPolygon":
        for polygon in geometry["coordinates"]:
            yield from polygon


def geometry_center(geometry: dict[str, Any]) -> tuple[float, float]:
    """用全部顶点的包围盒中心生成稳定的制图标注位置。"""
    points = [point for ring in iter_rings(geometry) for point in ring]
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    return ((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2)


def build_ghsl() -> list[dict[str, Any]]:
    """下载 GHSL 城市形态区，统一字段名，并保存 GeoJSON 与 CSV。"""
    raw = fetch_json(
        GHSL_SERVICE,
        {
            "where": f"ID_UC_G0 IN ({','.join(map(str, GHSL_IDS))})",
            "outFields": ",".join(GHSL_FIELDS),
            "returnGeometry": "true",
            "outSR": "4326",
            "f": "geojson",
        },
    )

    features: list[dict[str, Any]] = []
    for feature in raw["features"]:
        p = feature["properties"]
        area = p["GC_UCA_KM2_2025"]
        population = p["GC_POP_TOT_2025"]
        name_en = p["GC_UCN_MAI_2025"]
        properties = {
            "uc_id": p["ID_UC_G0"],
            "city_name_en": name_en,
            "city_name_zh": CITY_NAME_ZH.get(name_en, name_en),
            "country": p["GC_CNT_GAD_2025"],
            "urban_area_km2_2025": area,
            "population_2025": population,
            "population_density_km2_2025": round(population / area, 2),
            "gdp_average_ppp_1990": p["SC_GDP_AVG_1990"],
            "gdp_average_ppp_2000": p["SC_GDP_AVG_2000"],
            "gdp_average_ppp_2010": p["SC_GDP_AVG_2010"],
            "gdp_average_ppp_2020": p["SC_GDP_AVG_2020"],
            "gdp_total_ppp_1990": p["SC_GDP_SUM_1990"],
            "gdp_total_ppp_2000": p["SC_GDP_SUM_2000"],
            "gdp_total_ppp_2010": p["SC_GDP_SUM_2010"],
            "gdp_total_ppp_2020": p["SC_GDP_SUM_2020"],
            "hdi_1990": p["SC_SEC_HDI_1990"],
            "hdi_2000": p["SC_SEC_HDI_2000"],
            "hdi_2010": p["SC_SEC_HDI_2010"],
            "hdi_2020": p["SC_SEC_HDI_2020"],
        }
        features.append(
            {"type": "Feature", "properties": properties, "geometry": feature["geometry"]}
        )

    features.sort(key=lambda item: item["properties"]["population_2025"], reverse=True)
    collection = {
        "type": "FeatureCollection",
        "name": "ghsl_china_major_urban_centres_2024",
        "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"}},
        "features": features,
    }
    (DATA_DIR / "ghsl_china_major_cities.geojson").write_text(
        json.dumps(collection, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )

    fieldnames = list(features[0]["properties"].keys()) + ["label_lon", "label_lat"]
    with (DATA_DIR / "ghsl_china_major_cities.csv").open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for feature in features:
            lon, lat = geometry_center(feature["geometry"])
            writer.writerow({**feature["properties"], "label_lon": lon, "label_lat": lat})
    return features


def classify_osm(tags: dict[str, Any]) -> tuple[str, str]:
    """把 OSM 原始标签整理为适合课堂分组的六类设施。"""
    if tags.get("railway") in {"station", "halt", "subway_entrance"}:
        return "transit", "轨道交通"
    if tags.get("leisure") == "park":
        return "park", "公园"
    amenity = tags.get("amenity", "other")
    mapping = {
        "hospital": ("healthcare", "医院与诊所"),
        "clinic": ("healthcare", "医院与诊所"),
        "school": ("education", "学校与幼儿园"),
        "kindergarten": ("education", "学校与幼儿园"),
        "library": ("culture", "图书馆"),
        "community_centre": ("community", "社区服务"),
    }
    return mapping.get(amenity, ("other", "其他"))


def enrich_node_coordinates(elements: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """在 Overpass 只返回标签时，从 OSM 主 API 分批补齐节点坐标。"""
    missing_ids = [str(item["id"]) for item in elements if "lat" not in item or "lon" not in item]
    coordinates: dict[int, tuple[float, float]] = {}
    for start in range(0, len(missing_ids), 100):
        ids = ",".join(missing_ids[start : start + 100])
        request = urllib.request.Request(
            f"{OSM_NODE_SERVICE}?{urllib.parse.urlencode({'nodes': ids})}",
            headers={"User-Agent": "urban-spatial-data-science-textbook/0.10"},
        )
        with urllib.request.urlopen(request, timeout=120) as response:
            root = ET.fromstring(response.read())
        for node in root.findall("node"):
            coordinates[int(node.attrib["id"])] = (
                float(node.attrib["lon"]),
                float(node.attrib["lat"]),
            )
    for item in elements:
        if item["id"] in coordinates:
            item["lon"], item["lat"] = coordinates[item["id"]]
    return elements


def build_osm() -> list[dict[str, Any]]:
    """下载南京 OSM 节点并转换为字段清晰的 GeoJSON。"""
    cache_path = os.environ.get("OSM_CACHE_JSON")
    if cache_path:
        raw = json.loads(Path(cache_path).read_text(encoding="utf-8"))
    else:
        raw = {}
    # 公共 Overpass 实例在高负载时偶尔会返回空结果，因此同时检查记录数。
    for attempt in range(1, 4):
        if raw.get("elements"):
            break
        try:
            raw = fetch_json(OVERPASS_SERVICE, {"data": OVERPASS_QUERY})
        except Exception:
            raw = {}
        if not raw.get("elements"):
            time.sleep(attempt * 2)
    if not raw.get("elements"):
        raise RuntimeError("Overpass API 连续返回空结果；请稍后重试。")
    raw["elements"] = enrich_node_coordinates(raw["elements"])
    features: list[dict[str, Any]] = []
    for element in raw.get("elements", []):
        if "lat" not in element or "lon" not in element:
            continue
        tags = element.get("tags", {})
        category, category_zh = classify_osm(tags)
        name = tags.get("name:zh") or tags.get("name") or "未命名节点"
        features.append(
            {
                "type": "Feature",
                "properties": {
                    "osm_type": element["type"],
                    "osm_id": element["id"],
                    "name": name,
                    "category": category,
                    "category_zh": category_zh,
                    "amenity": tags.get("amenity"),
                    "railway": tags.get("railway"),
                    "leisure": tags.get("leisure"),
                },
                "geometry": {"type": "Point", "coordinates": [element["lon"], element["lat"]]},
            }
        )
    features.sort(key=lambda item: (item["properties"]["category"], item["properties"]["osm_id"]))
    collection = {
        "type": "FeatureCollection",
        "name": "nanjing_osm_public_services",
        "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"}},
        "features": features,
    }
    (DATA_DIR / "nanjing_osm_public_services.geojson").write_text(
        json.dumps(collection, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )
    return features


def plot_ghsl(features: list[dict[str, Any]]) -> None:
    """输出城市形态区地图与人口—面积关系图。"""
    plt.style.use("seaborn-v0_8-whitegrid")
    fig, (ax_map, ax_scatter) = plt.subplots(1, 2, figsize=(15, 7), dpi=180)
    populations = [f["properties"]["population_2025"] / 1_000_000 for f in features]
    norm = Normalize(min(populations), max(populations))
    cmap = plt.colormaps["YlOrRd"]

    for feature, population in zip(features, populations):
        for index, ring in enumerate(iter_rings(feature["geometry"])):
            if index > 0:  # 教学图只画外环，避免孔洞遮挡使图面过密
                continue
            ax_map.add_patch(
                MplPolygon(ring, facecolor=cmap(norm(population)), edgecolor="#334e5c", linewidth=0.35)
            )
        lon, lat = geometry_center(feature["geometry"])
        ax_map.text(lon, lat, feature["properties"]["city_name_en"], fontsize=7, ha="center")
    ax_map.autoscale()
    ax_map.set_aspect("equal", adjustable="datalim")
    ax_map.set_xlabel("Longitude")
    ax_map.set_ylabel("Latitude")
    ax_map.set_title("A  Selected GHSL urban-centre extents")

    areas = [f["properties"]["urban_area_km2_2025"] for f in features]
    densities = [f["properties"]["population_density_km2_2025"] for f in features]
    points = ax_scatter.scatter(
        areas,
        populations,
        c=densities,
        s=[35 + math.sqrt(value) * 40 for value in populations],
        cmap="viridis",
        edgecolor="white",
        linewidth=0.8,
        alpha=0.9,
    )
    for feature, area, population in zip(features, areas, populations):
        ax_scatter.annotate(
            feature["properties"]["city_name_en"],
            (area, population),
            xytext=(4, 4),
            textcoords="offset points",
            fontsize=7,
        )
    ax_scatter.set_xlabel("Urban-centre area in 2025 (km²)")
    ax_scatter.set_ylabel("Population in 2025 (million)")
    ax_scatter.set_title("B  Population, area and morphological density")
    colorbar = fig.colorbar(points, ax=ax_scatter, fraction=0.046, pad=0.04)
    colorbar.set_label("Population density (persons/km²)")
    fig.suptitle("Representative Chinese urban centres in GHSL UCDB R2024A", fontsize=16, weight="bold")
    fig.text(
        0.01,
        0.01,
        "Source: European Commission, GHSL UCDB R2024A · Urban-centre geometry is not an administrative boundary",
        fontsize=8,
        color="#5d6d72",
    )
    fig.tight_layout(rect=(0, 0.04, 1, 0.95))
    fig.savefig(FIGURE_DIR / "data-ghsl-city-comparison.png", bbox_inches="tight", facecolor="white")
    plt.close(fig)


def plot_osm(features: list[dict[str, Any]]) -> None:
    """输出南京公共服务点分布图与分类计数图。"""
    plt.style.use("seaborn-v0_8-whitegrid")
    colors = {
        "transit": "#386cb0",
        "education": "#7fc97f",
        "healthcare": "#ef3b2c",
        "park": "#31a354",
        "culture": "#984ea3",
        "community": "#ff9f1c",
        "other": "#969696",
    }
    labels = {
        "transit": "Transit",
        "education": "Education",
        "healthcare": "Healthcare",
        "park": "Park",
        "culture": "Library",
        "community": "Community",
        "other": "Other",
    }
    counts = Counter(feature["properties"]["category"] for feature in features)
    fig, (ax_map, ax_bar) = plt.subplots(1, 2, figsize=(14, 6.2), dpi=180, gridspec_kw={"width_ratios": [1.3, 1]})
    for category in colors:
        selected = [f for f in features if f["properties"]["category"] == category]
        if not selected:
            continue
        xs = [f["geometry"]["coordinates"][0] for f in selected]
        ys = [f["geometry"]["coordinates"][1] for f in selected]
        ax_map.scatter(xs, ys, s=13 if category == "transit" else 28, color=colors[category], label=labels[category], alpha=0.78)
    ax_map.set_xlim(NANJING_BBOX[1], NANJING_BBOX[3])
    ax_map.set_ylim(NANJING_BBOX[0], NANJING_BBOX[2])
    ax_map.set_aspect(1 / math.cos(math.radians(32.04)))
    ax_map.set_xlabel("Longitude")
    ax_map.set_ylabel("Latitude")
    ax_map.set_title("A  OpenStreetMap points in central Nanjing")
    ax_map.legend(loc="lower left", fontsize=8, frameon=True, ncol=2)

    ordered = [key for key in colors if counts.get(key)]
    values = [counts[key] for key in ordered]
    bars = ax_bar.barh([labels[key] for key in ordered], values, color=[colors[key] for key in ordered])
    ax_bar.bar_label(bars, padding=3, fontsize=9)
    ax_bar.set_xlabel("Number of mapped nodes")
    ax_bar.set_title("B  Counts reflect mapping completeness")
    ax_bar.spines[["top", "right"]].set_visible(False)
    fig.suptitle("Public services and rail access: a reproducible OSM extract", fontsize=16, weight="bold")
    fig.text(
        0.01,
        0.01,
        "© OpenStreetMap contributors, ODbL · Query date: " + date.today().isoformat(),
        fontsize=8,
        color="#5d6d72",
    )
    fig.tight_layout(rect=(0, 0.04, 1, 0.94))
    fig.savefig(FIGURE_DIR / "data-nanjing-osm-services.png", bbox_inches="tight", facecolor="white")
    plt.close(fig)


def write_metadata(ghsl: list[dict[str, Any]], osm: list[dict[str, Any]]) -> None:
    """保存机器可读的来源、许可与查询说明。"""
    metadata = {
        "generated_on": date.today().isoformat(),
        "coordinate_reference_system": "OGC:CRS84 / WGS 84 longitude-latitude",
        "datasets": {
            "ghsl_china_major_cities": {
                "files": ["ghsl_china_major_cities.geojson", "ghsl_china_major_cities.csv"],
                "records": len(ghsl),
                "source": "European Commission Joint Research Centre, GHSL Urban Centre Database R2024A",
                "source_page": "https://human-settlement.emergency.copernicus.eu/ghs_ucdb_2024.php",
                "service": GHSL_SERVICE,
                "selected_ids": GHSL_IDS,
                "reuse": "Free and open reuse with source acknowledgement; consult the GHSL data package for the complete terms.",
                "attribution": "European Commission, Joint Research Centre (JRC), GHSL UCDB R2024A.",
                "scope_note": "Urban-centre polygons are morphology- and population-based analytical units, not Chinese administrative boundaries.",
            },
            "nanjing_osm_public_services": {
                "files": ["nanjing_osm_public_services.geojson"],
                "records": len(osm),
                "source": "OpenStreetMap contributors",
                "source_page": "https://www.openstreetmap.org/copyright",
                "service": OVERPASS_SERVICE,
                "license": "Open Data Commons Open Database License (ODbL) 1.0",
                "attribution": "© OpenStreetMap contributors",
                "bbox_south_west_north_east": NANJING_BBOX,
                "overpass_query": OVERPASS_QUERY,
                "scope_note": "Counts describe mapped nodes returned by this query and date; they are not an official facility census.",
            },
        },
    }
    (DATA_DIR / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    ghsl = build_ghsl()
    osm = build_osm()
    write_metadata(ghsl, osm)
    plot_ghsl(ghsl)
    plot_osm(osm)
    print(f"GHSL urban centres: {len(ghsl)}")
    print(f"OSM service nodes: {len(osm)}")
    print(f"Data directory: {DATA_DIR}")


if __name__ == "__main__":
    main()
