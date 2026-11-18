# Nginx 反向代理配置

本文档给出 [Random Image API](https://github.com/Komeiji-V/random-image-api) 的 nginx 反向代理建议配置。

核心原则三句话：**不要缓存、透传 Range、保护上游 gunicorn**。

---

## 目录

- [核心注意点](#核心注意点)
- [场景 A：域名反代（推荐）](#场景-a域名反代推荐)
- [场景 B：博客子路径反代](#场景-b博客子路径反代)
- [验证配置](#验证配置)
- [常见坑](#常见坑)

---

## 核心注意点

### 1. 关闭 nginx 缓存（最关键）

接口每次请求都应返回随机图，上游已声明 `Cache-Control: no-store`。如果开启 `proxy_cache`，`/day` 的响应会被缓存，**之后所有人拿到的都是同一张图**，随机性失效。

```nginx
proxy_cache off;
proxy_no_cache 1;
proxy_cache_bypass 1;
```

同时**不要**加 `expires 30d;` 或自行覆盖 `Cache-Control`，否则浏览器会缓存 `/day`，刷新也不换图。

### 2. 透传 Range 请求

Flask 的 `send_file` 支持 `Range`（返回 `206 Partial Content`）。nginx 默认会透传，但前提是**没有开启缓存**（缓存会接管 Range，可能返回 200 整图）。一般无需额外配置；如需显式声明，可加：

```nginx
proxy_set_header Range $http_range;
proxy_set_header If-Range $http_if_range;
```

> 注意：客户端未发送 Range 时这两行会发送空的 `Range` 头，通常无害，但并非必需，默认透传即可。

### 3. 保持 `proxy_buffering` 开启

服务使用 `gunicorn -w 2` 的 sync worker，慢客户端会一直占用 worker。`proxy_buffering on`（默认）会先读完上游响应再慢慢发给客户端，等于给上游加了一层保护，**不要关闭**：

```nginx
proxy_buffering on;
proxy_buffers 16 64k;
proxy_buffer_size 128k;
proxy_busy_buffers_size 256k;
proxy_max_temp_file_size 16m;
```

### 4. HTTP/1.1 + keepalive

```nginx
upstream random_image_api {
    server 127.0.0.1:5000;
    keepalive 16;
}

proxy_http_version 1.1;
proxy_set_header Connection "";
```

### 5. 不要覆盖 `Accept` 头

AVIF 降级依赖浏览器的 `Accept` 头是否包含 `image/avif`。nginx 默认透传，**不要**清空或改写它，否则所有客户端都会被当成不支持 AVIF。

### 6. 端口只绑本机

```bash
docker run -d -p 127.0.0.1:5000:5000 ...
```

不要 `-p 5000:5000` 暴露公网，否则别人可以绕过 nginx 直接访问容器。

---

## 场景 A：域名反代（推荐）

假设图片域名为 `img.example.com`，容器映射到 `127.0.0.1:5000`。

```nginx
upstream random_image_api {
    server 127.0.0.1:5000;
    keepalive 16;
}

server {
    listen 443 ssl http2;
    server_name img.example.com;

    ssl_certificate     /etc/letsencrypt/live/img.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/img.example.com/privkey.pem;

    location / {
        proxy_pass http://random_image_api;

        proxy_http_version 1.1;
        proxy_set_header Connection "";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # 随机接口不允许缓存
        proxy_cache off;
        proxy_no_cache 1;
        proxy_cache_bypass 1;

        # 缓冲保护上游 sync worker
        proxy_buffering on;
        proxy_buffers 16 64k;
        proxy_buffer_size 128k;
        proxy_busy_buffers_size 256k;
        proxy_max_temp_file_size 16m;

        proxy_connect_timeout 5s;
        proxy_read_timeout 60s;
        proxy_send_timeout 60s;

        # 上游 404 JSON 原样透传，不要被 nginx 错误页替换
        proxy_intercept_errors off;
    }
}
```

部署后访问：

- `https://img.example.com/` — 全部图片随机
- `https://img.example.com/day` — day 频道
- `https://img.example.com/channels` — 频道列表
- `https://img.example.com/health` — 健康检查

---

## 场景 B：博客子路径反代

如果不想单独用域名，可以把 API 挂在博客的 `/img/` 路径下：

```nginx
location /img/ {
    proxy_pass http://127.0.0.1:5000/;   # 结尾斜杠：会去掉 /img/ 前缀

    proxy_http_version 1.1;
    proxy_set_header Connection "";
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;

    proxy_cache off;
    proxy_no_cache 1;
    proxy_cache_bypass 1;
}
```

访问 `/img/day` 会被转发为 `/day`，`/img/channels`、`/img/health` 同理。

---

## 验证配置

```bash
# 1) 响应头应带 no-store，Content-Type 正确
curl -sI https://img.example.com/day | grep -iE 'cache-control|content-type'
# Cache-Control: no-store
# Content-Type: image/avif

# 2) Range 应返回 206
curl -sI -H 'Range: bytes=0-99' https://img.example.com/day | head -1
# HTTP/2 206

# 3) 连续请求应换图（no-store 生效）
for i in 1 2 3; do
  curl -s -o /dev/null -w '%{size_download}\n' https://img.example.com/
done
```

---

## 常见坑

| 坑 | 说明 |
|----|------|
| **误开 `proxy_cache`** | 随机接口一旦被缓存，所有人拿到同一张图，随即失效。 |
| **加 `expires`** | 会覆盖上游的 `no-store`，浏览器把 `/day` 缓存数天。 |
| **清空 `Accept` 头** | AVIF 降级机制失效，旧浏览器可能拿到无法渲染的图片。 |
| **关闭 `proxy_buffering`** | 慢客户端直接拖住 gunicorn sync worker，2 个 worker 很快被占满。 |
| **`proxy_intercept_errors on`** | 上游的 404 JSON 会被 nginx 默认错误页替换，接口行为不一致。 |
| **gzip 图片** | 默认 `gzip_types` 不含图片；不要手动加 `image/avif`，压缩已编码图片纯属浪费 CPU。 |
| **真实 IP** | 若前面还有 Cloudflare，需要配置 `real_ip_header CF-Connecting-IP` 与 `set_real_ip_from`。 |
| **健康检查** | 开源版 nginx 没有主动健康检查，可用 `max_fails=3 fail_timeout=30s` 或外部监控定时请求 `/health`。 |
| **HTTPS 混合内容** | 博客是 HTTPS 时，图片地址也必须走 HTTPS，否则浏览器会拦截。 |
| **限流/防盗链** | 公网部署建议加 `limit_req_zone` 限流；`valid_referers` 防盗链注意别误伤友链和阅读器。 |
