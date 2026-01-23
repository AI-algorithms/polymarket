"""
Polymarket API 客户端
支持异步请求、重试机制、速率限制
"""
import asyncio
import aiohttp
import requests
import time
from typing import Dict, List, Optional, Any
from loguru import logger
from functools import wraps
from dataclasses import dataclass
from datetime import datetime, timedelta
import hashlib
import json


@dataclass
class RateLimiter:
    """速率限制器"""
    requests_per_second: float = 5.0
    last_request_time: float = 0.0
    
    def wait(self):
        current = time.time()
        elapsed = current - self.last_request_time
        min_interval = 1.0 / self.requests_per_second
        
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
        
        self.last_request_time = time.time()
    
    async def async_wait(self):
        current = time.time()
        elapsed = current - self.last_request_time
        min_interval = 1.0 / self.requests_per_second
        
        if elapsed < min_interval:
            await asyncio.sleep(min_interval - elapsed)
        
        self.last_request_time = time.time()


@dataclass
class CacheEntry:
    """缓存条目"""
    data: Any
    timestamp: datetime
    ttl: timedelta


class ResponseCache:
    """响应缓存"""
    
    def __init__(self, default_ttl: int = 60):
        self.cache: Dict[str, CacheEntry] = {}
        self.default_ttl = timedelta(seconds=default_ttl)
    
    def _make_key(self, url: str, params: Optional[Dict] = None) -> str:
        key_data = f"{url}:{json.dumps(params or {}, sort_keys=True)}"
        return hashlib.md5(key_data.encode()).hexdigest()
    
    def get(self, url: str, params: Optional[Dict] = None) -> Optional[Any]:
        key = self._make_key(url, params)
        entry = self.cache.get(key)
        
        if entry is None:
            return None
        
        if datetime.now() - entry.timestamp > entry.ttl:
            del self.cache[key]
            return None
        
        return entry.data
    
    def set(self, url: str, params: Optional[Dict], data: Any, ttl: Optional[int] = None):
        key = self._make_key(url, params)
        self.cache[key] = CacheEntry(
            data=data,
            timestamp=datetime.now(),
            ttl=timedelta(seconds=ttl) if ttl else self.default_ttl,
        )
    
    def clear(self):
        self.cache.clear()


def retry(max_attempts: int = 3, delay: float = 1.0, backoff: float = 2.0):
    """重试装饰器"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        sleep_time = delay * (backoff ** attempt)
                        logger.warning(f"请求失败，{sleep_time:.1f}s 后重试 ({attempt + 1}/{max_attempts}): {e}")
                        time.sleep(sleep_time)
            raise last_exception
        return wrapper
    return decorator


def async_retry(max_attempts: int = 3, delay: float = 1.0, backoff: float = 2.0):
    """异步重试装饰器"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        sleep_time = delay * (backoff ** attempt)
                        logger.warning(f"请求失败，{sleep_time:.1f}s 后重试 ({attempt + 1}/{max_attempts}): {e}")
                        await asyncio.sleep(sleep_time)
            raise last_exception
        return wrapper
    return decorator


class PolymarketClient:
    """Polymarket API 客户端"""

    def __init__(
        self,
        requests_per_second: float = 5.0,
        cache_ttl: int = 60,
        timeout: int = 30,
    ):
        self.data_api_base = "https://data-api.polymarket.com"
        self.clob_api_base = "https://clob.polymarket.com"
        self.gamma_api_base = "https://gamma-api.polymarket.com"
        
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "PolymarketQuantBot/1.0",
            "Accept": "application/json",
        })
        
        self.rate_limiter = RateLimiter(requests_per_second=requests_per_second)
        self.cache = ResponseCache(default_ttl=cache_ttl)
        self.timeout = timeout
        
        self._async_session: Optional[aiohttp.ClientSession] = None

    async def _get_async_session(self) -> aiohttp.ClientSession:
        if self._async_session is None or self._async_session.closed:
            self._async_session = aiohttp.ClientSession(
                headers={
                    "User-Agent": "PolymarketQuantBot/1.0",
                    "Accept": "application/json",
                },
                timeout=aiohttp.ClientTimeout(total=self.timeout),
            )
        return self._async_session

    async def close(self):
        if self._async_session and not self._async_session.closed:
            await self._async_session.close()

    @retry(max_attempts=3)
    def _get(self, url: str, params: Optional[Dict] = None, use_cache: bool = True) -> Any:
        if use_cache:
            cached = self.cache.get(url, params)
            if cached is not None:
                logger.debug(f"Cache hit: {url}")
                return cached
        
        self.rate_limiter.wait()
        
        response = self.session.get(url, params=params, timeout=self.timeout)
        response.raise_for_status()
        data = response.json()
        
        if use_cache:
            self.cache.set(url, params, data)
        
        return data

    @async_retry(max_attempts=3)
    async def _async_get(self, url: str, params: Optional[Dict] = None, use_cache: bool = True) -> Any:
        if use_cache:
            cached = self.cache.get(url, params)
            if cached is not None:
                logger.debug(f"Cache hit: {url}")
                return cached
        
        await self.rate_limiter.async_wait()
        
        session = await self._get_async_session()
        async with session.get(url, params=params) as response:
            response.raise_for_status()
            data = await response.json()
        
        if use_cache:
            self.cache.set(url, params, data)
        
        return data

    def get_user_positions(self, address: str) -> List[Dict]:
        url = f"{self.data_api_base}/positions"
        params = {"user": address}
        try:
            return self._get(url, params)
        except Exception as e:
            logger.error(f"获取用户持仓失败: {e}")
            return []

    async def async_get_user_positions(self, address: str) -> List[Dict]:
        url = f"{self.data_api_base}/positions"
        params = {"user": address}
        try:
            return await self._async_get(url, params)
        except Exception as e:
            logger.error(f"获取用户持仓失败: {e}")
            return []

    def get_user_trades(self, address: str, limit: int = 100) -> List[Dict]:
        url = f"{self.clob_api_base}/trades"
        params = {"maker": address, "limit": limit}
        try:
            return self._get(url, params)
        except Exception as e:
            logger.error(f"获取用户交易历史失败: {e}")
            return []

    async def async_get_user_trades(self, address: str, limit: int = 100) -> List[Dict]:
        url = f"{self.clob_api_base}/trades"
        params = {"maker": address, "limit": limit}
        try:
            return await self._async_get(url, params)
        except Exception as e:
            logger.error(f"获取用户交易历史失败: {e}")
            return []

    def get_markets(self, limit: int = 100, active: bool = True) -> List[Dict]:
        url = f"{self.gamma_api_base}/markets"
        params = {"limit": limit, "active": active}
        try:
            return self._get(url, params)
        except Exception as e:
            logger.error(f"获取市场列表失败: {e}")
            return []

    async def async_get_markets(self, limit: int = 100, active: bool = True) -> List[Dict]:
        url = f"{self.gamma_api_base}/markets"
        params = {"limit": limit, "active": active}
        try:
            return await self._async_get(url, params)
        except Exception as e:
            logger.error(f"获取市场列表失败: {e}")
            return []

    def get_market_trades(self, market_id: str, limit: int = 100) -> List[Dict]:
        url = f"{self.clob_api_base}/trades"
        params = {"market": market_id, "limit": limit}
        try:
            return self._get(url, params)
        except Exception as e:
            logger.error(f"获取市场交易历史失败: {e}")
            return []

    def get_market_info(self, market_id: str) -> Optional[Dict]:
        url = f"{self.gamma_api_base}/markets/{market_id}"
        try:
            return self._get(url)
        except Exception as e:
            logger.error(f"获取市场信息失败: {e}")
            return None

    def get_orderbook(self, market_id: str) -> Optional[Dict]:
        url = f"{self.clob_api_base}/book"
        params = {"token_id": market_id}
        try:
            return self._get(url, params, use_cache=False)
        except Exception as e:
            logger.error(f"获取订单簿失败: {e}")
            return None

    def get_market_volume(self, market_id: str) -> float:
        info = self.get_market_info(market_id)
        if info:
            return float(info.get("volume", 0))
        return 0.0

    async def batch_get_user_data(self, addresses: List[str]) -> List[Dict]:
        async def fetch_one(address: str) -> Dict:
            trades, positions = await asyncio.gather(
                self.async_get_user_trades(address, limit=500),
                self.async_get_user_positions(address),
            )
            return {
                "address": address,
                "trades": trades,
                "positions": positions,
            }
        
        tasks = [fetch_one(addr) for addr in addresses]
        return await asyncio.gather(*tasks)

    def get_leaderboard(self, limit: int = 100) -> List[Dict]:
        url = f"{self.data_api_base}/leaderboard"
        params = {"limit": limit}
        try:
            return self._get(url, params)
        except Exception as e:
            logger.error(f"获取排行榜失败: {e}")
            return []

    def search_markets(self, query: str, limit: int = 50) -> List[Dict]:
        url = f"{self.gamma_api_base}/markets"
        params = {"_q": query, "limit": limit, "active": True}
        try:
            return self._get(url, params)
        except Exception as e:
            logger.error(f"搜索市场失败: {e}")
            return []

    def get_user_history(
        self,
        address: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> List[Dict]:
        all_trades = []
        offset = 0
        batch_size = 500
        
        while True:
            url = f"{self.clob_api_base}/trades"
            params = {
                "maker": address,
                "limit": batch_size,
                "offset": offset,
            }
            
            if start_time:
                params["start_ts"] = int(start_time.timestamp())
            if end_time:
                params["end_ts"] = int(end_time.timestamp())
            
            try:
                trades = self._get(url, params, use_cache=False)
                if not trades:
                    break
                
                all_trades.extend(trades)
                offset += batch_size
                
                if len(trades) < batch_size:
                    break
                    
            except Exception as e:
                logger.error(f"获取用户历史失败: {e}")
                break
        
        return all_trades

    def health_check(self) -> Dict[str, bool]:
        results = {}
        
        endpoints = [
            ("data_api", f"{self.data_api_base}/positions?user=0x0"),
            ("clob_api", f"{self.clob_api_base}/trades?limit=1"),
            ("gamma_api", f"{self.gamma_api_base}/markets?limit=1"),
        ]
        
        for name, url in endpoints:
            try:
                response = self.session.get(url, timeout=5)
                results[name] = response.status_code in [200, 404]
            except Exception:
                results[name] = False
        
        return results
