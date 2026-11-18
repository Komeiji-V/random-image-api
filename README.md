# 📌 Random Image API

一个轻量级的随机图片 API，基于 **Flask** 和 **Docker**，支持多种格式（含 **AVIF**）图片的随机返回。图片通过挂载目录管理，无需数据库；一个容器可同时提供多个独立的随机图频道。

- GitHub：<https://github.com/Komeiji-V/random-image-api>
- Docker Hub：<https://hub.docker.com/r/komeijiv/random-image-api>

---

## ✨ 特性

- 访问根路径 `/` 随机返回一张图片
- **多频道**：`images/` 下每个一级子目录自动成为一个独立 API，如 `/day`、`/night`
- 支持 **JPG / JPEG / PNG / WEBP / GIF / BMP / TIFF / AVIF**
- 递归扫描子目录，图片可按相册/年份自由分目录
- 目录索引缓存（默认 10 秒），避免每次请求全量扫描
- 按 `Accept` 头自动降级：不支持 AVIF 的旧浏览器不会拿到无法渲染的图片
- 非 root 运行、带健康检查、访问日志输出到 stdout
- 响应带 `Cache-Control: no-store`，保证每次刷新都能换图

---

## 🗂️ 多频道

把不同主题的图片放进不同的一级子目录，即可得到多个互相独立的随机图 API：

```
images/
├── day/                 →  GET /day
│   ├── 01.avif
│   └── 02.jpg
├── night/               →  GET /night
│   └── 01.avif
├── 风景/                →  GET /风景
│   └── 01.webp
└── top.jpg              →  GET /        （根路径仍返回全部）
```

| URL | 返回内容 |
|-----|----------|
| `/` | 整个 `images/` 目录递归随机（兼容旧用法） |
| `/day`、`/night` | 只在对应频道目录内递归随机 |
| `/day/` | 同上（容忍尾斜杠） |
| `/channels` | 频道列表，含每个频道的图片数量 |
| `/health` | 健康检查 |

要点：

- **新增频道无需改代码**：直接在 `images/` 下建文件夹，最多等 `CACHE_TTL` 秒即可访问，不需要重启容器。
- **频道名限制**：不能含 `/`、`\`、控制字符，不能以 `.` 开头；频道必须真实存在于一级目录，否则返回 404。
- **保留路径**：`/health` 和 `/channels` 是固定路由，同名文件夹不会被当作频道。
- **中文频道名可用**：如 `/风景`。
- **软链接**：频道目录若是指向 `images/` 之外的软链接会被拒绝；目录内指向外部的软链接文件也不会被返回。

---

## 🚀 部署

三种方式任选其一。图片统一放在宿主机的 `./images/` 目录（可建子目录作为频道）。

### 方式一：本地构建镜像

```bash
git clone https://github.com/Komeiji-V/random-image-api.git
cd random-image-api

docker build -t random-image-api .

docker run -d --name random-image-api --restart unless-stopped \
  -p 5000:5000 \
  -v "$PWD/images:/app/images:ro" \
  random-image-api
```

> 默认使用清华 PyPI 镜像加速构建。海外网络可改用官方源：
> `docker build --build-arg PIP_INDEX_URL=https://pypi.org/simple -t random-image-api .`

### 方式二：直接运行 Docker Hub 镜像

```bash
docker pull komeijiv/random-image-api:latest

docker run -d --name random-image-api --restart unless-stopped \
  -p 5000:5000 \
  -v "$PWD/images:/app/images:ro" \
  komeijiv/random-image-api:latest
```

### 方式三：Docker Compose

仓库已自带 `docker-compose.yml`：

```bash
mkdir -p images/day images/night
docker compose up -d --build
```

常用命令：

```bash
docker compose logs -f          # 查看日志
docker compose down             # 停止并移除容器
docker compose up -d --build    # 修改代码后重新构建
```

如需调整配置，编辑 `docker-compose.yml` 中的 `environment` 或 `volumes` 即可。

---

## 🔐 挂载权限

容器内以 UID 1000 的 `appuser` 运行，宿主机目录必须对该 UID 可读：

```bash
chmod -R o+rX ./images
```

或者直接以当前用户身份运行（推荐，避免放宽目录权限）：

```bash
docker run -d --name random-image-api --restart unless-stopped \
  --user "$(id -u):$(id -g)" \
  -p 5000:5000 \
  -v "$PWD/images:/app/images:ro" \
  komeijiv/random-image-api:latest
```

使用 Compose 时，可取消 `docker-compose.yml` 中 `user:` 一行注释。

---

## ⚙️ 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `IMAGE_FOLDER` | `/app/images` | 图片目录，容器内路径 |
| `CACHE_TTL` | `10` | 目录索引缓存秒数；上传新图后最多等这么久可见，设为 `0` 则每次请求都重新扫描 |

---

## 🌍 使用

容器运行后访问：

```
http://localhost:5000/          # 全部图片随机
http://localhost:5000/day       # day 频道随机
http://localhost:5000/night     # night 频道随机
http://localhost:5000/channels  # 频道列表
http://localhost:5000/health    # 健康检查
```

博客中直接引用即可：

```html
<img src="http://你的服务器:5000/day" alt="日间随机图">
<img src="http://你的服务器:5000/night" alt="夜间随机图">
```

### 频道列表

```bash
curl http://localhost:5000/channels
# {"channels":[{"name":"day","count":2},{"name":"night","count":1}]}
```

### 健康检查

```bash
curl http://localhost:5000/health
# {"status":"ok"}
```

Docker 已内置 `HEALTHCHECK`，`docker ps` 中可看到 `healthy` 状态。

---

## 🖼️ 支持的图片格式

| 格式 | MIME |
|------|------|
| `.jpg` / `.jpeg` | `image/jpeg` |
| `.png` | `image/png` |
| `.webp` | `image/webp` |
| `.gif` | `image/gif` |
| `.bmp` | `image/bmp` |
| `.tiff` | `image/tiff` |
| `.avif` | `image/avif` |

> **关于 AVIF**：Chrome 85+、Firefox 93+、Safari 16.4+（iOS 16.4+）均已支持。对于不支持的旧客户端，接口会根据 `Accept` 头自动跳过 AVIF 文件；如果某个频道里只有 AVIF 图片，旧客户端会收到 404 而不是破图。
>
> 本项目只做文件分发，**不做转码**，因此不需要 Pillow。AVIF 图片可用 `avifenc`、ImageMagick（`magick in.jpg out.avif`）、Squoosh 或 `sharp` 生成。

---

## 💻 本地开发

```bash
pip install -r requirements.txt
IMAGE_FOLDER=./images CACHE_TTL=0 python3 app.py
```

浏览器访问 <http://localhost:5000/day> 或 <http://localhost:5000>。

---

## 🔧 适用场景

🔹 个人博客随机头图 / 随机插图（可按日间、夜间等主题分频道）  
🔹 简单的图片存储与分发（无需数据库）  
🔹 Docker 轻量级部署，本地或小型服务器均适用  

---

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=Komeiji-V/random-image-api&type=date&legend=top-left)](https://www.star-history.com/#Komeiji-V/random-image-api&type=date&legend=top-left)
