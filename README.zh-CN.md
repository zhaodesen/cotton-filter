# Cotton Filter

一个用于筛选、评分并导出棉花资源 Excel 工作簿的跨平台桌面工具。

[English](./README.md) | [简体中文](./README.zh-CN.md)

## 项目简介

Cotton Filter 由 Tauri 桌面壳、React 界面和本地 Python 服务组成。Tauri 负责原生窗口、文件选择、打包和更新；Python 负责 Excel 解析、表头匹配、规则评分、筛选及结果生成。

```text
Tauri 桌面应用
  └── React + Vite 界面
        └── 本地 FastAPI sidecar
              └── pandas / openpyxl / xlrd
```

## 主要功能

- 处理单个或多个 Excel 工作簿
- 通过可维护的别名规则适配不同列名
- 在本地 SQLite 中维护评分与筛选规则
- 导出筛选结果，并保留中文日志和输出列名
- 使用 Tauri 2 打包 macOS 与 Windows 应用
- 为 GitHub Releases 生成自动更新产物

## 环境要求

- Node.js 24 或兼容版本
- Rust stable
- Python 3.10
- [uv](https://docs.astral.sh/uv/)
- 当前平台对应的 Tauri 系统依赖

## 快速开始

```bash
uv sync
npm install
npm run dev
```

开发命令会构建 Python sidecar、启动 Vite 并打开 Tauri 应用。本地 API 仅监听 `127.0.0.1`，端口由应用动态选择。

## 常用开发命令

| 命令 | 说明 |
| --- | --- |
| `npm run dev` | 运行完整桌面应用 |
| `npm run build:backend` | 构建 Python sidecar |
| `npm run build:frontend` | 构建 sidecar 与前端资源 |
| `npm run build` | 使用 Tauri 生成平台安装包 |
| `uv run --with pytest python -m pytest` | 运行 Python 测试 |
| `cargo check --manifest-path src-tauri/Cargo.toml` | 检查 Rust 项目 |

## 项目结构

```text
backend/             # FastAPI sidecar 入口
cotton_filter_app/   # Excel 处理与规则引擎
src/                 # React 用户界面
src-tauri/           # Tauri 配置与 Rust 入口
scripts/             # sidecar 构建、版本与更新脚本
```

## 打包与更新

```bash
npm run build
```

发布自动更新产物时，需要通过本机环境变量或 GitHub Actions Secrets 提供 `TAURI_SIGNING_PRIVATE_KEY` 与 `TAURI_SIGNING_PRIVATE_KEY_PASSWORD`。不要把签名私钥提交到仓库。

## 维护约定

- Excel 处理逻辑统一保留在 `cotton_filter_app/`。
- 客户特有列名通过别名规则维护，不写死到代码常量中。
- 数据识别、评分区间和过滤条件优先使用 SQLite 规则。
- 后端保持本地运行，并保留中文日志和中文导出列名。
