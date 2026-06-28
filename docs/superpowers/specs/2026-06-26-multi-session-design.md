# 用户系统设计文档

> Phase 1（多会话）已于 2026-06-28 全部实现并验证。本文档仅保留 Phase 2 用户系统。

## 概述

当前项目为多会话、无用户状态的应用。本文档设计如何升级为多用户系统，每个用户的会话和数据隔离。

---

### 目标

支持用户注册/登录，每个用户拥有独立的会话。

### 1. 用户表（users）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | TEXT (UUID) | 主键 |
| username | TEXT (UNIQUE) | 用户名 |
| password_hash | TEXT | 密码哈希（bcrypt） |
| created_at | TEXT | 注册时间 |

### 2. 改动点

#### sessions 表加 user_id 字段

```sql
ALTER TABLE sessions ADD COLUMN user_id TEXT REFERENCES users(id);
```

#### 新增 API

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/auth/register` | 注册 |
| POST | `/auth/login` | 登录，返回 JWT |
| GET | `/auth/me` | 获取当前用户信息 |
| POST | `/auth/logout` | 登出 |

#### JWT 鉴权

- 登录后前端存 token（localStorage）
- 每次请求带 `Authorization: Bearer <token>`
- 后端中间件验证 token，从请求中提取 `user_id`
- 所有查询都加上 `WHERE user_id=?` 做数据隔离

#### 依赖新增

```
pyjwt
bcrypt 或 passlib[bcrypt]
```

### 3. 前端改动

- 新增 `LoginPage.vue`、`RegisterPage.vue`
- 路由守卫：未登录跳转到登录页
- API 请求统一加 token 头

---

## 非目标

- ~~MySQL 迁移~~（SQLite 完全满足当前数据量，面试不因数据库扣分）
- ~~OAuth/第三方登录~~（不需要）
- ~~权限/角色系统~~（不需要）
- ~~WebSocket~~（SSE 已够用）

---

## 实施顺序

1. 后端：用户表 + 注册/登录 API（`database.py` + `routers/auth.py`）
2. 后端：JWT 中间件 + 会话数据隔离（`session_id` 查询加 `user_id` 过滤）
3. 前端：登录/注册页面 + token 管理 + 路由守卫
4. 部署验证

---

## 自检

- [x] 用户模型满足注册登录基本需求
- [x] API 设计覆盖了注册/登录/鉴权/登出
- [x] 没有 TODO 占位符
- [x] 实施顺序依赖关系正确
- [x] 非目标明确标出
- [x] 迁移路径清晰：ALTER TABLE 加 user_id，不破坏现有数据
