import {
  CheckCircle2,
  Database,
  FilePlus2,
  FileSpreadsheet,
  FolderOpen,
  Loader2,
  RefreshCw,
  X,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { open } from "@tauri-apps/plugin-dialog";
import { openPath } from "@tauri-apps/plugin-opener";
import { relaunch } from "@tauri-apps/plugin-process";
import { confirm } from "@tauri-apps/plugin-dialog";
import { check } from "@tauri-apps/plugin-updater";

import { expandTargets, filterExcelFilesStream } from "./api";
import { BackendService, startBackend } from "./backend";
import RulesView from "./RulesView";

function formatError(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }
  return String(error);
}

export default function App() {
  const [apiBase, setApiBase] = useState<string | null>(null);
  const [activeView, setActiveView] = useState<"filter" | "rules">("filter");
  const [outputDir, setOutputDir] = useState<string | null>(null);
  const [logs, setLogs] = useState<string[]>(["正在启动 Python 后端"]);
  const [isProcessing, setIsProcessing] = useState(false);
  const [progress, setProgress] = useState<{ done: number; total: number } | null>(
    null,
  );
  const [notice, setNotice] = useState<string | null>(null);
  const [backendReady, setBackendReady] = useState(false);
  const backendRef = useRef<BackendService | null>(null);

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

  useEffect(() => {
    if (!notice) {
      return;
    }
    const timer = window.setTimeout(() => setNotice(null), 6000);
    return () => window.clearTimeout(timer);
  }, [notice]);

  async function runFilterFor(fileList: string[]) {
    if (!apiBase || isProcessing || !fileList.length) {
      return;
    }
    setIsProcessing(true);
    setNotice(null);
    setProgress({ done: 0, total: fileList.length });
    appendLog("开始筛选");
    try {
      const response = await filterExcelFilesStream(
        apiBase,
        fileList,
        outputDir,
        (event) => {
          setProgress({ done: event.index, total: event.total });
        },
      );
      setOutputDir(response.output_dir);
      setLogs((current) => [...current, ...response.logs]);
      setNotice("已筛选完毕，请打开目录进行查看");
    } catch (error) {
      appendLog(`筛选失败: ${formatError(error)}`);
      setNotice(null);
    } finally {
      setIsProcessing(false);
      setProgress(null);
    }
  }

  async function addTargets(targets: string[]) {
    if (!apiBase || !targets.length) {
      return;
    }
    const response = await expandTargets(apiBase, targets);
    if (!response.files.length) {
      appendLog("未发现可处理的 Excel 文件");
      return;
    }
    appendLog(`本次选择 ${response.files.length} 个 Excel 文件`);
    await runFilterFor(response.files);
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

  async function openResultDir() {
    if (outputDir) {
      await openPath(outputDir);
    }
  }

  async function checkForUpdates() {
    try {
      const update = await check();
      if (!update) {
        setNotice("当前已是最新版本");
        return;
      }

      const shouldInstall = await confirm(
        `发现新版本 ${update.version}，是否立即安装？`,
        { title: "检查更新", kind: "info" },
      );
      if (!shouldInstall) {
        return;
      }

      await update.downloadAndInstall();
      await relaunch();
    } catch (error) {
      setNotice(`检查失败: ${formatError(error)}`);
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
        <section className="filter-hero" aria-label="文件筛选">
          <div className="filter-hero-inner">
            <button
              className="hero-add"
              type="button"
              onClick={selectFiles}
              disabled={!backendReady || isProcessing}
            >
              <span className="hero-add-icon">
                {isProcessing ? (
                  <Loader2 className="spin" size={17} />
                ) : (
                  <FilePlus2 size={17} />
                )}
              </span>
              <span className="hero-add-label">
                {isProcessing ? "正在筛选…" : "添加 Excel"}
              </span>
            </button>

            {isProcessing && progress ? (
              <div
                className="hero-progress"
                role="progressbar"
                aria-label="筛选进度"
                aria-valuemin={0}
                aria-valuemax={progress.total}
                aria-valuenow={progress.done}
              >
                <div className="hero-progress-track">
                  <span
                    className="hero-progress-fill"
                    style={{
                      width: `${
                        progress.total
                          ? Math.round(
                              (progress.done / progress.total) * 100,
                            )
                          : 0
                      }%`,
                    }}
                  />
                </div>
                <span className="hero-progress-text">
                  {progress.done}/{progress.total}
                </span>
              </div>
            ) : (
              <button
                className="hero-open"
                type="button"
                onClick={openResultDir}
                disabled={!outputDir}
              >
                <FolderOpen size={15} />
                打开目录
              </button>
            )}
          </div>
        </section>
      ) : (
        <RulesView
          baseUrl={apiBase}
          backendReady={backendReady}
          onLog={appendLog}
        />
      )}

      {notice ? (
        <div className="toast" role="status">
          <CheckCircle2 size={18} className="toast-icon" />
          <span className="toast-text">{notice}</span>
          <button
            className="toast-action"
            type="button"
            onClick={openResultDir}
            disabled={!outputDir}
          >
            打开目录
          </button>
          <button
            className="toast-close"
            type="button"
            aria-label="关闭"
            onClick={() => setNotice(null)}
          >
            <X size={15} />
          </button>
        </div>
      ) : null}
    </main>
  );
}
