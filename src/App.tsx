import {
  CheckCircle2,
  Database,
  FilePlus2,
  FileSpreadsheet,
  FolderOpen,
  Loader2,
  Minus,
  RefreshCw,
  Square,
  X,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { open } from "@tauri-apps/plugin-dialog";
import { openPath } from "@tauri-apps/plugin-opener";
import { relaunch } from "@tauri-apps/plugin-process";
import { confirm } from "@tauri-apps/plugin-dialog";
import { check } from "@tauri-apps/plugin-updater";
import { getCurrentWindow } from "@tauri-apps/api/window";

import { expandTargets, filterExcelFilesStream } from "./api";
import { BackendService, startBackend } from "./backend";
import RulesView from "./RulesView";

function formatError(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }
  return String(error);
}

function CottonSketchIllustration() {
  return (
    <svg
      className="cotton-sketch"
      viewBox="0 0 520 360"
      role="img"
      aria-label="铅笔描绘的棉花插画"
      xmlns="http://www.w3.org/2000/svg"
    >
      <defs>
        <filter id="pencil-grain" x="-10%" y="-10%" width="120%" height="120%">
          <feTurbulence
            type="fractalNoise"
            baseFrequency="0.88"
            numOctaves="3"
            seed="8"
            result="noise"
          />
          <feDisplacementMap
            in="SourceGraphic"
            in2="noise"
            scale="1.4"
            xChannelSelector="R"
            yChannelSelector="G"
          />
        </filter>
      </defs>
      <g filter="url(#pencil-grain)">
        <path
          className="cotton-shadow-line"
          d="M115 311c82 16 218 15 294-2"
          pathLength="1"
        />
        <path
          className="cotton-stem"
          d="M262 286c-5-46 6-89 30-128"
          pathLength="1"
        />
        <path
          className="cotton-stem"
          d="M256 280c-21-38-51-64-92-81"
          pathLength="1"
        />
        <path
          className="cotton-stem"
          d="M270 272c38-21 68-48 90-84"
          pathLength="1"
        />

        <path
          className="cotton-leaf"
          d="M173 219c-31 5-60-8-78-35 30-11 61-3 82 28"
          pathLength="1"
        />
        <path
          className="cotton-leaf-vein"
          d="M101 185c25 6 48 16 72 30"
          pathLength="1"
        />
        <path
          className="cotton-leaf"
          d="M341 209c28-25 62-28 96-12-23 28-57 41-94 19"
          pathLength="1"
        />
        <path
          className="cotton-leaf-vein"
          d="M432 198c-29 4-58 9-87 17"
          pathLength="1"
        />

        <g className="cotton-boll">
          <path
            d="M213 139c-19-30 5-70 43-64 10-40 65-43 82-7 37-7 63 30 47 62 32 10 38 55 7 75-22 14-53 7-68-15-18 28-58 30-78 3-25 20-62 8-71-23-5-17 6-32 38-31Z"
            pathLength="1"
          />
          <path
            className="cotton-soft-line"
            d="M250 88c17 20 18 45 3 74"
            pathLength="1"
          />
          <path
            className="cotton-soft-line"
            d="M318 76c-14 28-12 55 6 82"
            pathLength="1"
          />
          <path
            className="cotton-soft-line"
            d="M217 141c33-8 62 1 84 28"
            pathLength="1"
          />
          <path
            className="cotton-soft-line"
            d="M331 166c22-26 48-37 75-30"
            pathLength="1"
          />
          <path
            className="cotton-hatch"
            d="M222 125c13-13 28-20 47-21M342 95c16 4 28 13 38 28M203 169c20 18 43 24 68 17M333 188c23 9 44 8 62-5"
            pathLength="1"
          />
        </g>

        <g className="cotton-boll cotton-boll-small">
          <path
            d="M120 150c-11-20 5-45 29-42 7-26 43-28 54-5 22-4 39 20 30 40 20 8 23 36 2 48-15 9-35 3-44-11-12 18-38 20-51 3-17 12-40 4-46-16-3-10 4-19 26-17Z"
            pathLength="1"
          />
          <path
            className="cotton-soft-line"
            d="M147 116c9 13 10 30 1 48"
            pathLength="1"
          />
          <path
            className="cotton-soft-line"
            d="M193 109c-8 18-7 35 4 52"
            pathLength="1"
          />
          <path
            className="cotton-hatch"
            d="M116 168c15 12 32 16 49 10M203 171c14 5 27 4 39-4"
            pathLength="1"
          />
        </g>

        <g className="cotton-boll cotton-boll-small">
          <path
            d="M337 151c-12-20 4-46 29-42 8-27 44-29 56-6 23-5 41 20 31 41 21 8 24 37 3 50-16 9-37 3-47-12-12 19-39 21-53 3-17 13-41 4-47-17-4-11 4-20 28-17Z"
            pathLength="1"
          />
          <path
            className="cotton-soft-line"
            d="M365 116c9 14 10 31 0 50"
            pathLength="1"
          />
          <path
            className="cotton-soft-line"
            d="M413 109c-9 19-7 36 4 54"
            pathLength="1"
          />
          <path
            className="cotton-hatch"
            d="M331 169c16 13 34 17 52 10M423 173c15 5 29 4 42-5"
            pathLength="1"
          />
        </g>
      </g>
    </svg>
  );
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
  const [useWindowsCustomFrame, setUseWindowsCustomFrame] = useState(false);
  const backendRef = useRef<BackendService | null>(null);

  function appendLog(message: string) {
    setLogs((current) => [...current, message]);
  }

  useEffect(() => {
    setUseWindowsCustomFrame(navigator.userAgent.toLowerCase().includes("windows"));
  }, []);

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

  async function minimizeWindow() {
    await getCurrentWindow().minimize();
  }

  async function toggleMaximizeWindow() {
    await getCurrentWindow().toggleMaximize();
  }

  async function closeWindow() {
    await getCurrentWindow().close();
  }

  return (
    <main className={activeView === "rules" ? "app-shell rules-mode" : "app-shell"}>
      <div
        className={
          useWindowsCustomFrame
            ? "window-drag-bar window-drag-bar-with-controls"
            : "window-drag-bar"
        }
      >
        <div className="window-drag-region" data-tauri-drag-region />
        {useWindowsCustomFrame ? (
          <div className="window-controls">
            <button
              className="window-control-btn"
              type="button"
              title="最小化"
              aria-label="最小化"
              onClick={() => void minimizeWindow()}
            >
              <Minus size={13} />
            </button>
            <button
              className="window-control-btn"
              type="button"
              title="最大化"
              aria-label="最大化"
              onClick={() => void toggleMaximizeWindow()}
            >
              <Square size={12} />
            </button>
            <button
              className="window-control-btn window-control-btn-close"
              type="button"
              title="关闭"
              aria-label="关闭"
              onClick={() => void closeWindow()}
            >
              <X size={14} />
            </button>
          </div>
        ) : null}
      </div>

      <section className="topbar" data-tauri-drag-region>
        <nav className="view-tabs" aria-label="菜单" data-tauri-no-drag>
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
        <button
          className="ghost-button"
          type="button"
          onClick={checkForUpdates}
          data-tauri-no-drag
        >
          <RefreshCw size={17} />
          检查更新
        </button>
      </section>

      {activeView === "filter" ? (
        <section className="filter-hero" aria-label="文件筛选">
          <div className="filter-hero-inner">
            <CottonSketchIllustration />
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
