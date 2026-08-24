# 中国八城市空间数据科学教学包

本目录为《数据科学与城市空间研究》第6—16章提供统一、可重复读取的课堂数据。八个城市分别是北京、上海、南京、广州、成都、武汉、西安和杭州。每个城市采用相同的目录结构与字段约定，学生可以先在南京完成随书练习，再更换城市检验方法的适用范围。

## 直接下载

- [八城市完整数据包](china_eight_city_course_data.zip)
- [北京](beijing/beijing_course_data.zip)
- [上海](shanghai/shanghai_course_data.zip)
- [南京](nanjing/nanjing_course_data.zip)
- [广州](guangzhou/guangzhou_course_data.zip)
- [成都](chengdu/chengdu_course_data.zip)
- [武汉](wuhan/wuhan_course_data.zip)
- [西安](xian/xian_course_data.zip)
- [杭州](hangzhou/hangzhou_course_data.zip)

## 每个城市包含什么

| 文件 | 数据类型 | 主要内容 | 典型用途 |
|---|---|---|---|
| `boundary.geojson` | 面矢量 | GHSL城市形态区边界与城市尺度统计 | 城市边界、地图底图、城市比较 |
| `facilities.geojson` | 点矢量 | OSM公共交通、医疗、教育、文化、社区服务和公园设施 | 点模式、可达性、设施供给 |
| `network_nodes.geojson` | 点矢量 | OSM道路网络节点及节点度数 | 网络拓扑、交叉口识别 |
| `network_edges.geojson` | 线矢量 | OSM道路分段、长度、步行时间代理 | 网络分析、街道连通性 |
| `analysis_grid.geojson` | 面矢量 | 8×8规则网格与聚合指标 | 空间连接、专题制图、空间自相关、机器学习 |
| `grid_indicators.csv` | 统计表 | 与分析网格一一对应的非空间属性表 | 表格清洗、连接、建模 |
| `elevation_250m.tif` | 栅格 | 约200—260 m地面分辨率的SRTM高程裁剪 | 栅格读取、地形统计、矢栅叠加 |
| `city_profile.csv` | 统计表 | GHSL城市尺度指标及课程裁剪摘要 | 描述统计、跨城市比较 |
| `metadata.json` | 元数据 | 范围、来源、许可、字段推导、计数和SHA-256 | 研究记录、复现、质量审查 |

顶层的`catalog.csv`和`catalog.json`是下载索引；`city_profiles.csv`适合八城比较；`all_grid_indicators.csv`合并了全部512个分析单元；`data_inventory.csv`记录来源与许可；`quality_report.json`保存自动审计结果。

## 最短上手路径

下载南京数据包并解压到项目目录后，可在Python中读取：

```python
from pathlib import Path

import geopandas as gpd
import pandas as pd
import rasterio

DATA = Path("data/china_city_cases/nanjing")

grid = gpd.read_file(DATA / "analysis_grid.geojson")
indicators = pd.read_csv(DATA / "grid_indicators.csv")
facilities = gpd.read_file(DATA / "facilities.geojson")

# cell_id是空间网格与统计表之间的稳定主键
grid_model = grid[["cell_id", "geometry"]].merge(
    indicators,
    on="cell_id",
    validate="one_to_one",
)

with rasterio.open(DATA / "elevation_250m.tif") as src:
    elevation = src.read(1, masked=True)
    print(src.crs, src.bounds, elevation.shape)
```

## 范围与解释边界

课程裁剪覆盖各城市中心点附近约5—7 km范围，用于保证下载体量适合课堂网络环境，并使八城具有一致的数据结构。它不是行政区全域数据，也不是官方设施普查。OpenStreetMap由社区协作维护，不同城市、不同设施类型的完整程度可能不同。因此，原始设施数量适合用于数据处理和方法练习，跨城市比较前必须评估覆盖差异。

`accessibility_proxy`由设施密度、道路密度和中心距离共同构成，是解释方法链条的教学变量。它不表示官方可达性评价，不能直接支持规划决策。正式研究应使用路网阻抗、实际出行时间、人口需求和服务容量重新定义指标。

## 更新与质量控制

数据由`scripts/build_china_city_cases.py`生成，`scripts/validate_china_city_cases.py`检查：

- 八城文件是否齐全且可解析；
- GeoJSON主键是否唯一、坐标是否在合法范围；
- 64个分析网格与CSV能否通过`cell_id`一一连接；
- GeoTIFF是否保留WGS84空间参考和无数据值；
- 文件计数、大小和SHA-256是否与元数据一致；
- 八城合并表是否包含8条城市摘要和512条网格记录。

完整审计过程保存在`notebooks/00_china_city_data_quality.ipynb`。数据生成日期见每个城市的`metadata.json`，引用或提交课程报告时应同时记录该日期。

## 数据许可

GHSL、OpenStreetMap和Terrain Tiles/SRTM保留各自的来源与许可条件。课程项目允许下载、分析和复制教材代码；重新分发或发布派生数据库时，仍需遵守原始数据的署名与许可要求。详见[数据许可与署名](LICENSES.md)。
