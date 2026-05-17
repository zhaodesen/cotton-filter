export interface ExpandResponse {
  files: string[];
}

export interface DefaultOutputResponse {
  output_dir: string;
}

export interface FileResult {
  src: string;
  out: string | null;
  kept: number;
  error: string | null;
}

export interface FilterResponse {
  output_dir: string;
  total_files: number;
  total_kept: number;
  results: FileResult[];
  logs: string[];
}

export interface ColumnRule {
  id: number;
  field_name: string;
  alias: string;
  alias_key: string;
  enabled: boolean;
  sort_order: number;
  notes: string;
}

export interface DataRule {
  id: number;
  field_name: string;
  rule_name: string;
  rule_type: "value_alias" | "score_range" | "filter_range";
  match_value: string;
  match_key: string;
  min_value: number | null;
  max_value: number | null;
  min_inclusive: boolean;
  max_inclusive: boolean;
  score_delta: number | null;
  output_value: string;
  enabled: boolean;
  sort_order: number;
  notes: string;
}

export interface RulesResponse {
  database_path: string;
  column_rules: ColumnRule[];
  data_rules: DataRule[];
}

export interface ColumnRulePayload {
  field_name?: string;
  alias?: string;
  enabled?: boolean;
  sort_order?: number;
  notes?: string;
}

export interface DataRulePayload {
  field_name?: string;
  rule_name?: string;
  rule_type?: "value_alias" | "score_range" | "filter_range";
  match_value?: string;
  min_value?: number | null;
  max_value?: number | null;
  min_inclusive?: boolean;
  max_inclusive?: boolean;
  score_delta?: number | null;
  output_value?: string;
  enabled?: boolean;
  sort_order?: number;
  notes?: string;
}

async function getJson<TResponse>(
  baseUrl: string,
  path: string,
): Promise<TResponse> {
  const response = await fetch(`${baseUrl}${path}`);

  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    const detail = payload?.detail || response.statusText;
    throw new Error(String(detail));
  }

  return response.json() as Promise<TResponse>;
}

async function postJson<TResponse, TBody>(
  baseUrl: string,
  path: string,
  body: TBody,
): Promise<TResponse> {
  const response = await fetch(`${baseUrl}${path}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    const detail = payload?.detail || response.statusText;
    throw new Error(String(detail));
  }

  return response.json() as Promise<TResponse>;
}

async function putJson<TResponse, TBody>(
  baseUrl: string,
  path: string,
  body: TBody,
): Promise<TResponse> {
  const response = await fetch(`${baseUrl}${path}`, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    const detail = payload?.detail || response.statusText;
    throw new Error(String(detail));
  }

  return response.json() as Promise<TResponse>;
}

async function deleteJson(baseUrl: string, path: string): Promise<void> {
  const response = await fetch(`${baseUrl}${path}`, {
    method: "DELETE",
  });

  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    const detail = payload?.detail || response.statusText;
    throw new Error(String(detail));
  }
}

export function expandTargets(
  baseUrl: string,
  targets: string[],
): Promise<ExpandResponse> {
  return postJson(baseUrl, "/api/expand", { targets });
}

export function getDefaultOutputDir(
  baseUrl: string,
  files: string[],
): Promise<DefaultOutputResponse> {
  return postJson(baseUrl, "/api/default-output-dir", { files });
}

export function filterExcelFiles(
  baseUrl: string,
  files: string[],
  outputDir: string | null,
): Promise<FilterResponse> {
  return postJson(baseUrl, "/api/filter", {
    files,
    output_dir: outputDir,
  });
}

export function listRules(baseUrl: string): Promise<RulesResponse> {
  return getJson(baseUrl, "/api/rules");
}

export function createColumnRule(
  baseUrl: string,
  payload: ColumnRulePayload,
): Promise<ColumnRule> {
  return postJson(baseUrl, "/api/rules/column", payload);
}

export function updateColumnRule(
  baseUrl: string,
  ruleId: number,
  payload: ColumnRulePayload,
): Promise<ColumnRule> {
  return putJson(baseUrl, `/api/rules/column/${ruleId}`, payload);
}

export function deleteColumnRule(
  baseUrl: string,
  ruleId: number,
): Promise<void> {
  return deleteJson(baseUrl, `/api/rules/column/${ruleId}`);
}

export function createDataRule(
  baseUrl: string,
  payload: DataRulePayload,
): Promise<DataRule> {
  return postJson(baseUrl, "/api/rules/data", payload);
}

export function updateDataRule(
  baseUrl: string,
  ruleId: number,
  payload: DataRulePayload,
): Promise<DataRule> {
  return putJson(baseUrl, `/api/rules/data/${ruleId}`, payload);
}

export function deleteDataRule(
  baseUrl: string,
  ruleId: number,
): Promise<void> {
  return deleteJson(baseUrl, `/api/rules/data/${ruleId}`);
}

export function resetRules(baseUrl: string): Promise<RulesResponse> {
  return postJson(baseUrl, "/api/rules/reset", {});
}
