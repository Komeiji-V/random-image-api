import os
import random
import re
import time

from flask import Flask, abort, request, send_file

app = Flask(__name__)

# 图片根目录：容器内默认 /app/images，本地开发可用环境变量覆盖
IMAGE_FOLDER = os.environ.get("IMAGE_FOLDER", "/app/images")
# 目录扫描缓存秒数：上传新图后最多等这么久可见
CACHE_TTL = float(os.environ.get("CACHE_TTL", "10"))

SUPPORTED_FORMATS = (".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tiff", ".avif")

MIME_TYPES = {
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "webp": "image/webp",
    "gif": "image/gif",
    "bmp": "image/bmp",
    "tiff": "image/tiff",
    "avif": "image/avif",  # 不显式指定时部分环境会返回 octet-stream，浏览器不渲染
}

# 频道名不允许路径分隔符和控制字符，且不能以点开头（防隐藏目录/路径穿越）
CHANNEL_RE = re.compile(r"^[^/\\\x00]{1,64}$")

# 频道名 -> {"ts": 时间戳, "files": [...]}；根路径用空字符串作 key
_cache = {}


def _scan(folder):
    """递归扫描单个目录，只返回白名单格式的图片绝对路径。"""
    base_real = os.path.realpath(IMAGE_FOLDER)
    folder_real = os.path.realpath(folder)
    # 频道目录必须落在 IMAGE_FOLDER 内，防止软链接把外部目录暴露出去
    if folder_real != base_real and not folder_real.startswith(base_real + os.sep):
        return []
    if not os.path.isdir(folder_real):
        return []

    files = []
    for root, dirs, names in os.walk(folder_real):
        dirs[:] = [d for d in dirs if not d.startswith(".")]  # 跳过隐藏目录
        for name in names:
            if name.startswith(".") or not name.lower().endswith(SUPPORTED_FORMATS):
                continue
            path = os.path.realpath(os.path.join(root, name))
            # 防止软链接把目录外的文件带进来
            if path.startswith(folder_real + os.sep):
                files.append(path)
    return files


def scan_images(channel=""):
    """按频道扫描并缓存；channel 为空字符串表示根目录。"""
    now = time.monotonic()
    cached = _cache.get(channel)
    if cached and now - cached["ts"] < CACHE_TTL:
        return cached["files"]

    folder = os.path.join(IMAGE_FOLDER, channel) if channel else IMAGE_FOLDER
    files = _scan(folder)
    _cache[channel] = {"ts": now, "files": files}
    return files


def list_channels():
    """列出 images/ 下的一级子目录（排除隐藏目录和软链接目录）。"""
    if not os.path.isdir(IMAGE_FOLDER):
        return []
    result = []
    for name in sorted(os.listdir(IMAGE_FOLDER)):
        path = os.path.join(IMAGE_FOLDER, name)
        if name.startswith(".") or os.path.islink(path) or not os.path.isdir(path):
            continue
        result.append(name)
    return result


def accepts_avif():
    """判断客户端能否渲染 AVIF，避免老浏览器拿到无法显示的图片。"""
    accept = request.headers.get("Accept")
    if not accept:  # 无 Accept 头（部分脚本）默认放行
        return True
    accept = accept.lower()
    if "image/avif" in accept:
        return True
    # curl / requests 等只发 */* 的客户端视为无偏好
    return accept.replace(" ", "") in ("*/*", "*/*;q=1", "*/*;q=1.0")


def _respond(images):
    """从候选列表里随机返回一张；无可用图片时返回 None。"""
    if not accepts_avif():
        images = [p for p in images if not p.lower().endswith(".avif")]
    if not images:
        return None

    path = random.choice(images)
    ext = path.rsplit(".", 1)[-1].lower()
    try:
        resp = send_file(path, mimetype=MIME_TYPES.get(ext, "application/octet-stream"))
    except OSError:
        # 文件在扫描后被删除或替换成目录，清空缓存并返回 404
        _cache.clear()
        abort(404)
    # 随机接口不应被浏览器/CDN 缓存，否则"每次刷新换图"会失效
    resp.headers["Cache-Control"] = "no-store"
    return resp


@app.route("/")
def get_random_image():
    resp = _respond(scan_images())
    if resp is None:
        return {"error": "No images found", "folder": IMAGE_FOLDER}, 404
    return resp


@app.route("/channels", strict_slashes=False)
def get_channels():
    return {
        "channels": [
            {"name": name, "count": len(scan_images(name))}
            for name in list_channels()
        ]
    }


@app.route("/health", strict_slashes=False)
def health():
    return {"status": "ok"}


@app.route("/<channel>", strict_slashes=False)
def get_channel_image(channel):
    # 双重校验：格式合法 + 确实是一级目录，才允许访问
    if (
        not CHANNEL_RE.match(channel)
        or channel.startswith(".")
        or channel not in list_channels()
    ):
        abort(404)
    resp = _respond(scan_images(channel))
    if resp is None:
        return {"error": "No images found", "channel": channel}, 404
    return resp


@app.errorhandler(404)
def not_found(_err):
    return {"error": "Not found"}, 404


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
