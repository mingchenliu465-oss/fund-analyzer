# 智投 · AI 基金投资分析助手

一个面向个人投资者的本地基金研究工具。

它把基金净值、风险、回撤、持仓、市场行情和个人组合放在一个界面里，帮助你回答三个实际问题：

> 这只基金过去表现怎么样？
>
> 我的组合今天为什么涨跌？
>
> 我看到的数据到底新不新鲜？

项目运行在本地，数据来自公开接口，不需要把持仓记录上传到第三方服务。

![Next.js](https://img.shields.io/badge/Next.js-16-black?logo=next.js)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688?logo=fastapi)
![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python)
![Data](https://img.shields.io/badge/data-akshare-blue)

## 你可以用它做什么

### 看懂一只基金

- 搜索基金名称或代码
- 查看净值、收益、年化波动率、夏普比率和最大回撤
- 区分场外基金、场内 ETF 和 LOF 的行情语义
- 查看净值走势、ETF K 线、行业分布和前十大持仓
- 查看同类比较与收益排名（数据可用时显示）

### 管理自己的组合

- 录入买入日期、金额、净值、份额和手续费
- 支持单笔持仓和自动定投记录
- 查看持仓市值、成本、浮动盈亏和历史资产走势
- 解释“今天我的组合为什么涨跌”
- 按基金贡献拆分上涨来源和拖累来源
- 行情过期或缺失时明确提示，不把缺失数据伪装成 0

### 从多个角度复盘

- 组合洞察：收益解释、集中度、指数对比和历史变化
- 投资复盘：按当前持仓生成规则化的复盘内容
- 基金对比：把多只基金放在一起查看关键指标
- Workbench：快速搜索、标记和观察基金走势

## 页面导航

| 页面 | 地址 | 用途 |
|---|---|---|
| 首页 | `/` | 市场状态、热门基金和最近浏览 |
| 基金分析 | `/fund` | 搜索基金并进入详情 |
| 基金详情 | `/fund/{基金代码}` | 业绩、风险、走势、持仓和行业 |
| 我的组合 | `/portfolio` | 录入交易、查看持仓和今日收益 |
| 组合洞察 | `/insights` | 收益、风险、集中度和市场比较 |
| 基金对比 | `/compare` | 多只基金横向比较 |
| 投资复盘 | `/review` | 查看组合复盘结果 |
| Workbench | `/workbench` | 快速研究基金 |

## 真实数据优先

这个项目有一条明确的数据原则：**没有数据就明确显示没有数据。**

- 不使用 mock 基金行情或虚构收益
- 不用 `0` 替代缺失的净值、涨跌幅或风险指标
- 基金净值、ETF 市价和 ETF 净值分开处理
- 收益、波动率和最大回撤优先使用累计净值口径，避免把分红误算成亏损
- 持仓和行业配置锁定在同一个报告期，避免跨季度混算
- 每条行情都尽量保留观测日期，并区分 `fresh`、`stale`、`unavailable` 等状态

数据源来自 [akshare](https://www.akshare.xyz/)，底层接口主要覆盖东方财富、天天基金和新浪公开数据。公开数据可能受到网络、接口限流或反爬策略影响，遇到暂不可用时请稍后重试。

## 快速开始

### 环境要求

- Python 3.11 或更高版本
- Node.js 20 或更高版本
- 能访问 akshare 所使用的公开数据接口

### 1. 安装后端

在项目根目录执行：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend/requirements.txt
```

### 2. 启动后端

```powershell
cd backend
..\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

后端地址：`http://localhost:8000`<br>
健康检查：`http://localhost:8000/health`<br>
API 前缀：`/api`

### 3. 安装并启动前端

另开一个终端：

```powershell
cd frontend
npm install
npm run dev
```

前端地址：`http://localhost:3000`

前端通过 `next.config.ts` 将 `/api/*` 转发到本地 FastAPI 后端。项目已移除桌面快捷启动器，使用上述两个终端命令即可启动。

### 4. 生产构建（可选）

```powershell
cd frontend
npm run build
npm run start
```

## 主要 API

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/funds?q={query}&limit={limit}` | 基金搜索与列表 |
| GET | `/api/funds/rankings?limit={limit}` | 近一年收益排行 |
| GET | `/api/funds/popular?limit={limit}` | 热门基金 |
| GET | `/api/funds/{code}` | 基金详情 |
| GET | `/api/funds/{code}/nav-history?period=...` | 基金净值历史 |
| GET | `/api/market/kline?code={code}&period=...` | 基金或 ETF 行情 |
| GET | `/api/market/indices` | 市场指数 |
| GET | `/api/market/status` | 当前交易日状态 |
| GET | `/api/analysis/drawdown/{code}?period=...` | 历史回撤 |
| GET | `/api/analysis/peers/{code}` | 同类比较 |
| GET | `/api/analysis/ranking/{code}` | 收益排名 |
| GET | `/api/portfolio` | 组合概览 |
| GET | `/api/portfolio/attribution` | 今日收益归因 |
| GET | `/api/portfolio/insights?period=...` | 组合洞察 |
| GET | `/api/review/daily` | 投资复盘 |

启动后也可以打开 FastAPI 文档：`http://localhost:8000/docs`。

## 数据与本地文件

- 默认持仓数据库：`backend/database/portfolio.db`
- 可通过 `FUND_ANALYZER_DB_PATH` 指定其他 SQLite 文件
- `backend/database/*.db`、日志和测试缓存不会提交到 Git
- 最近浏览记录保存在浏览器本地，不上传到服务器

## 开发与验证

后端测试需要使用仓库内虚拟环境：

```powershell
.\.venv\Scripts\python.exe -m pytest -q --basetemp=.tmp-pytest-base
```

前端检查：

```powershell
cd frontend
npm.cmd run lint
npm.cmd exec tsc -- --noEmit
npm.cmd run build
```

当前版本已通过完整后端测试、TypeScript 检查、ESLint 和 Next.js 生产构建。

## 重要说明

- 场外基金净值通常是 T-1，ETF 行情可能是交易日收盘数据；页面会显示数据状态，不把它们混称为同一种“实时价格”。
- 首次加载基金全量列表可能需要一段时间，后续请求会使用内存缓存。
- 组合今日收益按当前持有份额和最近两次可用净值计算，日内现金流、分红和已卖出持仓不等同于完整券商账户收益。
- 所有分析仅用于理解历史数据，不构成投资建议。

## 技术栈

- 前端：Next.js 16、React 19、TypeScript、Tailwind CSS、React Query、Recharts、Lightweight Charts
- 后端：FastAPI、Pydantic、Pandas、NumPy、SQLite
- 数据：akshare

## License

本项目目前主要用于个人学习和本地研究。使用公开数据时请遵守相关数据源的服务条款。
