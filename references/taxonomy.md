# L1 知识分类体系（适配本 Vault 真实结构）

> 本文件描述配置中 `vault_root`（见 Skill 根目录 `config.json`）指向的 Vault 的实际目录结构。
> 根层为 `10-项目/`、`20-领域/`、`30-资源/`、`40-归档/`、`99-每日笔记/`、`99-模板/`。
> 本 Vault 使用**中文目录命名**（非 01-15 编号），归类按技术栈语义匹配。

## 目录结构总览

```
20-领域/编程/
├── 前端开发/                    # 所有前端技术栈的总目录
│   ├── HTML-CSS基础/            # HTML 标签、CSS 样式/布局/盒模型
│   │   ├── 01-HTML/
│   │   └── 02-CSS/
│   ├── JavaScript/              # JS 语言核心
│   │   ├── 01-数据类型与结构/    # Map/Object/原型链/JSON
│   │   ├── 02-数组方法/          # map/forEach/filter/split/join
│   │   ├── 03-变量与作用域/      # var/let/const/闭包/作用域
│   │   ├── 04-函数/             # this/箭头函数/回调/导出
│   │   ├── 05-语法特性/         # 解构/拓展运算符/运算符/DOM/localStorage
│   │   └── 06-异步编程/         # Promise/async-await/Error/try-catch
│   ├── TypeScript/              # TS 类型系统（类型注解/断言/interface/泛型）
│   ├── Vue/                     # Vue 框架（2.x + 3.x）
│   │   ├── 01-核心概念/          # 生命周期/指令/响应式/computed/watch
│   │   ├── 02-Vue2/             # Vue 2 专属（含 vuex）
│   │   ├── 03-Vue3/             # Vue 3 专属（组合式 API/Store）
│   │   ├── 04-路由/             # Vue Router
│   │   └── 05-插件与配置/        # 插件/app.config/globalProperties
│   ├── 网络与HTTP/              # HTTP 请求、Axios、Fetch
│   │   ├── 01-基础概念/
│   │   ├── Axios/
│   │   └── Fetch/
│   ├── 数据可视化/              # Canvas、SVG、图表、图例设计
│   └── 工程化/                  # 构建工具、命名规范、代码片段、Emmet、Vite
├── 后端与数据库/                # 后端 + 数据库合集
│   ├── 后端框架/                # Node/Express/REST/ORM/FastAPI/sequelize
│   └── 数据库/                  # SQL/MySQL/表连接/Schema
├── WebGIS/                      # GIS 技术栈
│   └── GIS与地图/               # Leaflet/Cesium/Turf/高德/天地图/GeoServer/GeoJSON
├── AI与数据科学/                # AI / ML / 算法 / 点云
│   ├── 机器学习/                # ML/DL 算法、PointNet、神经网络
│   ├── AI与智能体/              # Agent/LLM/智能体/Prompt
│   ├── 算法/                    # 数据结构与算法
│   └── 点云处理/                # 点云算法、体积计算、凸包、协方差、栅格
├── Git/                         # Git 配置、仓库管理、GitHub
├── Python/                      # Python 语法/库（pandas/f-string/pathlib 等）
├── 知识点清单/                  # 各技术栈的"知识点清单"汇总文件
└── 学习路径/                    # 所有 *学习路径.md
```

---

## 归类规则

### 规则 1：按技术栈匹配（顶层目录）

| 文件关键词/特征 | 归属目录 |
|---------------|---------|
| 含 `<html>`, `<div>`, `<img>`, HTML 标签, `css`, `样式`, `盒模型`, `flex`, `grid`, `选择器` | `前端开发/HTML-CSS基础/` |
| 纯 JavaScript 语法/API，无框架（含 `=`/`==`/`===` 运算符、`let`/`const`/数组/异步） | `前端开发/JavaScript/` |
| 含 `type`, `interface`, `泛型`, `TypeScript`, 类型注解/断言 | `前端开发/TypeScript/` |
| 含 `Vue`, `v-`, `vue`, `组件`, `vuex`, `pinia` | `前端开发/Vue/` |
| 含 `axios`, `fetch`, `HTTP`, `请求`, `AJAX`, `API调用` | `前端开发/网络与HTTP/` |
| 含 `Canvas`, `SVG`, `图表`, `图例`, `可视化` | `前端开发/数据可视化/` |
| 含 `Vite`, `Webpack`, `命名`, `Emmet`, `代码片段`, `构建` | `前端开发/工程化/` |
| 含 `express`, `Node`, `后端`, `ORM`, `REST`, `FastAPI`, `API设计` | `后端与数据库/后端框架/` |
| 含 `SQL`, `MySQL`, `数据库`, `表`, `查询`, `Schema` | `后端与数据库/数据库/` |
| 含 `Leaflet`, `Cesium`, `Turf`, `高德`, `天地图`, `GIS`, `地图`, `GeoJSON`, `GeoServer` | `WebGIS/GIS与地图/` |
| 含 `机器学习`, `ML`, `神经网络`, `PointNet`, `MLP` | `AI与数据科学/机器学习/` |
| 含 `Agent`, `LLM`, `AI`, `智能体`, `Prompt` | `AI与数据科学/AI与智能体/` |
| 含 `算法`, `排序`, `复杂度`, `数据结构` | `AI与数据科学/算法/` |
| 含 `点云`, `凸包`, `体积计算`, `协方差`, `栅格` | `AI与数据科学/点云处理/` |
| 含 `git`, `github`, `分支`, `commit`, `仓库` | `Git/` |
| 含 `python`, `pandas`, `f-string`, `pathlib`, `推导式` | `Python/` |
| 各技术栈的"知识点清单"汇总 | `知识点清单/` |
| `*学习路径.md` | `学习路径/` |

### 规则 2：按子目录细化

**前端开发/JavaScript 子目录匹配：**

| 关键词 | 子目录 |
|--------|--------|
| `Map`, `Object`, `原型`, `继承`, `JSON`, `数据结构` | `01-数据类型与结构/` |
| `数组`, `map`, `forEach`, `filter`, `split`, `join` | `02-数组方法/` |
| `变量`, `作用域`, `闭包`, `var`, `let`, `const` | `03-变量与作用域/` |
| `函数`, `this`, `箭头`, `回调`, `参数`, `export` | `04-函数/` |
| `解构`, `拓展`, `DOM`, `localStorage`, `运算符`, `for` | `05-语法特性/` |
| `Promise`, `async`, `await`, `Error`, `try-catch`, `异步` | `06-异步编程/` |

**前端开发/Vue 子目录匹配：**

| 关键词 | 子目录 |
|--------|--------|
| `v-bind`, `v-model`, `v-for`, `computed`, `watch`, `生命周期`, `指令`, `ref` | `01-核心概念/` |
| `Vue2`, `$emit`, `$event`, `vuex`, `.sync` | `02-Vue2/` |
| `Vue3`, `组合式`, `composable`, `setup`, `pinia` | `03-Vue3/` |
| `router`, `路由`, `导航` | `04-路由/` |
| `插件`, `install`, `app.config`, `globalProperties` | `05-插件与配置/` |

**WebGIS/GIS与地图 子目录匹配：** `Leaflet/`、`Cesium/`、`Turf/`、`高德地图/`、`天地图/`、`GeoServer/` 按具体地图库名归位；通用 GIS 概念（偏移/技术栈/GeoJSON 格式）放 `GIS与地图/` 根。

### 规则 3：跨域文件优先级

有些文件涉及多个技术栈，按以下优先级决定归属：

1. **框架优先**：Vue + Axios → `前端开发/Vue/`（Vue 语境下的用法）
2. **核心概念优先**：Axios 拦截器但纯 Axios 教程 → `前端开发/网络与HTTP/`
3. **项目优先**：如果文件引用了项目代码路径 → L3（`10-项目/`）

### 规则 4：L2 疑问文件

命名约定：与对应 L1 知识放在同一目录，文件名 `疑问.md` 或在原文件名后加 `-疑问`。
例如：
- `前端开发/JavaScript/06-异步编程/Promise疑问.md`
- `WebGIS/GIS与地图/疑问.md`（已存在示范）
- `前端开发/Vue/01-核心概念/疑问.md`

### 规则 5：学习路径

所有 `*学习路径.md` 文件统一放在 `学习路径/`，不随技术栈分布。

---

## 不可分类的放哪

| 文件类型 | 位置 |
|---------|------|
| 学习方法论 | `20-领域/学习方法论/` |
| 软件使用教程 | `30-资源/工具/01-软件使用/` |
| Excalidraw 绘图 | `30-资源/工具/02-Excalidraw/` |
| 图片/PDF 附件 | `30-资源/媒体附件/` |
| 每日笔记 | `99-每日笔记/` |
| 模板 | `99-模板/` |
| AI 对话记录 | 不单独存档，有价值的问答归入 L2 疑问或 `问答记录.md` |
