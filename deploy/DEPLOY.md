# FastGenerate SQL 生产部署说明

## 推荐目录结构

```text
/opt/fastgenerate-sql/
  app/
    api/
    frontend-dist/
  data/
    app/
    wiki/
  logs/
```

## 1. 构建前端

在项目根目录执行：

```bash
npm install
npm run build
```

执行后会生成 `dist/`。

## 2. 准备后端目录

在服务器上执行：

```bash
mkdir -p /opt/fastgenerate-sql/app
mkdir -p /opt/fastgenerate-sql/data/app
mkdir -p /opt/fastgenerate-sql/data/wiki
mkdir -p /opt/fastgenerate-sql/logs
```

将项目中的 `api/` 目录上传到：

```text
/opt/fastgenerate-sql/app/api
```

然后创建 Python 虚拟环境并安装依赖：

```bash
cd /opt/fastgenerate-sql/app/api
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## 3. 配置后端环境变量

将以下环境文件：

```text
deploy/fastgenerate-sql.env
```

复制到：

```text
/etc/fastgenerate-sql/fastgenerate-sql.env
```

然后至少填写这些配置：

- `AUTH_TOKEN_SECRET`
- `DEEPSEEK_API_KEY`
- `ALLOWED_ORIGINS`
- `ORACLE_CLIENT_PATH`，如果生产环境需要 Oracle Thick Mode

## 4. 安装 systemd 服务

将以下文件：

```text
deploy/fastgenerate-sql-api.service
```

复制到：

```text
/etc/systemd/system/fastgenerate-sql-api.service
```

然后执行：

```bash
sudo systemctl daemon-reload
sudo systemctl enable fastgenerate-sql-api
sudo systemctl restart fastgenerate-sql-api
sudo systemctl status fastgenerate-sql-api
```

## 5. 部署前端静态文件

将构建后的 `dist/` 内容复制到：

```text
/opt/fastgenerate-sql/app/frontend-dist
```

## 6. 配置 Nginx

将以下模板文件：

```text
deploy/nginx.fastgenerate-sql.conf
```

复制到你的 Nginx 站点配置位置，然后把：

```text
your-domain.example
```

替换成你自己的实际域名。

之后执行：

```bash
sudo nginx -t
sudo systemctl reload nginx
```

## 7. 后续升级流程

以后升级时建议按这个顺序操作：

1. 备份 `/opt/fastgenerate-sql/data/app`
2. 备份 `/opt/fastgenerate-sql/data/wiki`
3. 重新构建前端：`npm run build`
4. 上传新的 `dist/`
5. 上传新的 `api/`
6. 如果 `requirements.txt` 变了，重新安装 Python 依赖
7. 重启 `fastgenerate-sql-api`

## 注意事项

- 不要把 wiki markdown 放进前端 `dist/`
- `DATA_DIR` 和 `WIKI_ROOT` 必须放在持久化目录
- 前端是通过 `/api/v1/wiki/tree` 和 `/api/v1/wiki/content` 读取知识库内容的
