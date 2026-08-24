# 南京中心城区教学样例数据

本目录服务于《数据科学与城市空间研究》的贯穿案例。几何范围采用南京中心城区附近的 WGS84 经纬度范围，空间单元、属性数值、设施点和教学道路均由固定随机种子生成。它们具有完整的 GIS 数据结构和可重复的空间关系，可以用于运行 GeoPandas、PySAL、scikit-learn 与 ArcGIS Pro 实验；不得把其中的数值解释为南京市官方统计、现状设施清单或规划结论。

## 文件组成

| 文件 | 几何或格式 | 主要用途 |
|---|---|---|
| `community_grid.geojson` | 96个面要素 | 专题制图、空间连接、空间权重、聚类和模型评价 |
| `community_indicators.csv` | UTF-8 CSV | Pandas清洗、属性连接、描述统计和机器学习 |
| `facilities.geojson` | 36个点要素 | 设施覆盖、最近邻、供需可达性和选址分析 |
| `teaching_roads.geojson` | 10条线要素 | 线网检查、服务联系和廊道方案演示 |
| `metadata.json` | JSON | 坐标系、范围、数据性质、生成脚本和随机种子 |

## 主要字段

| 字段 | 含义 | 单位或范围 |
|---|---|---|
| `grid_id` | 稳定空间主键 | 文本 |
| `population` | 教学人口规模 | 人 |
| `elderly_share` | 老年人口比例 | 0—1 |
| `tree_cover` | 树冠覆盖比例 | 0—1 |
| `heat_c` | 教学地表热环境指标 | 摄氏度 |
| `transit_access` | 公共交通可达性指数 | 0—1 |
| `health_access` | 基层医疗可达性指数 | 0—1 |
| `data_coverage` | 有效观测覆盖率 | 0—1 |
| `vulnerability` | 教学脆弱性指数 | 0—1 |
| `priority_score` | 标准化干预优先度 | 连续值 |

## 重新生成

从仓库根目录执行：

```bash
python scripts/generate_nanjing_case_assets.py
```

脚本会重建本目录中的数据文件，并更新第1—5、8、14和16章使用的结果图。正式研究需要用可核验的行政边界、人口、设施、道路、遥感和监测数据替换教学属性，并逐项记录来源、许可、年份、空间精度与已知偏差。
