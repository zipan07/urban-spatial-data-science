"""用八城市数据运行第7—13章的代表性代码并生成真实GIS预览。"""

from __future__ import annotations

import json
import math
from pathlib import Path

import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import networkx as nx
import numpy as np
import pandas as pd
import rasterio
from esda.moran import Moran
from libpysal.weights import Queen
from matplotlib import pyplot as plt
from matplotlib.cm import ScalarMappable
from matplotlib.colors import Normalize
from rasterio.plot import show
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error
from sklearn.model_selection import GroupKFold, cross_val_predict


ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = ROOT / "data" / "china_city_cases"
CITY = DATA_ROOT / "nanjing"


def build_graph(nodes: gpd.GeoDataFrame, edges: gpd.GeoDataFrame) -> nx.Graph:
    graph = nx.Graph()
    for row in nodes.itertuples():
        graph.add_node(row.node_id, x=row.geometry.x, y=row.geometry.y)
    for row in edges.itertuples():
        if not graph.has_edge(row.u, row.v) or row.length_m < graph[row.u][row.v]["length_m"]:
            graph.add_edge(
                row.u,
                row.v,
                edge_id=row.edge_id,
                length_m=float(row.length_m),
                walk_minutes=float(row.walk_minutes),
            )
    return graph


def main() -> None:
    catalog = pd.read_csv(DATA_ROOT / "catalog.csv")
    assert len(catalog) == 8 and catalog["city_id"].is_unique

    indicators = pd.read_csv(CITY / "grid_indicators.csv", dtype={"cell_id": "string"})
    grid_geometry = gpd.read_file(CITY / "analysis_grid.geojson")[["cell_id", "geometry"]]
    facilities = gpd.read_file(CITY / "facilities.geojson")
    nodes = gpd.read_file(CITY / "network_nodes.geojson")
    edges = gpd.read_file(CITY / "network_edges.geojson")

    grid = grid_geometry.merge(indicators, on="cell_id", validate="one_to_one")
    assert len(grid) == 64 and grid["cell_id"].is_unique

    matched = gpd.sjoin(
        facilities[["facility_id", "geometry"]],
        grid[["cell_id", "geometry"]],
        how="left",
        predicate="within",
    )
    recalculated = matched.groupby("cell_id")["facility_id"].nunique()
    count_check = grid.set_index("cell_id")["facility_count"].sub(recalculated, fill_value=0)
    assert count_check.abs().sum() == 0, "空间连接重算的设施数与发布指标不一致"

    with rasterio.open(CITY / "elevation_250m.tif") as source:
        elevation = source.read(1, masked=True)
        raster_shape = source.shape
        raster_crs = str(source.crs)
        raster_bounds = tuple(source.bounds)
        raster_transform = source.transform
    assert raster_shape == (24, 24) and raster_crs == "EPSG:4326"

    weights = Queen.from_dataframe(grid, ids="cell_id", use_index=False)
    weights.transform = "R"
    values = grid.set_index("cell_id").loc[weights.id_order, "accessibility_proxy"].to_numpy()
    np.random.seed(42)
    moran = Moran(values, weights, permutations=999)

    graph = build_graph(nodes, edges)
    components = list(nx.connected_components(graph))
    largest = max(components, key=len)
    component_nodes = sorted(largest)
    origin, destination = component_nodes[0], component_nodes[-1]
    route_length_m = nx.shortest_path_length(graph, origin, destination, weight="length_m")

    all_grids = pd.read_csv(DATA_ROOT / "all_grid_indicators.csv")
    feature_cols = [
        "road_density_km_km2",
        "intersection_count",
        "distance_to_center_km",
        "elevation_m",
        "terrain_relief_m",
    ]
    X = all_grids[feature_cols].fillna(all_grids[feature_cols].median())
    y = all_grids["facility_count"]
    groups = all_grids["city_id"]
    model = RandomForestRegressor(
        n_estimators=200,
        min_samples_leaf=5,
        random_state=42,
        n_jobs=-1,
    )
    prediction = cross_val_predict(
        model,
        X,
        y,
        groups=groups,
        cv=GroupKFold(n_splits=8),
        n_jobs=-1,
    )
    mae = mean_absolute_error(y, prediction)
    assert math.isfinite(mae)

    fig, axes = plt.subplots(1, 2, figsize=(13, 6), constrained_layout=True)
    grid.plot(
        column="facility_density_km2",
        cmap="YlGnBu",
        edgecolor="white",
        linewidth=0.45,
        legend=True,
        legend_kwds={"label": "OSM facilities per km²", "shrink": 0.72},
        ax=axes[0],
    )
    facilities.plot(ax=axes[0], color="#7a2648", markersize=5, alpha=0.65)
    axes[0].set_title("Nanjing: facilities and grid density")
    axes[0].set_axis_off()

    show(elevation, transform=raster_transform, cmap="terrain", ax=axes[1])
    grid.boundary.plot(ax=axes[1], color="white", linewidth=0.45)
    axes[1].set_title("Nanjing: SRTM elevation and analysis grid")
    axes[1].set_axis_off()

    preview_path = DATA_ROOT / "nanjing_case_preview.png"
    fig.savefig(preview_path, dpi=200, facecolor="#fffdf8", bbox_inches="tight")
    plt.close(fig)

    city_grids = [
        gpd.read_file(DATA_ROOT / city_id / "analysis_grid.geojson")
        for city_id in catalog["city_id"]
    ]
    upper = float(
        pd.concat([frame["facility_density_km2"] for frame in city_grids], ignore_index=True)
        .quantile(0.95)
    )
    upper = max(upper, 1.0)
    fig, axes = plt.subplots(2, 4, figsize=(15, 8), constrained_layout=True)
    for ax, frame, city_name_en in zip(axes.flat, city_grids, catalog["city_name_en"]):
        frame.plot(
            column="facility_density_km2",
            cmap="YlGnBu",
            vmin=0,
            vmax=upper,
            edgecolor="white",
            linewidth=0.35,
            ax=ax,
        )
        ax.set_title(city_name_en)
        ax.set_axis_off()
    colorbar = fig.colorbar(
        ScalarMappable(norm=Normalize(vmin=0, vmax=upper), cmap="YlGnBu"),
        ax=axes,
        orientation="horizontal",
        shrink=0.60,
        pad=0.02,
    )
    colorbar.set_label("OSM facilities per km² (shared scale; capped at pooled 95th percentile)")
    overview_path = DATA_ROOT / "eight_city_facility_density.png"
    fig.savefig(overview_path, dpi=190, facecolor="#fffdf8", bbox_inches="tight")
    plt.close(fig)

    results = {
        "status": "PASS",
        "city_count": int(len(catalog)),
        "combined_grid_rows": int(len(all_grids)),
        "nanjing": {
            "grid_cells": int(len(grid)),
            "facilities": int(len(facilities)),
            "network_nodes_file": int(len(nodes)),
            "network_edges_file": int(len(edges)),
            "simple_graph_nodes": int(graph.number_of_nodes()),
            "simple_graph_edges": int(graph.number_of_edges()),
            "connected_components": int(len(components)),
            "largest_component_nodes": int(len(largest)),
            "demonstration_route_length_m": round(float(route_length_m), 2),
            "moran_I_accessibility_proxy": round(float(moran.I), 6),
            "moran_permutation_p": round(float(moran.p_sim), 6),
            "raster_shape": list(raster_shape),
            "raster_crs": raster_crs,
            "raster_bounds": list(raster_bounds),
        },
        "leave_one_city_out_random_forest": {
            "target": "facility_count",
            "features": feature_cols,
            "folds": 8,
            "MAE": round(float(mae), 6),
            "interpretation": "Technical reproducibility check; OSM coverage differences prevent direct service-performance ranking.",
        },
        "generated_maps": [preview_path.name, overview_path.name],
    }
    (DATA_ROOT / "sample_results.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
