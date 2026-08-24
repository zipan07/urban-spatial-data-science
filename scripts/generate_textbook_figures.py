"""Generate original teaching figures from deterministic synthetic spatial data."""

from __future__ import annotations

import heapq
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import BoundaryNorm, ListedColormap
from matplotlib.lines import Line2D


OUT = Path(__file__).resolve().parents[1] / "figures"
OUT.mkdir(parents=True, exist_ok=True)
RNG = np.random.default_rng(42)
NY, NX = 8, 10
X, Y = np.meshgrid(np.arange(NX), np.arange(NY))


def style_axis(ax, title: str) -> None:
    ax.set_title(title, loc="left", fontsize=11, fontweight="bold", color="#173f50")
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)


def footer(fig) -> None:
    fig.text(
        0.01,
        0.01,
        "Synthetic teaching data · Recreate with scripts/generate_textbook_figures.py",
        fontsize=7,
        color="#64716e",
    )


def save(fig, name: str) -> None:
    footer(fig)
    fig.savefig(OUT / name, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def spatial_surface() -> np.ndarray:
    hotspot = 2.3 * np.exp(-((X - 2.0) ** 2 + (Y - 5.5) ** 2) / 6)
    secondary = 1.5 * np.exp(-((X - 7.5) ** 2 + (Y - 2.0) ** 2) / 4)
    trend = 0.12 * X - 0.06 * Y
    return hotspot + secondary + trend + RNG.normal(0, 0.18, (NY, NX))


def map_panel(ax, values, cmap="YlGnBu", vmin=None, vmax=None, title=""):
    im = ax.imshow(values, origin="lower", cmap=cmap, vmin=vmin, vmax=vmax)
    ax.set_xticks(np.arange(-0.5, NX, 1), minor=True)
    ax.set_yticks(np.arange(-0.5, NY, 1), minor=True)
    ax.grid(which="minor", color="white", linewidth=0.65)
    ax.tick_params(which="minor", bottom=False, left=False)
    style_axis(ax, title)
    return im


def figure_data_quality() -> None:
    coverage = 0.78 + 0.18 * np.exp(-((X - 3) ** 2 + (Y - 4) ** 2) / 18)
    coverage -= 0.035 * X + RNG.normal(0, 0.025, (NY, NX))
    coverage = np.clip(coverage, 0.18, 0.98)
    district = [
        "Central-1", "Central-2", "Inner-1", "Inner-2",
        "Outer-1", "Outer-2", "Edge-1", "Edge-2",
    ]
    missing = np.array([4, 6, 9, 12, 18, 22, 31, 39])

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.3), gridspec_kw={"width_ratios": [1.15, 1]})
    im = map_panel(axes[0], coverage * 100, cmap="YlGnBu", vmin=20, vmax=100,
                   title="A  Street-view coverage by grid")
    cb = fig.colorbar(im, ax=axes[0], fraction=.046, pad=.03)
    cb.set_label("Coverage (%)")
    colors = ["#28766f" if v < 20 else "#c96852" for v in missing]
    axes[1].barh(np.arange(len(district)), missing, color=colors)
    axes[1].set_yticks(np.arange(len(district)), district)
    axes[1].invert_yaxis()
    axes[1].set_xlabel("Missing records (%)")
    axes[1].set_xlim(0, 45)
    axes[1].grid(axis="x", color="#d9e2df", linewidth=.7)
    axes[1].spines[["top", "right", "left"]].set_visible(False)
    axes[1].set_title("B  Missingness varies within area types", loc="left",
                      fontsize=11, fontweight="bold", color="#173f50")
    fig.suptitle("Data coverage must be audited spatially", x=.01, ha="left",
                 fontsize=15, fontweight="bold", color="#173f50")
    fig.tight_layout(rect=[0, .05, 1, .93])
    save(fig, "07-data-quality-output.png")


def classify(values, breaks):
    return np.digitize(values, breaks, right=True)


def figure_classification() -> None:
    values = np.exp(spatial_surface() / 1.4)
    quantile = np.quantile(values, [.2, .4, .6, .8])
    equal = np.linspace(values.min(), values.max(), 6)[1:-1]
    policy = np.array([1.2, 1.8, 2.5, 3.5])
    schemes = [("A  Quantiles", quantile), ("B  Equal interval", equal),
               ("C  Policy thresholds", policy)]
    cmap = ListedColormap(["#edf5f3", "#badbd4", "#72b7ad", "#337f79", "#174c54"])
    fig, axes = plt.subplots(1, 3, figsize=(13, 4.3))
    for ax, (title, breaks) in zip(axes, schemes):
        classes = classify(values, breaks)
        map_panel(ax, classes, cmap=cmap, vmin=0, vmax=4, title=title)
        counts = np.bincount(classes.ravel(), minlength=5)
        ax.text(.01, -.10, "Class counts: " + " / ".join(map(str, counts)),
                transform=ax.transAxes, fontsize=7.5, color="#64716e")
    fig.suptitle("One indicator, three defensible classification stories", x=.01,
                 ha="left", fontsize=15, fontweight="bold", color="#173f50")
    fig.tight_layout(rect=[0, .06, 1, .92])
    save(fig, "09-classification-comparison.png")


def rook_lag(z):
    total = np.zeros_like(z, dtype=float)
    count = np.zeros_like(z, dtype=float)
    for dy, dx in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
        shifted = np.roll(z, (dy, dx), axis=(0, 1))
        valid = np.ones_like(z, dtype=bool)
        if dy == -1: valid[-1, :] = False
        if dy == 1: valid[0, :] = False
        if dx == -1: valid[:, -1] = False
        if dx == 1: valid[:, 0] = False
        total[valid] += shifted[valid]
        count[valid] += 1
    return total / count


def figure_moran_lisa() -> None:
    raw = spatial_surface()
    z = (raw - raw.mean()) / raw.std()
    lag = rook_lag(z)
    lisa = np.zeros_like(z, dtype=int)
    strong = (np.abs(z) > .55) & (np.abs(lag) > .35)
    lisa[strong & (z > 0) & (lag > 0)] = 1
    lisa[strong & (z < 0) & (lag < 0)] = 2
    lisa[strong & (z > 0) & (lag < 0)] = 3
    lisa[strong & (z < 0) & (lag > 0)] = 4

    fig, axes = plt.subplots(1, 3, figsize=(13, 4.2))
    im = map_panel(axes[0], z, cmap="RdBu_r", vmin=-2, vmax=2, title="A  Standardized indicator")
    fig.colorbar(im, ax=axes[0], fraction=.046, pad=.03, label="z-score")
    axes[1].scatter(z.ravel(), lag.ravel(), s=28, color="#28766f", alpha=.75,
                    edgecolor="white", linewidth=.4)
    slope = np.polyfit(z.ravel(), lag.ravel(), 1)
    xx = np.linspace(z.min(), z.max(), 100)
    axes[1].plot(xx, slope[0] * xx + slope[1], color="#c96852", linewidth=2)
    axes[1].axhline(0, color="#9aa7a4", linewidth=.7)
    axes[1].axvline(0, color="#9aa7a4", linewidth=.7)
    axes[1].set_xlabel("Indicator z-score")
    axes[1].set_ylabel("Spatial lag")
    axes[1].set_title("B  Moran scatter plot", loc="left", fontsize=11,
                      fontweight="bold", color="#173f50")
    axes[1].spines[["top", "right"]].set_visible(False)
    colors = ["#ecefed", "#b2182b", "#2166ac", "#ef8a62", "#67a9cf"]
    map_panel(axes[2], lisa, cmap=ListedColormap(colors), vmin=0, vmax=4,
              title="C  Local cluster diagnosis")
    labels = ["Not flagged", "High–high", "Low–low", "High–low", "Low–high"]
    handles = [Line2D([0], [0], marker="s", color="none", markerfacecolor=c,
                      markeredgecolor="none", markersize=8, label=l)
               for c, l in zip(colors, labels)]
    axes[2].legend(handles=handles, loc="lower left", bbox_to_anchor=(0, -.30),
                   frameon=False, ncol=2, fontsize=7)
    fig.suptitle("Global association and local clusters answer different questions",
                 x=.01, ha="left", fontsize=15, fontweight="bold", color="#173f50")
    fig.tight_layout(rect=[0, .08, 1, .92])
    save(fig, "10-moran-lisa-output.png")


def network_graph():
    nodes = [(x, y) for y in range(NY) for x in range(NX)]
    edges = []
    for x, y in nodes:
        if x + 1 < NX and not (x == 4 and y not in (2, 5)):
            edges.append(((x, y), (x + 1, y)))
        if y + 1 < NY:
            edges.append(((x, y), (x, y + 1)))
    return nodes, edges


def distances(nodes, edges, sources):
    adjacency = {n: [] for n in nodes}
    for a, b in edges:
        adjacency[a].append(b); adjacency[b].append(a)
    dist = {n: float("inf") for n in nodes}
    queue = []
    for source in sources:
        dist[source] = 0; heapq.heappush(queue, (0, source))
    while queue:
        cost, node = heapq.heappop(queue)
        if cost != dist[node]: continue
        for nxt in adjacency[node]:
            new = cost + 1
            if new < dist[nxt]:
                dist[nxt] = new; heapq.heappush(queue, (new, nxt))
    return dist


def draw_network(ax, nodes, edges, values, facilities, title):
    for a, b in edges:
        ax.plot([a[0], b[0]], [a[1], b[1]], color="#cbd4d2", linewidth=1, zorder=1)
    vals = np.array([values[n] for n in nodes])
    sc = ax.scatter([n[0] for n in nodes], [n[1] for n in nodes], c=vals,
                    cmap="YlGnBu_r", s=48, edgecolor="white", linewidth=.45, zorder=2)
    ax.scatter([n[0] for n in facilities], [n[1] for n in facilities], marker="*",
               s=180, color="#c96852", edgecolor="white", linewidth=.8, zorder=3)
    style_axis(ax, title)
    ax.set_aspect("equal")
    return sc


def figure_accessibility() -> None:
    nodes, edges = network_graph()
    central = [(2, 5), (7, 2)]
    added = central + [(8, 6)]
    d0 = distances(nodes, edges, central)
    d1 = distances(nodes, edges, added)
    fig, axes = plt.subplots(1, 3, figsize=(13, 4.1))
    sc = draw_network(axes[0], nodes, edges, d0, central, "A  Baseline travel cost")
    draw_network(axes[1], nodes, edges, d1, added, "B  Add one facility")
    gain = {n: d0[n] - d1[n] for n in nodes}
    for a, b in edges:
        axes[2].plot([a[0], b[0]], [a[1], b[1]], color="#d9e2df", linewidth=1)
    vals = np.array([gain[n] for n in nodes])
    im = axes[2].scatter([n[0] for n in nodes], [n[1] for n in nodes], c=vals,
                         cmap="YlOrRd", s=52, edgecolor="white", linewidth=.45)
    style_axis(axes[2], "C  Accessibility improvement")
    axes[2].set_aspect("equal")
    fig.colorbar(sc, ax=axes[:2], fraction=.022, pad=.02, label="Network steps")
    fig.colorbar(im, ax=axes[2], fraction=.046, pad=.03, label="Steps saved")
    fig.suptitle("Network barriers change who benefits from a new facility", x=.01,
                 ha="left", fontsize=15, fontweight="bold", color="#173f50")
    fig.subplots_adjust(left=.02, right=.96, bottom=.10, top=.84, wspace=.18)
    save(fig, "11-network-accessibility-output.png")


def figure_spatial_model() -> None:
    actual = spatial_surface()
    neighbor = rook_lag(actual)
    prediction = .72 * actual + .28 * neighbor + RNG.normal(0, .12, actual.shape)
    prediction[:, -2:] -= .45
    error = np.abs(actual - prediction)
    lo, hi = min(actual.min(), prediction.min()), max(actual.max(), prediction.max())
    fig, axes = plt.subplots(1, 3, figsize=(13, 4.1))
    im0 = map_panel(axes[0], actual, cmap="viridis", vmin=lo, vmax=hi,
                    title="A  Observed heat risk")
    map_panel(axes[1], prediction, cmap="viridis", vmin=lo, vmax=hi,
              title="B  Spatial model prediction")
    im2 = map_panel(axes[2], error, cmap="OrRd", vmin=0, vmax=np.quantile(error, .95),
                    title="C  Absolute error")
    fig.colorbar(im0, ax=axes[:2], fraction=.022, pad=.02, label="Risk score")
    fig.colorbar(im2, ax=axes[2], fraction=.046, pad=.03, label="Absolute error")
    fig.suptitle("A prediction map must be read together with its error map", x=.01,
                 ha="left", fontsize=15, fontweight="bold", color="#173f50")
    fig.subplots_adjust(left=.02, right=.96, bottom=.10, top=.84, wspace=.18)
    save(fig, "12-spatial-model-output.png")


def figure_spatial_cv() -> None:
    folds = np.tile(np.repeat(np.arange(1, 6), 2), (NY, 1))
    base = np.array([.28, .31, .36, .48, .63])
    errors = np.repeat(base, 8) + RNG.normal(0, .035, 40)
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.3), gridspec_kw={"width_ratios": [1.05, 1.2]})
    map_panel(axes[0], folds, cmap=ListedColormap(["#edf5f3", "#badbd4", "#72b7ad", "#337f79", "#174c54"]),
              vmin=1, vmax=5, title="A  Contiguous spatial folds")
    axes[1].boxplot([errors[i * 8:(i + 1) * 8] for i in range(5)], patch_artist=True,
                    boxprops={"facecolor": "#badbd4", "edgecolor": "#28766f"},
                    medianprops={"color": "#c96852", "linewidth": 2},
                    whiskerprops={"color": "#64716e"}, capprops={"color": "#64716e"})
    axes[1].set_xticklabels([f"Fold {i}" for i in range(1, 6)])
    axes[1].set_ylabel("MAE")
    axes[1].grid(axis="y", color="#d9e2df", linewidth=.7)
    axes[1].spines[["top", "right"]].set_visible(False)
    axes[1].set_title("B  Report the distribution, not only the mean", loc="left",
                      fontsize=11, fontweight="bold", color="#173f50")
    fig.suptitle("Spatial validation exposes geographic transfer risk", x=.01,
                 ha="left", fontsize=15, fontweight="bold", color="#173f50")
    fig.tight_layout(rect=[0, .05, 1, .92])
    save(fig, "13-spatial-cv-output.png")


def figure_cool_corridors() -> None:
    heat = spatial_surface() + .15 * X
    scenarios = [
        ("A  Health first", [((1, 6), (4, 5)), ((4, 5), (7, 3)), ((7, 3), (9, 2))]),
        ("B  Feasibility first", [((0, 2), (3, 2)), ((3, 2), (6, 2)), ((6, 2), (9, 2))]),
        ("C  Service connection", [((1, 6), (3, 4)), ((3, 4), (6, 3)), ((6, 3), (8, 6))]),
    ]
    fig, axes = plt.subplots(1, 3, figsize=(13, 4.2))
    for ax, (title, paths) in zip(axes, scenarios):
        map_panel(ax, heat, cmap="YlOrRd", vmin=heat.min(), vmax=heat.max(), title=title)
        for (x0, y0), (x1, y1) in paths:
            ax.plot([x0, x1], [y0, y1], color="#0f6b6d", linewidth=5,
                    solid_capstyle="round", alpha=.92)
            ax.plot([x0, x1], [y0, y1], color="white", linewidth=1.1,
                    linestyle="--", alpha=.9)
    fig.suptitle("Alternative objectives produce different cool-corridor networks",
                 x=.01, ha="left", fontsize=15, fontweight="bold", color="#173f50")
    fig.tight_layout(rect=[0, .05, 1, .92])
    save(fig, "15-cool-corridor-output.png")


def main() -> None:
    plt.rcParams.update({"font.family": "DejaVu Sans", "axes.labelcolor": "#314a53"})
    figure_data_quality()
    figure_classification()
    figure_moran_lisa()
    figure_accessibility()
    figure_spatial_model()
    figure_spatial_cv()
    figure_cool_corridors()
    print(f"Generated 7 figures in {OUT}")


if __name__ == "__main__":
    main()
