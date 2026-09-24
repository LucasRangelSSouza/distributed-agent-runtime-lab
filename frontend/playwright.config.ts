import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  use: { baseURL: "http://127.0.0.1:5173", ...devices["Desktop Chrome"] },
  webServer: [
    { command: "python -m runtime_lab.web", cwd: "..", url: "http://127.0.0.1:8080/healthz", reuseExistingServer: true },
    { command: "npm run dev -- --host 127.0.0.1 --port 5173", url: "http://127.0.0.1:5173", reuseExistingServer: true },
  ],
});
