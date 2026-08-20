import os
import json
from typing import Dict, Any

DEFAULT_CONFIG_TEMPLATE = """# 多平台便签导出配置
# 运行前请根据需要填入对应平台的 Cookie 或凭据
# 获取 Cookie 方法详见 README.md

output_dir: "./export_output"

# 1. 小米便签 (i.mi.com)
xiaomi:
  # 登录 i.mi.com 后在浏览器控制台 (F12) -> Application -> Cookies 中获取
  cookie: ""
  # 或者填写 serviceToken 与 userId
  service_token: ""
  user_id: ""

# 2. OPPO 便签 (cloud.heytap.com)
oppo:
  # 登录 cloud.heytap.com 后获取 Cookie
  cookie: ""
  # 或指定本地已导出的文件夹路径 (HTML/TXT)
  export_path: ""

# 3. vivo 便签 (yun.vivo.com)
vivo:
  # 登录 yun.vivo.com 后获取 Cookie
  cookie: ""
  # 或指定本地已导出的文件夹路径
  export_path: ""

# 4. Apple 备忘录 (iCloud)
apple:
  apple_id: ""
  password: ""
  # 或指定本地导出的 Notes 文件夹路径
  export_path: ""

# 5. Google Keep
google:
  # Google 账号及应用专用密码 (App Password)
  username: ""
  password: ""
  # 或 Google Takeout 解压出来的 JSON 文件夹路径 (推荐，无需输密码)
  takeout_path: ""
"""


def load_config(config_path: str = "config.yaml") -> Dict[str, Any]:
    """Loads configuration from YAML or JSON file."""
    if not os.path.exists(config_path):
        # Check if config.json exists
        json_path = os.path.splitext(config_path)[0] + ".json"
        if os.path.exists(json_path):
            with open(json_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    # Try PyYAML if installed
    try:
        import yaml
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            return data or {}
    except ImportError:
        pass

    # Simple fallback parser for basic key: value lines
    data: Dict[str, Any] = {}
    current_section = None

    with open(config_path, "r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if not raw_line.startswith(" ") and not raw_line.startswith("\t") and line.endswith(":"):
                current_section = line[:-1].strip()
                data[current_section] = {}
            elif ":" in line:
                k, v = line.split(":", 1)
                k = k.strip()
                v = v.strip().strip('"').strip("'")
                if current_section:
                    data[current_section][k] = v
                else:
                    data[k] = v

    return data


def create_default_config_if_missing(config_path: str = "config.yaml"):
    """Generates default config.yaml if it does not exist or is empty."""
    if not os.path.exists(config_path) or os.path.getsize(config_path) == 0:
        with open(config_path, "w", encoding="utf-8") as f:
            f.write(DEFAULT_CONFIG_TEMPLATE)
