# 📌 Random Image API

轻量级随机图片 API，基于 Flask + Docker。支持 JPG / JPEG / PNG / WEBP / GIF / BMP / TIF / TIFF / AVIF，图片通过目录挂载管理，无需数据库。

- GitHub：<https://github.com/Komeiji-V/random-image-api>
- Docker Hub：<https://hub.docker.com/r/komeijiv/random-image-api>

## ✨ 特性

- **多频道**：`images/` 下每个一级子目录自动成为一个 API，如 `/day`、`/night`
- 递归扫描子目录，按主题/相册自由分类
- 目录索引缓存（默认 10 秒），避免每次请求全量扫描
- AVIF 支持，并按 `Accept` 头对旧浏览器自动降级
- 非 root 运行、内置健康检查、响应不缓存

## 🚀 快速开始

### 方式一：Docker Hub 镜像

```bash
mkdir -p images/day images/night
docker run -d --name random-image-api --restart unless-stopped \
  -p 127.0.0.1:5000:5000 \
  -v "$PWD/images:/app/images:ro" \
  komeijiv/random-image-api:latest
```

### 方式二：本地构建

```bash
git clone https://github.com/Komeiji-V/random-image-api.git
cd random-image-api
docker build -t random-image-api .
docker run -d --name random-image-api --restart unless-stopped \
  -p 127.0.0.1:5000:5000 \
  -v "$PWD/images:/app/images:ro" \
  random-image-api
```

### 方式三：Docker Compose

```bash
mkdir -p images/day images/night
docker compose up -d --build
```

> 默认只绑定 `127.0.0.1`，请通过 nginx 反代对外提供服务（见 [docs/nginx.md](docs/nginx.md)）。

## 🗂️ 多频道

```
images/
├── day/      → GET /day
├── night/    → GET /night
└── top.jpg   → GET /（全部）
```

| URL | 返回 |
|-----|------|
| `/` | 全部图片随机 |
| `/day` | day 频道随机 |
| `/channels` | 频道列表及数量 |
| `/health` | 健康检查 |

新增频道只需新建目录，无需重启。

## ⚙️ 环境变量

| 变量 | 默认 | 说明 |
|------|------|------|
| `IMAGE_FOLDER` | `/app/images` | 图片目录 |
| `CACHE_TTL` | `10` | 索引缓存秒数，0 为每次重扫 |

## 📝 说明

- **权限**：容器内以 UID 1000 运行，挂载目录需可读：`chmod -R o+rX ./images`，或启动时加 `--user "$(id -u):$(id -g)"`。
- **AVIF**：Chrome 85+ / Firefox 93+ / Safari 16.4+ 支持；不支持 AVIF 的客户端会自动跳过 AVIF 文件，频道内只有 AVIF 时会返回 404。
- **Nginx 反代**：见 [docs/nginx.md](docs/nginx.md)，注意关闭缓存、保持 `proxy_buffering`。
- **License**：[GPL-3.0](LICENSE)。
