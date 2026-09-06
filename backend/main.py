from contextlib import asynccontextmanager

# ── 在所有 import 之前：网络兼容性补丁 ──
import os
import socket
import urllib.request

os.environ.setdefault("TQDM_DISABLE", "1")
os.environ["no_proxy"] = "*"

# 1) 绕过 Windows 系统代理（若代理不可用会导致 akshare/requests 请求失败）
_original_getproxies = urllib.request.getproxies
def _getproxies_no_system():
    return {}
urllib.request.getproxies = _getproxies_no_system

# 2) 强制 IPv4（部分网络 IPv6 不稳定导致东方财富远程断开）
_original_getaddrinfo = socket.getaddrinfo
def _getaddrinfo_ipv4(host, port, family=0, *args, **kwargs):
    return _original_getaddrinfo(host, port, socket.AF_INET, *args, **kwargs)
socket.getaddrinfo = _getaddrinfo_ipv4

try:
    from tqdm import tqdm
    tqdm.pandas(disable=True)
except Exception:
    pass

from concurrent.futures import ThreadPoolExecutor

import logging
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

from api import analysis, fund, market, portfolio, review
from services import fund_service

# 用于后台预热缓存的线程池
_warmup_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="warmup-")


def _warmup_caches() -> None:
    """空闲片刻后只预热基金列表，避免和首页请求争抢资源。"""
    time.sleep(2)
    try:
        fund_service.list_all()
    except Exception as exc:
        print(f"Warmup fund list failed: {exc}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup: 后台预热缓存，应用本身可立即接收请求
    _warmup_executor.submit(_warmup_caches)
    yield
    # shutdown
    _warmup_executor.shutdown(wait=False)


app = FastAPI(
    title="Fund Analyzer API",
    description="基金分析助手后端 API",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(fund.router, prefix="/api")
app.include_router(market.router, prefix="/api")
app.include_router(analysis.router, prefix="/api")
app.include_router(portfolio.router, prefix="/api")
app.include_router(review.router, prefix="/api")


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """兜底异常处理：避免未捕获异常返回裸 500，记录日志并返回结构化错误。"""
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "服务器内部错误，请稍后重试"},
    )


@app.get("/health", tags=["system"])
def health():
    return {"status": "ok"}
