export interface ExpandResponse {
  files: string[];
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
  rule_type: "value_alias" | "score_range" | "filter_range" | "keyword_filter";
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
  rule_type?: "value_alias" | "score_range" | "filter_range" | "keyword_filter";
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

export interface FilterProgress {
  index: number;
  total: number;
  name: string;
  kept: number;
  error: string | null;
}

export async function filterExcelFilesStream(
  baseUrl: string,
  files: string[],
  outputDir: string | null,
  onProgress: (progress: FilterProgress) => void,
): Promise<FilterResponse> {
  const response = await fetch(`${baseUrl}/api/filter/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ files, output_dir: outputDir }),
  });

  if (!response.ok || !response.body) {
    const payload = await response.json().catch(() => null);
    const detail = payload?.detail || response.statusText;
    throw new Error(String(detail));
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let result: FilterResponse | null = null;

  const handleEvent = (raw: string) => {
    const line = raw
      .split("\n")
      .find((part) => part.startsWith("data:"));
    if (!line) {
      return;
    }
    const event = JSON.parse(line.slice(5).trim());
    if (event.type === "progress") {
      onProgress(event as FilterProgress);
    } else if (event.type === "done") {
      result = event as FilterResponse;
    } else if (event.type === "error") {
      throw new Error(String(event.detail || "筛选失败"));
    }
  };

  for (;;) {
    const { done, value } = await reader.read();
    if (value) {
      buffer += decoder.decode(value, { stream: true });
      let separator = buffer.indexOf("\n\n");
      while (separator !== -1) {
        handleEvent(buffer.slice(0, separator));
        buffer = buffer.slice(separator + 2);
        separator = buffer.indexOf("\n\n");
      }
    }
    if (done) {
      break;
    }
  }

  if (buffer.trim()) {
    handleEvent(buffer);
  }

  if (!result) {
    throw new Error("筛选未返回结果");
  }
  return result;
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

export function deleteDataRule(
  baseUrl: string,
  ruleId: number,
): Promise<void> {
  return deleteJson(baseUrl, `/api/rules/data/${ruleId}`);
}
