import { copyFileSync, mkdirSync, rmSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { execFileSync } from "node:child_process";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
function commandExists(command) {
  try {
    execFileSync(command, ["--version"], { stdio: "ignore" });
    return true;
  } catch {
    return false;
  }
}

const pythonCommand = process.env.PYTHON
  ? { bin: process.env.PYTHON, prefixArgs: [] }
  : commandExists("uv")
    ? { bin: "uv", prefixArgs: ["run", "python"] }
    : {
        bin: process.platform === "win32" ? "python" : "python3",
        prefixArgs: [],
      };
const exeSuffix = process.platform === "win32" ? ".exe" : "";
const targetTriple = execFileSync("rustc", ["--print", "host-tuple"], {
  encoding: "utf8",
}).trim();

const distDir = join(root, "dist", "backend");
const workDir = join(root, "build", "backend");
const binariesDir = join(root, "src-tauri", "binaries");
const backendName = `cotton-filter-backend${exeSuffix}`;
const sidecarName = `cotton-filter-backend-${targetTriple}${exeSuffix}`;

mkdirSync(distDir, { recursive: true });
mkdirSync(workDir, { recursive: true });
mkdirSync(binariesDir, { recursive: true });
rmSync(join(distDir, backendName), { force: true });

execFileSync(
  pythonCommand.bin,
  [
    ...pythonCommand.prefixArgs,
    "-m",
    "PyInstaller",
    "--noconfirm",
    "--clean",
    "--onefile",
    // Windows 上 PyInstaller 默认是控制台程序，会让 Tauri sidecar 弹出小黑窗。
    // --windowed 改为 GUI 子系统，不分配控制台。仅限 Windows：macOS 上
    // --windowed 会生成 .app bundle，破坏单文件 sidecar 的预期。
    ...(process.platform === "win32" ? ["--windowed"] : []),
    "--name",
    "cotton-filter-backend",
    "--distpath",
    distDir,
    "--workpath",
    workDir,
    "--specpath",
    workDir,
    "--hidden-import",
    "uvicorn.lifespan.on",
    "--hidden-import",
    "uvicorn.loops.auto",
    "--hidden-import",
    "uvicorn.protocols.http.auto",
    "--collect-submodules",
    "openpyxl",
    "--collect-submodules",
    "xlrd",
    join(root, "backend", "server.py"),
  ],
  {
    cwd: root,
    stdio: "inherit",
  },
);

copyFileSync(join(distDir, backendName), join(binariesDir, sidecarName));
console.log(`Backend sidecar ready: src-tauri/binaries/${sidecarName}`);
