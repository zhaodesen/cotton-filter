import { Command } from "@tauri-apps/plugin-shell";

export interface BackendService {
  baseUrl: string;
  stop: () => Promise<void>;
}

type LogSink = (message: string) => void;

function pickPort(): number {
  return 18763 + Math.floor(Math.random() * 1000);
}

async function waitForHealth(baseUrl: string): Promise<void> {
  const startedAt = Date.now();
  let lastError: unknown = null;

  while (Date.now() - startedAt < 30000) {
    try {
      const response = await fetch(`${baseUrl}/health`);
      if (response.ok) {
        return;
      }
      lastError = new Error(response.statusText);
    } catch (error) {
      lastError = error;
    }
    await new Promise((resolve) => window.setTimeout(resolve, 250));
  }

  throw new Error(`Python 后端启动超时: ${String(lastError)}`);
}

export async function startBackend(onLog: LogSink): Promise<BackendService> {
  const port = pickPort();
  const baseUrl = `http://127.0.0.1:${port}`;
  onLog(`准备启动 Python 后端: ${baseUrl}`);
  const command = Command.sidecar("binaries/cotton-filter-backend", [
    "--host",
    "127.0.0.1",
    "--port",
    String(port),
  ]);

  command.stdout.on("data", (data) => {
    const text = String(data).trim();
    if (text) {
      onLog(`[backend] ${text}`);
    }
  });
  command.stderr.on("data", (data) => {
    const text = String(data).trim();
    if (text) {
      onLog(`[backend] ${text}`);
    }
  });

  const child = await command.spawn();
  try {
    await waitForHealth(baseUrl);
  } catch (error) {
    await child.kill();
    throw error;
  }

  return {
    baseUrl,
    stop: async () => {
      await child.kill();
    },
  };
}
