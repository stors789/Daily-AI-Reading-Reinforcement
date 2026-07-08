#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::{
    env,
    io::{Read, Write},
    net::{SocketAddr, TcpStream},
    path::PathBuf,
    process::{Child, Command, Stdio},
    sync::{Arc, Mutex},
    thread,
    time::{Duration, Instant},
};

use serde_json::Value;
use tauri::Manager;

const BACKEND_HOST: &str = "127.0.0.1";
const BACKEND_PORT: u16 = 8755;
const BACKEND_WAIT: Duration = Duration::from_secs(8);
const DAIRR_APP_ID: &str = "DAIRR";
const SIDECAR_BASENAME: &str = "dairr-backend";
const SIDECAR_TARGET_TRIPLE: &str = {
    #[cfg(target_os = "macos")]
    {
        #[cfg(target_arch = "aarch64")]
        {
            "aarch64-apple-darwin"
        }
        #[cfg(target_arch = "x86_64")]
        {
            "x86_64-apple-darwin"
        }
    }
    #[cfg(target_os = "windows")]
    {
        "x86_64-pc-windows-msvc"
    }
    #[cfg(all(not(target_os = "macos"), not(target_os = "windows")))]
    {
        ""
    }
};

type BackendState = Arc<Mutex<Option<Child>>>;

#[derive(Debug)]
struct BackendHealth {
    provider: String,
    mode: String,
}

fn backend_url() -> String {
    format!("http://{}:{}", BACKEND_HOST, BACKEND_PORT)
}

fn backend_health_url() -> String {
    format!("{}/api/health", backend_url())
}

fn repo_root() -> PathBuf {
    if let Ok(root) = env::var("DAIRR_REPO_ROOT") {
        return PathBuf::from(root);
    }

    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("../../..")
        .canonicalize()
        .unwrap_or_else(|_| PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../.."))
}

fn backend_addr() -> SocketAddr {
    format!("{}:{}", BACKEND_HOST, BACKEND_PORT)
        .parse()
        .expect("static backend address should parse")
}

fn request_backend_health() -> Result<Option<BackendHealth>, String> {
    let addr = backend_addr();
    let mut stream = match TcpStream::connect_timeout(&addr, Duration::from_millis(250)) {
        Ok(stream) => stream,
        Err(exc)
            if matches!(
                exc.kind(),
                std::io::ErrorKind::ConnectionRefused | std::io::ErrorKind::TimedOut
            ) =>
        {
            return Ok(None);
        }
        Err(exc) => return Err(format!("could not connect to {}: {}", backend_url(), exc)),
    };

    stream
        .set_read_timeout(Some(Duration::from_millis(700)))
        .map_err(|exc| format!("could not set backend read timeout: {}", exc))?;
    stream
        .set_write_timeout(Some(Duration::from_millis(700)))
        .map_err(|exc| format!("could not set backend write timeout: {}", exc))?;
    let request = format!(
        "GET /api/health HTTP/1.1\r\nHost: {}:{}\r\nAccept: application/json\r\nConnection: close\r\n\r\n",
        BACKEND_HOST, BACKEND_PORT
    );
    stream
        .write_all(request.as_bytes())
        .map_err(|exc| format!("could not request {}: {}", backend_health_url(), exc))?;

    let mut response = String::new();
    stream
        .read_to_string(&mut response)
        .map_err(|exc| format!("could not read {}: {}", backend_health_url(), exc))?;
    parse_backend_health_response(&response).map(Some)
}

fn parse_backend_health_response(response: &str) -> Result<BackendHealth, String> {
    let mut parts = response.splitn(2, "\r\n\r\n");
    let headers = parts.next().unwrap_or_default();
    let body = parts.next().unwrap_or_default();
    let status = headers.lines().next().unwrap_or_default();
    if !status.contains(" 200 ") {
        return Err(format!(
            "{} returned unexpected status '{}'",
            backend_health_url(),
            status
        ));
    }
    let json: Value = serde_json::from_str(body).map_err(|exc| {
        format!(
            "{} did not return valid JSON: {}",
            backend_health_url(),
            exc
        )
    })?;
    let app = json.get("app").and_then(Value::as_str).unwrap_or_default();
    if app != DAIRR_APP_ID {
        return Err(format!(
            "port {} is already in use, but {} identified app '{}' instead of '{}'",
            BACKEND_PORT,
            backend_health_url(),
            app,
            DAIRR_APP_ID
        ));
    }
    let bridge_available = json
        .get("bridge")
        .and_then(|bridge| bridge.get("available"))
        .and_then(Value::as_bool)
        .unwrap_or(false);
    if !bridge_available {
        return Err(format!(
            "{} identified DAIRR but reported the bridge unavailable",
            backend_health_url()
        ));
    }
    Ok(BackendHealth {
        provider: json
            .get("provider")
            .and_then(Value::as_str)
            .unwrap_or("unknown")
            .to_string(),
        mode: json
            .get("mode")
            .and_then(Value::as_str)
            .unwrap_or("unknown")
            .to_string(),
    })
}

fn wait_for_backend_health(timeout: Duration) -> Result<BackendHealth, String> {
    let started = Instant::now();
    let mut last_error: Option<String> = None;
    while started.elapsed() < timeout {
        match request_backend_health() {
            Ok(Some(health)) => return Ok(health),
            Ok(None) => {}
            Err(exc) => last_error = Some(exc),
        }
        thread::sleep(Duration::from_millis(100));
    }
    Err(last_error.unwrap_or_else(|| {
        format!(
            "DAIRR backend did not become ready at {} before timeout",
            backend_health_url()
        )
    }))
}

fn apply_backend_args(command: &mut Command, provider: &str) {
    command
        .arg("--provider")
        .arg(provider)
        .arg("--host")
        .arg(BACKEND_HOST)
        .arg("--port")
        .arg(BACKEND_PORT.to_string())
        .arg("--no-browser")
        .stdin(Stdio::null())
        .stdout(Stdio::inherit())
        .stderr(Stdio::inherit());

    if let Ok(url) = env::var("DAIRR_ANKICONNECT_URL") {
        if !url.trim().is_empty() {
            command.arg("--ankiconnect-url").arg(url);
        }
    }
}

fn start_python_backend() -> Result<Child, String> {
    let root = repo_root();
    let python = env::var("DAIRR_PYTHON").unwrap_or_else(|_| "python3".to_string());
    let provider = env::var("DAIRR_DESKTOP_PROVIDER").unwrap_or_else(|_| "mock".to_string());
    let mut command = Command::new(python);
    command.current_dir(&root).arg("desktop_app.py");
    apply_backend_args(&mut command, &provider);

    command.spawn().map_err(|exc| {
        format!(
            "failed to start DAIRR Python backend from {}: {}",
            root.display(),
            exc
        )
    })
}

fn sidecar_filename() -> String {
    if cfg!(windows) {
        format!("{}.exe", SIDECAR_BASENAME)
    } else {
        SIDECAR_BASENAME.to_string()
    }
}

fn sidecar_target_triple_filename() -> Option<String> {
    if SIDECAR_TARGET_TRIPLE.is_empty() {
        return None;
    }
    let suffix = if cfg!(windows) { ".exe" } else { "" };
    Some(format!(
        "{}-{}{}",
        SIDECAR_BASENAME, SIDECAR_TARGET_TRIPLE, suffix
    ))
}

fn sidecar_candidates(app: &tauri::App) -> Vec<PathBuf> {
    let filenames = [Some(sidecar_filename()), sidecar_target_triple_filename()];
    let mut candidates = Vec::new();
    if let Ok(path) = env::var("DAIRR_BACKEND_SIDECAR") {
        if !path.trim().is_empty() {
            candidates.push(PathBuf::from(path));
        }
    }
    if let Ok(resource_dir) = app.path().resource_dir() {
        for filename in filenames.iter().flatten() {
            candidates.push(resource_dir.join(filename));
            candidates.push(resource_dir.join("binaries").join(filename));
        }
    }
    if let Ok(current_exe) = env::current_exe() {
        if let Some(exe_dir) = current_exe.parent() {
            for filename in filenames.iter().flatten() {
                candidates.push(exe_dir.join(filename));
                candidates.push(exe_dir.join("binaries").join(filename));
            }
        }
    }
    candidates
}

fn start_bundled_backend(app: &tauri::App) -> Result<Child, String> {
    let provider = env::var("DAIRR_DESKTOP_PROVIDER").unwrap_or_else(|_| "ankiconnect".to_string());
    let candidates = sidecar_candidates(app);
    let Some(sidecar) = candidates.iter().find(|path| path.is_file()) else {
        let searched = candidates
            .iter()
            .map(|path| path.display().to_string())
            .collect::<Vec<_>>()
            .join(", ");
        return Err(format!(
            "DAIRR production backend sidecar '{}' was not found. Searched: {}",
            sidecar_filename(),
            searched
        ));
    };

    let mut command = Command::new(sidecar);
    apply_backend_args(&mut command, &provider);
    command.spawn().map_err(|exc| {
        format!(
            "failed to start DAIRR backend sidecar from {}: {}",
            sidecar.display(),
            exc
        )
    })
}

fn should_use_python_backend() -> bool {
    match env::var("DAIRR_BACKEND_MODE") {
        Ok(mode) if mode.eq_ignore_ascii_case("dev") || mode.eq_ignore_ascii_case("python") => true,
        Ok(mode)
            if mode.eq_ignore_ascii_case("sidecar") || mode.eq_ignore_ascii_case("production") =>
        {
            false
        }
        _ => cfg!(debug_assertions),
    }
}

fn start_backend(app: &tauri::App) -> Result<Option<Child>, String> {
    match request_backend_health() {
        Ok(Some(health)) => {
            println!(
                "Reusing DAIRR backend at {} (mode={}, provider={})",
                backend_url(),
                health.mode,
                health.provider
            );
            return Ok(None);
        }
        Ok(None) => {}
        Err(exc) => {
            return Err(format!(
                "cannot reuse existing service on {}: {}",
                backend_url(),
                exc
            ))
        }
    }

    if should_use_python_backend() {
        start_python_backend().map(Some)
    } else {
        start_bundled_backend(app).map(Some)
    }
}

fn stop_python_backend(state: &BackendState) {
    let Ok(mut child_slot) = state.lock() else {
        return;
    };
    let Some(mut child) = child_slot.take() else {
        return;
    };
    let _ = child.kill();
    let _ = child.wait();
}

fn stop_child(child: Option<Child>) {
    let Some(mut child) = child else {
        return;
    };
    let _ = child.kill();
    let _ = child.wait();
}

fn main() {
    let backend_state: BackendState = Arc::new(Mutex::new(None));
    let setup_state = Arc::clone(&backend_state);

    let app = tauri::Builder::default()
        .setup(move |app| {
            let child = start_backend(app).map_err(std::io::Error::other)?;
            let health = match wait_for_backend_health(BACKEND_WAIT) {
                Ok(health) => health,
                Err(exc) => {
                    stop_child(child);
                    return Err(std::io::Error::other(exc).into());
                }
            };
            println!(
                "DAIRR backend ready at {} (mode={}, provider={})",
                backend_url(),
                health.mode,
                health.provider
            );
            if request_backend_health().is_err() {
                stop_child(child);
                return Err(std::io::Error::other(format!(
                    "DAIRR backend failed health confirmation at {}",
                    backend_health_url()
                ))
                .into());
            }

            let url = backend_url()
                .parse()
                .map_err(|exc| std::io::Error::other(format!("invalid backend URL: {}", exc)))?;
            let window_result =
                tauri::WebviewWindowBuilder::new(app, "main", tauri::WebviewUrl::External(url))
                    .title("Daily AI Reading Reinforcement")
                    .inner_size(1280.0, 860.0)
                    .min_inner_size(900.0, 640.0)
                    .resizable(true)
                    .build();
            if let Err(exc) = window_result {
                stop_child(child);
                return Err(exc.into());
            }

            if let Ok(mut child_slot) = setup_state.lock() {
                *child_slot = child;
            }
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("failed to build DAIRR Tauri app");

    app.run(move |_handle, event| match event {
        tauri::RunEvent::ExitRequested { .. } | tauri::RunEvent::Exit => {
            stop_python_backend(&backend_state);
        }
        _ => {}
    });
}
