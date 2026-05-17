"""FastAPI sidecar service for cotton-filter."""

from __future__ import annotations

import argparse
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from cotton_filter_app.build_info import BUILD_VERSION
from cotton_filter_app.constants import APP_NAME
from cotton_filter_app.file_utils import default_output_dir, expand_targets, filter_files


class ExpandRequest(BaseModel):
    """待展开的文件或目录路径。"""

    targets: list[str] = Field(default_factory=list)


class ExpandResponse(BaseModel):
    """展开后的 Excel 文件路径。"""

    files: list[str]


class DefaultOutputRequest(BaseModel):
    """根据输入文件计算默认输出目录。"""

    files: list[str] = Field(default_factory=list)


class DefaultOutputResponse(BaseModel):
    """默认输出目录。"""

    output_dir: str


class FilterRequest(BaseModel):
    """筛选请求。"""

    files: list[str] = Field(default_factory=list)
    output_dir: str | None = None


class FileResultResponse(BaseModel):
    """单个文件筛选结果。"""

    src: str
    out: str | None
    kept: int
    error: str | None = None


class FilterResponse(BaseModel):
    """批量筛选结果。"""

    output_dir: str
    total_files: int
    total_kept: int
    results: list[FileResultResponse]
    logs: list[str]


def create_app() -> FastAPI:
    """创建本地 API 应用。"""

    app = FastAPI(title=APP_NAME, version=BUILD_VERSION)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "tauri://localhost",
            "http://tauri.localhost",
            "https://tauri.localhost",
        ],
        allow_origin_regex=r"^http://(localhost|127\.0\.0\.1):\d+$",
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"app": APP_NAME, "version": BUILD_VERSION, "status": "ok"}

    @app.post("/api/expand", response_model=ExpandResponse)
    def expand(request: ExpandRequest) -> ExpandResponse:
        paths = expand_targets(request.targets)
        return ExpandResponse(files=[str(path.resolve()) for path in paths])

    @app.post("/api/default-output-dir", response_model=DefaultOutputResponse)
    def default_output(request: DefaultOutputRequest) -> DefaultOutputResponse:
        paths = [Path(path) for path in request.files]
        if not paths:
            raise HTTPException(status_code=400, detail="请先选择 Excel 文件")
        return DefaultOutputResponse(output_dir=str(default_output_dir(paths).resolve()))

    @app.post("/api/filter", response_model=FilterResponse)
    def filter_excel(request: FilterRequest) -> FilterResponse:
        files = [Path(path) for path in request.files]
        if not files:
            raise HTTPException(status_code=400, detail="请先选择 Excel 文件")

        out_dir = Path(request.output_dir) if request.output_dir else default_output_dir(files)
        logs: list[str] = ["开始筛选"]
        results = filter_files(files, out_dir, progress_callback=logs.append)
        total_kept = sum(result.kept for result in results)
        logs.append(f"筛选完成: 共 {len(results)} 个文件，命中 {total_kept} 行")

        return FilterResponse(
            output_dir=str(out_dir.resolve()),
            total_files=len(results),
            total_kept=total_kept,
            logs=logs,
            results=[
                FileResultResponse(
                    src=str(result.src.resolve()),
                    out=str(result.out.resolve()) if result.out else None,
                    kept=result.kept,
                    error=result.error,
                )
                for result in results
            ],
        )

    return app


def parse_args() -> argparse.Namespace:
    """解析 sidecar 启动参数。"""

    parser = argparse.ArgumentParser(description="cotton-filter local backend")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=18763)
    return parser.parse_args()


def main() -> None:
    """启动本地 API 服务。"""

    args = parse_args()
    print(f"LISTENING http://{args.host}:{args.port}", flush=True)
    uvicorn.run(
        create_app(),
        host=args.host,
        port=args.port,
        log_level="warning",
        access_log=False,
    )


if __name__ == "__main__":
    main()
