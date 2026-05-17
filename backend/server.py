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
from cotton_filter_app.rules import ColumnRule, DataRule, RuleRepository


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


class ColumnRulePayload(BaseModel):
    """列名规则提交数据。"""

    field_name: str | None = None
    alias: str | None = None
    enabled: bool | None = None
    sort_order: int | None = None
    notes: str | None = None


class ColumnRuleResponse(BaseModel):
    """列名规则响应。"""

    id: int
    field_name: str
    alias: str
    alias_key: str
    enabled: bool
    sort_order: int
    notes: str


class DataRulePayload(BaseModel):
    """数据规则提交数据。"""

    field_name: str | None = None
    rule_name: str | None = None
    rule_type: str | None = None
    match_value: str | None = None
    min_value: float | None = None
    max_value: float | None = None
    min_inclusive: bool | None = None
    max_inclusive: bool | None = None
    score_delta: int | None = None
    output_value: str | None = None
    enabled: bool | None = None
    sort_order: int | None = None
    notes: str | None = None


class DataRuleResponse(BaseModel):
    """数据规则响应。"""

    id: int
    field_name: str
    rule_name: str
    rule_type: str
    match_value: str
    match_key: str
    min_value: float | None
    max_value: float | None
    min_inclusive: bool
    max_inclusive: bool
    score_delta: int | None
    output_value: str
    enabled: bool
    sort_order: int
    notes: str


class RulesResponse(BaseModel):
    """规则总览响应。"""

    database_path: str
    column_rules: list[ColumnRuleResponse]
    data_rules: list[DataRuleResponse]


def model_payload(model: BaseModel) -> dict[str, object]:
    """兼容 Pydantic v1/v2 的局部更新 payload。"""

    if hasattr(model, "model_dump"):
        return model.model_dump(exclude_unset=True)
    return model.dict(exclude_unset=True)


def column_rule_response(rule: ColumnRule) -> ColumnRuleResponse:
    return ColumnRuleResponse(
        id=rule.id or 0,
        field_name=rule.field_name,
        alias=rule.alias,
        alias_key=rule.alias_key,
        enabled=rule.enabled,
        sort_order=rule.sort_order,
        notes=rule.notes,
    )


def data_rule_response(rule: DataRule) -> DataRuleResponse:
    return DataRuleResponse(
        id=rule.id or 0,
        field_name=rule.field_name,
        rule_name=rule.rule_name,
        rule_type=rule.rule_type,
        match_value=rule.match_value,
        match_key=rule.match_key,
        min_value=rule.min_value,
        max_value=rule.max_value,
        min_inclusive=rule.min_inclusive,
        max_inclusive=rule.max_inclusive,
        score_delta=rule.score_delta,
        output_value=rule.output_value,
        enabled=rule.enabled,
        sort_order=rule.sort_order,
        notes=rule.notes,
    )


def rule_error(error: Exception) -> HTTPException:
    if isinstance(error, KeyError):
        return HTTPException(status_code=404, detail="规则不存在")
    return HTTPException(status_code=400, detail=str(error))


def create_app() -> FastAPI:
    """创建本地 API 应用。"""

    app = FastAPI(title=APP_NAME, version=BUILD_VERSION)
    rule_repository = RuleRepository()
    rule_repository.initialize()
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

    @app.get("/api/rules", response_model=RulesResponse)
    def list_rules() -> RulesResponse:
        return RulesResponse(
            database_path=str(rule_repository.db_path.resolve()),
            column_rules=[
                column_rule_response(rule)
                for rule in rule_repository.list_column_rules()
            ],
            data_rules=[
                data_rule_response(rule)
                for rule in rule_repository.list_data_rules()
            ],
        )

    @app.post("/api/rules/column", response_model=ColumnRuleResponse)
    def create_column_rule(request: ColumnRulePayload) -> ColumnRuleResponse:
        try:
            rule = rule_repository.create_column_rule(model_payload(request))
        except (KeyError, ValueError) as error:
            raise rule_error(error) from error
        return column_rule_response(rule)

    @app.put("/api/rules/column/{rule_id}", response_model=ColumnRuleResponse)
    def update_column_rule(
        rule_id: int,
        request: ColumnRulePayload,
    ) -> ColumnRuleResponse:
        try:
            rule = rule_repository.update_column_rule(rule_id, model_payload(request))
        except (KeyError, ValueError) as error:
            raise rule_error(error) from error
        return column_rule_response(rule)

    @app.delete("/api/rules/column/{rule_id}")
    def delete_column_rule(rule_id: int) -> dict[str, str]:
        try:
            rule_repository.delete_column_rule(rule_id)
        except (KeyError, ValueError) as error:
            raise rule_error(error) from error
        return {"status": "ok"}

    @app.post("/api/rules/data", response_model=DataRuleResponse)
    def create_data_rule(request: DataRulePayload) -> DataRuleResponse:
        try:
            rule = rule_repository.create_data_rule(model_payload(request))
        except (KeyError, ValueError) as error:
            raise rule_error(error) from error
        return data_rule_response(rule)

    @app.put("/api/rules/data/{rule_id}", response_model=DataRuleResponse)
    def update_data_rule(
        rule_id: int,
        request: DataRulePayload,
    ) -> DataRuleResponse:
        try:
            rule = rule_repository.update_data_rule(rule_id, model_payload(request))
        except (KeyError, ValueError) as error:
            raise rule_error(error) from error
        return data_rule_response(rule)

    @app.delete("/api/rules/data/{rule_id}")
    def delete_data_rule(rule_id: int) -> dict[str, str]:
        try:
            rule_repository.delete_data_rule(rule_id)
        except (KeyError, ValueError) as error:
            raise rule_error(error) from error
        return {"status": "ok"}

    @app.post("/api/rules/reset", response_model=RulesResponse)
    def reset_rules() -> RulesResponse:
        rule_repository.reset_defaults()
        return list_rules()

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
