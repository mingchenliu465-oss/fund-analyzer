# Fund Analyzer

基金分析助手：Next.js 前端 + FastAPI 后端，接入 akshare 国内基金实时/历史数据。

## 项目结构

```
fund-analyzer/
├── frontend/          # Next.js 前端
│   ├── app/           # 页面路由
│   ├── components/    # 可复用组件
│   └── services/fund.ts   # 数据服务层（mock / 真实 API 切换）
├── backend/           # FastAPI 后端
│   ├── api/           # REST 路由
│   ├── models/        # Pydantic 模型
│   ├── services/      # 数据获取与业务逻辑
│   └── main.py        # 服务入口
└── components/        # 共享组件（预留）
```

## 快速开始

### 1. 安装后端依赖

```bash
cd backend
python -m pip install -r requirements.txt
```

### 2. 启动后端

```bash
cd backend
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

后端默认监听 `http://localhost:8000`，API 前缀为 `/api`。健康检查：`GET http://localhost:8000/health`。

### 3. 启动前端

**Mock 模式（默认，不依赖后端）：**

```bash
cd frontend
npm run dev
```

**真实数据模式（需先启动后端）：**

```bash
cd frontend
NEXT_PUBLIC_USE_REAL_API=true npm run dev
```

前端默认地址 `http://localhost:3000`。`next.config.ts` 已将 `/api/*` rewrite 到 `http://localhost:8000/api/*`。

## 数据源

后端使用 [akshare](https://www.akshare.xyz/) 获取国内公开基金数据，主要包括：

- `fund_name_em`：基金名称与类型列表
- `fund_individual_basic_info_xq`：基金基本信息（成立时间、规模、基金经理等）
- `fund_open_fund_info_em`：场外基金历史净值
- `fund_etf_hist_em`：场内 ETF 历史行情
- `fund_open_fund_rank_em` / `fund_exchange_rank_em`：开放式基金与 ETF 收益排名
- `stock_zh_index_spot_sina`：A 股主要指数行情

## 环境变量

| 变量 | 说明 | 默认值 |
|---|---|---|
| `NEXT_PUBLIC_USE_REAL_API` | 前端是否调用后端真实 API | `false` |
| `NEXT_PUBLIC_API_URL` | 前端 API 基础地址 | `""`（使用 Next.js rewrite） |

## 主要 API

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/funds?q={query}&limit={limit}` | 基金列表 / 搜索 |
| GET | `/api/funds/rankings?limit={limit}` | 近一年收益排行 |
| GET | `/api/funds/popular?limit={limit}` | 热门基金 |
| GET | `/api/funds/{code}` | 基金详情 |
| GET | `/api/funds/{code}/nav-history?period={1M\|3M\|6M\|1Y\|3Y}` | 净值历史 |
| GET | `/api/market/kline?code={code}&period={1M\|3M\|6M\|1Y\|3Y}` | K 线数据 |
| GET | `/api/market/indices` | 市场指数 |
| GET | `/api/market/status` | 市场状态 |
| GET | `/api/analysis/drawdown/{code}?period=...` | 历史回撤 |
| GET | `/api/analysis/peers/{code}` | 同类基金对比 |
| GET | `/api/analysis/ranking/{code}` | 收益排名 |
| GET | `/api/analysis/portfolio` | 组合概览 |
| GET | `/api/portfolio/insights?period=1W\|1M\|3M\|1Y\|ALL` | 组合洞察（收益解释、集中度、指数对比、历史变化） |
| GET | `/api/analysis/flow/{code}` | 资金流向（模拟） |
| GET | `/api/analysis/ai/{code}` | AI 解读（模拟） |

## 缓存策略

后端对基金列表、排名、净值历史等数据使用内存 TTL 缓存（默认 5 分钟，列表 30 分钟），降低对 akshare/东方财富接口的调用频率。

## 注意事项

- 基金净值通常为 T-1 或收盘后更新，"实时"主要指行情/估值类数据。
- akshare 依赖东方财富、天天基金等公开接口，可能因网络、反爬策略波动；后端在接口失败时会回退到默认数据，前端在 API 失败时会回退到 mock。
- 首次加载基金全量列表可能需要 10-20 秒，后续请求从缓存读取会快很多。


## Phase 2 验收

从仓库根目录安装开发依赖并运行后端完整测试：

```powershell
.\.venv\Scripts\python.exe -m pip install -r backend/requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
```

前端检查在 `frontend` 目录运行：

```powershell
npm.cmd run lint
npx.cmd tsc --noEmit
npm.cmd run build
```

pytest 自动使用临时 SQLite 数据库，不使用本地持仓库。运行服务时可用
`FUND_ANALYZER_DB_PATH` 指定数据库文件，默认仍为 `backend/database/portfolio.db`。
数据库、SQLite WAL/SHM、日志与测试缓存不纳入 Git。

收益归因按当前持有份额和最近两次可用净值计算，按基金代码合并多笔持仓，
组合收益等于展示的各基金贡献之和。行情缺失时保留估值并标记待更新，收益
汇总只含可用行情。复盘配置比例使用持仓市值，不能用当日收益计算。
此口径未覆盖日内买卖现金流、已卖出持仓和分红，因此不是完整账户收益核算。
场外基金与 ETF 的数据日期可能不同，外部行情实时性需要单独在线验收。
