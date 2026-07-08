#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::{
    env,
    net::{SocketAddr, TcpStream},
    path::PathBuf,
    process::{Child, Command, Stdio},
    sync::{Arc, Mutex},
    thread,
    time::{Duration, Instant},
};

const BACKEND_HOST: &str = "127.0.0.1";
const BACKEND_PORT: u16 = 8755;
const BACKEND_WAIT: Duration = Duration::from_secs(8);

type BackendState = Arc<Mutex<Option<Child>>>;

fn backend_url() -> String {
    format!("http://{}:{}", BACKEND_HOST, BACKEND_PORT)
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

fn backend_is_listening() -> bool {
    let addr: SocketAddr = format!("{}:{}", BACKEND_HOST, BACKEND_PORT)
        .parse()
        .expect("static backend address should parse");
    TcpStream::connect_timeout(&addr, Duration::from_millis(250)).is_ok()
}

fn wait_for_backend(timeout: Duration) -> bool {
    let started = Instant::now();
    while started.elapsed() < timeout {
        if backend_is_listening() {
            return true;
        }
        thread::sleep(Duration::from_millis(100));
    }
    false
}

fn start_python_backend() -> Result<Option<Child>, String> {
    if backend_is_listening() {
        return Ok(None);
    }

    let root = repo_root();
    let python = env::var("DAIRR_PYTHON").unwrap_or_else(|_| "python3".to_string());
    let provider = env::var("DAIRR_DESKTOP_PROVIDER").unwrap_or_else(|_| "mock".to_string());
    let mut command = Command::new(python);
    command
        .current_dir(&root)
        .arg("desktop_app.py")
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

    command
        .spawn()
        .map(Some)
        .map_err(|exc| format!("failed to start DAIRR Python backend from {}: {}", root.display(), exc))
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
            let child = start_python_backend().map_err(std::io::Error::other)?;
            if !wait_for_backend(BACKEND_WAIT) {
                stop_child(child);
                return Err(std::io::Error::other(format!(
                    "DAIRR backend did not become ready at {}",
                    backend_url()
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

    app.run(move |_handle, event| {
        match event {
            tauri::RunEvent::ExitRequested { .. } | tauri::RunEvent::Exit => {
                stop_python_backend(&backend_state);
            }
            _ => {}
        }
    });
}
