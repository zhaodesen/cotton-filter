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

