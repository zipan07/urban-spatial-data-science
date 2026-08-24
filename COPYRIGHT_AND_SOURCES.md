# 版权、改编与来源说明

本项目为《数据科学与城市空间研究》课程中文在线教材，由蔡子攀组织编写。

## 教材性质

本教材不是任何现有著作的授权中文版。全书围绕“问题—数据—方法—证据—判断—表达”重新组织，加入城乡规划解释、可重复计算、课堂实验、稳健性检验和综合案例。正文不以逐段翻译方式复制参考教材。

## 主要资源的使用方式

### Urban Informatics

Shi, W., Goodchild, M. F., Batty, M., Kwan, M.-P., & Zhang, A. (Eds.), 2021。

Springer 开放英文版采用 CC BY 4.0，可在署名、链接许可并注明改编的条件下使用和改编。本教材参考其城市信息学、城市科学、感知、计算和应用框架。科学出版社中文版本作为课程参考书，不视为开放许可来源。

https://link.springer.com/book/10.1007/978-981-15-8983-6

### Geographic Data Science with Python

Sergio J. Rey, Dani Arribas-Bel, Levi J. Wolf, 2023。

原书项目采用CC BY-NC-ND 4.0，包含非商业和禁止演绎限制。本教材仅参考其知识顺序、通用方法主题和公开链接，不发布整章翻译、原图、修改版Notebook或可替代原作的衍生文本。所有中文解释、示例、代码、练习数据和结果图按课程需要独立组织。

https://geographicdata.science/book/

### 空间数据分析案例式实验教程

翁敏、李霖、苏世亮，科学出版社。本教材借鉴“案例背景—问题—方法—实验—解释”的教学思路，不复制其正文、图表、数据或实验步骤。

### The Effect

Nick Huntington-Klein, Chapman & Hall/CRC。本教材把在线版作为研究设计与因果推断延伸阅读。免费在线访问不被视为允许制作中文译本。

https://theeffectbook.net/

## 数据、图片与代码

- 中国城市案例优先使用开放数据、教师自有数据、合成数据或取得教学授权的数据。
- 外部数据记录生产者、时间、许可、空间范围、处理过程和已知偏差。
- 外部图片、地图和代码分别核查许可，不因网页可访问而默认可转载。
- `figures/`中的教学结果图由本项目脚本使用合成数据生成，可通过`scripts/generate_textbook_figures.py`与`scripts/generate_nanjing_case_assets.py`重现；替换为真实城市数据时需要同步更新图注、数据来源和适用范围。
- `data/china_city_open/ghsl_china_major_cities.*`来自 European Commission Joint Research Centre 的 GHSL Urban Centre Database R2024A 教学子集。再使用时署名 European Commission, Joint Research Centre (JRC), GHSL UCDB R2024A，并查阅官方数据包条款：https://human-settlement.emergency.copernicus.eu/ghs_ucdb_2024.php
- `data/china_city_open/nanjing_osm_public_services.geojson`来自 OpenStreetMap 贡献者，依据 ODbL 1.0 使用。地图、图表与衍生数据库保留“© OpenStreetMap contributors”署名：https://www.openstreetmap.org/copyright
- 上述真实数据的查询范围、字段、记录数、获取日期和复现参数写入`data/china_city_open/metadata.json`，可通过`scripts/build_open_city_datasets.py`更新。
- 代码示例以课程自行编写为主；第三方软件调用遵守其软件许可与引用规范。
- 涉及个体位置和行为的数据遵守最小必要、去标识化、访问控制和科研伦理要求。

## 教学与再使用

当前版本为课堂试用稿。后续公开许可将由课程团队在核对所有第三方材料后确定。在正式许可发布前，不应推定整个仓库自动采用任何特定开放许可。
