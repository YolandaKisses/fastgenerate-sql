# FastGenerate SQL

FastGenerate SQL 是一个本地运行的 SQL 工作台项目，前端使用 Vue/Vite，后端使用 FastAPI。

## 本地数据库

项目使用本地 SQLite 作为应用运行数据库。数据库文件不会随代码仓库提交，首次启动后端服务时会自动生成：

```text
~/.fastgenerate_sql_data/fastgenerate.db
```

生产或容器化部署时，必须设置固定的 `AUTH_TOKEN_SECRET`，并将 `DATA_DIR` 指向持久化卷，避免重启后登录态失效或本地 SQLite 数据丢失。

后端启动流程会自动完成：

- 创建本地数据目录
- 创建 SQLite 数据库文件
- 根据 SQLModel 模型创建表结构
- 初始化默认管理员账号

默认登录账号：

```text
账号：admin
密码：888888
```

如果需要重置本地数据，可以停止后端服务后删除 `~/.fastgenerate_sql_data/fastgenerate.db`，下次启动会重新创建空数据库并初始化默认账号。

## 启动开发环境

安装前端依赖：

```bash
npm install
```

启动前端：

```bash
npm run dev
```

安装后端依赖：

```bash
cd api
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

启动后端：

```bash
uvicorn app.main:app --reload
```
