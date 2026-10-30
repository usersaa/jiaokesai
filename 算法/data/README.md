# 数据目录说明

本目录只放「输入数据」与「采集模板」，不放代码、不放模型。

```
data/
├── templates/                实地采集空模板（复制到手机/Excel 使用）
│   ├── stations_template.csv
│   ├── inventory_observations.csv
│   └── od_observations.csv
├── synthetic/                代码自检用占位数据（脚本生成，不可作为论文实证）
│   ├── stations.csv
│   └── demand_by_step.csv
└── real/                     【待建】真实观测数据（采集后放这里）
```

## 1. stations.csv（P 点表）

| 列 | 类型 | 说明 |
|---|---|---|
| id | str | P 点编号，如 P01 |
| name | str | 名称，如「笃行楼」 |
| lng | float | 经度（GCJ-02） |
| lat | float | 纬度（GCJ-02） |
| capacity | int | 容量（辆） |
| func | str | dorm/teach/canteen/library/gate/sport/other |
| attraction | float | 目的地吸引量，可留空由功能默认值填充 |
| init_bikes | int | 当日 06:30 初始车辆数 |
| target_bikes | float | 夜间静态调度目标库存，可留空取容量一半 |

采集方式：`web/` 地图标定工具导出 JSON → 转 CSV；容量用 `面积 / 1.8 m²` 估算后现场校正。

## 2. inventory_observations.csv（在点车辆数）

| 列 | 说明 |
|---|---|
| time | 观测时刻，`HH:MM` |
| station | P 点编号 |
| bikes | 在点车辆数（整数） |
| note | 备注（满位、故障车等） |

采集粒度：七个脉冲窗口内 10 min 一张，平峰 30–60 min 一张。

## 3. od_observations.csv（OD 观测）

| 列 | 说明 |
|---|---|
| time_window | 时段，如 `07:40-08:00` |
| origin | 起点 P 点 |
| destination | 终点 P 点（可由还车点推断） |
| trips | 人次 |
| note | 备注 |

说明：历史订单是供给约束下的观测值，会低估真实需求。建模时用「课程安排 + 门禁/人数」解耦，
OD 只用于标定目的地选择参数（吸引量、距离衰减），不直接当真实需求。

## 4. 待补数据清单（对应建模文档第十五章）

1. P 点数量、容量、坐标
2. 七脉冲窗口各点借还计数（10 min 粒度）
3. 平峰在点车辆数（30 min 粒度）
4. 点位功能类别
5. 运维车数量、载量、作业频次
6. 换电作业时间与路线
7. 单次用户 / 月卡用户比例 γ
8. 在校生规模与宿舍分布
9. SP 问卷：λ、VOT（有效样本 ≥ 300）
10. 校园路网距离矩阵（高德 + 实测校正）

## 5. 缺失时的处理

- 代码默认读取 `data/synthetic/stations.csv`，保证可跑通；
- 所有 `[TODO]` 参数在 `configs/default.yaml` 中集中管理；
- 真实数据到位后，只改配置与 CSV，不改代码。
