import {
  CheckCircle2,
  Database,
  FilePlus2,
  FileSpreadsheet,
  FolderOpen,
  Loader2,
  Play,
  RefreshCw,
  RotateCcw,
  XCircle,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { open } from "@tauri-apps/plugin-dialog";
import { openPath } from "@tauri-apps/plugin-opener";
import { relaunch } from "@tauri-apps/plugin-process";
import { confirm } from "@tauri-apps/plugin-dialog";
import { check } from "@tauri-apps/plugin-updater";

import {
  FileResult,
  expandTargets,
  filterExcelFiles,
  getDefaultOutputDir,
} from "./api";
import { BackendService, startBackend } from "./backend";
import RulesView from "./RulesView";

function fileName(path: string): string {
  return path.split(/[\\/]/).pop() || path;
}

function dirName(path: string): string {
  const index = Math.max(path.lastIndexOf("/"), path.lastIndexOf("\\"));
  return index >= 0 ? path.slice(0, index) : "";
}

function mergeUnique(current: string[], incoming: string[]): string[] {
  return Array.from(new Set([...current, ...incoming]));
}

function formatError(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }
  return String(error);
}

export default function App() {
  const [apiBase, setApiBase] = useState<string | null>(null);
  const [activeView, setActiveView] = useState<"filter" | "rules">("filter");
  const [files, setFiles] = useState<string[]>([]);
  const [outputDir, setOutputDir] = useState<string | null>(null);
  const [logs, setLogs] = useState<string[]>(["正在启动 Python 后端"]);
  const [results, setResults] = useState<FileResult[]>([]);
  const [isProcessing, setIsProcessing] = useState(false);
  const [backendReady, setBackendReady] = useState(false);
  const [updateState, setUpdateState] = useState("未检查");
  const backendRef = useRef<BackendService | null>(null);

  const totalKept = useMemo(
    () => results.reduce((sum, result) => sum + result.kept, 0),
    [results],
  );

  function appendLog(message: string) {
    setLogs((current) => [...current, message]);
  }

  useEffect(() => {
    let disposed = false;

    startBackend((message) => {
      if (!disposed) {
        appendLog(message);
      }
    })
      .then((service) => {
        if (disposed) {
          void service.stop();
          return;
        }
        backendRef.current = service;
        setApiBase(service.baseUrl);
        setBackendReady(true);
        appendLog("Python 后端已启动");
      })
      .catch((error) => {
        if (!disposed) {
          appendLog(`Python 后端启动失败: ${formatError(error)}`);
        }
      });

    return () => {
      disposed = true;
      const service = backendRef.current;
      backendRef.current = null;
      if (service) {
        void service.stop();
      }
    };
  }, []);

  async function addTargets(targets: string[]) {
    if (!apiBase || !targets.length) {
      return;
    }
    const response = await expandTargets(apiBase, targets);
    const nextFiles = mergeUnique(files, response.files);
    setFiles(nextFiles);
    setResults([]);
    appendLog(`已加入 ${response.files.length} 个 Excel 文件`);
    if (!outputDir && nextFiles.length) {
      const defaultOutput = await getDefaultOutputDir(apiBase, nextFiles);
      setOutputDir(defaultOutput.output_dir);
    }
  }

  async function selectFiles() {
    const selected = await open({
      title: "选择 Excel 文件",
      multiple: true,
      directory: false,
      filters: [{ name: "Excel", extensions: ["xlsx", "xls"] }],
    });
    if (selected) {
      await addTargets(Array.isArray(selected) ? selected : [selected]);
    }
  }

  async function selectOutputDir() {
    const selected = await open({
      title: "选择保存目录",
      multiple: false,
      directory: true,
      canCreateDirectories: true,
    });
    if (typeof selected === "string") {
      setOutputDir(selected);
      appendLog(`保存目录: ${selected}`);
    }
  }

  function removeFile(path: string) {
    setFiles((current) => current.filter((file) => file !== path));
    setResults([]);
  }

  function clearAll() {
    setFiles([]);
    setResults([]);
    setOutputDir(null);
    setLogs(["已清空待处理文件"]);
  }

  async function runFilter() {
    if (!apiBase || isProcessing || !files.length) {
      return;
    }
    setIsProcessing(true);
    setResults([]);
    appendLog("开始筛选");
    try {
      const response = await filterExcelFiles(apiBase, files, outputDir);
      setOutputDir(response.output_dir);
      setResults(response.results);
      setLogs((current) => [...current, ...response.logs]);
    } catch (error) {
      appendLog(`筛选失败: ${formatError(error)}`);
    } finally {
      setIsProcessing(false);
    }
  }

  async function openResultDir() {
    if (outputDir) {
      await openPath(outputDir);
    }
  }

  async function checkForUpdates() {
    setUpdateState("检查中");
    try {
      const update = await check();
      if (!update) {
        setUpdateState("当前已是最新版本");
        return;
      }

      const shouldInstall = await confirm(
        `发现新版本 ${update.version}，是否立即安装？`,
        { title: "检查更新", kind: "info" },
      );
      if (!shouldInstall) {
        setUpdateState(`发现新版本 ${update.version}`);
        return;
      }

      setUpdateState("下载并安装中");
      await update.downloadAndInstall();
      await relaunch();
    } catch (error) {
      setUpdateState(`检查失败: ${formatError(error)}`);
    }
  }

  return (
    <main className={activeView === "rules" ? "app-shell rules-mode" : "app-shell"}>
      <section className="topbar">
        <nav className="view-tabs" aria-label="菜单">
          <button
            className={activeView === "filter" ? "active" : ""}
            type="button"
            onClick={() => setActiveView("filter")}
          >
            <FileSpreadsheet size={17} />
            文件筛选
          </button>
          <button
            className={activeView === "rules" ? "active" : ""}
            type="button"
            onClick={() => setActiveView("rules")}
          >
            <Database size={17} />
            规则维护
          </button>
        </nav>
        <button className="ghost-button" type="button" onClick={checkForUpdates}>
          <RefreshCw size={17} />
          检查更新
        </button>
      </section>

 
      {activeView === "filter" ? (
        <>
          <section className="toolbar" aria-label="操作">
            <button type="button" onClick={selectFiles} disabled={!backendReady}>
              <FilePlus2 size={18} />
              添加 Excel
            </button>
            <button type="button" onClick={selectOutputDir} disabled={!backendReady}>
              <FolderOpen size={18} />
              保存目录
            </button>
            <button
              className="primary-button"
              type="button"
              onClick={runFilter}
              disabled={!backendReady || isProcessing || files.length === 0}
            >
              {isProcessing ? (
                <Loader2 className="spin" size={18} />
              ) : (
                <Play size={18} />
              )}
              开始筛选
            </button>
            <button type="button" onClick={clearAll} disabled={isProcessing}>
              <RotateCcw size={18} />
              清空
            </button>
          </section>

          <section className="workspace">
            <div className="file-pane">
              <div className="pane-header">
                <h2>待处理文件</h2>
                <span>{outputDir || "未选择保存目录"}</span>
              </div>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>文件名</th>
                      <th>位置</th>
                      <th>操作</th>
                    </tr>
                  </thead>
                  <tbody>
                    {files.length === 0 ? (
                      <tr>
                        <td colSpan={3} className="empty-row">
                          请选择 .xlsx 或 .xls 文件
                        </td>
                      </tr>
                    ) : (
                      files.map((file) => (
                        <tr key={file}>
                          <td>{fileName(file)}</td>
                          <td className="path-cell">{dirName(file)}</td>
                          <td>
                            <button
                              className="icon-button"
                              type="button"
                              aria-label="移除文件"
                              title="移除文件"
                              onClick={() => removeFile(file)}
                              disabled={isProcessing}
                            >
                              <XCircle size={17} />
                            </button>
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>

            <aside className="side-pane">
              <div className="pane-header">
                <h2>筛选结果</h2>
                <button
                  className="text-button"
                  type="button"
                  onClick={openResultDir}
                  disabled={!outputDir}
                >
                  打开目录
                </button>
              </div>
              <div className="result-list">
                {results.length === 0 ? (
                  <p className="empty-text">暂无结果</p>
                ) : (
                  results.map((result) => (
                    <div className="result-item" key={result.src}>
                      {result.error ? (
                        <XCircle className="danger" size={18} />
                      ) : (
                        <CheckCircle2 className="ok" size={18} />
                      )}
                      <div>
                        <strong>{fileName(result.src)}</strong>
                        <span>
                          {result.error
                            ? result.error
                            : `保留 ${result.kept} 行${
                                result.out ? ` -> ${fileName(result.out)}` : ""
                              }`}
                        </span>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </aside>
          </section>

          <section className="log-pane" aria-label="处理日志">
            <div className="pane-header">
              <h2>处理日志</h2>
              <span>{logs.length} 条</span>
            </div>
            <pre>{logs.join("\n")}</pre>
          </section>
        </>
      ) : (
        <RulesView
          baseUrl={apiBase}
          backendReady={backendReady}
          onLog={appendLog}
        />
      )}
    </main>
  );
}
