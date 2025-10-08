import { Command, Child } from "@tauri-apps/plugin-shell";
import { getCurrentWindow } from "@tauri-apps/api/window";

let child: Child | null = null;
const appWindow = getCurrentWindow();

async function startServer() {
  const statusEl = document.getElementById("status");
  if (statusEl) statusEl.textContent = "Spawning Python server...";

  console.log("Creating command: python3 server.py");
  console.log("CWD:", "/Users/danielchayes/Workspace/photo-organizer");

  const cmd = Command.create("python3", ["server.py"], {
    cwd: "/Users/danielchayes/Workspace/photo-organizer",
  });

  // Attach event listeners to the command object BEFORE spawning
  cmd.stdout.on("data", (line: string) => {
    console.log("[Python stdout]:", line);
  });
  cmd.stderr.on("data", (line: string) => {
    console.error("[Python stderr]:", line);
  });

  // Spawn the command and store the Child object
  console.log("About to spawn command...");
  child = await cmd.spawn();
  console.log("Python server process spawned:", child.pid);
}

async function waitForServer(
  url = "http://localhost:3000/",
  timeoutMs = 30000,
  intervalMs = 500
): Promise<boolean> {
  const started = Date.now();
  const statusEl = document.getElementById("status");

  console.log(`Waiting for server at ${url}...`);

  while (Date.now() - started < timeoutMs) {
    try {
      console.log(`Attempting fetch to ${url}...`);
      const res = await fetch(url, { method: "GET", cache: "no-store" });
      console.log(`Fetch response: status=${res.status}, ok=${res.ok}`);
      if (res.ok) {
        console.log("Server is ready!");
        return true;
      }
    } catch (err) {
      console.error("Fetch error:", err);
      // Server not ready yet, continue waiting
    }

    if (statusEl) {
      const elapsed = Math.floor((Date.now() - started) / 1000);
      statusEl.textContent = `Waiting for server... (${elapsed}s)`;
    }
    await new Promise((r) => setTimeout(r, intervalMs));
  }

  console.error("Server wait timed out");
  return false;
}

async function navigateToApp() {
  console.log("Navigating to http://localhost:3000");
  window.location.href = "http://localhost:3000/";
}

async function init() {
  try {
    await startServer();
    const ready = await waitForServer();

    if (ready) {
      await navigateToApp();
    } else {
      const statusEl = document.getElementById("status");
      if (statusEl) {
        statusEl.textContent = "❌ Server failed to start. Check console.";
      }
      console.error("Server did not start in time");
    }
  } catch (err) {
    console.error("Error during initialization:", err);
    const statusEl = document.getElementById("status");
    if (statusEl) {
      statusEl.textContent = `❌ Error: ${err}`;
    }
  }
}

// Ensure server process is killed on close
appWindow.onCloseRequested(async (event) => {
  if (child) {
    event.preventDefault(); // Delay close while we clean up
    console.log("Killing Python server process...");
    try {
      await child.kill();
      console.log("Python server killed successfully");
    } catch (err) {
      console.error("Failed to kill server:", err);
    }
  }
  // Proceed to close after cleanup
  await appWindow.close();
});

// Start when DOM is ready
window.addEventListener("DOMContentLoaded", () => {
  init();
});
