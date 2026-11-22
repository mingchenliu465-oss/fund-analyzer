# 智投 · AI 基金投资分析助手 (Fund Analyzer)

![Next.js](https://img.shields.io/badge/Next.js-16-black?logo=next.js)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688?logo=fastapi)
![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python)
![Data](https://img.shields.io/badge/data-akshare-blue)

面向个人投资者的本地基金研究工具。把基金净值、风险、回撤、持仓、市场行情和个人组合放在同一个界面里，回答三个问题：

1. **这只基金过去表现怎么样？**
2. **我的组合今天为什么涨跌？**
3. **我看到的数据新不新鲜？**

项目在本地运行，行情与净值数据来自公开接口（`akshare`，底层覆盖东方财富、天天基金、新浪），个人持仓记录不上传第三方。

---

## 版本状态

- **当前正式发布版本：** **v2.0**（2026-10-25，GitHub Releases 有正式版本页，正式主干后端 357 项测试全过）。
- **v3 整合进展：** v3 整合版已在分支 `integration/v3-nightly-2026-11-21` 完成代码整合，后端 396 项测试、前端单元测试、TypeScript、ESLint、生产构建全过。
- **v3 还差三步才正式发布：** 界面视觉定稿、真实数据联调、合并主干验收。完成验收后才打 v3.0 标签，现阶段以 v2.0 为正式版。
- 完整版本登记见仓库 `VERSIONS.md`。

---

## v2 已有功能

### 基金搜索与详情

- 净值、收益、年化波动率、夏普比率、最大回撤。
- 区分场外基金 / 场内 ETF / LOF 的行情语义；净值走势、ETF K 线、行业分布、前十大持仓、同类比较与收益排名。

### 个人组合

- 录入买入日期 / 金额 / 净值 / 份额 / 手续费，支持单笔与自动定投。
- 持仓市值、成本、浮动盈亏、历史资产走势。
- 今日收益归因：按基金拆分上涨与拖累来源。

### 组合洞察

- 收益解释、集中度、指数对比。

### 投资复盘

- 规则引擎按真实持仓生成复盘。

### 基金对比与 Workbench

- 基金对比（/compare）。
- Workbench（/workbench）：快速搜索、标记、观察。

---

## v3 新增

### 1. 历史频率（/history-frequency）

不预测，只统计历史。过去任意一天买入后，接下来一年赚钱的频率、途中跌超 10% 的频率、跌 5% 后中位等多少个交易日回本。每个数字都标统计口径和样本范围。

- 页面：`/history-frequency`
- 接口：`GET /api/history-frequency/{code}`

### 2. 回测实验室（/backtest）

诚实回测。规则事先写死：250 日新高回撤 10% / 15% / 20% 触发买入，持有 6 / 12 个月。只看样本外、扣手续费、与买入持有对比。样本不足三年拒绝出结论，结论三档：**成立 / 不成立 / 证据不足**。

- 页面：`/backtest`
- 接口：`GET /api/backtest/{code}`

### 3. 研究能力

市场概览与基金研究数据（概览、表现、资金流向、持仓结构），从研究分支摘取并入统一代码。

---

## 数据原则（项目铁律）

没有数据就明确显示没有数据：

- 不用 mock 行情或虚构收益，不用 0 代替缺失值。
- 净值 / ETF 市价 / ETF 净值分开处理。
- 收益与风险优先用累计净值口径（避免把分红误算成亏损）。
- 持仓与行业锁定同一报告期。
- 每条行情保留观测日期，并区分 `fresh` / `stale` / `unavailable`。

## 预测立场：只讲历史，不做预测

项目内部用 22 轮严格样本外实验验证过概率预测，结论是只靠净值历史算不出可信概率（深跌后是续跌还是跌透，纯价格数据不可稳定区分），因此预测数字不进入任何页面。实验代码只在本地实验分支作离线研究。

---

## 页面导航

| 页面 | 说明 |
| --- | --- |
| `/` | 首页：市场状态、热门基金、最近浏览 |
| `/fund` | 基金分析 |
| `/fund/{code}` | 基金详情 |
| `/history-frequency` | 历史频率（v3 新增） |
| `/backtest` | 回测实验室（v3 新增） |
| `/portfolio` | 我的组合 |
| `/insights` | 组合洞察 |
| `/compare` | 基金对比 |
| `/review` | 投资复盘 |
| `/workbench` | Workbench |

---

## 主要 API

| 接口 | 说明 |
| --- | --- |
| `GET /api/funds` | 搜索列表 |
| `GET /api/funds/rankings` | 收益排名 |
| `GET /api/funds/popular` | 热门基金 |
| `GET /api/funds/{code}` | 基金详情 |
| `GET /api/funds/{code}/nav-history` | 净值历史 |
| `GET /api/market/kline` | K 线行情 |
| `GET /api/market/indices` | 指数行情 |
| `GET /api/market/status` | 市场状态 |
| `GET /api/analysis/drawdown/{code}` | 回撤分析 |
| `GET /api/analysis/peers/{code}` | 同类比较 |
| `GET /api/analysis/ranking/{code}` | 收益排名 |
| `GET /api/portfolio` | 我的组合 |
| `GET /api/portfolio/attribution` | 今日收益归因 |
| `GET /api/portfolio/insights` | 组合洞察 |
| `GET /api/review/daily` | 每日复盘 |
| `GET /api/history-frequency/{code}` | 历史频率（v3 新增） |
| `GET /api/backtest/{code}` | 回测实验室（v3 新增） |

API 文档（后端启动后）：`http://localhost:8000/docs`

---

## 快速开始

环境：Python 3.11+、Node.js 20+。

### 后端

```powershell
# 在项目根目录创建并激活虚拟环境
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 安装后端依赖
pip install -r backend/requirements.txt

# 启动后端
cd backend
..\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

后端地址：`http://localhost:8000`，健康检查：`/health`。

### 前端

```powershell
cd frontend
npm install
npm run dev
```

前端地址：`http://localhost:3000`。前端经 `next.config.ts` 把 `/api/*` 转发到后端。

### 生产构建（可选）

```powershell
cd frontend
npm run build
npm run start
```

---

## 数据与本地文件

- 默认持仓数据库：`backend/database/portfolio.db`，可用环境变量 `FUND_ANALYZER_DB_PATH` 指定。
- `*.db`、日志、测试缓存不进 Git。
- 最近浏览记录只存浏览器本地。

---

## 开发与验证

后端：

```powershell
pytest
```

（仓库虚拟环境运行。）

前端：

```powershell
npm run lint
npx tsc --noEmit
npm run build
```

测试状态：v3 整合分支后端 396 项全过；正式主干后端 357 项全过。

---

## 重要说明

- 场外基金净值通常 T-1，ETF 行情可能是收盘数据。页面显示数据状态，不混称实时价格。
- 名称里的“AI”目前指规则引擎复盘，大语言模型尚未接入（后端预留了接口），页面没有 AI 自由生成的内容。
- 首次加载基金全量列表较慢，之后走内存缓存；数据源不可用时回退到本地上次成功的基金列表。
- 组合资产快照在持仓增删改时每日记录一条。
- 组合今日收益按当前份额与最近两次可用净值计算，不等同完整券商账户收益。
- 所有分析仅用于理解历史数据，不构成投资建议。

---

## 技术栈

| 层 | 技术 |
| --- | --- |
| 前端 | Next.js 16、React 19、TypeScript、Tailwind CSS、React Query、Recharts、Lightweight Charts |
| 后端 | FastAPI、Pydantic、Pandas、NumPy、SQLite |
| 数据 | akshare |

---

## 版本历史

| 版本 | 时间 | 说明 |
| --- | --- | --- |
| v1.0 | 2026-08 | 最早历史快照 |
| v2.0 | 2026-10-25 | 正式产品基线：诚实回测引擎、组合与复盘 |
| v3 | 整合完成待发布 | 数据质量修复 + 历史频率 + 回测实验室 + 研究能力 |

---

## License

本项目目前主要用于个人学习和本地研究；使用公开数据请遵守数据源服务条款。
