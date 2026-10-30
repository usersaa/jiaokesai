# 兰州交通大学校园共享电单车调度算法

第三届甘肃省大学生交通运输科技大赛（硕士生 K 类）参赛作品代码。

面向校园半封闭场景，构建「需求侧（七脉冲 + OD）— 供给侧（库存 + 可用率 + 作业时间）— 下层用户选择（移步 + 激励）— 上层 MDP/PPO 调度」的完整算法链路，配套夜间静态 MILP、六条基线、消融/敏感性/泛化实验。

> 数据尚未采集完成。仓库内 `data/synthetic/` 为**占位数据**，仅用于跑通代码；所有待观测参数在 `configs/default.yaml` 中以 `[TODO]` 标注。

## 目录

```
代码/
├── configs/              参数配置（唯一参数入口）
├── data/                 数据与采集模板（见 data/README.md）
├── docs/                 开发文档（建模/算法/数据/实验/接口）
├── scripts/              训练、评估、基线、夜间 MILP、实验入口
├── src/bike_sched/       算法源码
│   ├── config.py         配置与时间轴
│   ├── entities.py       站点/脉冲/运维车/场景
│   ├── scenario.py       合成算例与 CSV 载入
│   ├── demand.py         需求侧：七脉冲 + OD
│   ├── supply.py         供给侧：库存/可用率/作业时间
│   ├── choice.py         下层用户选择：移步 + 激励
│   ├── metrics.py        八项指标
│   ├── bilevel.py        双层固定点迭代
│   ├── env/              Gymnasium 环境 + 奖励
│   ├── rl/               PPO 训练与评估
│   ├── baselines/        六条基线
│   ├── night/            夜间静态 MILP
│   └── utils/            地理与 CSV 工具
├── tests/                pytest 单元测试
├── web/                  地图标定工具（P 点坐标采集）
├── requirements.txt
└── pytest.ini
```

## 快速开始

```bash
# 1) 安装依赖（建议独立虚拟环境）
pip install -r requirements.txt

# 2) 真实数据准备（可选；没有数据时用占位数据）
python scripts/json_to_stations.py --input web_export.json --output data/real/stations.csv
python scripts/check_data.py --data data/real

# 3) 生成合成占位数据
python scripts/make_synthetic_data.py

# 4) 冒烟测试（几分钟内可跑完）
python scripts/train_ppo.py --smoke

# 5) 基线对比
python scripts/run_baselines.py

# 6) 夜间 MILP
python scripts/run_night_milp.py

# 7) 单元测试
pytest
```

## 文档

| 文档 | 内容 |
|---|---|
| `docs/00_开发说明.md` | 项目定位、环境、目录、运行方式 |
| `docs/01_建模说明.md` | 符号、公式、文献来源、与论文的对应 |
| `docs/02_算法设计.md` | MDP、动作编码、PPO、基线、夜间 MILP、双层迭代 |
| `docs/03_数据字典与采集规范.md` | 数据表结构、采集方案、缺失处理 |
| `docs/04_实验设计.md` | 主实验、消融、敏感性、泛化、精确解对照 |
| `docs/05_代码结构与接口.md` | 模块职责、关键类/函数、扩展点 |

## 与论文的对应

建模严格遵循以下五篇文献的分工，不做跨篇拼接：

- **L1 崔春生等 (2024)**：夜间静态目标函数、状态演化
- **L2 李兴华等 (2020)**：双层结构、移步意愿 κ(·)、竞争取车 f(·)
- **L3 Staffolani et al. (2025, IEEE T-ITS)**：MDP、动作剪枝、奖励三分解、PPO 双头、评估协议
- **L4 桂志鹏等 (2026)**：校园场景、供需失衡指数、需求与供给解耦
- **L5 胡宝雨等 (2024)**：OD 分布（POI 吸引 + 距离衰减）

## 地图工具

`web/` 为独立的 P 点标定地图（高德 JS API 2.0），双击 `web/index.html` 打开。
用于采集 P 点坐标与容量，导出 JSON 后可转为 `data/real/stations.csv`。

## 系统层（Web 系统）

`system/` 是完整 Web 系统：登录 / 角色 / 点位 / 方案 / 实时推演 / 对比 / 夜间调度 / 1920×1080 大屏。

- 启动：`python system/run.py`，浏览器打开 `http://127.0.0.1:8000`
- 默认账号：`admin / admin123`（首次登录强制改密）
- 大屏：`/screen`；录屏模式：`/screen?record=1`
- 详见 `system/README.md`，方案见 `system/docs/系统实现方案.md`

## 许可与数据合规

- 不包含任何爬虫或绕过平台鉴权的代码；
- 观测数据来自实地计数、截图人工核对与公开资料；
- 引用文献仅用于学术研究，按论文规范标注。
