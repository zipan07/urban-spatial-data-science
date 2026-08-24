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
- 除下列明确署名的第三方图像外，`figures/`中的GIS与模型结果图由本项目脚本使用开放数据或生成式教学数据制作，可通过`scripts/generate_textbook_figures.py`、`scripts/generate_nanjing_case_assets.py`与相应数据脚本重现；第一部分的概念关系图由本教材绘制。替换数据时需要同步更新图注、来源和适用范围。
- `figures/part1/urban-systems-flow.jpg`为Gallotti、Bertagnolli与De Domenico发表于*EPJ Data Science*的论文“Unraveling the Hidden Organisation of Urban Systems and Their Mobility Flows”的Figure 1，原图采用CC BY 4.0许可，本教材原样转载并在图注中署名：https://link.springer.com/article/10.1140/epjds/s13688-020-00258-3
- `figures/part1/shanghai-landsat-2016.jpg`与`figures/part1/shanghai-landsat-2019.jpg`来自NASA Earth Observatory文章“The Expansion of Shanghai”，图像由Joshua Stevens使用USGS Landsat数据制作；本教材依据NASA图像与媒体使用指南用于教育并在图注中署名：https://science.nasa.gov/earth/earth-observatory/the-expansion-of-shanghai-145968/ ，使用指南：https://www.nasa.gov/nasa-brand-center/images-and-media/
- `data/china_city_open/ghsl_china_major_cities.*`来自 European Commission Joint Research Centre 的 GHSL Urban Centre Database R2024A 教学子集。再使用时署名 European Commission, Joint Research Centre (JRC), GHSL UCDB R2024A，并查阅官方数据包条款：https://human-settlement.emergency.copernicus.eu/ghs_ucdb_2024.php
- `data/china_city_open/nanjing_osm_public_services.geojson`来自 OpenStreetMap 贡献者，依据 ODbL 1.0 使用。地图、图表与衍生数据库保留“© OpenStreetMap contributors”署名：https://www.openstreetmap.org/copyright
- 上述真实数据的查询范围、字段、记录数、获取日期和复现参数写入`data/china_city_open/metadata.json`，可通过`scripts/build_open_city_datasets.py`更新。
- 教材代码块和`scripts/`目录采用MIT License。学生可以复制、运行、修改和再发布代码；再发布时保留版权与MIT许可声明。第三方软件调用遵守其软件许可与引用规范。
- 涉及个体位置和行为的数据遵守最小必要、去标识化、访问控制和科研伦理要求。

## 教学与再使用

除文件或页面另有说明外，本教材原创中文正文、原创教学图件和课程组织采用CC BY-NC-ND 4.0许可。未经改动的内容可以在署名条件下用于非商业分享；商业使用以及公开传播翻译、改写、重组或删节版本需要事先取得书面许可。

教材代码块和`scripts/`目录采用MIT License，允许复制、运行、修改和再发布。本项目生成的`data/nanjing_teaching/`教学数据采用CC BY 4.0，允许下载、修改和分享，但不得表述为南京官方统计、真实设施或规划结论。GHSL、OpenStreetMap及其他第三方数据继续适用各自许可。

该许可只覆盖本项目有权许可的原创内容。第三方数据、软件、底图、引文和署名材料继续遵守各自条款。完整说明见[`LICENSE.md`](LICENSE.md)和在线[版权与使用说明](copyright.qmd)。
