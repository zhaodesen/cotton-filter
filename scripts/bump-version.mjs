import { readFileSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const nextVersion = process.argv[2];

if (!nextVersion || !/^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$/.test(nextVersion)) {
  console.error("用法: npm run bump-version -- 1.2.4");
  process.exit(1);
}

const releaseTag = `v${nextVersion}`;

function pathFromRoot(path) {
  return resolve(root, path);
}

function readText(path) {
  return readFileSync(pathFromRoot(path), "utf8");
}

function writeText(path, content) {
  writeFileSync(pathFromRoot(path), content);
}

function updateJson(path, updater) {
  const data = JSON.parse(readText(path));
  updater(data);
  writeText(path, `${JSON.stringify(data, null, 2)}\n`);
}

function replaceRequired(path, pattern, replacement) {
  const content = readText(path);
  if (!pattern.test(content)) {
    throw new Error(`未匹配到需要更新的版本字段: ${path}`);
  }
  const nextContent = content.replace(pattern, replacement);
  writeText(path, nextContent);
}

updateJson("package.json", (data) => {
  data.version = nextVersion;
});

updateJson("package-lock.json", (data) => {
  data.version = nextVersion;
  if (data.packages?.[""]) {
    data.packages[""].version = nextVersion;
  }
});

replaceRequired(
  "src-tauri/tauri.conf.json",
  /("version": ")[^"]+"/,
  `$1${nextVersion}"`,
);

replaceRequired(
  "pyproject.toml",
  /^version = "[^"]+"/m,
  `version = "${nextVersion}"`,
);

replaceRequired(
  "uv.lock",
  /(\[\[package\]\]\nname = "cotton-filter"\nversion = ")[^"]+"/,
  `$1${nextVersion}"`,
);

replaceRequired(
  "src-tauri/Cargo.toml",
  /^version = "[^"]+"/m,
  `version = "${nextVersion}"`,
);

replaceRequired(
  "src-tauri/Cargo.lock",
  /(\[\[package\]\]\nname = "cotton-filter"\nversion = ")[^"]+"/,
  `$1${nextVersion}"`,
);

replaceRequired(
  "README.md",
  /GITHUB_REF_NAME=v\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)? \\/,
  `GITHUB_REF_NAME=${releaseTag} \\`,
);

console.log(`已更新项目版本为 ${nextVersion}，发布 tag 为 ${releaseTag}`);
