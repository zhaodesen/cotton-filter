import { mkdirSync, readdirSync, readFileSync, writeFileSync } from "node:fs";
import { basename, dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const version = process.env.GITHUB_REF_NAME || process.env.APP_VERSION || "0.1.0";
const repository = process.env.GITHUB_REPOSITORY || "zhaodesen/cotton-filter";

function mapTarget() {
  if (process.platform === "win32") {
    return "windows";
  }
  if (process.platform === "darwin") {
    return "darwin";
  }
  return "linux";
}

function mapArch() {
  if (process.arch === "x64") {
    return "x86_64";
  }
  if (process.arch === "arm64") {
    return "aarch64";
  }
  return process.arch;
}

function walk(dir) {
  return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const path = join(dir, entry.name);
    return entry.isDirectory() ? walk(path) : [path];
  });
}

const target = mapTarget();
const arch = mapArch();
const bundleDir = join(root, "src-tauri", "target", "release", "bundle");
const files = walk(bundleDir);
const updateArtifact = files.find((file) => {
  if (target === "windows") {
    return /-setup\.exe$/.test(file) && files.includes(`${file}.sig`);
  }
  if (target === "darwin") {
    return /\.app\.tar\.gz$/.test(file) && files.includes(`${file}.sig`);
  }
  return /\.AppImage$/.test(file) && files.includes(`${file}.sig`);
});

if (!updateArtifact) {
  throw new Error(`未找到 ${target}-${arch} 的 Tauri 更新产物`);
}

const signature = readFileSync(`${updateArtifact}.sig`, "utf8").trim();
const artifactName = basename(updateArtifact);
const manifest = {
  version,
  notes: `cotton-filter ${version}`,
  pub_date: new Date().toISOString(),
  platforms: {
    [`${target}-${arch}`]: {
      signature,
      url: `https://github.com/${repository}/releases/download/${version}/${artifactName}`,
    },
  },
};

const outputDir = join(root, "dist", "updater");
mkdirSync(outputDir, { recursive: true });
writeFileSync(
  join(outputDir, `latest-${target}-${arch}.json`),
  `${JSON.stringify(manifest, null, 2)}\n`,
);

console.log(`Updater manifest ready: dist/updater/latest-${target}-${arch}.json`);

