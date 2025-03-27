"use client";

import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import {
  Play,
  RefreshCcw,
  Server,
  Loader2,
  Moon,
  Sun,
  Power,
  Settings as SettingsIcon,
  Crown,
  Trash2,
} from "lucide-react";
import "./App.css";
import { Toaster, toast } from "react-hot-toast";
import { invoke } from "@tauri-apps/api/core"
import { listen } from '@tauri-apps/api/event';

enum LauncherState {
  NeedsUpdate = "Needs Update",
  Updating = "Updating...",
  Ready = "Launch Game",
  InitialState = "Check For Update"
}

export default function HomePage() {
  // Dark mode state
  const [darkMode, setDarkMode] = useState(false);

  // Server and logs
  const [serverRunning, setServerRunning] = useState(false);
  const [logs, setLogs] = useState<string[]>([]);

  // Game update/launch logic
  const [launcherState, setLauncherState] = useState(LauncherState.InitialState);
  const [updateProgress, setUpdateProgress] = useState(0);
  const [gameLoading, setGameLoading] = useState(false);

  // Settings (Name & IP)
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [name, setName] = useState("");
  const [ip, setIp] = useState("");
  const [currentVersion, setCurrentVersion] = useState("LOADING");
  const [loaded, setLoaded] = useState(false);

  // console.log(invoke("check_for_updates", {currentTag: ""}))

  // Sync darkMode with the .dark class on <html/>
  useEffect(() => {
    const root = document.documentElement;
    darkMode ? root.classList.add("dark") : root.classList.remove("dark");
  }, [darkMode]);


  useEffect(() => {
    if (serverRunning) {
        const logListener = listen<string>('server-log', (event) => {
            setLogs(prevLogs => {
                const updatedLogs = [...prevLogs, `${event.payload}`];
                return updatedLogs.slice(-100);
            });
        });

        const errorListener = listen<string>('server-error', (event) => {
            setLogs(prevLogs => {
                const updatedLogs = [...prevLogs, `${event.payload}`];
                return updatedLogs.slice(-100);
            });
        });

        return () => {
            // Unlisten to both events when component unmounts or server stops
            Promise.all([logListener, errorListener]).then(unlisteners => {
                unlisteners.forEach(unlisten => unlisten());
            });
        };
    }
}, [serverRunning]);

    useEffect(() => {
    if (!loaded) {
      setLoaded(true);

      listen<string>("config-current-version", (event) => {
        console.log(event.payload);
        setCurrentVersion(event.payload);

        // Check for updates when version is received
        const checkUpdates = async () => {
          try {
            const updateInfo = await invoke("check_for_updates", { currentTag: event.payload }) as [string, string] | null;
            
            if (updateInfo) {
              setLauncherState(LauncherState.NeedsUpdate);
            } else {
              setLauncherState(LauncherState.Ready);
            }
          } catch (error) {
            console.error("Update check failed:", error);
          }
        };

        checkUpdates();
      });

      invoke("get_current_version");
    }
  }, [loaded]);

    useEffect(() => {
    // Only start periodic checks if initial load is done
    if (!loaded) return;

    // Check version every 5 seconds
    const versionInterval = setInterval(() => {
      console.log()
      invoke("get_current_version");
    }, 5000);

    // Clean up interval when component unmounts
    return () => clearInterval(versionInterval);
  }, [loaded]);

  /**
   * Main "Update / Launch" action.
   */
  const handleAction = async () => {
    if (launcherState === LauncherState.NeedsUpdate || launcherState == LauncherState.InitialState) {
      try {
        // Simulate update progress for UI
        setLauncherState(LauncherState.Updating);
        
        // Fetch update info again to get download URLs
        const updateInfo = await invoke("check_for_updates", { currentTag: currentVersion }) as [string, string] | null;

        console.log(updateInfo)
        
        if (updateInfo) {
          const [clientUrl, serverUrl] = updateInfo;
          
          // Download and extract updates
          await invoke("download_and_extract_updates", { 
            clientUrl, 
            serverUrl 
          });

          console.log("ok")

          // Update current version 
          // Note: In a real app, you'd extract the new version from the release
          setCurrentVersion("v0.1.0");
          
          // Simulate progress
          for (let progress = 0; progress <= 100; progress += 10) {
            await new Promise(resolve => setTimeout(resolve, 200));
            setUpdateProgress(progress);
          }
          
          setLauncherState(LauncherState.Ready);
          toast.success("Update completed successfully!");
        } else {
          toast.success("No update required");
          setLauncherState(LauncherState.Ready);
        }
      } catch (error) {
        console.error("Update failed:", error);
        toast.error("Update failed. Please try again.");
        setLauncherState(LauncherState.Ready);
      }
    } else if (ip == "" || name == "") {
      toast.error("You have not set the client IP or name!")
    } else if (launcherState === LauncherState.Ready) {
      // Launch the game
      setGameLoading(true);
      setTimeout(async () => {
        setGameLoading(false);
        await invoke("start_game", { ip, name });
      }, 2000);
    }
  };

  /**
   * Toggle server on/off + logs.
   */
  const handleToggleServer = async () => {
    if (serverRunning) {
      setTimeout(async () => {
        await invoke("stop_server");
        setServerRunning(false);
      }, 1000);
    } else {
      setLogs([])
      await invoke("start_server"); 
      setServerRunning(true);
    }
  };

  /**
   * Refresh logs (just a UI action) or Clear logs.
   */
  const handleRefreshLogs = () => {
    setLogs((prev) => [...prev, "[Manual Refresh] Logs have been refreshed."]);
  };
  const handleClearLogs = () => {
    setLogs([]);
  };

  return (
    <>
    <Toaster />
    <div
      className={`
        min-h-screen w-full
        text-gray-900 dark:text-gray-100
        transition-colors duration-500 
        flex flex-col items-center
        px-6 py-8
        relative overflow-hidden
        bg-gray-100 dark:bg-gray-900
      `}
      style={{ fontFamily: "Inter, sans-serif" }}
    >
      {/* 
        Top Wave 
      */}
      <div className="absolute top-0 left-0 w-full z-0 overflow-hidden leading-none pointer-events-none">
        <svg
          className="dark:hidden"
          viewBox="0 0 1200 120"
          preserveAspectRatio="none"
          style={{ height: "100px", width: "100%" }}
        >
          <path
            d="M321.39,56.41C246.62,39.06,171.94,19.29,97.21,1.29
            C54.13-9.19,10.75-17.94-33.49,2.09
            c-25.14,11.03-48.63,27.08-74.15,37.54
            C-167.26,54.77-218.83,61.94-270,56.41v63h540Z"
            fill="#E5E7EB" /* Light wave color */
          />
        </svg>
        <svg
          className="hidden dark:block"
          viewBox="0 0 1200 120"
          preserveAspectRatio="none"
          style={{ height: "100px", width: "100%" }}
        >
          <path
            d="M321.39,56.41C246.62,39.06,171.94,19.29,97.21,1.29
            C54.13-9.19,10.75-17.94-33.49,2.09
            c-25.14,11.03-48.63,27.08-74.15,37.54
            C-167.26,54.77-218.83,61.94-270,56.41v63h540Z"
            fill="#1F2937" /* Dark wave color */
          />
        </svg>
      </div>

      {/* Title + Settings + Dark Mode */}
      <div className="flex items-center justify-between w-full max-w-5xl mb-8 z-10">
        <div className="flex items-center gap-2">
          <Crown size={28} />
          <h1 className="text-3xl md:text-4xl font-extrabold tracking-tight">
            Clash Royale
          </h1>
        </div>
        <div className="flex items-center gap-3">
          {/* Settings Button */}
          <Button
            variant="outline"
            className="
              inline-flex items-center gap-2 
              rounded-full px-3 py-2
              border-gray-300 dark:border-gray-700 
              hover:bg-gray-200 dark:hover:bg-gray-700
              transition-colors
              relative z-20
            "
            aria-label="Open settings"
            onClick={() => setSettingsOpen(true)}
          >
            <SettingsIcon size={18} />
            <span className="hidden sm:inline">Settings</span>
          </Button>

          {/* Dark Mode Toggle */}
          <Button
            variant="outline"
            onClick={() => setDarkMode(!darkMode)}
            className="
              inline-flex items-center gap-2 
              rounded-full px-3 py-2
              border-gray-300 dark:border-gray-700 
              hover:bg-gray-200 dark:hover:bg-gray-700
              transition-colors
              relative z-20
            "
            aria-label="Toggle dark mode"
          >
            {darkMode ? (
              <>
                <Sun size={18} />
                <span className="hidden sm:inline">Light Mode</span>
              </>
            ) : (
              <>
                <Moon size={18} />
                <span className="hidden sm:inline">Dark Mode</span>
              </>
            )}
          </Button>
        </div>
      </div>

      {/* Body */}
      <div className="flex flex-col md:flex-row items-start justify-center w-full max-w-5xl space-y-8 md:space-y-0 md:space-x-8 z-10">
        {/* Left Column: Game Update + Server Control */}
        <div className="w-full md:w-1/3 space-y-6">
          {/* Game Update/Launch Card */}
          <Card
            className="
              relative z-10
              rounded-lg 
              border border-gray-200 dark:border-gray-700 
              bg-white/70 dark:bg-gray-800/70 
              backdrop-blur-md
              shadow-md
              transition-all transform
              hover:shadow-lg hover:-translate-y-1 hover:rotate-[-1deg]
            "
          >
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-lg font-semibold">
                {launcherState === LauncherState.Updating ? (
                  <RefreshCcw className="animate-spin" size={20} />
                ) : launcherState === LauncherState.Ready ? (
                  <Play size={20} />
                ) : (
                  <RefreshCcw size={20} />
                )}
                Client
              </CardTitle>
            </CardHeader>
            <CardContent>
              <Button
                size="lg"
                onClick={handleAction}
                  disabled={currentVersion == "LOADING"}
                className="
                  relative w-full 
                  rounded-md
                  bg-gray-900 text-white 
                  hover:bg-gray-700
                  dark:bg-gray-100 dark:text-gray-900
                  dark:hover:bg-gray-300
                  transition-colors
                  focus:outline-none
                  focus:ring-2 focus:ring-offset-2
                  focus:ring-gray-400 dark:focus:ring-gray-600
                "
              >
                {launcherState}
                {launcherState === LauncherState.Updating && (
                  <div className="absolute bottom-0 left-0 w-full">
                    <Progress
                      className="
                        h-1
                        bg-gray-300 dark:bg-gray-700 
                        transition-all
                      "
                      value={updateProgress}
                      max={100}
                    />
                  </div>
                )}
              </Button>
            </CardContent>
          </Card>

          {/* Server Control Card */}
          <Card
            className="
              relative z-10
              rounded-lg 
              border border-gray-200 dark:border-gray-700 
              bg-white/70 dark:bg-gray-800/70 
              backdrop-blur-md
              shadow-md
              transition-all transform
              hover:shadow-lg hover:-translate-y-1 hover:rotate-[-1deg]
            "
          >
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-lg font-semibold">
                <Server size={20} />
                Server Control
              </CardTitle>
            </CardHeader>
            <CardContent>
              <Button
                onClick={handleToggleServer}
                  disabled={currentVersion == "LOADING" || launcherState == LauncherState.NeedsUpdate}
                className="
                  w-full 
                  rounded-md
                  bg-gray-900 text-white 
                  hover:bg-gray-700
                  dark:bg-gray-100 dark:text-gray-900
                  dark:hover:bg-gray-300
                  transition-colors
                  flex items-center justify-center gap-2
                  mb-3
                  focus:outline-none
                  focus:ring-2 focus:ring-offset-2
                  focus:ring-gray-400 dark:focus:ring-gray-600
                "
              >
                <Power size={16} />
                {serverRunning ? "Stop Server" : "Start Server"}
              </Button>

              {serverRunning && (
                <div className="flex flex-col gap-2">
                  <Button
                    variant="outline"
                    onClick={handleRefreshLogs}
                    className="
                      w-full
                      rounded-md
                      border border-gray-300 dark:border-gray-600
                      text-gray-700 dark:text-gray-200
                      hover:bg-gray-100 dark:hover:bg-gray-700
                      transition-colors
                      flex items-center justify-center gap-2
                      focus:outline-none
                      focus:ring-2 focus:ring-offset-2
                      focus:ring-gray-400 dark:focus:ring-gray-600
                    "
                  >
                    <RefreshCcw size={16} />
                    Refresh Logs
                  </Button>
                  <Button
                    variant="outline"
                    onClick={handleClearLogs}
                    className="
                      w-full
                      rounded-md
                      border border-gray-300 dark:border-gray-600
                      text-gray-700 dark:text-gray-200
                      hover:bg-gray-100 dark:hover:bg-gray-700
                      transition-colors
                      flex items-center justify-center gap-2
                      focus:outline-none
                      focus:ring-2 focus:ring-offset-2
                      focus:ring-gray-400 dark:focus:ring-gray-600
                    "
                  >
                    <Trash2 size={16} />
                    Clear Logs
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Right Column: Logs or Changelog */}
        <div className="w-full md:w-2/3 flex flex-col items-center text-center">
          {serverRunning ? (
            <Card
              className="
                w-full max-w-lg 
                relative z-10
                rounded-lg 
                border border-gray-200 dark:border-gray-700 
                bg-white/70 dark:bg-gray-800/70 
                backdrop-blur-md
                shadow-md
                transition-all transform
                hover:shadow-lg hover:-translate-y-1 hover:rotate-[-1deg]
              "
            >
              <CardHeader>
                <CardTitle className="text-base font-medium flex justify-between items-center">
                  <span>Server Logs</span>
                </CardTitle>
              </CardHeader>
              <CardContent className="text-sm space-y-2 h-44 overflow-auto pr-2">
                {logs.map((log, index) => (
                  <div
                    key={index}
                    className="
                      p-2 rounded 
                      hover:bg-gray-50 dark:hover:bg-gray-700
                      transition-colors
                    "
                  >
                    {log}
                  </div>
                ))}
              </CardContent>
            </Card>
          ) : (
            <Card
              className="
                w-full max-w-lg
                relative z-10
                rounded-lg 
                border border-gray-200 dark:border-gray-700 
                bg-white/70 dark:bg-gray-800/70 
                backdrop-blur-md
                shadow-md
                transition-all transform
                hover:shadow-lg hover:-translate-y-1 hover:rotate-[-1deg]
              "
            >
              <CardHeader>
                <CardTitle className="text-base font-medium">
                  Latest Updates
                </CardTitle>
              </CardHeader>
              <CardContent>
                <ul className="list-disc list-inside text-sm space-y-2 text-left md:text-center">
                  <li>New "Electro Giant" card joins the arena!</li>
                  <li>Balance changes for Archer Queen and Royal Ghost.</li>
                  <li>Various bug fixes and performance improvements.</li>
                  <li>New season with exclusive rewards!</li>
                </ul>
              </CardContent>
            </Card>
          )}
        </div>
      </div>

      {/* Bottom Wave */}
      <div className="absolute bottom-0 left-0 w-full z-0 overflow-hidden leading-none pointer-events-none">
        <svg
          className="dark:hidden rotate-180"
          viewBox="0 0 1200 120"
          preserveAspectRatio="none"
          style={{ height: "100px", width: "100%" }}
        >
          <path
            d="M321.39,56.41C246.62,39.06,171.94,19.29,97.21,1.29
            C54.13-9.19,10.75-17.94-33.49,2.09
            c-25.14,11.03-48.63,27.08-74.15,37.54
            C-167.26,54.77-218.83,61.94-270,56.41v63h540Z"
            fill="#E5E7EB"
          />
        </svg>
        <svg
          className="hidden dark:block rotate-180"
          viewBox="0 0 1200 120"
          preserveAspectRatio="none"
          style={{ height: "100px", width: "100%" }}
        >
          <path
            d="M321.39,56.41C246.62,39.06,171.94,19.29,97.21,1.29
            C54.13-9.19,10.75-17.94-33.49,2.09
            c-25.14,11.03-48.63,27.08-74.15,37.54
            C-167.26,54.77-218.83,61.94-270,56.41v63h540Z"
            fill="#1F2937"
          />
        </svg>
      </div>

      {/* Settings Dialog */}
      <Dialog open={settingsOpen} onOpenChange={setSettingsOpen}>
        <DialogContent
          className="
            rounded-md border
            border-gray-200 dark:border-gray-700 
            bg-white dark:bg-gray-800
            shadow-2xl 
            max-w-lg
          "
        >
          <DialogHeader>
            <DialogTitle className="text-lg font-semibold">
              Settings
            </DialogTitle>
          </DialogHeader>
          <p className="text-sm text-gray-700 dark:text-gray-300 mb-4">
            Configure your Clash Royale Name and Server IP here.
          </p>
          <div className="space-y-4">
            <Input
              placeholder="In-Game Name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="
                w-full rounded-md
                bg-gray-100 dark:bg-gray-700 
                text-gray-900 dark:text-gray-100
                border border-gray-200 dark:border-gray-600
                focus:outline-none focus:ring-2 
                focus:ring-gray-300 dark:focus:ring-gray-500
              "
            />
            <Input
              placeholder="Server IP:Port"
              value={ip}
              onChange={(e) => setIp(e.target.value)}
              className="
                w-full rounded-md
                bg-gray-100 dark:bg-gray-700 
                text-gray-900 dark:text-gray-100
                border border-gray-200 dark:border-gray-600
                focus:outline-none focus:ring-2 
                focus:ring-gray-300 dark:focus:ring-gray-500
              "
            />
          </div>
          <DialogFooter className="mt-4 flex justify-end">
            <Button
              variant="outline"
              onClick={() => setSettingsOpen(false)}
              className="
                rounded-md 
                border border-gray-300 dark:border-gray-600 
                text-gray-700 dark:text-gray-200 
                hover:bg-gray-100 dark:hover:bg-gray-700
                transition-colors
              "
            >
              Close
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Game Launching Dialog */}
      <Dialog open={gameLoading}>
        <DialogContent
          className="
            rounded-md border 
            border-gray-200 dark:border-gray-700 
            bg-white dark:bg-gray-800 
            shadow-2xl flex flex-col items-center
          "
        >
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-lg font-semibold">
              <Loader2 className="animate-spin" size={20} />
              <span>Launching...</span>
            </DialogTitle>
          </DialogHeader>
          <p className="text-sm text-gray-700 dark:text-gray-300">
            Loading Clash Royale, please wait...
          </p>
        </DialogContent>
      </Dialog>
    </div>
    </>
  );
}
