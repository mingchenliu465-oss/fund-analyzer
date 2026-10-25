# Fund Analyzer 交接文档

> ⚠️ **本文档为 2026-09-25 的交接快照，部分内容已过期**（如文中提到的
> TypeScript 错误、未提交改动、时间依赖测试等问题此后均已处理或变化）。
> 项目最新状态以 `README.md` 和 git 提交历史为准，本文档仅保留作历史参考，
> 不要按其中的"未决问题/建议下一步"直接施工。

> 交接时间：2026-09-25
> 交接人：DeepSeek Harness（前一任 AI 施工方）
> 接任方：Codex
> 用户：mingchenliu465（**不编程，无法审阅代码**，见 §9）

---

## 0. 一句话现状

**后端已修好且经过真实数据验证；前端欠一次"空值语义"的债，尚未在真实浏览器里验证过。**
项目没有变差，但当前处于"后端已诚实、前端还没跟上"的中间状态。

---

## 1. 项目定位与技术栈

基金分析助手。本地个人工具，非商业产品。

```
backend/    FastAPI + akshare + SQLite（持仓/快照）
frontend/   Next.js 16 (Turbopack) + React Query + recharts + Tailwind
```

- 后端入口 `backend/main.py`，API 前缀 `/api`
- 前端 `frontend`，`next.config.ts` 把 `/api/*` rewrite 到 `localhost:8000`
- **数据源唯一**：akshare（东方财富 / 新浪 / 天天基金）

---

## 2. Git 状态（首要须知）

```
分支:  phase2-backend   （跟踪 origin/phase2-backend）
HEAD:  d2b4809  fix(data): 修复 P0-1~P0-4 金融数据真实性、P0-6 数据新鲜度
本地领先远程 7 个提交，从未 push
```

**11 个修改文件 + 5 个新测试文件尚未提交**（都是后一任的成果）：

```
 M backend/services/analysis_service.py
 M backend/services/fund_service.py
 M backend/services/market_service.py
 M frontend/app/fund/[id]/page.tsx
 M frontend/app/fund/page.tsx
 M frontend/app/page.tsx
 M frontend/app/portfolio/page.tsx
 M frontend/components/fund-rankings.tsx
 M frontend/components/portfolio-overview.tsx
 M frontend/components/recent-watched.tsx
 M frontend/services/fund.ts
?? backend/tests/test_commentary.py
?? backend/tests/test_data_availability.py
?? backend/tests/test_hot_paths.py
?? backend/tests/test_market_indices.py
?? backend/tests/test_market_status.py
?? .tmp-pytest-base/        ← 测试临时目录（内含 SQLite），不要提交
```

**建议 Codex 第一件事**：先看清 `git diff`，确认理解每一处改动，再决定是否提交。用户不懂代码，所以他依赖"提交"作为还原点。

**未提交改动量**：11 files changed, 259 insertions(+), 112 deletions(-)

---

## 3. 测试状态

### 运行方式（**必须加 `--basetemp`**）

```powershell
.\.venv\Scripts\python.exe -m pytest -q --basetemp=.tmp-pytest-base
```

不加 `--basetemp` 会产生 5 个 **PermissionError** —— 这台机器上 `%TEMP%\pytest-of-liulei` 无写权限。**这是环境问题，不是代码问题，不要去"修"。**

### 当前结果

```
262 passed, 1 failed, 3 subtests passed
```

### ❌ 唯一的失败是一个"定时炸弹"测试（前一任的责任）

```
FAILED backend/tests/test_nav_freshness.py::test_case_f_fresh_nav_is_used_for_current_valuation
  assert None == 1.25
```

**根因**：该测试把日期硬编码成 `FRIDAY = date(2026, 9, 18)`，调用 `_getportfolio_nav_fallback()` 时**没有注入 `today`**，于是用真实系统日期去比。系统日期已推进到 **2026-09-25**，两者差 5 个交易日 → 新鲜度判为 `stale` → 函数返回 `None` → 断言失败。

**这不是代码回归，是测试写得不对**（时间依赖）。2026-09-18 之后它会永久失败。

**最小修法**（一行）：给该测试注入固定日期，与同文件其他测试保持一致：

```python
def test_case_f_fresh_nav_is_used_for_current_valuation(calendar):
    with patch.object(portfolio_service, "_get_holding_nav", return_value=(1.25, FRIDAY.isoformat())), \
         patch.object(fund_service, "latest_trading_day", return_value=FRIDAY):
        nav, nav_date, stale = portfolio_service._getportfolio_nav_fallback("000001")
    assert nav == 1.25
```

**同类问题排查结论**：全测试目录扫过，**只有这 1 个**测试存在时间依赖。其余要么显式注入 `today=`，要么 patch 了 `is_current_nav`。修完即可恢复 263 passed。

---

## 4. 前端状态

### ❌ 1 个 TypeScript 错误（前一任上一轮引入）

```
components/portfolio-overview.tsx(18,43): error TS18047: 'data.cumulativeReturn' is possibly 'null'
```

**根因**：上一任加了 `const hasCumulative = data.cumulativeReturn != null;`，但 TS **不能通过布尔变量收窄**，所以下一行的 `data.cumulativeReturn >= 0` 仍报错。

**最小修法**：把判断内联，不要走中间变量：
```tsx
const isCumulativeUp = data.cumulativeReturn != null && data.cumulativeReturn >= 0;
```
（同时删掉 `hasCumulative`，第 37 行的 `trend` 里改用 `data.cumulativeReturn == null` 内联判断。）

### `npm run build` 的状态

- 修掉上面这 1 个错误后，`tsc --noEmit` 会归零，`next build` 的 TS 检查即可通过
- **`npm run dev` 不受影响**（dev 不做类型检查），所以之前一直能用
- **`npm run lint` 通过**

### `/fund/[id]` 的运行时崩溃 —— 根因（重要）

**症状**：页面显示 `This page couldn't load`，整页渲染中断。

**根因是一个"类型说谎"**：

| 层 | 声明 | 运行时实际 |
|---|---|---|
| 后端 Pydantic | `manager_days: int \| None = None` | 序列化成 **`null`** |
| 前端 TS | `managerDays?: number` | 意为 `number \| undefined` |

于是旧代码 `managerDays !== undefined ? managerDays.toLocaleString() : ""` **通过了类型检查**，运行时却拿到 `null` → `null.toLocaleString()` → 抛异常 → 整页崩溃。

**对每只基金都会触发**（后端 `manager_days` 恒为 `null`）。

**已改为**（`frontend/app/fund/[id]/page.tsx:344`）：
```tsx
typeof managerDays === "number"
  ? `${fund.manager} · 从业 ${managerDays.toLocaleString()} 天`
  : fund.manager
```

⚠️ **但尚未在真实浏览器验证过**。这是接任方要做的第一件事。

### 同类隐患（同类"类型说谎"，尚未全修）

| 后端字段 | 后端 | 前端 TS | 实际 |
|---|---|---|---|
| `TopHolding.change_pct` | `float \| None` | `changePct: number` | **null** |
| `KlinePoint.volume` | `float \| None` | `volume?: number` | **null** |
| `FundSummary.nav_date/nav_status` | P0-6 新增 | **前端类型里根本没有** | — |

**规律**：凡是后端 `None`、前端写成 `?:` 或非 nullable 的字段，都会犯同一个错。

---

## 5. 已完成的工作（按轮次）

### 第一轮：P0-1 ~ P0-6（**已提交** `d2b4809`）

| 编号 | 修了什么 | 关键证据 |
|---|---|---|
| P0-1 | **收益基准改用累计净值** | 161725 用单位净值算 −47.17%，用累计净值是 **+124.44%**；MDD −69.88% → **−36.01%**。000001 差 257pp、519066 差 133pp，而 110022 **差 0** —— 所以抽查发现不了 |
| P0-2 | **ETF/LOF/场外语义分离** | 代码前缀法命中 2473 只，真实场内 ETF 只有 **1660** 只（33% 误判）。519066（场外）以 51 开头、162411/160632/161725（LOF）以 16 开头，全被误判为 ETF |
| P0-3 | **持仓/行业锁定单一报告期** | `fund_portfolio_hold_em(date="")` 返回多期且**顺序不是最新在前**：`iloc[0]` 取到 1 季度（中际旭创 4.31%），最新是 2 季度（6.45%）。行业配置跨期相加：制造业 72.78+61.14=133.92，再缩放成 87.8% |
| P0-4 | **删掉硬编码风险评分** | `risk_score` 一律 `null`（无输入指标/权重/阈值依据）；`risk_level` 只由真实年化波动率推导；`investment_style` 不再按基金类型猜 |
| P0-6 | **建立 freshness 状态机** | 5 态 `fresh/stale/inactive/unavailable/unknown`，基于真实交易日历 |

### 第二轮：9 个 bug（**未提交**，即 §2 的改动）

| # | 修了什么 | 关键证据 |
|---|---|---|
| 1 | `commentary` 空值崩溃 | `/api/analysis/ai/{code}` 对历史不足一年的基金返回 **500**。真实标的 560160（242 天）、159253（295 天）复现 |
| 2 | ETF 名录并发超时 → 空名录 | 每次冷启动 3/3 在 **30.04s** 被掐断，缓存空名录 600s → K 线消失、类型标成"股票型" |
| 3 | `nav_data_status` 是 O(n) 热路径 | 单次 **1770µs** → 逐行 27,879 次 = 49.3s。改 bisect 后 **12.2µs**，冷启动 55.3s → 27.9s |
| 4 | 删掉编造的同类比较 | "显著跑赢同类平均"—— 该函数从未取过任何同业数据 |
| 5 | 市场状态接入真实日历 | 原实现周六 10:00 返回 **"交易中"** |
| 6 | 指数行情缺数据 → 跳过 | 原实现缺值回退 0.0 → 显示 **0.00 点位 / "涨 0.00%" / 上涨箭头** |
| 7 | 抓取失败负缓存 24 小时 | 一次网络抖动让该基金重仓/行业空一整天。改为异常路径 5 分钟 |
| 8 | `hold_structure` 列映射缺失 → 0% | "取不到机构持有比例"显示成"机构持有 0%" |
| 9 | 前端 `?? 0` | 缺失显示成绿色 "+0.00%" + 上涨箭头 |

---

## 6. ⭐ 实测得到的数据源知识（最值钱的部分，不要重新踩）

以下全部是**实测**结论（akshare 1.18.94），不是推测：

### 6.1 净值接口

- `ak.fund_open_fund_info_em(symbol, indicator, period="成立来")`
  - `indicator="单位净值走势"` → 列：净值日期 / 单位净值 / 日增长率
  - `indicator="累计净值走势"` → 列：净值日期 / 累计净值
  - **收益、波动率、最大回撤必须用累计净值**；单位净值在除息日下跌，会把"分红"算成"亏损"
  - ETF 同样可用（510300 与 `fund_etf_fund_info_em` 的序列**逐行一致**，各 3497 行）
- **货币基金取不到**：`000198` 等返回 `ReferenceError: Data_netWorthTrend is not defined`（它们用"每万份收益"）。这是正常的，不是 bug。

### 6.2 ETF 名录

- `ak.fund_etf_fund_daily_em()` → **1660 行**，是"是不是场内 ETF"的**唯一可靠真源**
  - `类型` 全部是 `指数型-*`
  - **所有列都是字符串**，且净值列名带日期前缀：`2026-09-18-单位净值`、`2026-09-18-累计净值`
  - `市价` 是字符串 `'4.5820'`；`折价率` 是 `'-0.06%'`（**带百分号，直接 float() 会失败**）
  - 同时提供 **NAV / market price / 折价率** 三个分离字段
- **`fund_name_em` 的 `基金类型` 无法区分 ETF 与 LOF**：159915（真 ETF）、161725、160632（都是 LOF）在它里面**同为 `指数型-股票`**
- **代码前缀不可用**：`51/56/58/15/16` 命中 2473 只，真实只有 1660 只

### 6.3 ⚠️ 东财接口并发会互相拖慢（最重要的性能陷阱）

实测（三个同源东财接口）：

| | 并发（3 线程） | 串行 |
|---|---|---|
| `fund_name_em` | 19.85s | 12.33s |
| `fund_open_fund_rank_em` | 16.81s | 7.62s |
| `fund_etf_fund_daily_em` | **20.58s（单独只要 1.55s，慢 13 倍）** | 1.55s |
| 合计 | 20.6s | 21.5s |

**结论：并发没有收益，只有伤害。** 把第三个同源请求放进线程池会导致它被拖到超时。
`_load_fund_list()` 现在只保留 2 路并发，ETF 名录在之后单独取。

### 6.4 持仓与行业

- `ak.fund_portfolio_hold_em(symbol, date="")` → **返回最新年度内所有季度**，且**行序不保证最新在前**（实测 `iloc[0]` 是 `2026年1季度`，最新是 `2026年2季度`）
  - 季报只披露**前十大**；半年报/年报披露**全部持仓**（实测 000001 的 2 季度有 77 行）
- `ak.fund_portfolio_industry_allocation_em(symbol, date="")` → **同时返回多个 `截止时间`**（实测 2026-06-30 与 2026-03-31）
- `ak.tool_trade_date_hist_sina()` → **8797 行**，`datetime.date` 对象，覆盖到 2026-12-31

### 6.5 超时与稳定性

- `fund_open_fund_info_em` 单次 **0.25–0.33s**（正常），但曾观测到 **1.33s**（占 3s 默认超时的 44%）
- `_AKSHARE_TIMEOUT = 3` 是全局默认，对净值调用偏紧（**但未能稳定复现失败，故未改**）
- **冷启动 28–45 秒**：主要是 `fund_name_em`（12–21s）+ 排行榜（7–16s）
- ⚠️ **数据源会整体间歇性失败**：实测同一进程内 `_load_fund_list()` 曾返回 0，重跑即恢复正常。用户会看到"这次能打开、下次说数据不可用"。**这是用户困惑的重要来源，不是代码确定性损坏。**

---

## 7. 真实数据基线（回归对照用）

重建或修改后，这三个数字必须保持一致：

| 标的 | 类型 | 单位净值 | 累计净值 | as_of | freshness | 关键指标 |
|---|---|---|---|---|---|---|
| **110022** 易方达消费行业 | 场外股票型 | 2.811 | — | 2026-09-18 | fresh | vol 0.2251 / MDD −0.5732 / sharpe 0.32 / 近一年 −24.01% |
| **510300** 沪深300ETF | **ETF** | 4.5793 | 2.0251 | 2026-09-18 | fresh | 市价 **4.582**（与 NAV 分离）/ K线 **3481** 点 / vol 0.1977 |
| **161725** 招商中证白酒 | **LOF（非 ETF）** | 0.5283 | 2.2444 | 2026-09-18 | fresh | 累计口径总收益 **+124.44%**（单位净值口径 −47.17%）/ K线 **0** 点（不伪造 OHLC） |

其他可用基准：
- `000001` 持仓 as_of = `2026年2季度股票投资明细`，中际旭创 6.45%；行业 as_of = `2026-06-30`，制造业 72.78%，**合计 79.98%（未归一化到 100%）**
- `150153`（已退市分级基金）：最后数据 2020-12-31，状态 **inactive**，不在当前基金列表
- 市场状态：周六/周日 → **休市**（不是"交易中"）

---

## 8. 前一任犯过的错（请不要重复）

| 错误 | 后果 | 教训 |
|---|---|---|
| 往热路径里加调用却没测性能 | 冷启动 22s → **55s** | 逐行调用的函数必须 O(log n) |
| 把 3 个同源接口放进线程池 | ETF 名录每次冷启动超时 | 见 §6.3 |
| 写时间依赖的测试 | 系统日期一推进就永久失败 | 日期必须注入，不能用 `now()` |
| 为修数据语义改后端 nullable，但**没检查前端** | 前端出现一批"新"bug（实为既有错误假设暴露） | 改契约必须同步查前端 |
| 多轮从未运行前端检查 | `npm run build` 其实一直是坏的 | 至少要跑 `tsc --noEmit` |
| 每轮继续审计、从未定义结束点 | 清单无限变长，用户感觉"越修越多" | 先定义"到什么程度算够" |

---

## 9. ⚠️ 用户情况与协作约束（务必读）

**用户不编程，无法审阅代码，也无法评估技术方案。**

由此产生的硬约束：

1. **不要问他技术问题**（"要不要重构"、"用哪个方案"）—— 他没法判断，只会让他困惑
2. **不要做大重构 / 大爆炸式重写** —— 如果悄悄改坏了，**没有任何人能发现**
3. **产品决策问他，技术决策自己定**
4. **要经常 `git commit`** —— 这是他的唯一还原手段。他只会说"退回上一个版本"
5. **每次改动后告诉他：打开哪个网址、应该看到什么** —— 这是他唯一能验证的方式
6. 用中文、用非技术语言解释

用户上一轮的原话（重要）：
> 「现在这个项目到底什么情况，我不知道为什么越改bug越多」

他的挫败来自：**改动不可见、验证靠他、而失败是间歇性的**。请优先恢复"确定性"。

---

## 10. 建议的下一步（按优先级）

### 第一步：让它确定能跑（建议最先做）
1. 修 `portfolio-overview.tsx` 那 1 个 TS 错误（一行，见 §4）
2. 修 `test_nav_freshness.py` 那个时间炸弹测试（见 §3）→ 恢复 263 passed
3. **实际启动前后端**，打开并验证：`/`、基金列表、`/fund/110022`、`/fund/510300`、`/fund/161725`、市场页、组合页
4. `git commit` 存档

### 第二步：把契约说谎一次性补完
前端 TS 里把**所有**后端为 `None` 的字段从 `?:` / 非 nullable 改为 `| null`（至少 `TopHolding.changePct`、`KlinePoint.volume`、以及 P0-6 新增但前端缺失的 `navDate`/`navStatus`）。

### 第三步：交付一个用户能亲眼判断的功能
例："今天我的组合为什么涨跌"—— 用户能拿手算的数字对照。

### ❌ 明确不要做
- **不要**大规模重构（前一任曾提议重建 Provider/Normalization/Validation/Domain 分层，**已判定为错误建议**：收益是代码整洁，风险是无人能发现的静默错误）
- **不要**为了清零 TS 错误而用 `?? 0` / `as number`
- **不要**动 `portfolio_service.py`、`review_service.py`（与 Fund Detail 无关）
- **不要**清理死代码（`_enrich_holding_from_map`、`_upsert_snapshot` 无调用者，但无害）
- **不要**在未做真实数据验证的情况下宣布完成

---

## 11. 未决问题

| # | 问题 | 建议 |
|---|---|---|
| 1 | 1 个 TS 错误（`portfolio-overview.tsx:18`）未修 | 一行改，见 §4 |
| 2 | 1 个时间炸弹测试未修 | 见 §3 |
| 3 | `/fund/[id]` 崩溃已修但**未在浏览器验证** | 最优先 |
| 4 | `.tmp-pytest-base/` 未被 `.gitignore` 覆盖 | 建议加进 `.gitignore`（需用户同意） |
| 5 | 本地领先远程 7 个提交，从未 push | 问用户是否要 push |
| 6 | 冷启动 28–45s | 产品决策（预热/骨架屏），非 bug |
| 7 | `portfolio_insights.py` 用 `= 0.0` 默认值（同类契约缺陷） | 属 Portfolio 切片，迁移时一并改 |
| 8 | 前端 review/portfolio 页仍有大量 `?? 0`（约 60 处） | 逐页迁移，不要一次性动 |
| 9 | `investment_style` 永久为 null（无数据源） | 需 RBSA 或持仓风格数据 |
| 10 | 数据源间歇性整体失败 | 非代码问题，需产品层兜底（提示重试） |

---

## 12. 环境备忘

```powershell
# 后端测试（必须带 --basetemp）
.\.venv\Scripts\python.exe -m pytest -q --basetemp=.tmp-pytest-base

# 启动后端
cd backend; ..\.venv\Scripts\python.exe -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# 前端
cd frontend; npm.cmd run dev      # dev 不检查类型，可用
cd frontend; npm.cmd run build    # 当前因 1 个 TS 错误失败
cd frontend; npm.cmd run lint     # 通过
cd frontend; npx.cmd tsc --noEmit # 检查类型
```

- Python 用 `.venv`（仓库根目录），akshare 1.18.94
- `.pytest_cache` 与 `%TEMP%\pytest-of-liulei` 在本机无写权限 → **必须用 `--basetemp`**
