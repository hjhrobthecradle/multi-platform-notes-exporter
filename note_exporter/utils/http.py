import json
import urllib.request
import urllib.parse
import urllib.error
import ssl
from typing import Dict, Any, Optional, Union


class SimpleHttpResponse:
    def __init__(self, status_code: int, headers: Dict[str, str], body: bytes):
        self.status_code = status_code
        self.headers = headers
        self.body = body

    @property
    def text(self) -> str:
        return self.body.decode("utf-8", errors="replace")

    def json(self) -> Any:
        return json.loads(self.text)


class SimpleHttpSession:
    """Lightweight HTTP session supporting cookies, headers, JSON serialization."""

    def __init__(self, user_agent: Optional[str] = None):
        self.cookies: Dict[str, str] = {}
        self.headers: Dict[str, str] = {
            "User-Agent": user_agent or "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }

    def set_cookie_string(self, cookie_str: str):
        """Parse raw Cookie string like 'key1=val1; key2=val2' into dict."""
        if not cookie_str:
            return
        parts = cookie_str.split(";")
        for part in parts:
            if "=" in part:
                k, v = part.strip().split("=", 1)
                self.cookies[k.strip()] = v.strip()

    def get_cookie_string(self) -> str:
        return "; ".join([f"{k}={v}" for k, v in self.cookies.items()])

    def request(
        self,
        method: str,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Union[Dict[str, Any], str, bytes]] = None,
        json_data: Optional[Any] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: int = 15
    ) -> SimpleHttpResponse:
        if params:
            query = urllib.parse.urlencode(params)
            sep = "&" if "?" in url else "?"
            url = f"{url}{sep}{query}"

        req_headers = dict(self.headers)
        if headers:
            req_headers.update(headers)

        if self.cookies:
            req_headers["Cookie"] = self.get_cookie_string()

        encoded_data = None
        if json_data is not None:
            encoded_data = json.dumps(json_data).encode("utf-8")
            req_headers["Content-Type"] = "application/json"
        elif isinstance(data, dict):
            encoded_data = urllib.parse.urlencode(data).encode("utf-8")
            req_headers["Content-Type"] = "application/x-www-form-urlencoded; charset=UTF-8"
        elif isinstance(data, str):
            encoded_data = data.encode("utf-8")
        elif isinstance(data, bytes):
            encoded_data = data

        req = urllib.request.Request(
            url=url,
            data=encoded_data,
            headers=req_headers,
            method=method.upper()
        )

        ctx = ssl.create_default_context()
        
        try:
            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
                status_code = resp.status
                resp_headers = dict(resp.headers)
                
                set_cookies = resp.headers.get_all("Set-Cookie") or []
                for sc in set_cookies:
                    cookie_part = sc.split(";")[0]
                    if "=" in cookie_part:
                        ck, cv = cookie_part.split("=", 1)
                        self.cookies[ck.strip()] = cv.strip()

                body = resp.read()
                return SimpleHttpResponse(status_code, resp_headers, body)
        except urllib.error.HTTPError as e:
            body = e.read() if hasattr(e, "read") else b""
            return SimpleHttpResponse(e.code, dict(e.headers), body)
        except Exception as e:
            return SimpleHttpResponse(500, {}, str(e).encode("utf-8"))

    def get(self, url: str, **kwargs) -> SimpleHttpResponse:
        return self.request("GET", url, **kwargs)

    def post(self, url: str, **kwargs) -> SimpleHttpResponse:
        return self.request("POST", url, **kwargs)
