"""Build a reproducible Nanjing teaching dataset and GIS result figures.

The geometries use a real WGS84 coordinate extent around central Nanjing, while
all attributes and facility records are deterministic synthetic teaching data.
They must not be interpreted as official statistics or current facility data.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import ListedColormap
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "nanjing_teaching"
FIGURES = ROOT / "figures"
DATA.mkdir(parents=True, exist_ok=True)
FIGURES.mkdir(parents=True, exist_ok=True)

RNG = np.random.default_rng(20260824)
NX, NY = 12, 8
WEST, SOUTH = 118.68, 31.96
DX, DY = 0.02, 0.02
X, Y = np.meshgrid(np.arange(NX), np.arange(NY))


def logistic(value: np.ndarray) -> np.ndarray:
    return 1 / (1 + np.exp(-value))


def build_surfaces() -> dict[str, np.ndarray]:
    """Create spatially structured variables with known teaching mechanisms."""
    centre = np.exp(-((X - 5.4) ** 2 / 12 + (Y - 3.5) ** 2 / 7))
    river_edge = np.exp(-((Y - 6.7) ** 2) / 1.7)
    eastern_growth = logistic((X - 7.2) / 1.2)
    population = 2800 + 7800 * centre + 1800 * eastern_growth + RNG.normal(0, 450, X.shape)
    elderly = np.clip(0.12 + 0.09 * (1 - centre) + 0.035 * (X < 3) + RNG.normal(0, .012, X.shape), .08, .34)
    tree = np.clip(0.18 + 0.34 * river_edge + 0.10 * (1 - centre) + RNG.normal(0, .035, X.shape), .08, .72)
    heat = 35.8 + 3.7 * centre + 1.4 * eastern_growth - 3.0 * tree + RNG.normal(0, .35, X.shape)
    transit = np.clip(0.28 + 0.58 * centre + 0.20 * eastern_growth + RNG.normal(0, .05, X.shape), .05, .98)
    health = np.clip(0.22 + 0.55 * centre + 0.12 * (X > 7) + RNG.normal(0, .06, X.shape), .03, .95)
    coverage = np.clip(0.94 - .035 * X - .018 * np.abs(Y - 3.5) + RNG.normal(0, .025, X.shape), .38, .98)
    vulnerability = np.clip(.55 * elderly + .45 * (1 - transit), 0, 1)
    risk = (heat - heat.mean()) / heat.std() + (vulnerability - vulnerability.mean()) / vulnerability.std()
    return {
        "population": np.rint(population).astype(int),
        "elderly_share": elderly,
        "tree_cover": tree,
        "heat_c": heat,
        "transit_access": transit,
        "health_access": health,
        "data_coverage": coverage,
        "vulnerability": vulnerability,
        "priority_score": risk,
    }


SURFACES = build_surfaces()


def polygon_feature(col: int, row: int) -> dict:
    x0, y0 = WEST + col * DX, SOUTH + row * DY
    ring = [[x0, y0], [x0 + DX, y0], [x0 + DX, y0 + DY], [x0, y0 + DY], [x0, y0]]
    props = {"grid_id": f"NJ{row + 1:02d}{col + 1:02d}", "area_name": f"Teaching area {row + 1}-{col + 1}"}
    for name, values in SURFACES.items():
        value = values[row, col]
        props[name] = int(value) if name == "population" else round(float(value), 4)
    return {"type": "Feature", "properties": props, "geometry": {"type": "Polygon", "coordinates": [ring]}}


def write_geojson(path: Path, features: list[dict]) -> None:
    payload = {"type": "FeatureCollection", "name": path.stem, "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"}}, "features": features}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def create_practice_data() -> list[dict]:
    communities = [polygon_feature(col, row) for row in range(NY) for col in range(NX)]
    write_geojson(DATA / "community_grid.geojson", communities)

    with (DATA / "community_indicators.csv").open("w", encoding="utf-8-sig", newline="") as file:
        fields = list(communities[0]["properties"].keys())
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(feature["properties"] for feature in communities)

    facility_types = ["community_health", "elderly_service", "metro_station", "park_entrance"]
    facilities = []
    for idx in range(36):
        col = int(RNG.integers(0, NX)); row = int(RNG.integers(0, NY))
        x = WEST + (col + RNG.uniform(.15, .85)) * DX
        y = SOUTH + (row + RNG.uniform(.15, .85)) * DY
        kind = facility_types[idx % len(facility_types)]
        facilities.append({
            "type": "Feature",
            "properties": {"facility_id": f"F{idx + 1:03d}", "facility_type": kind, "capacity": int(RNG.integers(80, 900))},
            "geometry": {"type": "Point", "coordinates": [round(x, 6), round(y, 6)]},
        })
    write_geojson(DATA / "facilities.geojson", facilities)

    roads = []
    road_id = 1
    for row in [1, 3, 5, 7]:
        y = SOUTH + row * DY
        roads.append({"type": "Feature", "properties": {"road_id": f"R{road_id:03d}", "road_class": "east_west", "walk_speed_kmh": 4.5}, "geometry": {"type": "LineString", "coordinates": [[WEST, y], [WEST + NX * DX, y]]}})
        road_id += 1
    for col in [1, 3, 5, 7, 9, 11]:
        x = WEST + col * DX
        roads.append({"type": "Feature", "properties": {"road_id": f"R{road_id:03d}", "road_class": "north_south", "walk_speed_kmh": 4.5}, "geometry": {"type": "LineString", "coordinates": [[x, SOUTH], [x, SOUTH + NY * DY]]}})
        road_id += 1
    write_geojson(DATA / "teaching_roads.geojson", roads)

    metadata = {
        "title": "Nanjing central-city teaching sample",
        "crs": "OGC:CRS84 / WGS84 longitude-latitude",
        "spatial_extent": [WEST, SOUTH, WEST + NX * DX, SOUTH + NY * DY],
        "status": "Deterministic synthetic attributes and facilities for teaching; not official statistics.",
        "generator": "scripts/generate_nanjing_case_assets.py",
        "seed": 20260824,
    }
    (DATA / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    return facilities


def grid_map(ax, values, title, cmap="YlGnBu", vmin=None, vmax=None):
    im = ax.imshow(values, origin="lower", extent=[WEST, WEST + NX * DX, SOUTH, SOUTH + NY * DY], cmap=cmap, vmin=vmin, vmax=vmax, aspect="equal")
    for col in range(NX + 1):
        ax.axvline(WEST + col * DX, color="white", lw=.35, alpha=.85)
    for row in range(NY + 1):
        ax.axhline(SOUTH + row * DY, color="white", lw=.35, alpha=.85)
    ax.set_title(title, loc="left", fontsize=10.5, fontweight="bold", color="#173f50")
    ax.tick_params(labelsize=7, colors="#5d6c70")
    for spine in ax.spines.values(): spine.set_visible(False)
    return im


def finish(fig, name, source="Nanjing teaching sample · Synthetic attributes · WGS84 geometries"):
    fig.text(.01, .01, source, fontsize=6.8, color="#64716e")
    fig.savefig(FIGURES / name, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def facility_xy(facilities, kind=None):
    selected = [f for f in facilities if kind is None or f["properties"]["facility_type"] == kind]
    return np.array([f["geometry"]["coordinates"] for f in selected])


def figure_evidence_layers(facilities):
    fig, axes = plt.subplots(1, 3, figsize=(13, 4.1))
    im0 = grid_map(axes[0], SURFACES["population"], "A  Population support", "YlGnBu")
    im1 = grid_map(axes[1], SURFACES["data_coverage"] * 100, "B  Observation coverage", "PuBuGn", 35, 100)
    grid_map(axes[2], np.ones((NY, NX)), "C  Recorded urban facilities", ListedColormap(["#f3f5f4"]))
    colors = {"community_health": "#c96852", "elderly_service": "#7f5aa2", "metro_station": "#2166ac", "park_entrance": "#3f8f62"}
    for kind, color in colors.items():
        xy = facility_xy(facilities, kind)
        axes[2].scatter(xy[:, 0], xy[:, 1], s=25, color=color, edgecolor="white", lw=.4, label=kind.replace("_", " "))
    axes[2].legend(frameon=False, fontsize=6.7, loc="lower left", ncol=2)
    fig.colorbar(im0, ax=axes[0], fraction=.045, pad=.03, label="Population")
    fig.colorbar(im1, ax=axes[1], fraction=.045, pad=.03, label="Coverage (%)")
    fig.suptitle("One urban question requires several evidence layers", x=.01, ha="left", fontsize=15, fontweight="bold", color="#173f50")
    fig.tight_layout(rect=[0, .06, 1, .91]); finish(fig, "01-nanjing-evidence-layers.png")


def figure_transit_design(facilities):
    stations = facility_xy(facilities, "metro_station")[:3]
    centres_x = WEST + (X + .5) * DX; centres_y = SOUTH + (Y + .5) * DY
    dist = np.min(np.sqrt((centres_x[..., None] - stations[:, 0]) ** 2 + (centres_y[..., None] - stations[:, 1]) ** 2), axis=2)
    treated = dist < .035
    rings = (dist >= .035) & (dist < .065)
    labels = np.zeros_like(dist); labels[rings] = 1; labels[treated] = 2
    fig, axes = plt.subplots(1, 3, figsize=(13, 4.1))
    grid_map(axes[0], labels, "A  Treatment and comparison areas", ListedColormap(["#edf0ef", "#72b7ad", "#c96852"]), 0, 2)
    axes[0].scatter(stations[:, 0], stations[:, 1], marker="s", s=70, color="#173f50", edgecolor="white")
    grid_map(axes[1], SURFACES["transit_access"], "B  Pre-intervention accessibility", "YlGnBu", 0, 1)
    trend = np.vstack([np.linspace(48, 55, 5), np.linspace(47, 54, 5)]) + RNG.normal(0, .6, (2, 5))
    axes[2].plot(range(5), trend[0], marker="o", color="#c96852", label="treated")
    axes[2].plot(range(5), trend[1], marker="o", color="#28766f", label="comparison")
    axes[2].set_xticks(range(5), ["t-4", "t-3", "t-2", "t-1", "opening"])
    axes[2].set_ylabel("Activity index"); axes[2].legend(frameon=False); axes[2].grid(axis="y", color="#dce4e1")
    axes[2].spines[["top", "right"]].set_visible(False); axes[2].set_title("C  Pre-trend diagnostic", loc="left", fontsize=10.5, fontweight="bold", color="#173f50")
    fig.suptitle("A credible transit evaluation begins with geography and comparison", x=.01, ha="left", fontsize=15, fontweight="bold", color="#173f50")
    fig.tight_layout(rect=[0, .06, 1, .91]); finish(fig, "02-nanjing-transit-study-design.png")


def figure_paradigms():
    prediction = .75 * SURFACES["heat_c"] + .25 * np.mean(SURFACES["heat_c"]) + RNG.normal(0, .2, (NY, NX))
    intervention = SURFACES["priority_score"] - 1.2 * SURFACES["tree_cover"]
    fig, axes = plt.subplots(1, 3, figsize=(13, 4.1))
    lo, hi = SURFACES["heat_c"].min(), SURFACES["heat_c"].max()
    grid_map(axes[0], SURFACES["heat_c"], "A  Description: observed heat", "magma", lo, hi)
    grid_map(axes[1], prediction, "B  Prediction: estimated heat", "magma", lo, hi)
    grid_map(axes[2], intervention, "C  Decision: intervention priority", "YlOrRd")
    fig.suptitle("Description, prediction and planning priority are different outputs", x=.01, ha="left", fontsize=15, fontweight="bold", color="#173f50")
    fig.tight_layout(rect=[0, .06, 1, .91]); finish(fig, "03-nanjing-paradigm-comparison.png")


def figure_sensing_audit():
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.3), gridspec_kw={"width_ratios": [1, 1.15]})
    im = grid_map(axes[0], SURFACES["data_coverage"] * 100, "A  Data coverage by grid", "PuBuGn", 35, 100)
    fig.colorbar(im, ax=axes[0], fraction=.045, pad=.03, label="Coverage (%)")
    sc = axes[1].scatter(SURFACES["vulnerability"].ravel(), SURFACES["data_coverage"].ravel() * 100, c=SURFACES["heat_c"].ravel(), cmap="magma", s=35, alpha=.8, edgecolor="white", lw=.4)
    axes[1].set_xlabel("Vulnerability score"); axes[1].set_ylabel("Coverage (%)")
    axes[1].grid(color="#dce4e1", lw=.6); axes[1].spines[["top", "right"]].set_visible(False)
    axes[1].set_title("B  Who is under-observed?", loc="left", fontsize=10.5, fontweight="bold", color="#173f50")
    fig.colorbar(sc, ax=axes[1], fraction=.045, pad=.03, label="Heat (°C)")
    fig.suptitle("Sensor coverage is part of the substantive finding", x=.01, ha="left", fontsize=15, fontweight="bold", color="#173f50")
    fig.tight_layout(rect=[0, .06, 1, .91]); finish(fig, "04-nanjing-sensing-audit.png")


def aggregate(values, fx, fy):
    return values.reshape(NY // fy, fy, NX // fx, fx).mean(axis=(1, 3))


def figure_scale():
    coarse = aggregate(SURFACES["heat_c"], 3, 2)
    shifted = np.roll(SURFACES["heat_c"], 1, axis=1)
    shifted_coarse = aggregate(shifted, 3, 2)
    lo, hi = SURFACES["heat_c"].min(), SURFACES["heat_c"].max()
    fig, axes = plt.subplots(1, 3, figsize=(13, 4.1))
    grid_map(axes[0], SURFACES["heat_c"], "A  Fine support: 96 grids", "magma", lo, hi)
    axes[1].imshow(coarse, origin="lower", cmap="magma", vmin=lo, vmax=hi, aspect="equal"); axes[1].set_title("B  Coarse zoning: 16 areas", loc="left", fontsize=10.5, fontweight="bold", color="#173f50")
    axes[2].imshow(shifted_coarse - coarse, origin="lower", cmap="RdBu_r", vmin=-1.2, vmax=1.2, aspect="equal"); axes[2].set_title("C  Boundary-shift difference", loc="left", fontsize=10.5, fontweight="bold", color="#173f50")
    for ax in axes[1:]: ax.set_xticks([]); ax.set_yticks([]); [s.set_visible(False) for s in ax.spines.values()]
    fig.suptitle("Scale and zoning alter the pattern that enters the analysis", x=.01, ha="left", fontsize=15, fontweight="bold", color="#173f50")
    fig.tight_layout(rect=[0, .06, 1, .91]); finish(fig, "05-nanjing-scale-sensitivity.png")


def figure_suitability(facilities):
    need = (SURFACES["elderly_share"] - SURFACES["elderly_share"].min()) / np.ptp(SURFACES["elderly_share"])
    gap = 1 - SURFACES["health_access"]
    suitability = .55 * need + .45 * gap - .25 * (SURFACES["heat_c"] > np.quantile(SURFACES["heat_c"], .8))
    candidates = np.argwhere(suitability >= np.quantile(suitability, .93))
    fig, axes = plt.subplots(1, 3, figsize=(13, 4.1))
    grid_map(axes[0], need, "A  Elderly-service need", "Purples", 0, 1)
    grid_map(axes[1], gap, "B  Existing accessibility gap", "YlOrRd", 0, 1)
    grid_map(axes[2], suitability, "C  Constrained suitability", "YlGn")
    axes[2].scatter(WEST + (candidates[:, 1] + .5) * DX, SOUTH + (candidates[:, 0] + .5) * DY, marker="*", s=120, color="#c96852", edgecolor="white", lw=.6)
    fig.suptitle("Facility siting combines need, service gaps and exclusion constraints", x=.01, ha="left", fontsize=15, fontweight="bold", color="#173f50")
    fig.tight_layout(rect=[0, .06, 1, .91]); finish(fig, "08-nanjing-facility-suitability.png")


def figure_evidence_brief():
    fig, axes = plt.subplots(1, 2, figsize=(10.8, 4.4), gridspec_kw={"width_ratios": [1, 1.1]})
    grid_map(axes[0], SURFACES["priority_score"], "A  Priority evidence map", "RdYlBu_r", -2.5, 2.5)
    names = ["Health first", "Balanced", "Low cost"]
    coverage = [82, 71, 49]; equity = [76, 68, 41]; cost = [88, 63, 39]
    ypos = np.arange(3); h = .23
    axes[1].barh(ypos + h, coverage, h, label="population coverage", color="#28766f")
    axes[1].barh(ypos, equity, h, label="equity score", color="#72b7ad")
    axes[1].barh(ypos - h, cost, h, label="cost index", color="#c96852")
    axes[1].set_yticks(ypos, names); axes[1].set_xlim(0, 100); axes[1].grid(axis="x", color="#dce4e1", lw=.6)
    axes[1].spines[["top", "right", "left"]].set_visible(False); axes[1].legend(frameon=False, fontsize=7, loc="lower right")
    axes[1].set_title("B  Comparable option table", loc="left", fontsize=10.5, fontweight="bold", color="#173f50")
    fig.suptitle("A planning brief links one main map to explicit trade-offs", x=.01, ha="left", fontsize=15, fontweight="bold", color="#173f50")
    fig.tight_layout(rect=[0, .06, 1, .91]); finish(fig, "14-nanjing-evidence-brief.png")


def figure_capstone():
    prediction = SURFACES["heat_c"] - .8 * SURFACES["tree_cover"] + RNG.normal(0, .18, (NY, NX))
    uncertainty = np.abs(prediction - SURFACES["heat_c"]) + (1 - SURFACES["data_coverage"])
    fig, axes = plt.subplots(2, 2, figsize=(8.7, 7.2))
    grid_map(axes[0, 0], SURFACES["data_coverage"] * 100, "A  Evidence coverage", "PuBuGn", 35, 100)
    grid_map(axes[0, 1], SURFACES["heat_c"], "B  Observed condition", "magma")
    grid_map(axes[1, 0], SURFACES["priority_score"], "C  Planning priority", "RdYlBu_r", -2.5, 2.5)
    grid_map(axes[1, 1], uncertainty, "D  Uncertainty and review", "OrRd")
    fig.suptitle("A complete spatial study publishes evidence, result, action and uncertainty", x=.02, ha="left", fontsize=14, fontweight="bold", color="#173f50")
    fig.tight_layout(rect=[0, .04, 1, .93]); finish(fig, "16-nanjing-capstone-output.png")


def main():
    plt.rcParams.update({"font.family": "DejaVu Sans", "axes.labelcolor": "#314a53"})
    facilities = create_practice_data()
    figure_evidence_layers(facilities)
    figure_transit_design(facilities)
    figure_paradigms()
    figure_sensing_audit()
    figure_scale()
    figure_suitability(facilities)
    figure_evidence_brief()
    figure_capstone()
    print(f"Generated Nanjing teaching data in {DATA}")
    print("Generated 8 Nanjing case figures")


if __name__ == "__main__":
    main()
