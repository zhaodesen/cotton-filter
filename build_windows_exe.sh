#!/bin/bash
# 在 Mac/Linux 上用 Docker 构建 Windows .exe (无需 Python 环境)
set -e
cd "$(dirname "$0")"

IMAGE="batonogov/pyinstaller-windows:latest"

echo "[1/3] 拉取打包镜像..."
docker pull --platform linux/amd64 "$IMAGE"

echo "[2/3] 打包 cotton_filter.py → 单文件 exe ..."
docker run --rm --platform linux/amd64 \
    -v "$(pwd):/src" \
    -e PYINSTALLER_COMMAND="pyinstaller --onefile --name 棉花筛选 --clean cotton_filter.py" \
    "$IMAGE"

echo "[3/3] 完成"
# batonogov 默认输出到 /src/dist
EXE="dist/棉花筛选.exe"
if [ -f "$EXE" ]; then
    ls -lh "$EXE"
    echo ""
    echo "✓ 把这一个文件发给同事即可:"
    echo "   $(pwd)/$EXE"
else
    echo "✗ 构建失败,检查上面日志"
    ls -la dist/ 2>/dev/null || true
    exit 1
fi
