use futures::stream::StreamExt;
use futures::try_join;
use serde::{Deserialize, Serialize};
use tokio::io::{AsyncBufRead, AsyncWriteExt};
use std::io::{BufRead, BufReader};
use std::net::{AddrParseError, SocketAddr, TcpListener};
use std::path::Path;
use std::process::{Child, Command, Stdio};
use std::str::FromStr;
use tokio::fs;
use tokio::{
    task,
};
use tauri::{AppHandle, Emitter, Listener, Manager};
use std::sync::Arc;
use tokio::sync::Mutex as AsyncMutex;

#[derive(serde::Deserialize)]
struct GitHubRelease {
    tag_name: String,
    assets: Vec<GitHubAsset>,
}

#[derive(serde::Deserialize)]
struct GitHubAsset {
    name: String,
    browser_download_url: String,
}

fn kill_process_using_port(port: u16) -> Result<Option<String>, String> {
    let addr: SocketAddr = format!("127.0.0.1:{}", port).parse().map_err(|e: AddrParseError| e.to_string())?;
    
    // Try to bind to the port to check if it's in use
    match TcpListener::bind(addr) {
        Ok(_) => {
            // Port is free
            Ok(None)
        }
        Err(_) => {
            // Port is in use, attempt to kill the process
            #[cfg(windows)]
            {
                let output = std::process::Command::new("netstat")
                    .args(&["-ano"])
                    .output()
                    .map_err(|e| format!("Failed to run netstat: {}", e))?;
                
                let output_str = String::from_utf8_lossy(&output.stdout);
                let pid_lines: Vec<&str> = output_str
                    .lines()
                    .filter(|line| line.contains(&format!(":{}", port)))
                    .collect();
                
                if let Some(line) = pid_lines.first() {
                    let parts: Vec<&str> = line.split_whitespace().collect();
                    if parts.len() >= 5 {
                        let pid = parts[4];
                        let kill_output = std::process::Command::new("taskkill")
                            .args(&["/PID", pid, "/F"])
                            .output()
                            .map_err(|e| format!("Failed to kill process: {}", e))?;
                        
                        return Ok(Some(format!("Killed process with PID {} using port {}", pid, port)));
                    }
                }
            }
            
            #[cfg(not(windows))]
            {
                let output = std::process::Command::new("lsof")
                    .args(&["-ti", &format!(":{}", port)])
                    .output()
                    .map_err(|e| format!("Failed to run lsof: {}", e))?;
                
                let pid = String::from_utf8_lossy(&output.stdout).trim().to_string();
                
                if !pid.is_empty() {
                    std::process::Command::new("kill")
                        .arg("-9")
                        .arg(&pid)
                        .output()
                        .map_err(|e| format!("Failed to kill process: {}", e))?;
                    
                    return Ok(Some(format!("Killed process with PID {} using port {}", pid, port)));
                }
            }
            
            Err(format!("Failed to identify process using port {}", port))
        }
    }
}



#[tauri::command]
async fn check_for_updates(current_tag: String) -> Result<Option<(String, String)>, String> {
    let repo_owner = "Superbro525Alt";
    let repo_name = "Y11PY";
    let api_url = format!(
        "https://api.github.com/repos/{}/{}/releases/latest",
        repo_owner, repo_name
    );

    let client = reqwest::Client::new();
    let response = match client
        .get(&api_url)
        .header("User-Agent", "ClashRoyale/v1")
        .send()
        .await
    {
        Ok(res) => res,
        Err(e) => return Err(format!("Failed to fetch latest release info: {}", e)),
    };

    if !response.status().is_success() {
        return Err(format!(
            "GitHub API request failed with status: {}",
            response.status()
        ));
    }

    let release_info: GitHubRelease = match response.json().await {
        Ok(data) => data,
        Err(e) => return Err(format!("Failed to parse latest release info: {}", e)),
    };

    if release_info.tag_name != current_tag {
        let mut client_url = None;
        let mut server_url = None;

        for asset in &release_info.assets {
            if asset.name.starts_with("client-") && asset.name.ends_with(".tar.gz") {
                client_url = Some(asset.browser_download_url.clone());
            } else if asset.name.starts_with("server-") && asset.name.ends_with(".tar.gz") {
                server_url = Some(asset.browser_download_url.clone());
            }
        }

        match (client_url, server_url) {
            (Some(client), Some(server)) => Ok(Some((client, server))),
            _ => Ok(Some(("Could not find both client and server packages.".into(), "".into()))), 
        }
    } else {
        Ok(None)
    }
}

#[tauri::command]
async fn download_and_extract_updates(client_url: String, server_url: String) -> Result<(), String> {
    let download_dir = Path::new("updates");
    fs::create_dir_all(&download_dir)
        .await
        .map_err(|e| format!("Failed to create download directory: {}", e))?;

    async fn download_file(url: String, filename: &Path) -> Result<(), String> {
        let client = reqwest::Client::new();
        let response = match client.get(&url).send().await {
            Ok(res) => res,
            Err(e) => return Err(format!("Failed to download {}: {}", filename.display(), e)),
        };

        if !response.status().is_success() {
            return Err(format!(
                "Failed to download {}, status: {}",
                filename.display(),
                response.status()
            ));
        }

        let mut stream = response.bytes_stream();
        let mut file = fs::File::create(filename)
            .await
            .map_err(|e| format!("Failed to create file {}: {}", filename.display(), e))?;

        while let Some(chunk) = stream.next().await {
            let bytes = chunk.map_err(|e| format!("Error reading download stream for {}: {}", filename.display(), e))?;
            file.write_all(&bytes)
                .await
                .map_err(|e| format!("Error writing to file {}: {}", filename.display(), e))?;
        }

        Ok(())
    }

    let client_file_path = download_dir.join("client.tar.gz");
    let server_file_path = download_dir.join("server.tar.gz");

    try_join!(
        download_file(client_url, &client_file_path),
        download_file(server_url, &server_file_path),
    )
    .map_err(|e| format!("Failed to download one or both files: {}", e))?;

    // Extraction
    let client_extract_dir = Path::new("client_update");
    fs::create_dir_all(&client_extract_dir)
        .await
        .map_err(|e| format!("Failed to create client extract directory: {}", e))?;

    let server_extract_dir = Path::new("server_update");
    fs::create_dir_all(&server_extract_dir)
        .await
        .map_err(|e| format!("Failed to create server extract directory: {}", e))?;

    async fn extract_tar_gz(archive_path: &Path, extract_path: &Path) -> Result<(), String> {
        let tar_gz = fs::File::open(archive_path)
            .await
            .map_err(|e| format!("Failed to open archive {}: {}", archive_path.display(), e))?;
        let tar = flate2::read::GzDecoder::new(tar_gz.into_std().await);
        let mut archive = tar::Archive::new(tar);
        archive
            .unpack(extract_path)
            .map_err(|e| format!("Failed to extract {} to {}: {}", archive_path.display(), extract_path.display(), e))?;
        Ok(())
    }

    try_join!(
        extract_tar_gz(&client_file_path, &client_extract_dir),
        extract_tar_gz(&server_file_path, &server_extract_dir),
    )
    .map_err(|e| format!("Failed to extract one or both archives: {}", e))?;

    Ok(())
}

#[tauri::command]
fn start_game(app_handle: AppHandle, name: String, ip: String) -> Result<(), String> {
    let game_path = Path::new("./client_update/client.dist").join("client.bin");
    
    if !game_path.exists() {
        return Err("Game executable not found".into());
    }

    let mut cmd = Command::new(game_path);
    cmd.arg("--name").arg(name);
    cmd.arg("--ip").arg(ip);

    match cmd.spawn() {
        Ok(child) => {
            app_handle.emit("game-process", child.id()).unwrap();
            Ok(())
        },
        Err(e) => Err(format!("Failed to launch game: {}", e)),
    }
}

#[tauri::command]
async fn start_server(app_handle: AppHandle) -> Result<(), String> {
    kill_process_using_port(12345).unwrap();

    let game_path = Path::new("./server_update").join("server.bin");

    if !game_path.exists() {
        return Err("Server executable not found".into());
    }

    let mut cmd = Command::new(game_path);
    cmd.stdout(Stdio::piped());
    cmd.stderr(Stdio::piped());
    let handle_stdout = app_handle.clone();
    let handle_stderr = app_handle.clone();

    match cmd.spawn() {
        Ok(mut child) => {
            let pid = child.id();
            app_handle.emit("server-process", pid).unwrap();

            let stdout_option = child.stdout.take();
            let stderr_option = child.stderr.take();

            if let Some(stdout) = stdout_option {
                task::spawn(async move {
                    let reader = BufReader::new(stdout);
                    let mut lines = reader.lines().fuse();

                    while let Some(result) = lines.next() {
                        match result {
                            Ok(line) => {
                                handle_stdout.emit("server-log", line).unwrap();
                            }
                            Err(e) => {
                                eprintln!("Error reading server stdout: {}", e);
                                break;
                            }
                        }
                    }
                });
            }

            if let Some(stderr) = stderr_option {
                task::spawn(async move {
                    let reader = BufReader::new(stderr);
                    let mut lines = reader.lines().fuse();
                    while let Some(result) = lines.next() {
                        match result {
                            Ok(line) => {
                                handle_stderr.emit("server-error", line).unwrap();
                            }
                            Err(e) => {
                                eprintln!("Error reading server stderr: {}", e);
                                break;
                            }
                        }
                    }
                });
            }

            Ok(())
        }
        Err(e) => Err(format!("Failed to start server: {}", e)),
    }
}

#[tauri::command]
async fn stop_server(app_handle: AppHandle) -> Result<(), String> {
    let result = app_handle.emit("stop-server", ());
    match result {
        Ok(_) => Ok(()),
        Err(e) => Err(format!("Failed to stop server: {}", e)),
    }
}

#[tauri::command]
async fn stop_game(app_handle: AppHandle) -> Result<(), String> {
    let result = app_handle.emit("stop-game", ());
    match result {
        Ok(_) => Ok(()),
        Err(e) => Err(format!("Failed to stop game: {}", e)),
    }
}

#[tauri::command]
fn get_current_version(app_handle: AppHandle) -> Result<(), String> {
    let file_content = std::fs::read_to_string("config.json")
        .map_err(|e| format!("Failed to read file: {}", e))?;

    let config: Config = serde_json::from_str(&file_content)
        .map_err(|e| format!("Failed to parse JSON: {}", e))?;

    app_handle.emit("config-current-version", config.current_version).unwrap();

    Ok(())
}

#[derive(Serialize, Deserialize)]
struct Config {
    current_version: String
}
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .setup(|app| {

            // Setup event listeners for stopping processes

            let app_handle = app.handle();

            app.listen("stop-server", move |_| {
                #[cfg(not(windows))]
                std::process::Command::new("pkill")
                    .arg("-f")
                    .arg("server.bin")
                    .spawn()
                    .ok();

                #[cfg(windows)]
                std::process::Command::new("taskkill")
                    .arg("/F")
                    .arg("/IM")
                    .arg("server.bin")
                    .spawn()
                    .ok();
            });

            let app_handle_game = app_handle.clone();
            app.listen("stop-game", move |_| {
                #[cfg(not(windows))]
                std::process::Command::new("pkill")
                    .arg("-f")
                    .arg("client.bin")
                    .spawn()
                    .ok();

                #[cfg(windows)]
                std::process::Command::new("taskkill")
                    .arg("/F")
                    .arg("/IM")
                    .arg("client.bin")
                    .spawn()
                    .ok();
            });

            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            download_and_extract_updates, 
            check_for_updates, 
            start_game, 
            start_server, 
            stop_server, 
            stop_game,
            get_current_version
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
