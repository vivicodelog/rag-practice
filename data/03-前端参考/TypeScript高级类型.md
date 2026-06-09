# TypeScript 高级类型

## 泛型

泛型允许在定义函数、接口或类时不指定具体类型，而在使用时再确定。

```typescript
function identity<T>(arg: T): T {
  return arg;
}
```

## 条件类型

根据条件动态确定类型。

```typescript
type IsString<T> = T extends string ? true : false;
```

## 映射类型

基于已有类型创建新类型。

```typescript
type Readonly<T> = {
  readonly [P in keyof T]: T[P];
};
```

## 工具类型

TypeScript 内置了常用的工具类型：

- `Partial<T>` — 将所有属性变为可选
- `Required<T>` — 将所有属性变为必选
- `Pick<T, K>` — 从 T 中选取部分属性
- `Omit<T, K>` — 从 T 中排除部分属性
- `Record<K, V>` — 创建键值对类型

## 实际应用

在 RAG 项目的 API 层中，用 TypeScript 定义请求和响应类型可以保证前后端数据类型一致。

```typescript
interface ChatRequest {
  question: string;
  history?: { role: string; content: string }[];
}

interface ChatResponse {
  answer: string;
  sources: { filename: string; score: number }[];
}
```
