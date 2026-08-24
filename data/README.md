# 教材数据目录

本目录保存《数据科学与城市空间研究》可直接下载的课堂数据。网页版入口见：

https://zipan07.github.io/urban-spatial-data-science/data.html

学生可以直接下载本目录中的文件，并把它们用于课程练习、作业和研究复现。不同数据包的权利来源并不相同，下载、修改和再分发时应分别遵守下表所列许可。

| 数据目录 | 性质 | 许可与允许的使用 |
|---|---|---|
| `nanjing_teaching/` | 本项目生成的教学数据 | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)；允许下载、复制、修改与分享，使用时署名，且不得表述为南京官方统计或真实设施 |
| `china_city_open/ghsl_*` | GHSL教学子集 | 按 European Commission JRC 官方数据包条款使用并署名 |
| `china_city_open/nanjing_osm_*` | OpenStreetMap衍生数据 | ODbL 1.0；保留“© OpenStreetMap contributors”署名 |
| 外部下载数据 | 各机构发布的数据产品 | 以相应产品页面和元数据列明的许可为准 |

## 可随教材下载的数据

### `china_city_open/`

- `ghsl_china_major_cities.geojson`：GHSL UCDB R2024A 的11个中国代表性城市形态区。
- `ghsl_china_major_cities.csv`：相同记录的非空间属性与标注坐标。
- `nanjing_osm_public_services.geojson`：南京中心城区的321个OSM公共服务与轨道节点。
- `metadata.json`：来源、许可、查询参数、记录数、空间范围与获取日期。

复现脚本：`scripts/build_open_city_datasets.py`。

GHSL 数据使用时请署名 European Commission, Joint Research Centre (JRC), GHSL UCDB R2024A，并查阅官方数据包使用说明。OSM 数据依据 ODbL 1.0 使用，署名 `© OpenStreetMap contributors`。

### `nanjing_teaching/`

- `community_grid.geojson`：96个教学网格。
- `community_indicators.csv`：96条生成式社区指标。
- `facilities.geojson`：36个生成式设施点。
- `teaching_roads.geojson`：10条教学道路。
- `metadata.json`：坐标、范围与生成参数。

此数据包的属性和设施记录由固定随机种子生成，不代表南京官方统计或现状设施。复现脚本：`scripts/generate_nanjing_case_assets.py`。

本项目对该生成式教学数据采用CC BY 4.0许可。建议署名为：“蔡子攀（2026），《数据科学与城市空间研究》南京教学样例数据，CC BY 4.0”。

## 数据使用顺序

1. 阅读对应数据页面和 `metadata.json`。
2. 核对记录数、字段、坐标系、时间与许可。
3. 从仓库根目录运行章节代码。
4. 把中间结果写入自己的项目目录，不覆盖 `data/` 中的原始教学文件。
5. 使用外部大数据时，把下载脚本、字段字典和校验值提交到项目仓库，原始大文件保存在本地或课程共享空间。

## 外部数据

WorldPop、Sentinel、MODIS、SRTM、ERA5-Land、geoBoundaries 和中国城市公共数据平台的官方入口见网页版“遥感、人口、地形与政府开放数据”。这些文件体量较大或使用条件因产品而异，默认不在本仓库镜像。
