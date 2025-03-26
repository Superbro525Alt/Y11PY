// Learn more about Tauri commands at https://tauri.app/develop/calling-rust/
use futures::stream::StreamExt;
use futures::try_join;
use std::path::Path;
use tokio::fs;
use tokio::io::AsyncWriteExt;

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
        .header("User-Agent", "YourAppName/YourVersion")
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

// #[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .invoke_handler(tauri::generate_handler![download_and_extract_updates, check_for_updates])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
