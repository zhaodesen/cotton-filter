import { Database, Plus, Trash2, X } from "lucide-react";
import { FormEvent, useEffect, useMemo, useState } from "react";

import {
  ColumnRule,
  DataRule,
  createColumnRule,
  createDataRule,
  deleteColumnRule,
  deleteDataRule,
  listRules,
  updateDataRule,
} from "./api";

interface RulesViewProps {
  baseUrl: string | null;
  backendReady: boolean;
  onLog: (message: string) => void;
}

interface DataRuleForm {
  field_name: string;
  rule_name: string;
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

const DEFAULT_STANDARD_FIELDS = [
  "基差",
  "颜色级",
  "长度",
  "强力",
  "马值",
  "整齐度",
  "批号",
];

const DEFAULT_DATA_FORM: DataRuleForm = {
  field_name: "颜色级",
  rule_name: "",
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
};

function formatError(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }
  return String(error);
}

function optionalNumber(value: string): number | null {
  const trimmed = value.trim();
  if (!trimmed) {
    return null;
  }
  const parsed = Number(trimmed);
  if (!Number.isFinite(parsed)) {
    throw new Error("数值格式不正确");
  }
  return parsed;
}

function formatRange(rule: DataRule): string {
  if (rule.rule_type === "value_alias") {
    return rule.output_value
      ? `${rule.match_value} -> ${rule.output_value}`
      : rule.match_value;
  }

  const left = rule.min_value === null
    ? "不限"
    : `${rule.min_inclusive ? ">=" : ">"} ${rule.min_value}`;
  const right = rule.max_value === null
    ? "不限"
    : `${rule.max_inclusive ? "<=" : "<"} ${rule.max_value}`;
  return `${left} / ${right}`;
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
  const [isSaving, setIsSaving] = useState(false);
  const [errorText, setErrorText] = useState("");

  const standardFields = useMemo(() => {
    const fields = columnRules.map((rule) => rule.field_name);
    return Array.from(new Set([...DEFAULT_STANDARD_FIELDS, ...fields]));
  }, [columnRules]);

  const columnRulesByField = useMemo(() => {
    const groups = new Map<string, ColumnRule[]>();
    for (const fieldName of standardFields) {
      groups.set(fieldName, []);
    }
    for (const rule of columnRules) {
      const rules = groups.get(rule.field_name) || [];
      rules.push(rule);
      groups.set(rule.field_name, rules);
    }
    for (const rules of groups.values()) {
      rules.sort((first, second) => first.alias.localeCompare(second.alias, "zh-CN"));
    }
    return groups;
  }, [columnRules, standardFields]);

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
    if (!baseUrl || isSaving) {
      return;
    }

    setIsSaving(true);
    setErrorText("");
    try {
      await createDataRule(baseUrl, {
        field_name: dataForm.field_name,
        rule_name: dataForm.rule_name,
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
      setDataForm(DEFAULT_DATA_FORM);
      await reloadRules();
      onLog("数据规则已保存");
    } catch (error) {
      setErrorText(formatError(error));
    } finally {
      setIsSaving(false);
    }
  }

  async function toggleData(rule: DataRule) {
    if (!baseUrl) {
      return;
    }
    try {
      await updateDataRule(baseUrl, rule.id, { enabled: !rule.enabled });
      await reloadRules();
    } catch (error) {
      setErrorText(formatError(error));
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
      onLog(`数据规则已删除: ${rule.rule_name}`);
    } catch (error) {
      setErrorText(formatError(error));
    }
  }

  return (
    <section className="rules-view">
      {errorText ? <div className="rules-error">{errorText}</div> : null}

      <div className="rules-grid">
        <section className="rules-pane column-rules-pane">
          <div className="pane-header">
            <h2>列名规则</h2>
            <Database size={17} />
          </div>
          <div className="field-rule-list">
            {standardFields.map((fieldName) => {
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
        </section>

        <section className="rules-pane">
          <div className="pane-header">
            <h2>数据规则</h2>
            <Database size={17} />
          </div>
          <form className="rule-form data-rule-form" onSubmit={handleDataSubmit}>
            <select
              value={dataForm.rule_type}
              onChange={(event) =>
                setDataForm((current) => ({
                  ...current,
                  rule_type: event.target.value as DataRule["rule_type"],
                }))
              }
            >
              <option value="value_alias">值别名</option>
              <option value="score_range">评分区间</option>
              <option value="filter_range">过滤区间</option>
            </select>
            <input
              value={dataForm.field_name}
              onChange={(event) =>
                setDataForm((current) => ({
                  ...current,
                  field_name: event.target.value,
                }))
              }
              placeholder="字段"
            />
            <input
              value={dataForm.rule_name}
              onChange={(event) =>
                setDataForm((current) => ({
                  ...current,
                  rule_name: event.target.value,
                }))
              }
              placeholder="规则名称"
            />
            <input
              value={dataForm.match_value}
              onChange={(event) =>
                setDataForm((current) => ({
                  ...current,
                  match_value: event.target.value,
                }))
              }
              placeholder="匹配值"
            />
            <input
              value={dataForm.min_value}
              onChange={(event) =>
                setDataForm((current) => ({
                  ...current,
                  min_value: event.target.value,
                }))
              }
              inputMode="decimal"
              placeholder="最小值"
            />
            <input
              value={dataForm.max_value}
              onChange={(event) =>
                setDataForm((current) => ({
                  ...current,
                  max_value: event.target.value,
                }))
              }
              inputMode="decimal"
              placeholder="最大值"
            />
            <input
              value={dataForm.score_delta}
              onChange={(event) =>
                setDataForm((current) => ({
                  ...current,
                  score_delta: event.target.value,
                }))
              }
              inputMode="numeric"
              placeholder="加减分"
            />
            <button type="submit" disabled={!backendReady || isSaving}>
              <Plus size={17} />
              新增
            </button>
          </form>
          <div className="table-wrap">
            <table className="rules-table data-rules-table">
              <thead>
                <tr>
                  <th>类型</th>
                  <th>字段</th>
                  <th>规则</th>
                  <th>匹配/区间</th>
                  <th>加减分</th>
                  <th>状态</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                {dataRules.map((rule) => (
                  <tr key={rule.id}>
                    <td>{RULE_TYPE_LABELS[rule.rule_type]}</td>
                    <td>{rule.field_name}</td>
                    <td>{rule.rule_name}</td>
                    <td>{formatRange(rule)}</td>
                    <td>{rule.score_delta ?? ""}</td>
                    <td>{rule.enabled ? "启用" : "停用"}</td>
                    <td>
                      <div className="row-actions">
                        <button
                          className="text-button"
                          type="button"
                          onClick={() => toggleData(rule)}
                        >
                          {rule.enabled ? "停用" : "启用"}
                        </button>
                        <button
                          className="icon-button"
                          type="button"
                          title="删除"
                          onClick={() => removeData(rule)}
                        >
                          <Trash2 size={17} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      </div>

      {aliasDialogField ? (
        <div className="modal-backdrop" role="presentation">
          <div className="modal" role="dialog" aria-modal="true" aria-labelledby="alias-dialog-title">
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
                <button type="button" onClick={closeAliasDialog} disabled={isSaving}>
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
    </section>
  );
}
