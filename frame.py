"""
圆角矩形 + 高斯模糊 图像处理模块

功能：给任意图片添加一个圆角矩形遮罩，矩形内部施加高斯模糊，
      外部保持原图清晰。提供丰富的自定义选项，均设有默认值。

画质提升手段：
  - SSAA 超采样 (2x / 3x / 4x)
  - 边缘抗锯齿 (feather / smoothstep)
  - LANCZOS 高质量下采样
  - 可选的 mask dither 平滑

依赖: Pillow, numpy (可选，用于高级抗锯齿)
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional, Tuple, Union

from PIL import Image, ImageDraw, ImageFilter, ImageOps

# ---------------------------------------------------------------------------
# 尝试导入 numpy（用于 smoothstep 等高级抗锯齿）；若无则回退到纯 PIL
# ---------------------------------------------------------------------------
try:
    import numpy as np

    _HAS_NUMPY = True
except ImportError:
    _HAS_NUMPY = False

# ---------------------------------------------------------------------------
# 颜色类型别名
# ---------------------------------------------------------------------------
ColorLike = Union[str, Tuple[int, int, int], Tuple[int, int, int, int]]


# ===================================================================
# 配置数据类 — 所有可自定义参数 + 默认值
# ===================================================================
@dataclass
class RoundedBlurConfig:
    """圆角矩形模糊的完整配置。

    所有字段均有默认值，可按需覆盖任意项。
    """

    # ---- 圆角矩形几何 ----
    corner_radius: int = 40
    """圆角半径（像素）。设为 0 即直角。"""

    rect_left: Optional[int] = None
    """矩形左边界（像素）；None 表示自动居中。"""

    rect_top: Optional[int] = None
    """矩形上边界（像素）；None 表示自动居中。"""

    rect_width: Optional[int] = None
    """矩形宽度（像素）；None 表示取图像宽度的 80%。"""

    rect_height: Optional[int] = None
    """矩形高度（像素）；None 表示取图像高度的 80%。"""

    # ---- 模糊 ----
    blur_radius: float = 15.0
    """高斯模糊 sigma。值越大越模糊；0 表示不模糊。"""

    blur_truncate: float = 3.0
    """高斯核截断半径（sigma 的倍数）。越大越精确但越慢。"""

    # ---- 矩形内部背景 ----
    fill_color: Optional[ColorLike] = None
    """矩形内部填充色；None 表示不额外填充（仅模糊原图）。"""

    fill_opacity: float = 0.0
    """填充色不透明度 0.0~1.0。仅在 fill_color 非 None 时生效。"""

    # ---- 模糊透明度 ----
    blur_opacity: float = 1.0
    """模糊效果的不透明度 0.0~1.0。1.0=完全模糊, 0.5=半透明模糊叠加, 0=无模糊。"""

    # ---- 边框 ----
    border_width: int = 0
    """边框宽度（像素）。0 表示无边框。"""

    border_color: ColorLike = (255, 255, 255, 200)
    """边框颜色，支持 (R,G,B) / (R,G,B,A) / CSS 字符串。"""

    # ---- 矩形外部 ----
    outside_fill_color: Optional[ColorLike] = None
    """矩形外部的填充色；None 表示保持原图。"""

    outside_fill_opacity: float = 0.0
    """外部填充不透明度 0.0~1.0。"""

    # ---- 画质 ----
    supersample: int = 2
    """SSAA 超采样倍率 (1/2/3/4)。2 即 2x 渲染后 LANCZOS 缩回。
       1 表示不超采样，直接渲染。"""

    antialias_feather: float = 1.5
    """mask 边缘羽化宽度（像素）。0 表示硬边。
       在超采样分辨率下计算，再随 downscale 自然抗锯齿。"""

    mask_smooth: bool = True
    """是否对 mask 做额外平滑（smoothstep 曲线），
       使圆角过渡更自然。需要 numpy。"""

    # ---- 输出 ----
    output_format: str = "PNG"
    """输出格式（仅用于 save 方法）。"""

    output_quality: int = 95
    """输出质量（对 JPEG 等有损格式生效）。"""

    def resolved_rect(self, img_w: int, img_h: int) -> Tuple[int, int, int, int]:
        """根据图像尺寸解析最终的矩形 (left, top, right, bottom)。"""
        rw = self.rect_width or int(img_w * 0.8)
        rh = self.rect_height or int(img_h * 0.8)
        left = self.rect_left if self.rect_left is not None else (img_w - rw) // 2
        top = self.rect_top if self.rect_top is not None else (img_h - rh) // 2
        return (left, top, left + rw, top + rh)


# ===================================================================
# Mask 构建 — 圆角矩形 + 抗锯齿
# ===================================================================
def _build_rounded_rect_mask(
    size: Tuple[int, int],
    rect: Tuple[int, int, int, int],
    radius: int,
    feather: float = 1.5,
    smooth: bool = True,
) -> Image.Image:
    """构建一张灰度 mask（L 模式），白色=矩形内部，黑色=外部。

    Parameters
    ----------
    size : (w, h)
        mask 图像尺寸。
    rect : (left, top, right, bottom)
        矩形坐标。
    radius : int
        圆角半径。
    feather : float
        羽化宽度（高斯模糊 sigma）。
    smooth : bool
        是否使用 smoothstep 曲线增强抗锯齿。需要 numpy。

    Returns
    -------
    PIL.Image (mode='L')
    """
    w, h = size
    left, top, right, bottom = rect

    # 1) 在黑色画布上画白色圆角矩形
    mask = Image.new("L", (w, h), 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle(
        [left, top, right, bottom],
        radius=radius,
        fill=255,
    )

    # 2) 羽化边缘（高斯模糊 mask 实现软边）
    if feather > 0:
        mask = mask.filter(ImageFilter.GaussianBlur(radius=feather))

    # 3) smoothstep 非线性映射 — 让边缘过渡更"陡但平滑"
    #    把中间灰度映射到更接近 0 或 255，减少半透明拖影
    if smooth and _HAS_NUMPY:
        arr = np.array(mask, dtype=np.float32) / 255.0  # [0, 1]
        # smoothstep: t^2 * (3 - 2t)
        arr = arr * arr * (3.0 - 2.0 * arr)
        arr = np.clip(arr * 255.0, 0, 255).astype(np.uint8)
        mask = Image.fromarray(arr, mode="L")

    return mask


# ===================================================================
# 核心处理函数
# ===================================================================
def apply_rounded_blur(
    image: Image.Image,
    config: Optional[RoundedBlurConfig] = None,
    **overrides,
) -> Image.Image:
    """给图片添加圆角矩形模糊遮罩（核心函数）。

    Parameters
    ----------
    image : PIL.Image
        输入图像。支持任何 Pillow 可读的模式（RGB / RGBA / …）。
    config : RoundedBlurConfig, optional
        配置对象。若为 None，使用全部默认值。
    **overrides
        关键字参数可覆盖 config 中的任意字段，例如
        ``apply_rounded_blur(img, blur_radius=25, corner_radius=60)``。

    Returns
    -------
    PIL.Image (mode='RGBA')
        处理后的图像。即使输入无 alpha 通道，输出也带 alpha。

    Examples
    --------
    # >>> from PIL import Image
    # >>> img = Image.open("photo.jpg")
    # >>> result = apply_rounded_blur(img)
    # >>> result.save("output.png")
    #
    # >>> result = apply_rounded_blur(
    # ...     img,
    # ...     blur_radius=20,
    # ...     corner_radius=60,
    # ...     border_width=3,
    # ...     border_color="white",
    # ...     supersample=3,
    # ... )
    """
    # ---- 合并配置 ----
    cfg = config or RoundedBlurConfig()
    for key, value in overrides.items():
        if hasattr(cfg, key):
            setattr(cfg, key, value)
        else:
            raise TypeError(f"RoundedBlurConfig 没有字段 '{key}'")

    # ---- 确保输入为 RGBA ----
    if image.mode != "RGBA":
        base = image.convert("RGBA")
    else:
        base = image.copy()

    orig_w, orig_h = base.size
    ss = max(1, min(cfg.supersample, 4))  # clamp 1~4

    # ---- 超采样渲染尺寸 ----
    render_w, render_h = orig_w * ss, orig_h * ss

    # ---- 在超采样分辨率下计算矩形坐标 ----
    rect = cfg.resolved_rect(orig_w, orig_h)
    scaled_rect = tuple(v * ss for v in rect)  # type: ignore[assignment]
    scaled_radius = cfg.corner_radius * ss
    scaled_feather = cfg.antialias_feather * ss

    # ---- Step 1: 放大原图到渲染分辨率 ----
    if ss > 1:
        work = base.resize((render_w, render_h), Image.LANCZOS)
    else:
        work = base

    # ---- Step 2: 对渲染分辨率下的图做高斯模糊 ----
    if cfg.blur_radius > 0:
        blurred = work.filter(
            ImageFilter.GaussianBlur(
                radius=cfg.blur_radius * ss,
            )
        )
    else:
        blurred = work

    # ---- Step 3: 构建圆角矩形 mask（超采样分辨率） ----
    mask = _build_rounded_rect_mask(
        size=(render_w, render_h),
        rect=scaled_rect,
        radius=scaled_radius,
        feather=scaled_feather,
        smooth=cfg.mask_smooth,
    )

    # ---- Step 4: 用 mask 合成 — 矩形内=模糊图，矩形外=原图 ----
    # PIL composite: composite(image1, image2, mask)
    #   mask=255 → 取 image1；mask=0 → 取 image2
    #   这里 image1 = blurred（矩形内），image2 = work（矩形外）
    composited = Image.composite(blurred, work, mask)

    # ---- 注：composited 现在不含 alpha 通道信息来自 composite 逻辑 ----
    #    我们需要把 alpha 也带回去，用原 work 的 alpha
    if composited.mode == "RGB":
        composited = composited.convert("RGBA")
    # 恢复 alpha 通道
    r, g, b, _ = composited.split()
    _, _, _, orig_a = work.split()
    composited = Image.merge("RGBA", (r, g, b, orig_a))

    # ---- Step 5: 矩形内部填充色 ----
    if cfg.fill_color is not None and cfg.fill_opacity > 0:
        fill_layer = Image.new("RGBA", (render_w, render_h), (0, 0, 0, 0))
        fill_draw = ImageDraw.Draw(fill_layer)
        # 解析颜色
        fc = _parse_color(cfg.fill_color)
        fill_rgba = (
            fc[0],
            fc[1],
            fc[2],
            int(255 * cfg.fill_opacity),
        )
        fill_draw.rounded_rectangle(
            list(scaled_rect),
            radius=scaled_radius,
            fill=fill_rgba,
        )
        # 需要带羽化
        if scaled_feather > 0:
            fill_layer = fill_layer.filter(
                ImageFilter.GaussianBlur(radius=scaled_feather)
            )
        composited = Image.alpha_composite(composited, fill_layer)

    # ---- Step 6: 矩形外部填充 ----
    if cfg.outside_fill_color is not None and cfg.outside_fill_opacity > 0:
        fc = _parse_color(cfg.outside_fill_color)
        outside = Image.new("RGBA", (render_w, render_h), (0, 0, 0, 0))
        outside_draw = ImageDraw.Draw(outside)
        outside_draw.rounded_rectangle(
            list(scaled_rect),
            radius=scaled_radius,
            fill=(0, 0, 0, 0),  # 内部透明
        )
        # 反转 mask 得到外部区域
        inv_mask = ImageOps.invert(mask)
        # 在外部分填充纯色
        outer_fill = Image.new(
            "RGBA",
            (render_w, render_h),
            (fc[0], fc[1], fc[2], int(255 * cfg.outside_fill_opacity)),
        )
        composited = Image.composite(outer_fill, composited, inv_mask)

    # ---- Step 7: 圆角矩形边框 ----
    if cfg.border_width > 0:
        border_layer = Image.new("RGBA", (render_w, render_h), (0, 0, 0, 0))
        border_draw = ImageDraw.Draw(border_layer)
        bc = _parse_color(cfg.border_color)
        bw = cfg.border_width * ss
        border_draw.rounded_rectangle(
            list(scaled_rect),
            radius=scaled_radius,
            outline=(bc[0], bc[1], bc[2], bc[3] if len(bc) > 3 else 255),
            width=bw,
        )
        # 对边框也做轻微羽化抗锯齿
        if scaled_feather > 0:
            border_layer = border_layer.filter(
                ImageFilter.GaussianBlur(radius=scaled_feather * 0.5)
            )
        composited = Image.alpha_composite(composited, border_layer)

    # ---- Step 8: 模糊透明度混合 ----
    if cfg.blur_opacity < 1.0:
        composited = Image.blend(composited, work, 1.0 - cfg.blur_opacity)

    # ---- Step 9: 下采样回原始分辨率 ----
    if ss > 1:
        result = composited.resize((orig_w, orig_h), Image.LANCZOS)
    else:
        result = composited

    return result


# ===================================================================
# 便捷函数
# ===================================================================
def blur_rect(
    image: Image.Image,
    x: int, y: int, w: int, h: int,
    *,
    corner_radius: int = 40,
    blur_radius: float = 15.0,
    border_width: int = 0,
    border_color: ColorLike = (255, 255, 255, 200),
    supersample: int = 2,
    blur_opacity: float = 1.0,
    fill_color: Optional[ColorLike] = None,
    fill_opacity: float = 0.0,
    **kwargs,
) -> Image.Image:
    """给图片指定像素区域添加圆角矩形模糊。

    x, y, w, h : 矩形左上角坐标 + 宽高（像素）
    blur_opacity : 模糊透明度 0~1
    fill_color : 矩形内部填充色，如 'white' 泛白
    fill_opacity : 填充不透明度，如 0.15 轻微泛白
    """
    cfg = RoundedBlurConfig(
        rect_left=x, rect_top=y,
        rect_width=w, rect_height=h,
        corner_radius=corner_radius,
        blur_radius=blur_radius,
        border_width=border_width,
        border_color=border_color,
        supersample=supersample,
        blur_opacity=blur_opacity,
        fill_color=fill_color,
        fill_opacity=fill_opacity,
        **kwargs,
    )
    return apply_rounded_blur(image, cfg)


def blur_rects(
    image: Image.Image,
    rects: list[tuple[int, int, int, int]],
    *,
    corner_radius: int = 40,
    blur_radius: float = 15.0,
    border_width: int = 0,
    border_color: ColorLike = (255, 255, 255, 200),
    supersample: int = 2,
    blur_opacity: float = 1.0,
    fill_color: Optional[ColorLike] = None,
    fill_opacity: float = 0.0,
    **kwargs,
) -> Image.Image:
    """一次性放置多个圆角矩形模糊。

    Parameters
    ----------
    image : PIL.Image
    rects : [(x, y, w, h), ...]  每个元组为左上角坐标 + 宽高

    Examples
    --------
    >>> result = blur_rects(img, [
    ...     (100, 50, 500, 300),
    ...     (700, 80, 400, 250),
    ... ], corner_radius=30, blur_radius=18)
    """
    for x, y, w, h in rects:
        image = blur_rect(image, x, y, w, h,
                          corner_radius=corner_radius,
                          blur_radius=blur_radius,
                          border_width=border_width,
                          border_color=border_color,
                          supersample=supersample,
                          blur_opacity=blur_opacity,
                          fill_color=fill_color,
                          fill_opacity=fill_opacity,
                          **kwargs)
    return image


def open_and_apply(
    image_path: str,
    config: Optional[RoundedBlurConfig] = None,
    **overrides,
) -> Image.Image:
    """从文件路径加载图片并应用圆角模糊。"""
    img = Image.open(image_path)
    return apply_rounded_blur(img, config, **overrides)


def save_result(
    image: Image.Image,
    output_path: str,
    config: Optional[RoundedBlurConfig] = None,
) -> None:
    """保存处理后的图像。

    自动使用 config.output_format / config.output_quality。
    """
    fmt = config.output_format if config else "PNG"
    quality = config.output_quality if config else 95
    save_kwargs = {}
    if fmt.upper() in ("JPEG", "JPG"):
        save_kwargs["quality"] = quality
        # 转为 RGB 保存 JPEG
        if image.mode == "RGBA":
            # 合成到白色背景
            bg = Image.new("RGB", image.size, (255, 255, 255))
            bg.paste(image, mask=image.split()[3])
            image = bg
    elif fmt.upper() == "WEBP":
        save_kwargs["quality"] = quality
    image.save(output_path, format=fmt, **save_kwargs)


# ===================================================================
# 辅助函数
# ===================================================================
def _parse_color(color: ColorLike) -> Tuple[int, int, int, int]:
    """将各种颜色表示法统一为 (R, G, B, A)。"""
    if isinstance(color, str):
        # 借助 PIL 的 ImageColor
        from PIL import ImageColor

        rgb = ImageColor.getrgb(color)
        return (rgb[0], rgb[1], rgb[2], 255)
    elif isinstance(color, (list, tuple)):
        if len(color) == 3:
            return (int(color[0]), int(color[1]), int(color[2]), 255)
        elif len(color) == 4:
            return (int(color[0]), int(color[1]), int(color[2]), int(color[3]))
    raise ValueError(f"无法解析颜色: {color!r}")


# ===================================================================
# 顶层封装函数 — 一行调用，从文件到文件
# ===================================================================
def process_image(
    input_path: str,
    output_path: Optional[str] = None,
    *,
    corner_radius: int = 40,
    rect_left: Optional[int] = None,
    rect_top: Optional[int] = None,
    rect_width: Optional[int] = None,
    rect_height: Optional[int] = None,
    blur_radius: float = 15.0,
    blur_truncate: float = 3.0,
    fill_color: Optional[ColorLike] = None,
    fill_opacity: float = 0.0,
    border_width: int = 0,
    border_color: ColorLike = (255, 255, 255, 200),
    outside_fill_color: Optional[ColorLike] = None,
    outside_fill_opacity: float = 0.0,
    supersample: int = 2,
    antialias_feather: float = 1.5,
    mask_smooth: bool = True,
    output_format: str = "PNG",
    output_quality: int = 95,
) -> Image.Image:
    """加载图片 → 添加圆角矩形模糊 → 保存（可选）→ 返回 Image。

    这是模块的主入口函数，封装了 加载/配置/处理/保存 全流程。
    所有参数均设有默认值，调用方只需传入 input_path 即可。

    Parameters
    ----------
    input_path : str
        输入图片路径。
    output_path : str, optional
        输出路径。为 None 则不保存，仅返回 Image 对象。
    其余关键字参数：
        与 RoundedBlurConfig 字段一一对应，见该类的文档。

    Returns
    -------
    PIL.Image (RGBA)
        处理后的图像对象，可继续用 PIL 操作。

    Examples
    --------
    # >>> from UI import process_image
    #
    # >>> # 最简调用：默认参数处理并保存
    # >>> img = process_image("photo.jpg", "output.png")
    #
    # >>> # 仅获取 Image 对象，不保存
    # >>> img = process_image("photo.jpg")
    # >>> img.show()
    #
    # >>> # 自定义模糊和圆角
    # >>> process_image(
    # ...     "photo.jpg", "out.png",
    # ...     blur_radius=25,
    # ...     corner_radius=60,
    # ...     border_width=3,
    # ...     border_color="white",
    # ...     supersample=3,
    # ... )
    """
    # 组装配置
    cfg = RoundedBlurConfig(
        corner_radius=corner_radius,
        rect_left=rect_left,
        rect_top=rect_top,
        rect_width=rect_width,
        rect_height=rect_height,
        blur_radius=blur_radius,
        blur_truncate=blur_truncate,
        fill_color=fill_color,
        fill_opacity=fill_opacity,
        border_width=border_width,
        border_color=border_color,
        outside_fill_color=outside_fill_color,
        outside_fill_opacity=outside_fill_opacity,
        supersample=supersample,
        antialias_feather=antialias_feather,
        mask_smooth=mask_smooth,
        output_format=output_format,
        output_quality=output_quality,
    )

    # 加载 & 处理
    image = Image.open(input_path)
    result = apply_rounded_blur(image, cfg)

    # 可选保存
    if output_path is not None:
        save_result(result, output_path, cfg)

    return result


# ===================================================================
# 预置风格
# ===================================================================
def preset_light_blur() -> RoundedBlurConfig:
    """轻量模糊 — 适合做卡片背景。"""
    return RoundedBlurConfig(
        blur_radius=8,
        corner_radius=30,
        border_width=2,
        border_color=(255, 255, 255, 180),
        supersample=2,
        antialias_feather=1.0,
    )


def preset_heavy_frosted() -> RoundedBlurConfig:
    """强磨砂玻璃效果 — 毛玻璃风格。"""
    return RoundedBlurConfig(
        blur_radius=25,
        corner_radius=50,
        fill_color=(255, 255, 255),
        fill_opacity=0.15,
        border_width=1,
        border_color=(255, 255, 255, 100),
        supersample=3,
        antialias_feather=2.0,
    )


def preset_dark_panel() -> RoundedBlurConfig:
    """深色面板 — 适合深色主题。"""
    return RoundedBlurConfig(
        blur_radius=20,
        corner_radius=40,
        fill_color=(0, 0, 0),
        fill_opacity=0.35,
        border_width=1,
        border_color=(255, 255, 255, 60),
        supersample=3,
        antialias_feather=2.0,
    )


def preset_sharp_frame() -> RoundedBlurConfig:
    """清晰相框 — 微模糊 + 明显边框，最高画质。"""
    return RoundedBlurConfig(
        blur_radius=5,
        corner_radius=20,
        border_width=4,
        border_color="white",
        supersample=4,
        antialias_feather=0.5,
        mask_smooth=True,
    )


def preset_vignette() -> RoundedBlurConfig:
    """暗角圆角 — 矩形外变暗，矩形内清晰。"""
    return RoundedBlurConfig(
        blur_radius=0,  # 内部不模糊
        corner_radius=50,
        outside_fill_color=(0, 0, 0),
        outside_fill_opacity=0.5,
        border_width=0,
        supersample=3,
        antialias_feather=3.0,
    )


# ===================================================================
# 命令行入口
# ===================================================================
if __name__ == "__main__":
    import sys

    input_path = sys.argv[1] if len(sys.argv) > 1 else "1.png"
    output_path = sys.argv[2] if len(sys.argv) > 2 else "ui_output.png"

    if not __import__("os").path.exists(input_path):
        print(f"文件不存在: {input_path}")
        print("请提供一个图片文件路径作为参数，例如:")
        print("  python frame.py my_photo.jpg result.png")
        sys.exit(1)

    result = process_image(
        input_path,
        output_path,
        blur_radius=18,
        corner_radius=50,
        border_width=1,
        border_color="white",
        supersample=3,
        antialias_feather=2.0,
    )

    print(f"已保存: {output_path}")
    print(f"  输入尺寸: ({result.width}, {result.height})")
    print(f"  输出模式: {result.mode}")
