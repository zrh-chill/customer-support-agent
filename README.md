# customer-support-agent

一个面向 SaaS 场景的智能客服助理项目，支持 FAQ 优先回答、业务工具调用、工单升级、人工接管和客服后台展示。

## 功能概览

- 6 类意图识别：`account_issue`、`billing_issue`、`refund_request`、`technical_problem`、`general_faq`、`human_support`
- FAQ 优先命中，本地 `seed/faq.json` 可直接维护
- 4 个业务工具：`get_user_profile`、`get_user_orders`、`get_subscription_status`、`create_ticket`
- SQLite 持久化：用户、订单、订阅、会话、消息、工单、Agent 决策日志
- React 三栏后台：会话列表、聊天窗口、用户上下文和 Agent 判断
- 高风险 guardrail：退款默认转人工并创建高优先级工单
- 会话满意度评价和人工接管按钮

## 技术栈

- Backend: FastAPI, Pydantic, SQLite
- Agent: PydanticAI with rule-based fallback
- Frontend: React + Vite
- Testing: pytest

## 业务流程图

```text
用户消息进入
  -> Agent 识别意图
  -> FAQ 优先查询
      -> 命中 FAQ: 直接回复用户
      -> 未命中 FAQ: 调用业务工具查询用户上下文
          -> 能结合上下文解答: 返回答案并展示上下文
          -> 无法解答或请求高风险操作: 创建/升级工单
              -> 可由客服后台点击人工接管
  -> 每次决策写入日志并展示在后台右侧面板
```

## 项目结构

```text
app/
  api/                FastAPI 路由
  agent/              Agent 决策逻辑
  repositories/       SQLite 数据访问
  schemas/            Pydantic 类型定义
  services/           FAQ、工具和客服编排
frontend/             React 后台
seed/                 FAQ 种子数据
tests/                单元与接口测试
```

## 本地运行

### 1. 安装后端依赖

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### 2. 启动后端

```bash
uvicorn app.main:app --reload
```

后端默认运行在 `http://127.0.0.1:8000`。

### 3. 启动前端

```bash
cd frontend
npm install
npm run dev
```

前端默认运行在 `http://127.0.0.1:5173`，并通过 Vite 代理访问后端 API。

### 4. 可选的模型增强

如果你想启用 `PydanticAI` 的模型调用能力，可以复制 `.env.example` 并设置：

```bash
pip install -e ".[llm]"
OPENAI_API_KEY=your_key
LLM_MODEL=openai:gpt-4o-mini
```

如果没有配置模型密钥，系统会自动退回规则式 Agent，依然可以完整演示项目流程。

## 数据模型

- `users`: mock 用户资料
- `orders`: 用户订单记录
- `subscriptions`: 订阅状态
- `tickets`: 工单与状态流转
- `conversations`: 会话状态与满意度
- `messages`: 用户与 Agent 消息
- `agent_decisions`: 每次 Agent 决策日志

## API 概览

- `POST /api/chat/sessions` 创建或恢复会话
- `GET /api/chat/sessions` 获取会话列表
- `GET /api/chat/sessions/{id}` 获取会话详情、上下文和日志结果
- `POST /api/chat/sessions/{id}/messages` 发送消息并触发 Agent
- `POST /api/tickets/{id}/handoff` 人工接管工单
- `POST /api/chat/sessions/{id}/feedback` 提交满意度评价
- `GET /api/faqs` 查看 FAQ 列表

统一返回结构围绕以下几块组织：

- `session`
- `messages`
- `context`
- `decision`
- `ticket`

## 演示脚本

可以用下面四条典型流程做演示：

1. 重置密码
   - 用户输入：`如何重置密码？`
   - 预期：FAQ 命中，直接回复，不创建工单
2. 订阅与账单查询
   - 用户输入：`我的账单有问题，帮我看看最近订单和订阅状态`
   - 预期：触发订单与订阅工具调用，右侧面板显示上下文
3. 退款请求
   - 用户输入：`我想退款，请尽快处理`
   - 预期：命中高风险 guardrail，创建高优先级工单并提示人工确认
4. 人工转接
   - 用户输入：`帮我转人工客服`
   - 预期：创建工单，点击后台 `Human Takeover` 后状态变为 `handed_off`

## 测试

```bash
pytest
```

测试覆盖：

- 6 类意图识别
- FAQ 优先回复
- 业务工具调用
- 工单创建与高风险 guardrail
- 人工接管与满意度评价 API
