"""
OpenAI 格式文生图模块

调用 OpenAI Images API (或兼容代理) 生成图片。
支持 DALL-E 2 / DALL-E 3 及所有兼容模型。

使用方式:
    from background import generate_image

    # 最简调用
    result = generate_image("一座雪山下的湖泊", api_key="sk-xxx")
    result.save("bg.png")

    # 完整参数
    result = generate_image(
        "日落时的海滩",
        api_key="sk-xxx",
        model="dall-e-3",
        size="1792x1024",
        quality="hd",
        style="vivid",
    )

依赖:
    - requests (必选)
    - openai (可选，提供 SDK 风格调用)
    - Pillow (可选，用于 b64_json 解码为 Image)
"""

from __future__ import annotations

import base64
import io
import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Union

import requests

# ---------------------------------------------------------------------------
# 配置文件加载
# ---------------------------------------------------------------------------
_CONFIG_PATH = __import__("os").path.join(
    __import__("os").path.dirname(__file__), "config.json"
)


def load_config() -> Dict[str, Any]:
    """从 config.json 加载 image_gen 和 ui 配置。"""
    try:
        with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def get_image_gen_config() -> Dict[str, Any]:
    """获取 image_gen 配置段，作为函数的默认参数来源。"""
    cfg = load_config()
    return cfg.get("image_gen", {})


def get_ui_config() -> Dict[str, Any]:
    """获取 ui 配置段。"""
    cfg = load_config()
    return cfg.get("ui", {})

# ---------------------------------------------------------------------------
# 可选导入
# ---------------------------------------------------------------------------
try:
    from PIL import Image

    _HAS_PIL = True
except ImportError:
    _HAS_PIL = False

try:
    import openai as openai_sdk

    _HAS_OPENAI_SDK = True
except ImportError:
    _HAS_OPENAI_SDK = False

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------
DEFAULT_API_BASE = "https://api.openai.com/v1"
DALL_E_2_SIZES = ("256x256", "512x512", "1024x1024")
DALL_E_3_SIZES = ("1024x1024", "1792x1024", "1024x1792")
VALID_QUALITIES = ("standard", "hd")
VALID_STYLES = ("vivid", "natural")
VALID_RESPONSE_FORMATS = ("url", "b64_json")


# ===================================================================
# 配置
# ===================================================================
@dataclass
class ImageGenConfig:
    """文生图参数配置，全部有默认值。"""

    model: str = "dall-e-3"
    """模型名。dall-e-3, dall-e-2, 或兼容模型。"""

    size: str = "1024x1024"
    """输出尺寸。DALL-E 2: 256/512/1024; DALL-E 3: 1024x1024, 1792x1024, 1024x1792。"""

    quality: str = "standard"
    """画质。'standard' 或 'hd'（仅 DALL-E 3）。"""

    style: str = "vivid"
    """风格。'vivid'（超现实）或 'natural'（更真实）。仅 DALL-E 3。"""

    n: int = 1
    """生成张数。DALL-E 3 仅支持 n=1。"""

    response_format: str = "url"
    """返回格式。'url' 返回临时 URL，'b64_json' 返回 base64 数据。"""

    user: Optional[str] = None
    """终端用户标识，用于 OpenAI 滥用监控。"""

    # ---- 连接参数 ----
    api_key: Optional[str] = None
    """API 密钥。若为 None，尝试从 OPENAI_API_KEY 环境变量读取。"""

    api_base: str = DEFAULT_API_BASE
    """API 端点。可设为兼容代理地址。"""

    timeout: float = 120.0
    """请求超时秒数。"""

    max_retries: int = 2
    """请求失败时的最大重试次数。"""

    # ---- 本地保存 ----
    download_to: Optional[str] = None
    """若 response_format='url'，自动下载并保存到此路径。"""


# ===================================================================
# 结果
# ===================================================================
@dataclass
class ImageGenResult:
    """文生图返回结果。"""

    images: List[Image.Image] = field(default_factory=list)
    """PIL Image 对象列表（response_format='b64_json' 或已下载时）。"""

    urls: List[str] = field(default_factory=list)
    """图片 URL 列表（response_format='url' 时）。"""

    b64_strings: List[str] = field(default_factory=list)
    """Base64 字符串列表（response_format='b64_json' 时）。"""

    revised_prompt: Optional[str] = None
    """DALL-E 3 自动改写后的 prompt。"""

    raw_response: Optional[Dict[str, Any]] = None
    """API 原始响应 JSON。"""

    model: str = ""
    """实际使用的模型。"""

    usage: Dict[str, int] = field(default_factory=dict)
    """Token / 图片用量信息（若 API 返回）。"""

    def save(self, path: str, index: int = 0) -> str:
        """保存第 index 张图片到 path。"""
        if self.images and index < len(self.images):
            self.images[index].save(path)
            return path
        raise ValueError(f"没有可保存的图片（index={index}, 共 {len(self.images)} 张）")

    def save_all(self, path_pattern: str) -> List[str]:
        """保存全部图片。path_pattern 中 {} 会被替换为序号，如 'img_{}.png'。"""
        paths = []
        for i, img in enumerate(self.images):
            p = path_pattern.format(i)
            img.save(p)
            paths.append(p)
        return paths

    def first(self) -> Optional[Image.Image]:
        """返回第一张 PIL Image（快捷方式）。"""
        return self.images[0] if self.images else None


# ===================================================================
# 核心：用 requests 直接调用 OpenAI API
# ===================================================================
def _get_api_key(config: ImageGenConfig) -> str:
    """解析 API key：配置 > 环境变量。"""
    import os

    key = config.api_key or os.environ.get("OPENAI_API_KEY", "")
    if not key:
        raise ValueError(
            "未提供 API key。请通过参数 api_key= 传入，"
            "或设置环境变量 OPENAI_API_KEY。"
        )
    return key


def _build_url(config: ImageGenConfig) -> str:
    """构建完整的 API 端点 URL。"""
    base = config.api_base.rstrip("/")
    return f"{base}/images/generations"


def _build_payload(config: ImageGenConfig, prompt: str) -> Dict[str, Any]:
    """构建请求体。"""
    payload: Dict[str, Any] = {
        "model": config.model,
        "prompt": prompt,
        "n": config.n,
        "size": config.size,
        "response_format": config.response_format,
    }

    # DALL-E 3 专属参数
    if config.model.startswith("dall-e-3"):
        payload["quality"] = config.quality
        payload["style"] = config.style

    if config.user:
        payload["user"] = config.user

    return payload


def _call_api(
    config: ImageGenConfig, payload: Dict[str, Any]
) -> Dict[str, Any]:
    """发送请求到 OpenAI Images API，带重试。"""
    url = _build_url(config)
    api_key = _get_api_key(config)

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    last_error: Optional[Exception] = None

    for attempt in range(config.max_retries + 1):
        try:
            resp = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=config.timeout,
            )
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.HTTPError as e:
            # 4xx 错误不重试
            if e.response is not None and 400 <= e.response.status_code < 500:
                raise
            last_error = e
        except requests.exceptions.RequestException as e:
            last_error = e

        if attempt < config.max_retries:
            time.sleep(2 ** attempt)  # 指数退避

    raise RuntimeError(
        f"API 请求失败，已重试 {config.max_retries} 次"
    ) from last_error


def _download_url(url: str, timeout: float = 60) -> Image.Image:
    """从 URL 下载图片并返回 PIL Image。"""
    resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()
    if _HAS_PIL:
        return Image.open(io.BytesIO(resp.content))
    raise ImportError("需要 Pillow 来解码图片：pip install Pillow")


def _decode_b64(b64_str: str) -> Image.Image:
    """解码 base64 为 PIL Image。"""
    if _HAS_PIL:
        return Image.open(io.BytesIO(base64.b64decode(b64_str)))
    raise ImportError("需要 Pillow 来解码图片：pip install Pillow")


# ===================================================================
# 主函数
# ===================================================================
def generate_image(
    prompt: str,
    *,
    api_key: Optional[str] = None,
    model: str = "dall-e-3",
    size: str = "1024x1024",
    quality: str = "standard",
    style: str = "vivid",
    n: int = 1,
    response_format: str = "url",
    api_base: str = DEFAULT_API_BASE,
    timeout: float = 120.0,
    max_retries: int = 2,
    download_to: Optional[str] = None,
    user: Optional[str] = None,
    auto_download: bool = True,
) -> ImageGenResult:
    """OpenAI 格式文生图 — 主入口函数。

    Parameters
    ----------
    prompt : str
        图片描述文本（中文/英文均可）。DALL-E 3 最长 4000 字符。
    api_key : str, optional
        API 密钥。默认从 OPENAI_API_KEY 环境变量读取。
    model : str
        模型名，默认 "dall-e-3"。
    size : str
        输出尺寸。DALL-E 2: 256/512/1024; DALL-E 3: 1024x1024 / 1792x1024 / 1024x1792。
    quality : str
        "standard" 或 "hd"（仅 DALL-E 3）。
    style : str
        "vivid" 或 "natural"（仅 DALL-E 3）。
    n : int
        生成张数（DALL-E 3 仅 1）。
    response_format : str
        "url" 或 "b64_json"。
    api_base : str
        API 端点，可指向兼容代理。
    timeout : float
        超时秒数。
    max_retries : int
        最大重试次数。
    download_to : str, optional
        自动下载并保存到此路径。仅对第一张图生效。
    user : str, optional
        终端用户标识。
    auto_download : bool
        若 True 且 response_format='url'，自动下载图片到内存（存入 result.images）。

    Returns
    -------
    ImageGenResult
        包含生成的图片、URL、原始响应等。

    Examples
    --------
    # >>> # 基础调用
    # >>> result = generate_image("一只柴犬在草地上奔跑", api_key="sk-xxx")
    # >>> result.save("dog.png")
    #
    # >>> # HD 宽屏
    # >>> result = generate_image(
    # ...     "赛博朋克城市雨夜，霓虹灯倒影",
    # ...     api_key="sk-xxx",
    # ...     size="1792x1024",
    # ...     quality="hd",
    # ...     style="vivid",
    # ... )
    #
    # >>> # 使用兼容代理 (如 Azure、本地模型)
    # >>> result = generate_image(
    # ...     "a cat",
    # ...     api_key="sk-xxx",
    # ...     api_base="https://your-proxy.com/v1",
    # ...     model="sdxl-turbo",
    # ... )
    """
    # ---- 合并 config.json：json 中的值作为新默认值 ----
    _cfg = get_image_gen_config()
    # 仅当用户未显式传入时（即参数仍为函数默认值），才用 config.json 覆盖
    # 判断依据：如果 api_key 为 None 且 config.json 有值 → 用 json
    #          如果 api_base/model/size 的参数名在 json 中且用户没改 → 用 json
    _api_key = api_key or _cfg.get("api_key") or None
    _api_base = _cfg.get("api_base", api_base)
    _model = _cfg.get("model", model)
    _size = _cfg.get("size", size)

    config = ImageGenConfig(
        model=_model,
        size=_size,
        quality=quality,
        style=style,
        n=n,
        response_format=response_format,
        api_key=_api_key,
        api_base=_api_base,
        timeout=timeout,
        max_retries=max_retries,
        download_to=download_to,
        user=user,
    )

    # 构建 & 发送
    payload = _build_payload(config, prompt)
    raw = _call_api(config, payload)

    # 解析结果
    result = ImageGenResult(
        raw_response=raw,
        model=config.model,
    )

    data_list = raw.get("data", [])

    for item in data_list:
        # b64_json
        if "b64_json" in item:
            result.b64_strings.append(item["b64_json"])
            if _HAS_PIL:
                result.images.append(_decode_b64(item["b64_json"]))

        # url
        if "url" in item:
            result.urls.append(item["url"])
            if auto_download and _HAS_PIL:
                result.images.append(_download_url(item["url"], timeout=config.timeout))

        # revised_prompt (DALL-E 3)
        if "revised_prompt" in item and item["revised_prompt"]:
            result.revised_prompt = item["revised_prompt"]

    # 用量信息
    if "usage" in raw:
        result.usage = raw["usage"]

    # 如果指定 download_to，保存第一张
    if download_to and result.images:
        result.images[0].save(download_to)

    return result


# ===================================================================
# 智谱AI (z.ai / ZhipuAI / 智谱清言) 预设
# ===================================================================
# 智谱AI 提供 OpenAI 兼容的文生图 API：
#   base_url: https://open.bigmodel.cn/api/paas/v4/
#   模型: cogview-4, cogview-4-250414, cogview-3-plus, cogview-3
#   尺寸: 1024x1024, 768x1344, 1344x768, 1440x720, 720x1440
#   注意: 智谱不支持 quality/style 参数（DALL-E 专属）

ZHIPU_API_BASE = "https://open.bigmodel.cn/api/paas/v4"
ZHIPU_MODELS = ("cogview-4", "cogview-4-250414", "cogview-3-plus", "cogview-3", "cogview-3-flash")
ZHIPU_SIZES = ("1024x1024", "768x1344", "1344x768", "1440x720", "720x1440")


def generate_with_zhipu(
    prompt: str,
    *,
    api_key: Optional[str] = None,
    model: str = "cogview-4",
    size: str = "1024x1024",
    n: int = 1,
    response_format: str = "url",
    timeout: float = 120.0,
    max_retries: int = 2,
    download_to: Optional[str] = None,
    auto_download: bool = True,
    user: Optional[str] = None,
) -> ImageGenResult:
    """使用智谱AI (z.ai / ZhipuAI / 智谱清言) 文生图。

    智谱AI 提供 OpenAI 兼容接口，支持 CogView 系列模型。
    底层直接复用 generate_image()，只是预设了智谱的端点和模型。

    Parameters
    ----------
    prompt : str
        图片描述文本。
    api_key : str, optional
        智谱 API key。默认从 ZHIPU_API_KEY 或 OPENAI_API_KEY 环境变量读取。
    model : str
        模型名。cogview-4（最新）/ cogview-4-250414 / cogview-3-plus / cogview-3。
    size : str
        输出尺寸。1024x1024 / 768x1344 / 1344x768 / 1440x720 / 720x1440。
    其余参数同 generate_image()。

    Returns
    -------
    ImageGenResult

    Examples
    --------
    # >>> result = generate_with_zhipu("一只熊猫在竹林里吃竹子", api_key="xxx")
    # >>> result.save("panda.png")
    #
    # >>> # 竖屏壁纸
    # >>> result = generate_with_zhipu(
    # ...     "赛博朋克城市夜景",
    # ...     model="cogview-4",
    # ...     size="768x1344",
    # ... )
    """
    import os

    _cfg = get_image_gen_config()
    _key = (api_key or _cfg.get("api_key") or
            os.environ.get("ZHIPU_API_KEY") or os.environ.get("OPENAI_API_KEY", ""))
    if not _key:
        raise ValueError(
            "未提供智谱 API key。请在 config.json 的 image_gen.api_key 中设置，"
            "或通过 api_key= 传入，或设置环境变量 ZHIPU_API_KEY。"
        )

    return generate_image(
        prompt=prompt,
        api_key=_key,
        api_base=ZHIPU_API_BASE,
        model=model,
        size=size,
        quality="standard",  # 智谱不用此参数
        style="vivid",       # 同上
        n=n,
        response_format=response_format,
        timeout=timeout,
        max_retries=max_retries,
        download_to=download_to,
        auto_download=auto_download,
        user=user,
    )


# ===================================================================
# SDK 风格封装 (pip install openai 后可用)
# ===================================================================
def generate_with_sdk(
    prompt: str,
    *,
    api_key: Optional[str] = None,
    api_base: Optional[str] = None,
    model: str = "dall-e-3",
    size: str = "1024x1024",
    quality: str = "standard",
    style: str = "vivid",
    n: int = 1,
    response_format: str = "url",
    user: Optional[str] = None,
    auto_download: bool = True,
    timeout: float = 120.0,
) -> ImageGenResult:
    """使用 openai SDK 调用文生图（需 pip install openai）。

    功能与 generate_image() 相同，区别在于底层使用 openai 库。
    适合已安装 SDK 的项目，可以利用 SDK 的连接池、重试等能力。

    Examples
    --------
    # >>> result = generate_with_sdk("a futuristic city", api_key="sk-xxx")
    # >>> result.first().show()
    """
    if not _HAS_OPENAI_SDK:
        raise ImportError(
            "需要安装 openai SDK: pip install openai"
        )

    import os

    _key = api_key or os.environ.get("OPENAI_API_KEY", "")
    if not _key:
        raise ValueError("未提供 API key")

    client_kwargs: Dict[str, Any] = {"api_key": _key, "timeout": timeout}
    if api_base:
        client_kwargs["base_url"] = api_base

    client = openai_sdk.OpenAI(**client_kwargs)

    sdk_kwargs: Dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "n": n,
        "size": size,
        "response_format": response_format,
    }

    if model.startswith("dall-e-3"):
        sdk_kwargs["quality"] = quality
        sdk_kwargs["style"] = style

    if user:
        sdk_kwargs["user"] = user

    sdk_response = client.images.generate(**sdk_kwargs)

    # 转换为统一结果格式
    result = ImageGenResult(model=model)

    for item in sdk_response.data:
        if hasattr(item, "b64_json") and item.b64_json:
            result.b64_strings.append(item.b64_json)
            if auto_download and _HAS_PIL:
                result.images.append(_decode_b64(item.b64_json))

        if hasattr(item, "url") and item.url:
            result.urls.append(item.url)
            if auto_download and _HAS_PIL:
                result.images.append(_download_url(item.url, timeout=timeout))

        if hasattr(item, "revised_prompt") and item.revised_prompt:
            result.revised_prompt = item.revised_prompt

    return result


# ===================================================================
# 命令行入口
# ===================================================================
if __name__ == "__main__":
    import os
    import sys

    if len(sys.argv) < 2:
        print("用法: python background.py <提示词> [输出路径]")
        print()
        print("示例:")
        print('  python background.py "a mountain lake at sunset" bg.png')
        print()
        print("环境变量:")
        print("  OPENAI_API_KEY   OpenAI API 密钥（必选）")
        print("  OPENAI_API_BASE  自定义 API 端点（可选）")
        sys.exit(1)

    prompt = sys.argv[1]
    output = sys.argv[2] if len(sys.argv) > 2 else "background_output.png"

    api_key = os.environ.get("OPENAI_API_KEY", "")
    api_base = os.environ.get("OPENAI_API_BASE", DEFAULT_API_BASE)

    if not api_key:
        print("[ERROR] 未设置 OPENAI_API_KEY 环境变量")
        print("  set OPENAI_API_KEY=sk-xxxx")
        sys.exit(1)

    print(f"正在生成: {prompt}")
    print(f"模型: dall-e-3  |  端点: {api_base}")

    result = generate_image(
        prompt,
        api_key=api_key,
        api_base=api_base,
        download_to=output,
        auto_download=True,
    )

    print(f"已保存: {output}")
    if result.revised_prompt:
        print(f"改写后的 prompt: {result.revised_prompt}")
    if result.urls:
        print(f"URL: {result.urls[0]}")
    print(f"图片尺寸: {result.images[0].size if result.images else 'N/A'}")
