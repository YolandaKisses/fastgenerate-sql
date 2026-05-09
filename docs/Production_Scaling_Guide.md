# FastGenerate SQL 分布式架构改造指南：突破高并发与水平扩展瓶颈

本指南详细说明了当 FastGenerate SQL 从“本地/单机桌面级应用”演进为“支持多并发、多 Worker 的企业级 Web 服务”时，如何重构底层的状态同步与消息推送架构。

## 1. 现存架构的隐患：内存隔离瓶颈

当前 `knowledge_service.py` 中的知识库同步进度推送，采用的是基于内存的 `threading.Condition` 机制。

*   **当前优势**：零依赖（无需安装外部消息中间件），性能极高，非常适合本地单体应用。
*   **生产环境灾难**：在生产环境中，FastAPI 通常通过 Gunicorn/Uvicorn 启动多个 Worker 进程（例如 `--workers 4`）来抗并发。**由于进程间的内存是完全隔离的**：
    *   负责执行后台同步任务的线程可能运行在 Worker A 中。
    *   而用户浏览器发起的监听进度的 SSE (Server-Sent Events) 请求，可能会被 Nginx/LB 路由到 Worker B 中。
    *   **结果**：Worker B 中的 SSE 连接会因为等不到同进程的 Condition 通知而永远阻塞，导致前端进度条卡死在 0%。

---

## 2. 终极架构方案：引入 Redis Pub/Sub 进行解耦

为了实现真正的无状态（Stateless）和水平扩展（Horizontal Scaling），我们需要移除基于进程内存的锁，引入外部的“广播大喇叭”—— **Redis**。

### 架构对比与流转图

改造前后的数据流转面对比如下：

```mermaid
graph TD
    subgraph 改造前（单机内存模式）
        Frontend[前端前端] -->|发起 SSE 监听| Worker1(FastAPI Worker 1)
        Worker1 -->|启动后台同步| SyncThread(后台同步线程)
        SyncThread -->|cond.notify_all| Worker1
        Worker1 -->|返回 SSE 数据| Frontend
    end

    subgraph 改造后（Redis 分布式模式）
        Frontend2[前端前端] -->|发起 SSE 监听| WorkerB(FastAPI Worker B)
        Frontend2 -->|发起同步指令| WorkerA(FastAPI Worker A)
        
        WorkerA -->|执行数据库同步| WorkerA
        WorkerA -.->|每同步一张表 PUBLISH| Redis[(Redis Pub/Sub)]
        
        Redis -.->|广播同步进度| WorkerB
        WorkerB -->|SUBSCRIBE 并推送 SSE| Frontend2
    end
```

---

## 3. 具体改造蓝图与核心代码参考

如果决定上生产环境，可参考以下伪代码进行重构。

### 第一步：准备 Redis 客户端
在 FastAPI 项目中引入异步/同步的 Redis 客户端（如 `redis-py` 或 `aioredis`）。

### 第二步：改造生产者（Producer）—— `knowledge_service.py`
移除 `_channels` 和 `threading.Condition`，改为向 Redis 发布消息。

```python
import redis
import json

redis_client = redis.Redis(host='localhost', port=6379, db=0)

def sync_datasource_knowledge(session: Session, task_id: int, datasource_id: int):
    # ... 前期准备逻辑保持不变 ...

    for index, item in enumerate(payload, 1):
        # ... 同步并写入 Markdown ...
        
        # 【修改点】：不再使用 cond.notify_all()
        # 而是将当前进度序列化后发布到属于这个 task 的独立频道
        progress_data = {
            "version": version,
            "processed": index,
            "total": total,
            "table": table_name
        }
        redis_client.publish(
            f"sync_channel_{task_id}", 
            json.dumps(progress_data)
        )
        
    # 结束后发送完成标识
    redis_client.publish(f"sync_channel_{task_id}", json.dumps({"status": "completed"}))
```

### 第三步：改造消费者（Consumer）—— SSE 路由
修改前端获取事件流的路由，让它去订阅 Redis 的对应频道，而不再是通过 `yield` 死等内存通知。

```python
from fastapi.responses import StreamingResponse
import asyncio

@router.get("/{task_id}/events")
async def get_sync_events(task_id: int):
    
    async def event_generator():
        # 获取异步 Redis 客户端
        pubsub = async_redis_client.pubsub()
        await pubsub.subscribe(f"sync_channel_{task_id}")
        
        # 持续监听频道消息
        async for message in pubsub.listen():
            if message['type'] == 'message':
                data = json.loads(message['data'])
                
                # 推送给前端
                yield f"data: {json.dumps(data)}\n\n"
                
                # 如果收到完成信号，关闭连接
                if data.get("status") == "completed":
                    break

        await pubsub.unsubscribe(f"sync_channel_{task_id}")

    return StreamingResponse(event_generator(), media_type="text/event-stream")
```

---

## 4. 总结

引入 Redis Pub/Sub 后：
1. **彻底无状态**：FastAPI 后端不再持有业务状态的内存锁，可以随时增加、重启、销毁 Worker 节点，完全不影响正在进行的任务通知。
2. **多端同步能力**：因为数据在中间件广播，同一个账户在电脑 A 和电脑 B 上同时打开页面，两边能看到完全同步的进度条。

**声明**：对于个人桌面端或无需大规模水平扩容的内部轻量级部署，保留目前的 `threading.Condition` 依然是**性能最好、最省心（免安装中间件）**的选择。本指南仅在遇到高并发拓展需求时作为技术升级路线图。
