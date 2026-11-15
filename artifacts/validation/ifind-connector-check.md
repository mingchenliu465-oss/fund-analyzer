# iFinD 连接器实测记录

- 实测时间：2026-11-15（响应时间戳：2026-11-15T19:57:28.753017+08:00）
- 连接器 API：`ifind_get_price`
- 请求参数：`ticker=000300.SH,510300.SH`、`start_date=2026-11-02`、`end_date=2026-11-13`、`interval=D`、`adjust=none`、`format=json`
- 结果：HTTP 200；返回 20 行，沪深300与 510300ETF 各 10 个真实交易日。
- 返回字段：`open, high, low, close, volume, thscode, time, thsname_cn, thsname_en, currency`。
- 原始数据：`ifind-connector-prices.csv`。
- 凭据：未写入项目、前端、日志或本证据文件。

## 边界

这次成功只证明当前会话连接器能够返回上述指数与 ETF 行情，不证明 FundAnalyzer 后端已经独立完成正式 iFinD 接入，也不证明当前连接器支持基金累计净值、分红或复权数据。项目运行时的 Provider 状态以 `GET /api/providers/status` 为准；没有服务端开关、凭据和经官方文档验证的传输实现时，状态必须为 `blocked`，并披露实际降级来源。
