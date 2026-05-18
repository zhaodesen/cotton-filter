import { Columns3, Plus, SlidersHorizontal, Tags, X } from "lucide-react";
import { FormEvent, useEffect, useMemo, useState } from "react";

import {
  ColumnRule,
  DataRule,
  createColumnRule,
  createDataRule,
  deleteColumnRule,
  deleteDataRule,
  listRules,
} from "./api";

interface RulesViewProps {
  baseUrl: string | null;
  backendReady: boolean;
  onLog: (message: string) => void;
}

interface DataRuleForm {
  field_name: string;
  rule_type: DataRule["rule_type"];
  match_value: string;
  min_value: string;
  max_value: string;
  min_inclusive: boolean;
  max_inclusive: boolean;
  score_delta: string;
  output_value: string;
  enabled: boolean;
  sort_order: string;
  notes: string;
}

type RulesPanel = "columns" | "aliases" | "intervals";

const DEFAULT_STANDARD_FIELDS = [
  "基差",
  "颜色级",
  "长度",
  "强力",
  "马值",
  "整齐度",
  "批号",
  "仓库",
];

// 列名规则中始终隐藏的字段。
const EXCLUDED_COLUMN_FIELDS = new Set(["与基差差距"]);

// 数据规则中始终隐藏的字段（基差不参与数据规则）。
const EXCLUDED_DATA_FIELDS = new Set(["基差", "与基差差距"]);

const DEFAULT_DATA_FORM: DataRuleForm = {
  field_name: "",
  rule_type: "value_alias",
  match_value: "",
  min_value: "",
  max_value: "",
  min_inclusive: true,
  max_inclusive: true,
  score_delta: "",
  output_value: "",
  enabled: true,
  sort_order: "0",
  notes: "",
};

const RULE_TYPE_LABELS: Record<DataRule["rule_type"], string> = {
  value_alias: "值别名",
  score_range: "评分区间",
  filter_range: "过滤区间",
  keyword_filter: "关键词过滤",
};

function formatError(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }
  return String(error);
}

function optionalNumber(value: string): number | null {
  const trimmed = value.trim().replace(/[%％]$/, "").trim();
  if (!trimmed) {
    return null;
  }
  const parsed = Number(trimmed);
  if (!Number.isFinite(parsed)) {
    throw new Error("数值格式不正确，请输入数字或百分比");
  }
  return parsed;
}

function formatRange(rule: DataRule): string {
  if (rule.rule_type === "value_alias") {
    return rule.output_value
      ? `${rule.match_value} -> ${rule.output_value}`
      : rule.match_value;
  }
  if (rule.rule_type === "keyword_filter") {
    return rule.match_value;
  }

  const left = rule.min_value === null
    ? "不限"
    : `${rule.min_inclusive ? ">=" : ">"} ${rule.min_value}`;
  const right = rule.max_value === null
    ? "不限"
    : `${rule.max_inclusive ? "<=" : "<"} ${rule.max_value}`;
  return `${left} / ${right}`;
}

function ruleDetail(rule: DataRule): string {
  const parts = [formatRange(rule)];
  if (rule.rule_type === "keyword_filter") {
    return parts.filter(Boolean).join(" · ");
  }
  if (rule.rule_type !== "value_alias" && rule.match_value) {
    parts.unshift(`适用值 ${rule.match_value}`);
  }
  if (rule.score_delta !== null && rule.score_delta !== undefined) {
    const sign = rule.score_delta > 0 ? "+" : "";
    parts.push(`${sign}${rule.score_delta}分`);
  }
  return parts.filter(Boolean).join(" · ");
}

function ruleSummary(rule: DataRule): string {
  return `${RULE_TYPE_LABELS[rule.rule_type]} · ${ruleDetail(rule)}`;
}

function aliasOutputValues(rules: DataRule[]): string[] {
  return Array.from(
    new Set(
      rules
        .map((rule) => rule.output_value.trim())
        .filter((value) => value.length > 0),
    ),
  ).sort((first, second) => first.localeCompare(second, "zh-CN"));
}

function groupAliasRulesByOutput(rules: DataRule[]): [string, DataRule[]][] {
  const groups = new Map<string, DataRule[]>();
  for (const rule of rules) {
    const outputValue = rule.output_value.trim() || rule.match_value.trim();
    const group = groups.get(outputValue) || [];
    group.push(rule);
    groups.set(outputValue, group);
  }
  return Array.from(groups.entries()).sort(([first], [second]) =>
    first.localeCompare(second, "zh-CN"),
  );
}

export default function RulesView({
  baseUrl,
  backendReady,
  onLog,
}: RulesViewProps) {
  const [columnRules, setColumnRules] = useState<ColumnRule[]>([]);
  const [dataRules, setDataRules] = useState<DataRule[]>([]);
  const [dataForm, setDataForm] = useState<DataRuleForm>(DEFAULT_DATA_FORM);
  const [aliasDialogField, setAliasDialogField] = useState<string | null>(null);
  const [aliasValue, setAliasValue] = useState("");
  const [dataDialogField, setDataDialogField] = useState<string | null>(null);
  const [detailRule, setDetailRule] = useState<DataRule | null>(null);
  const [activePanel, setActivePanel] = useState<RulesPanel>("columns");
  const [isSaving, setIsSaving] = useState(false);
  const [errorText, setErrorText] = useState("");

  const columnFields = useMemo(() => {
    const extra = columnRules.map((rule) => rule.field_name);
    return Array.from(
      new Set([...DEFAULT_STANDARD_FIELDS, ...extra]),
    ).filter((field) => !EXCLUDED_COLUMN_FIELDS.has(field));
  }, [columnRules]);

  const dataFields = useMemo(() => {
    const extra = dataRules.map((rule) => rule.field_name);
    return Array.from(
      new Set([...DEFAULT_STANDARD_FIELDS, ...extra]),
    ).filter((field) => !EXCLUDED_DATA_FIELDS.has(field));
  }, [dataRules]);

  const columnRulesByField = useMemo(() => {
    const groups = new Map<string, ColumnRule[]>();
    for (const fieldName of columnFields) {
      groups.set(fieldName, []);
    }
    for (const rule of columnRules) {
      const rules = groups.get(rule.field_name) || [];
      rules.push(rule);
      groups.set(rule.field_name, rules);
    }
    for (const rules of groups.values()) {
      rules.sort((first, second) =>
        first.alias.localeCompare(second.alias, "zh-CN"),
      );
    }
    return groups;
  }, [columnRules, columnFields]);

  const valueAliasRulesByField = useMemo(() => {
    const groups = new Map<string, DataRule[]>();
    for (const fieldName of dataFields) {
      groups.set(fieldName, []);
    }
    for (const rule of dataRules) {
      if (rule.rule_type !== "value_alias") {
        continue;
      }
      const rules = groups.get(rule.field_name) || [];
      rules.push(rule);
      groups.set(rule.field_name, rules);
    }
    for (const rules of groups.values()) {
      rules.sort(
        (first, second) =>
          first.sort_order - second.sort_order || first.id - second.id,
      );
    }
    return groups;
  }, [dataRules, dataFields]);

  const intervalRulesByField = useMemo(() => {
    const groups = new Map<string, DataRule[]>();
    for (const fieldName of dataFields) {
      groups.set(fieldName, []);
    }
    for (const rule of dataRules) {
      if (rule.rule_type === "value_alias") {
        continue;
      }
      const rules = groups.get(rule.field_name) || [];
      rules.push(rule);
      groups.set(rule.field_name, rules);
    }
    for (const rules of groups.values()) {
      rules.sort(
        (first, second) =>
          first.sort_order - second.sort_order || first.id - second.id,
      );
    }
    return groups;
  }, [dataRules, dataFields]);

  async function reloadRules() {
    if (!baseUrl) {
      return;
    }
    setErrorText("");
    try {
      const response = await listRules(baseUrl);
      setColumnRules(response.column_rules);
      setDataRules(response.data_rules);
    } catch (error) {
      setErrorText(formatError(error));
    }
  }

  useEffect(() => {
    if (backendReady) {
      void reloadRules();
    }
  }, [backendReady, baseUrl]);

  function openAliasDialog(fieldName: string) {
    setAliasDialogField(fieldName);
    setAliasValue("");
    setErrorText("");
  }

  function closeAliasDialog() {
    setAliasDialogField(null);
    setAliasValue("");
  }

  function openDataDialog(
    fieldName: string,
    ruleType: DataRule["rule_type"],
  ) {
    const aliasValues = aliasOutputValues(valueAliasRulesByField.get(fieldName) || []);
    setDataForm({
      ...DEFAULT_DATA_FORM,
      field_name: fieldName,
      rule_type: ruleType,
      match_value: ruleType === "filter_range" || ruleType === "score_range"
        ? aliasValues[0] || ""
        : "",
    });
    setDataDialogField(fieldName);
    setErrorText("");
  }

  function closeDataDialog() {
    setDataDialogField(null);
    setDataForm(DEFAULT_DATA_FORM);
  }

  async function handleAliasSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const alias = aliasValue.trim();
    if (!baseUrl || !aliasDialogField || !alias || isSaving) {
      return;
    }

    setIsSaving(true);
    setErrorText("");
    try {
      await createColumnRule(baseUrl, {
        field_name: aliasDialogField,
        alias,
        enabled: true,
      });
      await reloadRules();
      onLog(`列名别名已保存: ${aliasDialogField} / ${alias}`);
      closeAliasDialog();
    } catch (error) {
      setErrorText(formatError(error));
    } finally {
      setIsSaving(false);
    }
  }

  async function handleDataSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!baseUrl || !dataDialogField || isSaving) {
      return;
    }

    setIsSaving(true);
    setErrorText("");
    try {
      await createDataRule(baseUrl, {
        field_name: dataForm.field_name,
        rule_type: dataForm.rule_type,
        match_value: dataForm.match_value,
        min_value: optionalNumber(dataForm.min_value),
        max_value: optionalNumber(dataForm.max_value),
        min_inclusive: dataForm.min_inclusive,
        max_inclusive: dataForm.max_inclusive,
        score_delta: optionalNumber(dataForm.score_delta),
        output_value: dataForm.output_value,
        enabled: dataForm.enabled,
        sort_order: Number(dataForm.sort_order || 0),
        notes: dataForm.notes,
      });
      await reloadRules();
      onLog(`数据规则已保存: ${dataForm.field_name} / ${RULE_TYPE_LABELS[dataForm.rule_type]}`);
      closeDataDialog();
    } catch (error) {
      setErrorText(formatError(error));
    } finally {
      setIsSaving(false);
    }
  }


  async function removeColumn(rule: ColumnRule) {
    if (!baseUrl) {
      return;
    }
    try {
      await deleteColumnRule(baseUrl, rule.id);
      await reloadRules();
      onLog(`列名别名已删除: ${rule.alias}`);
    } catch (error) {
      setErrorText(formatError(error));
    }
  }

  async function removeData(rule: DataRule) {
    if (!baseUrl) {
      return;
    }
    try {
      await deleteDataRule(baseUrl, rule.id);
      await reloadRules();
      onLog(`数据规则已删除: ${rule.field_name} / ${RULE_TYPE_LABELS[rule.rule_type]}`);
    } catch (error) {
      setErrorText(formatError(error));
    }
  }

  const showAlias = dataForm.rule_type === "value_alias";
  const showScore = dataForm.rule_type === "score_range";
  const showKeyword = dataForm.rule_type === "keyword_filter";
  const showNumericRange = dataForm.rule_type === "score_range" || dataForm.rule_type === "filter_range";
  const applicableValues = dataDialogField
    ? aliasOutputValues(valueAliasRulesByField.get(dataDialogField) || [])
    : [];

  return (
    <section className="rules-view">
      {errorText ? <div className="rules-error">{errorText}</div> : null}

      <div className="rules-layout">
        <aside className="rules-sidebar" aria-label="规则维护菜单">
          <button
            className={activePanel === "columns" ? "rules-menu-item active" : "rules-menu-item"}
            type="button"
            onClick={() => setActivePanel("columns")}
          >
            <Columns3 size={16} />
            <span>列名规则</span>
          </button>
          <div className="rules-menu-heading">数据规则</div>
          <button
            className={activePanel === "aliases" ? "rules-menu-item active" : "rules-menu-item"}
            type="button"
            onClick={() => setActivePanel("aliases")}
          >
            <Tags size={16} />
            <span>值别名</span>
          </button>
          <button
            className={activePanel === "intervals" ? "rules-menu-item active" : "rules-menu-item"}
            type="button"
            onClick={() => setActivePanel("intervals")}
          >
            <SlidersHorizontal size={16} />
            <span>评分与过滤区间</span>
          </button>
        </aside>

        <section className="rules-pane rules-content-pane">
          <div className="pane-header">
            <h2>
              {activePanel === "columns"
                ? "列名规则"
                : activePanel === "aliases"
                  ? "值别名"
                  : "评分与过滤区间"}
            </h2>
          </div>
          {activePanel === "columns" ? (
            <div className="field-rule-list">
              {columnFields.map((fieldName) => {
                const aliases = columnRulesByField.get(fieldName) || [];
                return (
                  <div className="field-rule-row" key={fieldName}>
                    <strong className="field-rule-name">{fieldName}</strong>
                    <div className="alias-list">
                      {aliases.length === 0 ? (
                        <span className="alias-empty">暂无别名</span>
                      ) : (
                        aliases.map((rule) => (
                          <span className="alias-chip" key={rule.id}>
                            {rule.alias}
                            <button
                              className="chip-delete"
                              type="button"
                              title="删除别名"
                              onClick={() => removeColumn(rule)}
                              disabled={isSaving}
                            >
                              <X size={14} />
                            </button>
                          </span>
                        ))
                      )}
                    </div>
                    <button
                      className="alias-add-button"
                      type="button"
                      title={`为 ${fieldName} 新增别名`}
                      onClick={() => openAliasDialog(fieldName)}
                      disabled={!backendReady || isSaving}
                    >
                      <Plus size={15} />
                    </button>
                  </div>
                );
              })}
            </div>
          ) : null}
          {activePanel === "aliases" ? (
            <div className="field-rule-list">
              {dataFields.map((fieldName) => {
                const rules = valueAliasRulesByField.get(fieldName) || [];
                return (
                  <div
                    className="field-rule-row data-rule-row"
                    key={`alias-${fieldName}`}
                  >
                    <strong className="field-rule-name">{fieldName}</strong>
                    <div className="rule-pill-list alias-rule-group-list">
                      {rules.length === 0 ? (
                        <span className="alias-empty">暂无别名</span>
                      ) : (
                        groupAliasRulesByOutput(rules).map(([outputValue, groupedRules]) => (
                          <div className="alias-rule-group" key={outputValue}>
                            <div className="alias-rule-group-title">
                              {outputValue}
                            </div>
                            <div className="alias-rule-group-items">
                              {groupedRules.map((rule) => (
                                <div className="rule-pill" key={rule.id}>
                                  <button
                                    className="rule-pill-body rule-pill-view"
                                    type="button"
                                    title="查看规则详情"
                                    onClick={() => setDetailRule(rule)}
                                  >
                                    <span className="rule-pill-meta">
                                      {rule.match_value}
                                    </span>
                                  </button>
                                  <button
                                    className="chip-delete"
                                    type="button"
                                    title="删除别名"
                                    onClick={() => removeData(rule)}
                                    disabled={isSaving}
                                  >
                                    <X size={14} />
                                  </button>
                                </div>
                              ))}
                            </div>
                          </div>
                        ))
                      )}
                    </div>
                    <button
                      className="alias-add-button"
                      type="button"
                      title={`为 ${fieldName} 新增值别名`}
                      onClick={() => openDataDialog(fieldName, "value_alias")}
                      disabled={!backendReady || isSaving}
                    >
                      <Plus size={15} />
                    </button>
                  </div>
                );
              })}
            </div>
          ) : null}
          {activePanel === "intervals" ? (
            <div className="field-rule-list">
              {dataFields.map((fieldName) => {
                const rules = intervalRulesByField.get(fieldName) || [];
                return (
                  <div
                    className="field-rule-row data-rule-row"
                    key={`range-${fieldName}`}
                  >
                    <strong className="field-rule-name">{fieldName}</strong>
                    <div className="rule-pill-list">
                      {rules.length === 0 ? (
                        <span className="alias-empty">暂无区间</span>
                      ) : (
                        rules.map((rule) => (
                          <div className="rule-pill" key={rule.id}>
                            <button
                              className="rule-pill-body rule-pill-view"
                              type="button"
                              title="查看规则详情"
                              onClick={() => setDetailRule(rule)}
                            >
                              <span className="rule-pill-top">
                                <span className="rule-pill-tag">
                                  {RULE_TYPE_LABELS[rule.rule_type]}
                                </span>
                              </span>
                              <span
                                className="rule-pill-meta"
                                title={ruleSummary(rule)}
                              >
                                {ruleDetail(rule)}
                              </span>
                            </button>
                            <button
                              className="chip-delete"
                              type="button"
                              title="删除区间"
                              onClick={() => removeData(rule)}
                              disabled={isSaving}
                            >
                              <X size={14} />
                            </button>
                          </div>
                        ))
                      )}
                    </div>
                    <button
                      className="alias-add-button"
                      type="button"
                      title={`为 ${fieldName} 新增区间`}
                      onClick={() => openDataDialog(fieldName, "score_range")}
                      disabled={
                        !backendReady ||
                        isSaving ||
                        aliasOutputValues(valueAliasRulesByField.get(fieldName) || [])
                          .length === 0
                      }
                    >
                      <Plus size={15} />
                    </button>
                  </div>
                );
              })}
            </div>
          ) : null}
        </section>
      </div>

      {aliasDialogField ? (
        <div className="modal-backdrop" role="presentation">
          <div
            className="modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="alias-dialog-title"
          >
            <div className="modal-header">
              <h2 id="alias-dialog-title">新增列名别名</h2>
              <button
                className="icon-button"
                type="button"
                title="关闭"
                onClick={closeAliasDialog}
                disabled={isSaving}
              >
                <X size={17} />
              </button>
            </div>
            <form className="modal-form" onSubmit={handleAliasSubmit}>
              <label>
                <span>标准字段</span>
                <input value={aliasDialogField} readOnly />
              </label>
              <label>
                <span>列名别名</span>
                <input
                  autoFocus
                  value={aliasValue}
                  onChange={(event) => setAliasValue(event.target.value)}
                  placeholder="输入 Excel 中出现的列名"
                />
              </label>
              <div className="modal-actions">
                <button
                  type="button"
                  onClick={closeAliasDialog}
                  disabled={isSaving}
                >
                  取消
                </button>
                <button
                  className="primary-button"
                  type="submit"
                  disabled={!backendReady || isSaving || !aliasValue.trim()}
                >
                  保存
                </button>
              </div>
            </form>
          </div>
        </div>
      ) : null}

      {dataDialogField ? (
        <div className="modal-backdrop" role="presentation">
          <div
            className="modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="data-dialog-title"
          >
            <div className="modal-header">
              <h2 id="data-dialog-title">
                新增数据规则 · {dataDialogField}
              </h2>
              <button
                className="icon-button"
                type="button"
                title="关闭"
                onClick={closeDataDialog}
                disabled={isSaving}
              >
                <X size={17} />
              </button>
            </div>
            <form className="modal-form" onSubmit={handleDataSubmit}>
              <label>
                <span>规则类型</span>
                <select
                  value={dataForm.rule_type}
                  onChange={(event) =>
                    setDataForm((current) => ({
                      ...current,
                      rule_type: event.target
                        .value as DataRule["rule_type"],
                    }))
                  }
                >
                  {showAlias ? (
                    <option value="value_alias">值别名</option>
                  ) : (
                    <>
                      <option value="score_range">评分区间</option>
                      <option value="filter_range">过滤区间</option>
                      <option value="keyword_filter">关键词过滤</option>
                    </>
                  )}
                </select>
              </label>
              {showAlias ? (
                <>
                  <label>
                    <span>匹配值</span>
                    <input
                      autoFocus
                      value={dataForm.match_value}
                      onChange={(event) =>
                        setDataForm((current) => ({
                          ...current,
                          match_value: event.target.value,
                        }))
                      }
                      placeholder="Excel 中出现的值"
                    />
                  </label>
                  <label>
                    <span>输出值</span>
                    <input
                      value={dataForm.output_value}
                      onChange={(event) =>
                        setDataForm((current) => ({
                          ...current,
                          output_value: event.target.value,
                        }))
                      }
                      placeholder="替换为的标准值"
                    />
                  </label>
                </>
              ) : null}
              {showKeyword ? (
                <label>
                  <span>关键词</span>
                  <input
                    autoFocus
                    value={dataForm.match_value}
                    onChange={(event) =>
                      setDataForm((current) => ({
                        ...current,
                        match_value: event.target.value,
                      }))
                    }
                    placeholder="命中该关键词则保留"
                  />
                </label>
              ) : null}
              {showNumericRange ? (
                <>
                  <label>
                    <span>适用值</span>
                    <select
                      autoFocus
                      value={dataForm.match_value}
                      onChange={(event) =>
                        setDataForm((current) => ({
                          ...current,
                          match_value: event.target.value,
                        }))
                      }
                    >
                      {applicableValues.map((value) => (
                        <option key={value} value={value}>
                          {value}
                        </option>
                      ))}
                    </select>
                  </label>
                  <div className="modal-field-pair">
                    <label>
                      <span>最小值</span>
                      <input
                        value={dataForm.min_value}
                        onChange={(event) =>
                          setDataForm((current) => ({
                            ...current,
                            min_value: event.target.value,
                          }))
                        }
                        inputMode="decimal"
                        placeholder="不限，支持 80 或 80%"
                      />
                    </label>
                    <label>
                      <span>最大值</span>
                      <input
                        value={dataForm.max_value}
                        onChange={(event) =>
                          setDataForm((current) => ({
                            ...current,
                            max_value: event.target.value,
                          }))
                        }
                        inputMode="decimal"
                        placeholder="不限，支持 80 或 80%"
                      />
                    </label>
                  </div>
                </>
              ) : null}
              {showScore ? (
                <label>
                  <span>加减分</span>
                  <input
                    value={dataForm.score_delta}
                    onChange={(event) =>
                      setDataForm((current) => ({
                        ...current,
                        score_delta: event.target.value,
                      }))
                    }
                    inputMode="numeric"
                    placeholder="例如 5 或 -3"
                  />
                </label>
              ) : null}
              <div className="modal-actions">
                <button
                  type="button"
                  onClick={closeDataDialog}
                  disabled={isSaving}
                >
                  取消
                </button>
                <button
                  className="primary-button"
                  type="submit"
                  disabled={
                    !backendReady ||
                    isSaving ||
                    (showAlias && (!dataForm.match_value.trim() || !dataForm.output_value.trim())) ||
                    (showKeyword && !dataForm.match_value.trim()) ||
                    (showNumericRange && !dataForm.match_value)
                  }
                >
                  保存
                </button>
              </div>
            </form>
          </div>
        </div>
      ) : null}

      {detailRule ? (
        <div className="modal-backdrop" role="presentation">
          <div
            className="modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="rule-detail-title"
          >
            <div className="modal-header">
              <h2 id="rule-detail-title">规则详情</h2>
              <button
                className="icon-button"
                type="button"
                title="关闭"
                onClick={() => setDetailRule(null)}
              >
                <X size={17} />
              </button>
            </div>
            <div className="rule-detail">
              <div>
                <span>字段</span>
                <strong>{detailRule.field_name}</strong>
              </div>
              <div>
                <span>类型</span>
                <strong>{RULE_TYPE_LABELS[detailRule.rule_type]}</strong>
              </div>
              <div>
                <span>规则</span>
                <strong>{ruleDetail(detailRule)}</strong>
              </div>
              {detailRule.output_value ? (
                <div>
                  <span>输出值</span>
                  <strong>{detailRule.output_value}</strong>
                </div>
              ) : null}
              {detailRule.notes ? (
                <div>
                  <span>备注</span>
                  <strong>{detailRule.notes}</strong>
                </div>
              ) : null}
            </div>
          </div>
        </div>
      ) : null}
    </section>
  );
}
