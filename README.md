# cotton-filter

`cotton-filter` 是一个用于筛选 Excel 棉花资源表的桌面工具。当前架构是：

```text
Tauri 桌面壳
  -> React/Vite 前端
  -> Python FastAPI 本地后端 sidecar
  -> pandas/openpyxl/xlrd 处理 Excel
```

Tauri 负责窗口、安装包、自动更新、文件选择、打开目录、启动/停止后端。Python 负责 Excel 解析、字段匹配、评分、筛选和写出结果。

## 环境要求

本地需要安装：

- Node.js 24 或兼容版本
- Rust stable
- Python 3.10
- uv
- macOS/Windows 对应的 Tauri 系统依赖

检查命令：

```bash
node --version
npm --version
rustc --version
cargo --version
python3 --version
uv --version
```

## 安装依赖

在项目根目录执行：

```bash
cd /Users/zhaodesen/Movies/cotton_filter
uv sync
npm install
```

## 本地启动

```bash
npm run dev
```

这个命令会自动执行：

1. 用 PyInstaller 构建 Python 后端 sidecar。
2. 启动 Vite 前端开发服务。
3. 启动 Tauri 桌面窗口。
4. 前端通过 Tauri shell plugin 启动本地 Python 后端。

后端只监听 `127.0.0.1`，端口由前端在 `18763` 起的一段范围内随机选择。界面日志中会显示类似：

```text
准备启动 Python 后端: http://127.0.0.1:18xxx
Python 后端已启动
```

## 常用开发命令

只构建 Python sidecar：

```bash
npm run build:backend
```

只检查 TypeScript：

```bash
npx tsc -b
```

只检查 Rust/Tauri：

```bash
cargo check --manifest-path src-tauri/Cargo.toml
```

运行 Python 测试：

```bash
uv run --with pytest python -m pytest
```

构建前端静态文件：

```bash
npm run build:frontend
```

## 本地打包

普通打包：

```bash
npm run build
```

如果启用了 Tauri updater，打包时需要 updater 签名私钥。当前本机私钥路径是：

```text
/Users/zhaodesen/.tauri/cotton-filter.key
```

使用本机私钥打包：

```bash
TAURI_SIGNING_PRIVATE_KEY="$(cat /Users/zhaodesen/.tauri/cotton-filter.key)" \
TAURI_SIGNING_PRIVATE_KEY_PASSWORD="" \
npm run build
```

构建产物输出在：

```text
src-tauri/target/release/bundle/
```

macOS 常见产物：

```text
src-tauri/target/release/bundle/dmg/*.dmg
src-tauri/target/release/bundle/macos/*.app
src-tauri/target/release/bundle/macos/*.app.tar.gz
src-tauri/target/release/bundle/macos/*.sig
```

Windows 常见产物：

```text
src-tauri/target/release/bundle/**/*.exe
src-tauri/target/release/bundle/**/*.msi
src-tauri/target/release/bundle/**/*.sig
```

## 自动更新

项目使用 Tauri v2 官方 updater plugin。

配置位置：

- `src-tauri/tauri.conf.json`
- `scripts/write-updater-manifest.mjs`
- `.github/workflows/build.yml`

发布可自动更新版本时，GitHub Actions 需要配置 secret：

```text
TAURI_SIGNING_PRIVATE_KEY
TAURI_SIGNING_PRIVATE_KEY_PASSWORD
```

当前私钥没有密码，所以 `TAURI_SIGNING_PRIVATE_KEY_PASSWORD` 可以为空。

手动生成 updater manifest：

```bash
GITHUB_REF_NAME=v1.2.3 \
GITHUB_REPOSITORY=zhaodesen/cotton-filter \
npm run manifest:updater
```

manifest 输出在：

```text
dist/updater/
```

## 项目结构

```text
backend/
  server.py                Python FastAPI 本地后端

cotton_filter_app/
  constants.py             共享应用常量
  rules.py                 SQLite 规则库和默认规则初始化
  text_utils.py            表头/规则文本标准化
  header.py                Excel 表头识别和字段映射
  scoring.py               基于数据规则计算棉花评分
  processor.py             sheet/workbook 处理
  file_utils.py            批量文件处理和输出路径

src/
  App.tsx                  React 主界面
  RulesView.tsx            列名规则和数据规则维护页
  api.ts                   本地 API 调用
  backend.ts               Tauri sidecar 启动/停止
  styles.css               界面样式

src-tauri/
  tauri.conf.json          Tauri 配置
  capabilities/            Tauri 权限
  src/                     Rust 启动入口

scripts/
  build-backend.mjs        构建 Python sidecar
  write-updater-manifest.mjs
```

## 常见问题

### Python 后端启动失败: shell.spawn not allowed

说明 Tauri shell 权限没有生效。检查：

```text
src-tauri/capabilities/default.json
```

需要包含：

```json
"shell:allow-spawn"
```

修改后关闭旧 Tauri 窗口，重新运行：

```bash
npm run dev
```

### Python 后端启动超时: TypeError: Load failed

常见原因是旧 sidecar 没重建或后端 CORS 配置没有生效。执行：

```bash
npm run build:backend
npm run dev
```

如果仍失败，查看界面日志中的 `[backend]` 输出。

### No module named pytest

本项目没有把 pytest 固定在运行依赖里。测试时使用：

```bash
uv run --with pytest python -m pytest
```

### Tauri build 提示没有私钥

启用了 updater 产物时，需要传入：

```bash
TAURI_SIGNING_PRIVATE_KEY
TAURI_SIGNING_PRIVATE_KEY_PASSWORD
```

本机可用：

```bash
TAURI_SIGNING_PRIVATE_KEY="$(cat /Users/zhaodesen/.tauri/cotton-filter.key)" \
TAURI_SIGNING_PRIVATE_KEY_PASSWORD="" \
npm run build
```

## 维护原则

- 不要恢复 Tkinter。
- 不要恢复旧 `main.py` GUI 入口。
- 不要恢复 Inno Setup 旧打包链路。
- Excel 筛选核心逻辑继续放在 `cotton_filter_app/`。
- 新增 Excel 模板优先在“规则维护”里添加列名规则，不要把客户列名写死到 Python 常量里。
- 列名规则按标准字段分组维护，标准字段不可编辑；新增别名使用弹框录入，页面只提供新增/删除。
- 数据识别、评分区间和过滤区间优先通过本地 SQLite 数据规则维护。
- 保持中文日志和中文输出列名。
