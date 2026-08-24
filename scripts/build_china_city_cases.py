"""构建八个中国城市的可下载课程数据包。

每个城市采用统一文件契约：GHSL城市形态区边界、OpenStreetMap设施点与
道路网络、规则分析网格、网格统计表和SRTM高程栅格。脚本只保存适合课堂
下载的小范围裁剪，不镜像全国尺度原始数据。

数据来源
--------
* GHSL UCDB R2024A：城市形态区与城市尺度统计；
* OpenStreetMap：中心城区设施点与道路网络，ODbL 1.0；
* Terrain Tiles / NASA SRTM：高程数据。

运行方式
--------
    python scripts/build_china_city_cases.py
"""

from __future__ import annotations

import csv
import gzip
import hashlib
import json
import math
import os
import time
import urllib.parse
import urllib.request
import zipfile
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, TiffImagePlugin


ROOT = Path(__file__).resolve().parents[1]
SOURCE_GHSL = ROOT / "data" / "china_city_open" / "ghsl_china_major_cities.geojson"
OUTPUT = ROOT / "data" / "china_city_cases"
CACHE = Path(os.environ.get("COURSE_DATA_CACHE", ROOT / ".cache" / "course_data"))

EXTRACT_DATE = date.today().isoformat()
GRID_ROWS = 8
GRID_COLS = 8
# 八城裁剪约为5—7 km见方；24×24像元对应约200—260 m的课堂栅格。
RASTER_ROWS = 24
RASTER_COLS = 24

OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]
SRTM_TEMPLATE = "https://s3.amazonaws.com/elevation-tiles-prod/skadi/{band}/{tile}.hgt.gz"

# 研究范围是约5—7公里见方的中心城区教学裁剪，不代表完整行政区。
CITIES = [
    {"city_id": "beijing", "name_zh": "北京", "name_en": "Beijing", "lon": 116.4074, "lat": 39.9042},
    {"city_id": "shanghai", "name_zh": "上海", "name_en": "Shanghai", "lon": 121.4737, "lat": 31.2304},
    {"city_id": "nanjing", "name_zh": "南京", "name_en": "Nanjing", "lon": 118.7969, "lat": 32.0603},
    {"city_id": "guangzhou", "name_zh": "广州", "name_en": "Guangzhou", "lon": 113.2644, "lat": 23.1291},
    {"city_id": "chengdu", "name_zh": "成都", "name_en": "Chengdu", "lon": 104.0668, "lat": 30.5728},
    {"city_id": "wuhan", "name_zh": "武汉", "name_en": "Wuhan", "lon": 114.3055, "lat": 30.5928},
    {"city_id": "xian", "name_zh": "西安", "name_en": "Xi'an", "lon": 108.9398, "lat": 34.3416},
    {"city_id": "hangzhou", "name_zh": "杭州", "name_en": "Hangzhou", "lon": 120.1551, "lat": 30.2741},
]

ROAD_TYPES = "primary|secondary|tertiary|residential|living_street|pedestrian|unclassified"
AMENITIES = "hospital|clinic|school|kindergarten|library|community_centre|college|university"
RAIL_TYPES = "station|halt|subway_entrance|tram_stop"


def compact_geojson(name: str, features: list[dict[str, Any]]) -> dict[str, Any]:
    """形成带明确CRS的GeoJSON FeatureCollection。"""
    return {
        "type": "FeatureCollection",
        "name": name,
        "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"}},
        "features": features,
    }


def write_json(path: Path, value: Any, *, pretty: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2 if pretty else None, separators=None if pretty else (",", ":")),
        encoding="utf-8",
    )


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def bbox_for(city: dict[str, Any]) -> tuple[float, float, float, float]:
    """返回south, west, north, east。"""
    half_lat = 0.025
    half_lon = 0.03
    return (
        round(city["lat"] - half_lat, 6),
        round(city["lon"] - half_lon, 6),
        round(city["lat"] + half_lat, 6),
        round(city["lon"] + half_lon, 6),
    )


def overpass_query(bbox: tuple[float, float, float, float]) -> str:
    south, west, north, east = bbox
    extent = f"({south},{west},{north},{east})"
    return f'''[out:json][timeout:180];
(
  way["highway"~"^({ROAD_TYPES})$"]{extent};
  node["amenity"~"^({AMENITIES})$"]{extent};
  node["leisure"="park"]{extent};
  node["railway"~"^({RAIL_TYPES})$"]{extent};
);
out body geom;'''


def fetch_overpass(city: dict[str, Any], bbox: tuple[float, float, float, float]) -> dict[str, Any]:
    """下载并缓存一次有边界的OSM教学裁剪。"""
    cache_path = CACHE / "overpass" / f"{city['city_id']}.json"
    if cache_path.exists():
        return json.loads(cache_path.read_text(encoding="utf-8"))

    payload = urllib.parse.urlencode({"data": overpass_query(bbox)}).encode("utf-8")
    last_error: Exception | None = None
    for endpoint in OVERPASS_ENDPOINTS:
        for attempt in range(1, 4):
            request = urllib.request.Request(
                endpoint,
                data=payload,
                headers={
                    "User-Agent": "urban-spatial-data-science-textbook/0.13 (+https://github.com/zipan07/urban-spatial-data-science)",
                    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                },
            )
            try:
                with urllib.request.urlopen(request, timeout=240) as response:
                    result = json.load(response)
                if result.get("elements"):
                    cache_path.parent.mkdir(parents=True, exist_ok=True)
                    write_json(cache_path, result)
                    return result
                raise RuntimeError("Overpass returned no elements")
            except Exception as error:  # 服务繁忙时有限重试并切换公开实例
                last_error = error
                time.sleep(5 * attempt)
        time.sleep(5)
    raise RuntimeError(f"无法下载{city['name_zh']}OSM裁剪：{last_error}")


def classify_facility(tags: dict[str, Any]) -> tuple[str, str]:
    if tags.get("railway") in {"station", "halt", "subway_entrance", "tram_stop"}:
        return "transit", "公共交通"
    if tags.get("leisure") == "park":
        return "park", "公园"
    amenity = tags.get("amenity")
    if amenity in {"hospital", "clinic"}:
        return "healthcare", "医疗"
    if amenity in {"school", "kindergarten", "college", "university"}:
        return "education", "教育"
    if amenity == "library":
        return "culture", "文化"
    if amenity == "community_centre":
        return "community", "社区服务"
    return "other", "其他"


def haversine_m(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    radius = 6_371_008.8
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(a))


def parse_osm(raw: dict[str, Any], city_id: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """将Overpass响应整理为设施点、网络节点和网络边。"""
    facilities: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    node_coordinates: dict[str, tuple[float, float]] = {}
    degrees: Counter[str] = Counter()

    for element in raw.get("elements", []):
        if element.get("type") == "node" and "lat" in element and "lon" in element:
            tags = element.get("tags", {})
            category, category_zh = classify_facility(tags)
            if category == "other":
                continue
            facilities.append(
                {
                    "type": "Feature",
                    "properties": {
                        "facility_id": f"osm_node_{element['id']}",
                        "osm_id": str(element["id"]),
                        "name": tags.get("name:zh") or tags.get("name") or "未命名设施",
                        "category": category,
                        "category_zh": category_zh,
                        "amenity": tags.get("amenity"),
                        "railway": tags.get("railway"),
                        "source": "OpenStreetMap",
                    },
                    "geometry": {
                        "type": "Point",
                        "coordinates": [round(element["lon"], 7), round(element["lat"], 7)],
                    },
                }
            )

        if element.get("type") != "way":
            continue
        geometry = element.get("geometry") or []
        if len(geometry) < 2:
            continue
        osm_nodes = [str(value) for value in element.get("nodes", [])]
        if len(osm_nodes) != len(geometry):
            osm_nodes = [f"w{element['id']}_n{index}" for index in range(len(geometry))]
        tags = element.get("tags", {})
        for index in range(len(geometry) - 1):
            start, end = geometry[index], geometry[index + 1]
            u, v = osm_nodes[index], osm_nodes[index + 1]
            lon1, lat1 = float(start["lon"]), float(start["lat"])
            lon2, lat2 = float(end["lon"]), float(end["lat"])
            length = haversine_m(lon1, lat1, lon2, lat2)
            if length <= 0:
                continue
            node_coordinates[u] = (lon1, lat1)
            node_coordinates[v] = (lon2, lat2)
            degrees[u] += 1
            degrees[v] += 1
            edges.append(
                {
                    "type": "Feature",
                    "properties": {
                        "edge_id": f"{city_id}_w{element['id']}_{index:04d}",
                        "osm_way_id": str(element["id"]),
                        "u": u,
                        "v": v,
                        "name": tags.get("name:zh") or tags.get("name") or "未命名道路",
                        "highway": tags.get("highway"),
                        "oneway": str(tags.get("oneway", "no")).lower() in {"yes", "true", "1"},
                        "length_m": round(length, 2),
                        "walk_minutes": round(length / 75.0, 3),
                        "source": "OpenStreetMap",
                    },
                    "geometry": {
                        "type": "LineString",
                        "coordinates": [[round(lon1, 7), round(lat1, 7)], [round(lon2, 7), round(lat2, 7)]],
                    },
                }
            )

    nodes = [
        {
            "type": "Feature",
            "properties": {
                "node_id": node_id,
                "degree": degrees[node_id],
                "is_intersection": degrees[node_id] >= 3,
                "source": "OpenStreetMap",
            },
            "geometry": {"type": "Point", "coordinates": [round(lon, 7), round(lat, 7)]},
        }
        for node_id, (lon, lat) in node_coordinates.items()
    ]
    facilities.sort(key=lambda feature: (feature["properties"]["category"], feature["properties"]["osm_id"]))
    nodes.sort(key=lambda feature: feature["properties"]["node_id"])
    edges.sort(key=lambda feature: feature["properties"]["edge_id"])
    return facilities, nodes, edges


def srtm_tile_name(lat: float, lon: float) -> str:
    south = math.floor(lat)
    west = math.floor(lon)
    lat_part = f"N{south:02d}" if south >= 0 else f"S{abs(south):02d}"
    lon_part = f"E{west:03d}" if west >= 0 else f"W{abs(west):03d}"
    return lat_part + lon_part


def fetch_hgt(city: dict[str, Any]) -> tuple[np.ndarray, str, str]:
    """下载Mapzen Terrain Tiles中的Skadi/SRTM HGT瓦片。"""
    tile = srtm_tile_name(city["lat"], city["lon"])
    cache_path = CACHE / "srtm" / f"{tile}.hgt.gz"
    url = SRTM_TEMPLATE.format(band=tile[:3], tile=tile)
    if not cache_path.exists():
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "urban-spatial-data-science-textbook/0.13"},
        )
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(request, timeout=240) as response:
            cache_path.write_bytes(response.read())
    raw = gzip.decompress(cache_path.read_bytes())
    cell_count = len(raw) // 2
    size = int(round(math.sqrt(cell_count)))
    if size * size != cell_count:
        raise ValueError(f"无法识别SRTM瓦片尺寸：{tile}, {len(raw)} bytes")
    array = np.frombuffer(raw, dtype=">i2").reshape((size, size))
    return array, tile, url


def sample_hgt(array: np.ndarray, tile: str, lon: float, lat: float) -> int | None:
    south = int(tile[1:3]) * (1 if tile[0] == "N" else -1)
    west = int(tile[4:7]) * (1 if tile[3] == "E" else -1)
    size = array.shape[0]
    row = int(round((south + 1 - lat) * (size - 1)))
    col = int(round((lon - west) * (size - 1)))
    row = min(max(row, 0), size - 1)
    col = min(max(col, 0), size - 1)
    value = int(array[row, col])
    return None if value <= -32768 else value


def write_elevation_geotiff(
    path: Path,
    array: np.ndarray,
    tile: str,
    bbox: tuple[float, float, float, float],
) -> dict[str, float | int | None]:
    """用Pillow写入带WGS84 GeoTIFF标签的课堂裁剪。"""
    south, west, north, east = bbox
    lons = west + (np.arange(RASTER_COLS) + 0.5) * (east - west) / RASTER_COLS
    lats = north - (np.arange(RASTER_ROWS) + 0.5) * (north - south) / RASTER_ROWS
    raster = np.full((RASTER_ROWS, RASTER_COLS), 65535, dtype=np.uint16)
    valid_values: list[int] = []
    for row, lat in enumerate(lats):
        for col, lon in enumerate(lons):
            value = sample_hgt(array, tile, float(lon), float(lat))
            if value is not None and value >= 0:
                raster[row, col] = value
                valid_values.append(value)

    pixel_width = (east - west) / RASTER_COLS
    pixel_height = (north - south) / RASTER_ROWS
    info = TiffImagePlugin.ImageFileDirectory_v2()
    info[270] = "SRTM elevation teaching subset; Terrain Tiles accessed " + EXTRACT_DATE
    info[33550] = (pixel_width, pixel_height, 0.0)  # ModelPixelScaleTag
    info[33922] = (0.0, 0.0, 0.0, west, north, 0.0)  # ModelTiepointTag
    info[34735] = (  # GeoKeyDirectoryTag: geographic WGS84, PixelIsArea
        1, 1, 0, 3,
        1024, 0, 1, 2,
        1025, 0, 1, 1,
        2048, 0, 1, 4326,
    )
    info[42113] = "65535"
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(raster, mode="I;16").save(path, compression="tiff_deflate", tiffinfo=info)
    return {
        "minimum_m": min(valid_values) if valid_values else None,
        "maximum_m": max(valid_values) if valid_values else None,
        "mean_m": round(float(np.mean(valid_values)), 2) if valid_values else None,
        "valid_cell_count": len(valid_values),
        "rows": RASTER_ROWS,
        "columns": RASTER_COLS,
    }


def cell_index(
    lon: float,
    lat: float,
    bbox: tuple[float, float, float, float],
) -> tuple[int, int] | None:
    south, west, north, east = bbox
    if not (west <= lon <= east and south <= lat <= north):
        return None
    col = min(int((lon - west) / (east - west) * GRID_COLS), GRID_COLS - 1)
    row = min(int((north - lat) / (north - south) * GRID_ROWS), GRID_ROWS - 1)
    return row, col


def build_grid(
    city: dict[str, Any],
    bbox: tuple[float, float, float, float],
    facilities: list[dict[str, Any]],
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    hgt: np.ndarray,
    tile: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """建立64个规则网格并聚合OSM与SRTM指标。"""
    south, west, north, east = bbox
    dx = (east - west) / GRID_COLS
    dy = (north - south) / GRID_ROWS
    metrics: dict[tuple[int, int], dict[str, Any]] = defaultdict(
        lambda: {
            "facility_count": 0,
            "transit_count": 0,
            "healthcare_count": 0,
            "education_count": 0,
            "park_count": 0,
            "road_segment_count": 0,
            "road_length_m": 0.0,
            "intersection_count": 0,
            "categories": set(),
        }
    )
    for feature in facilities:
        lon, lat = feature["geometry"]["coordinates"]
        key = cell_index(lon, lat, bbox)
        if key is None:
            continue
        category = feature["properties"]["category"]
        metrics[key]["facility_count"] += 1
        metrics[key]["categories"].add(category)
        if category in {"transit", "healthcare", "education", "park"}:
            metrics[key][f"{category}_count"] += 1
    for feature in nodes:
        if not feature["properties"]["is_intersection"]:
            continue
        lon, lat = feature["geometry"]["coordinates"]
        key = cell_index(lon, lat, bbox)
        if key is not None:
            metrics[key]["intersection_count"] += 1
    for feature in edges:
        coordinates = feature["geometry"]["coordinates"]
        lon = (coordinates[0][0] + coordinates[1][0]) / 2
        lat = (coordinates[0][1] + coordinates[1][1]) / 2
        key = cell_index(lon, lat, bbox)
        if key is not None:
            metrics[key]["road_segment_count"] += 1
            metrics[key]["road_length_m"] += feature["properties"]["length_m"]

    records: list[dict[str, Any]] = []
    for row in range(GRID_ROWS):
        for col in range(GRID_COLS):
            left, right = west + col * dx, west + (col + 1) * dx
            top, bottom = north - row * dy, north - (row + 1) * dy
            center_lon, center_lat = (left + right) / 2, (bottom + top) / 2
            width_km = haversine_m(left, center_lat, right, center_lat) / 1000
            height_km = haversine_m(center_lon, bottom, center_lon, top) / 1000
            area_km2 = width_km * height_km
            values = metrics[(row, col)]
            samples = [
                sample_hgt(hgt, tile, center_lon, center_lat),
                sample_hgt(hgt, tile, left, top),
                sample_hgt(hgt, tile, right, top),
                sample_hgt(hgt, tile, left, bottom),
                sample_hgt(hgt, tile, right, bottom),
            ]
            valid_elevation = [value for value in samples if value is not None]
            distance = haversine_m(city["lon"], city["lat"], center_lon, center_lat) / 1000
            records.append(
                {
                    "cell_id": f"{city['city_id']}_{row + 1:02d}_{col + 1:02d}",
                    "city_id": city["city_id"],
                    "city_name_zh": city["name_zh"],
                    "row": row + 1,
                    "column": col + 1,
                    "area_km2": round(area_km2, 4),
                    "center_lon": round(center_lon, 7),
                    "center_lat": round(center_lat, 7),
                    "distance_to_center_km": round(distance, 3),
                    "facility_count": values["facility_count"],
                    "transit_count": values["transit_count"],
                    "healthcare_count": values["healthcare_count"],
                    "education_count": values["education_count"],
                    "park_count": values["park_count"],
                    "service_diversity": len(values["categories"]),
                    "facility_density_km2": round(values["facility_count"] / area_km2, 4),
                    "road_segment_count": values["road_segment_count"],
                    "road_length_m": round(values["road_length_m"], 2),
                    "road_density_km_km2": round(values["road_length_m"] / 1000 / area_km2, 4),
                    "intersection_count": values["intersection_count"],
                    "elevation_m": valid_elevation[0] if valid_elevation else None,
                    "terrain_relief_m": max(valid_elevation) - min(valid_elevation) if valid_elevation else None,
                    "source_note": "OSM道路与设施聚合；SRTM高程采样；均为教学裁剪",
                    "_geometry": [[
                        [round(left, 7), round(bottom, 7)],
                        [round(right, 7), round(bottom, 7)],
                        [round(right, 7), round(top, 7)],
                        [round(left, 7), round(top, 7)],
                        [round(left, 7), round(bottom, 7)],
                    ]],
                }
            )

    facility_max = max(record["facility_density_km2"] for record in records) or 1
    road_max = max(record["road_density_km_km2"] for record in records) or 1
    raw_scores: list[float] = []
    for record in records:
        center_score = math.exp(-record["distance_to_center_km"] / 3.0)
        score = (
            0.40 * record["facility_density_km2"] / facility_max
            + 0.35 * record["road_density_km_km2"] / road_max
            + 0.25 * center_score
        )
        record["accessibility_proxy"] = round(score, 4)
        raw_scores.append(score)
    q1, q2, q3 = [float(value) for value in np.quantile(raw_scores, [0.25, 0.50, 0.75])]
    for record in records:
        score = record["accessibility_proxy"]
        record["osm_intensity_class"] = (
            "低" if score <= q1 else "较低" if score <= q2 else "较高" if score <= q3 else "高"
        )
        distance = record["distance_to_center_km"]
        record["core_zone"] = "核心" if distance <= 1.5 else "内圈" if distance <= 3 else "外圈"

    features = []
    csv_records = []
    for record in records:
        properties = {key: value for key, value in record.items() if key != "_geometry"}
        features.append(
            {
                "type": "Feature",
                "properties": properties,
                "geometry": {"type": "Polygon", "coordinates": record["_geometry"]},
            }
        )
        csv_records.append(properties)
    return features, csv_records


def select_boundary(ghsl: dict[str, Any], city: dict[str, Any]) -> dict[str, Any]:
    matches = [
        feature for feature in ghsl["features"]
        if feature["properties"].get("city_name_en") == city["name_en"]
    ]
    if not matches:
        raise KeyError(f"GHSL中未找到{city['name_en']}")
    return matches[0]


def write_csv(path: Path, records: list[dict[str, Any]]) -> None:
    if not records:
        raise ValueError(f"无法写入空表：{path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(records[0].keys()))
        writer.writeheader()
        writer.writerows(records)


def write_zip(path: Path, members: list[Path]) -> None:
    """写入只包含课程成品文件的压缩包。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for member in members:
            archive.write(member, member.relative_to(OUTPUT))


def build_city(city: dict[str, Any], ghsl: dict[str, Any]) -> dict[str, Any]:
    city_dir = OUTPUT / city["city_id"]
    city_dir.mkdir(parents=True, exist_ok=True)
    bbox = bbox_for(city)
    boundary = select_boundary(ghsl, city)
    write_json(city_dir / "boundary.geojson", compact_geojson(f"{city['city_id']}_ghsl_boundary", [boundary]))

    osm_raw = fetch_overpass(city, bbox)
    facilities, nodes, edges = parse_osm(osm_raw, city["city_id"])
    if not facilities or not nodes or not edges:
        raise RuntimeError(f"{city['name_zh']}数据不足：facilities={len(facilities)}, nodes={len(nodes)}, edges={len(edges)}")
    write_json(city_dir / "facilities.geojson", compact_geojson(f"{city['city_id']}_facilities", facilities))
    write_json(city_dir / "network_nodes.geojson", compact_geojson(f"{city['city_id']}_network_nodes", nodes))
    write_json(city_dir / "network_edges.geojson", compact_geojson(f"{city['city_id']}_network_edges", edges))

    hgt, tile, srtm_url = fetch_hgt(city)
    elevation_stats = write_elevation_geotiff(city_dir / "elevation_250m.tif", hgt, tile, bbox)
    grid_features, grid_records = build_grid(city, bbox, facilities, nodes, edges, hgt, tile)
    write_json(city_dir / "analysis_grid.geojson", compact_geojson(f"{city['city_id']}_analysis_grid", grid_features))
    write_csv(city_dir / "grid_indicators.csv", grid_records)

    category_counts = Counter(feature["properties"]["category"] for feature in facilities)
    boundary_properties = boundary["properties"]
    profile = {
        "city_id": city["city_id"],
        "city_name_zh": city["name_zh"],
        "city_name_en": city["name_en"],
        "center_lon": city["lon"],
        "center_lat": city["lat"],
        "ghsl_uc_id": boundary_properties["uc_id"],
        "ghsl_urban_area_km2_2025": boundary_properties["urban_area_km2_2025"],
        "ghsl_population_2025": boundary_properties["population_2025"],
        "ghsl_population_density_km2_2025": boundary_properties["population_density_km2_2025"],
        "ghsl_gdp_total_ppp_2020": boundary_properties["gdp_total_ppp_2020"],
        "ghsl_hdi_2020": boundary_properties["hdi_2020"],
        "osm_facility_count": len(facilities),
        "osm_transit_count": category_counts["transit"],
        "osm_healthcare_count": category_counts["healthcare"],
        "osm_education_count": category_counts["education"],
        "osm_park_count": category_counts["park"],
        "osm_network_node_count": len(nodes),
        "osm_network_edge_count": len(edges),
        "osm_network_length_km": round(sum(feature["properties"]["length_m"] for feature in edges) / 1000, 3),
        "srtm_minimum_elevation_m": elevation_stats["minimum_m"],
        "srtm_maximum_elevation_m": elevation_stats["maximum_m"],
        "srtm_mean_elevation_m": elevation_stats["mean_m"],
        "extract_date": EXTRACT_DATE,
    }
    write_csv(city_dir / "city_profile.csv", [profile])

    files = [
        "boundary.geojson", "facilities.geojson", "network_nodes.geojson",
        "network_edges.geojson", "analysis_grid.geojson", "grid_indicators.csv",
        "elevation_250m.tif", "city_profile.csv",
    ]
    metadata = {
        "city": city,
        "extract_date": EXTRACT_DATE,
        "teaching_extent_bbox_south_west_north_east": bbox,
        "scope": "Bounded central-city teaching extract; not a complete administrative or facility census.",
        "coordinate_reference_system": "OGC:CRS84 for vectors; EPSG:4326 for raster",
        "sources": {
            "boundary_and_city_statistics": {
                "provider": "European Commission Joint Research Centre",
                "dataset": "GHSL Urban Centre Database R2024A",
                "url": "https://human-settlement.emergency.copernicus.eu/ghs_ucdb_2024.php",
                "reuse": "Open and free reuse with source acknowledgement.",
                "attribution": "European Commission, Joint Research Centre (JRC), GHSL UCDB R2024A.",
            },
            "facilities_and_network": {
                "provider": "OpenStreetMap contributors",
                "url": "https://www.openstreetmap.org/copyright",
                "license": "Open Data Commons Open Database License (ODbL) 1.0",
                "attribution": "© OpenStreetMap contributors",
                "query": overpass_query(bbox),
            },
            "elevation": {
                "provider": "Terrain Tiles on AWS / Mapzen; source elevation in this area is NASA SRTM",
                "url": srtm_url,
                "registry": "https://registry.opendata.aws/terrain-tiles/",
                "tile": tile,
                "attribution": "Terrain Tiles accessed from AWS; elevation source NASA SRTM.",
            },
        },
        "record_counts": {
            "boundary": 1,
            "facilities": len(facilities),
            "network_nodes": len(nodes),
            "network_edges": len(edges),
            "analysis_grid": len(grid_features),
            "grid_indicators": len(grid_records),
        },
        "elevation_statistics": elevation_stats,
        "raster_note": "The 24×24 WGS84 teaching raster has an approximate ground resolution of 200–260 m, depending on latitude and extract width.",
        "derived_fields": {
            "accessibility_proxy": "0.40×normalized facility density + 0.35×normalized road density + 0.25×distance-decay centrality; teaching proxy, not an official accessibility measure.",
            "osm_intensity_class": "City-specific quartiles of accessibility_proxy.",
            "terrain_relief_m": "Range of five SRTM samples per analysis cell.",
        },
        "files": {filename: {"sha256": sha256(city_dir / filename), "bytes": (city_dir / filename).stat().st_size} for filename in files},
    }
    write_json(city_dir / "metadata.json", metadata, pretty=True)
    write_zip(city_dir / f"{city['city_id']}_course_data.zip", [city_dir / filename for filename in [*files, "metadata.json"]])
    return {"profile": profile, "grid_records": grid_records, "metadata": metadata}


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    ghsl = json.loads(SOURCE_GHSL.read_text(encoding="utf-8"))
    profiles: list[dict[str, Any]] = []
    all_grid_records: list[dict[str, Any]] = []
    catalog: list[dict[str, Any]] = []
    inventory: list[dict[str, Any]] = []

    for index, city in enumerate(CITIES, start=1):
        print(f"[{index}/{len(CITIES)}] {city['name_zh']} / {city['name_en']}", flush=True)
        result = build_city(city, ghsl)
        profile = result["profile"]
        metadata = result["metadata"]
        profiles.append(profile)
        all_grid_records.extend(result["grid_records"])
        catalog.append(
            {
                "city_id": city["city_id"],
                "city_name_zh": city["name_zh"],
                "city_name_en": city["name_en"],
                "boundary_file": f"{city['city_id']}/boundary.geojson",
                "grid_file": f"{city['city_id']}/analysis_grid.geojson",
                "indicator_file": f"{city['city_id']}/grid_indicators.csv",
                "facility_file": f"{city['city_id']}/facilities.geojson",
                "network_node_file": f"{city['city_id']}/network_nodes.geojson",
                "network_edge_file": f"{city['city_id']}/network_edges.geojson",
                "elevation_file": f"{city['city_id']}/elevation_250m.tif",
                "metadata_file": f"{city['city_id']}/metadata.json",
                "download_file": f"{city['city_id']}/{city['city_id']}_course_data.zip",
                "facility_count": profile["osm_facility_count"],
                "network_edge_count": profile["osm_network_edge_count"],
                "grid_count": metadata["record_counts"]["analysis_grid"],
                "extract_date": EXTRACT_DATE,
            }
        )
        for source_id, source in metadata["sources"].items():
            inventory.append(
                {
                    "dataset_id": f"{city['city_id']}_{source_id}",
                    "city_id": city["city_id"],
                    "provider": source["provider"],
                    "source_url": source.get("url"),
                    "extract_date": EXTRACT_DATE,
                    "spatial_extent": ",".join(map(str, metadata["teaching_extent_bbox_south_west_north_east"])),
                    "crs": metadata["coordinate_reference_system"],
                    "license_or_reuse": source.get("license") or source.get("reuse") or "See source attribution",
                    "metadata_file": f"{city['city_id']}/metadata.json",
                }
            )
        time.sleep(2)

    write_csv(OUTPUT / "catalog.csv", catalog)
    write_csv(OUTPUT / "city_profiles.csv", profiles)
    write_csv(OUTPUT / "all_grid_indicators.csv", all_grid_records)
    write_csv(OUTPUT / "data_inventory.csv", inventory)
    write_json(
        OUTPUT / "catalog.json",
        {
            "title": "中国八城市空间数据科学教学包",
            "generated_on": EXTRACT_DATE,
            "city_count": len(CITIES),
            "cities": catalog,
            "license_note": "GHSL, OSM and Terrain Tiles/SRTM retain their source terms; see each metadata.json.",
        },
        pretty=True,
    )
    package_members = [
        path
        for city in CITIES
        for path in sorted((OUTPUT / city["city_id"]).iterdir())
        if path.is_file() and path.suffix != ".zip"
    ]
    package_members.extend(
        OUTPUT / filename
        for filename in ("catalog.csv", "catalog.json", "city_profiles.csv", "all_grid_indicators.csv", "data_inventory.csv")
        if (OUTPUT / filename).exists()
    )
    for supporting_file in (OUTPUT / "README.md", OUTPUT / "LICENSES.md"):
        if supporting_file.exists():
            package_members.append(supporting_file)
    write_zip(OUTPUT / "china_eight_city_course_data.zip", package_members)
    print(f"Completed {len(CITIES)} city packages in {OUTPUT}")


if __name__ == "__main__":
    main()
