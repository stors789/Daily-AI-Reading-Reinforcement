#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::{
    env,
    fs::{self, File, OpenOptions},
    io::{Read, Write},
    net::{SocketAddr, TcpStream},
    path::PathBuf,
    process::{Child, Command, Stdio},
    sync::{
        atomic::{AtomicBool, Ordering},
        Arc, Mutex,
    },
    thread,
    time::{Duration, Instant, SystemTime, UNIX_EPOCH},
};

#[cfg(unix)]
use std::os::unix::process::CommandExt;
#[cfg(windows)]
use std::os::windows::process::CommandExt;

use serde_json::Value;
use tauri::Manager;
use tauri_plugin_updater::UpdaterExt;

const BACKEND_HOST: &str = "127.0.0.1";
const BACKEND_PORT: u16 = 8755;
const BACKEND_WAIT: Duration = Duration::from_secs(45);
const DAIRR_APP_ID: &str = "DAIRR";
const SIDECAR_BASENAME: &str = "dairr-backend";
#[cfg(windows)]
const CREATE_NO_WINDOW: u32 = 0x0800_0000;

#[derive(Debug)]
struct BackendHealth {
    provider: String,
    mode: String,
    instance_id: String,
}

struct BackendProcess {
    child: Child,
    instance_id: String,
    shutdown_token: String,
    #[cfg(unix)]
    process_group: i32,
}

type BackendState = Arc<Mutex<Option<BackendProcess>>>;

struct ShellLogger {
    file: Mutex<Option<File>>,
}

impl ShellLogger {
    fn new(app: &tauri::App) -> Self {
        let file = app.path().app_log_dir().ok().and_then(|dir| {
            fs::create_dir_all(&dir).ok()?;
            OpenOptions::new()
                .create(true)
                .append(true)
                .open(dir.join("dairr-shell.log"))
                .ok()
        });
        Self {
            file: Mutex::new(file),
        }
    }

    fn log(&self, message: &str) {
        eprintln!("{message}");
        if let Ok(mut slot) = self.file.lock() {
            if let Some(file) = slot.as_mut() {
                let _ = writeln!(file, "{} {message}", timestamp_secs());
                let _ = file.flush();
            }
        }
    }

    fn clone_file(&self) -> Option<File> {
        self.file.lock().ok()?.as_ref()?.try_clone().ok()
    }
}

fn timestamp_secs() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_secs()
}

fn new_instance_value(label: &str) -> String {
    let nanos = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_nanos();
    format!("{label}-{}-{nanos}", std::process::id())
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
        .expect("static backend address")
}

fn request_backend_health() -> Result<Option<BackendHealth>, String> {
    let mut stream = match TcpStream::connect_timeout(&backend_addr(), Duration::from_millis(250)) {
        Ok(stream) => stream,
        Err(exc)
            if matches!(
                exc.kind(),
                std::io::ErrorKind::ConnectionRefused | std::io::ErrorKind::TimedOut
            ) =>
        {
            return Ok(None)
        }
        Err(exc) => return Err(format!("could not connect to local backend: {exc}")),
    };
    stream
        .set_read_timeout(Some(Duration::from_millis(700)))
        .map_err(|e| e.to_string())?;
    stream
        .set_write_timeout(Some(Duration::from_millis(700)))
        .map_err(|e| e.to_string())?;
    let request = format!(
        "GET /api/health HTTP/1.1\r\nHost: {}:{}\r\nAccept: application/json\r\nConnection: close\r\n\r\n",
        BACKEND_HOST, BACKEND_PORT
    );
    stream
        .write_all(request.as_bytes())
        .map_err(|e| e.to_string())?;
    let mut response = String::new();
    stream
        .read_to_string(&mut response)
        .map_err(|e| e.to_string())?;
    parse_backend_health_response(&response).map(Some)
}

fn parse_backend_health_response(response: &str) -> Result<BackendHealth, String> {
    let mut parts = response.splitn(2, "\r\n\r\n");
    let headers = parts.next().unwrap_or_default();
    let body = parts.next().unwrap_or_default();
    let status = headers.lines().next().unwrap_or_default();
    if !status.contains(" 200 ") {
        return Err(format!(
            "{} returned unexpected status",
            backend_health_url()
        ));
    }
    let json: Value = serde_json::from_str(body)
        .map_err(|_| format!("{} returned invalid JSON", backend_health_url()))?;
    let app = json.get("app").and_then(Value::as_str).unwrap_or_default();
    if app != DAIRR_APP_ID {
        return Err(format!(
            "port {} is already in use, but the service is not DAIRR",
            BACKEND_PORT
        ));
    }
    let bridge_available = json
        .get("bridge")
        .and_then(|v| v.get("available"))
        .and_then(Value::as_bool)
        .unwrap_or(false);
    if !bridge_available {
        return Err("DAIRR health response reported an unavailable bridge".into());
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
        instance_id: json
            .get("instanceId")
            .and_then(Value::as_str)
            .unwrap_or_default()
            .to_string(),
    })
}

fn wait_for_backend_health(timeout: Duration, instance_id: &str) -> Result<BackendHealth, String> {
    let started = Instant::now();
    let mut last_error = None;
    while started.elapsed() < timeout {
        match request_backend_health() {
            Ok(Some(health)) if health.instance_id == instance_id => return Ok(health),
            Ok(Some(_)) => {
                last_error = Some(format!(
                    "port {BACKEND_PORT} belongs to another DAIRR instance"
                ))
            }
            Ok(None) => {}
            Err(exc) => last_error = Some(exc),
        }
        thread::sleep(Duration::from_millis(150));
    }
    Err(last_error.unwrap_or_else(|| {
        format!(
            "DAIRR backend did not become ready within {} seconds",
            timeout.as_secs()
        )
    }))
}

fn apply_backend_args(
    command: &mut Command,
    provider: &str,
    instance_id: &str,
    shutdown_token: &str,
) {
    command
        .arg("--provider")
        .arg(provider)
        .arg("--host")
        .arg(BACKEND_HOST)
        .arg("--port")
        .arg(BACKEND_PORT.to_string())
        .arg("--no-browser")
        .arg("--parent-pid")
        .arg(std::process::id().to_string())
        .arg("--instance-id")
        .arg(instance_id)
        .arg("--shutdown-token")
        .arg(shutdown_token)
        .stdin(Stdio::null());
    if let Ok(url) = env::var("DAIRR_ANKICONNECT_URL") {
        if !url.trim().is_empty() {
            command.arg("--ankiconnect-url").arg(url);
        }
    }
}

fn configure_child(command: &mut Command, logger: &ShellLogger) {
    if let Some(file) = logger.clone_file() {
        if let Ok(stderr) = file.try_clone() {
            command
                .stdout(Stdio::from(file))
                .stderr(Stdio::from(stderr));
        }
    }
    #[cfg(unix)]
    command.process_group(0);
    // The packaged backend remains a console PyInstaller executable so its
    // stdout/stderr can be redirected to the shell log.  Suppress only the
    // transient Windows console window when Tauri spawns it.
    #[cfg(windows)]
    command.creation_flags(CREATE_NO_WINDOW);
}

fn start_python_backend(
    instance_id: &str,
    shutdown_token: &str,
    logger: &ShellLogger,
) -> Result<Child, String> {
    let root = repo_root();
    let python = env::var("DAIRR_PYTHON").unwrap_or_else(|_| "python3".to_string());
    let provider = env::var("DAIRR_DESKTOP_PROVIDER").unwrap_or_else(|_| "mock".to_string());
    let mut command = Command::new(python);
    command.current_dir(&root).arg("desktop_app.py");
    apply_backend_args(&mut command, &provider, instance_id, shutdown_token);
    configure_child(&mut command, logger);
    command.spawn().map_err(|exc| {
        format!(
            "failed to start Python backend from {}: {exc}",
            root.display()
        )
    })
}

fn sidecar_candidates(app: &tauri::AppHandle) -> Vec<PathBuf> {
    let mut candidates = Vec::new();
    if let Ok(path) = env::var("DAIRR_BACKEND_SIDECAR") {
        if !path.trim().is_empty() {
            candidates.push(PathBuf::from(path));
        }
    }
    if let Ok(resource_dir) = app.path().resource_dir() {
        let runtime_name = if cfg!(windows) {
            format!("{SIDECAR_BASENAME}.exe")
        } else {
            SIDECAR_BASENAME.to_string()
        };
        // The release contract has one path: the executable inside the
        // target-native PyInstaller onedir resource.
        candidates.push(
            resource_dir
                .join("binaries")
                .join(SIDECAR_BASENAME)
                .join(&runtime_name),
        );
        candidates.push(resource_dir.join(SIDECAR_BASENAME).join(&runtime_name));
    }
    if let Ok(current_exe) = env::current_exe() {
        if let Some(dir) = current_exe.parent() {
            let runtime_name = if cfg!(windows) {
                format!("{SIDECAR_BASENAME}.exe")
            } else {
                SIDECAR_BASENAME.to_string()
            };
            candidates.push(
                dir.join("binaries")
                    .join(SIDECAR_BASENAME)
                    .join(&runtime_name),
            );
            candidates.push(dir.join(SIDECAR_BASENAME).join(&runtime_name));
        }
    }
    candidates
}

fn start_bundled_backend(
    app: &tauri::AppHandle,
    instance_id: &str,
    shutdown_token: &str,
    logger: &ShellLogger,
) -> Result<Child, String> {
    let provider = env::var("DAIRR_DESKTOP_PROVIDER").unwrap_or_else(|_| "ankiconnect".to_string());
    let candidates = sidecar_candidates(app);
    let sidecar = candidates
        .iter()
        .find(|path| path.is_file())
        .ok_or_else(|| {
            format!(
                "DAIRR backend sidecar was not found (searched {} locations)",
                candidates.len()
            )
        })?;
    let mut command = Command::new(sidecar);
    apply_backend_args(&mut command, &provider, instance_id, shutdown_token);
    configure_child(&mut command, logger);
    command
        .spawn()
        .map_err(|exc| format!("failed to start bundled backend: {exc}"))
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

fn start_backend(app: &tauri::AppHandle, logger: &ShellLogger) -> Result<BackendProcess, String> {
    match request_backend_health() {
        Ok(None) => {}
        Ok(Some(_)) => {
            return Err(format!(
            "port {BACKEND_PORT} is already owned by another DAIRR instance; close it and retry"
        ))
        }
        Err(exc) => return Err(exc),
    }
    let instance_id = new_instance_value("instance");
    let shutdown_token = new_instance_value("shutdown");
    let child = if should_use_python_backend() {
        start_python_backend(&instance_id, &shutdown_token, logger)?
    } else {
        start_bundled_backend(app, &instance_id, &shutdown_token, logger)?
    };
    #[cfg(unix)]
    let process_group = child.id() as i32;
    Ok(BackendProcess {
        child,
        instance_id,
        shutdown_token,
        #[cfg(unix)]
        process_group,
    })
}

fn request_backend_shutdown(process: &BackendProcess) {
    let Ok(Some(health)) = request_backend_health() else {
        return;
    };
    if health.instance_id != process.instance_id {
        return;
    }
    let Ok(mut stream) = TcpStream::connect_timeout(&backend_addr(), Duration::from_millis(300))
    else {
        return;
    };
    let request = format!(
        "POST /api/shutdown HTTP/1.1\r\nHost: {}:{}\r\nX-DAIRR-Shutdown-Token: {}\r\nContent-Length: 0\r\nConnection: close\r\n\r\n",
        BACKEND_HOST, BACKEND_PORT, process.shutdown_token
    );
    let _ = stream.write_all(request.as_bytes());
}

fn stop_backend(state: &BackendState, logger: &ShellLogger) {
    let process = state.lock().ok().and_then(|mut slot| slot.take());
    let Some(mut process) = process else {
        return;
    };
    logger.log("Stopping owned DAIRR backend");
    request_backend_shutdown(&process);
    let deadline = Instant::now() + Duration::from_secs(4);
    while Instant::now() < deadline {
        if matches!(process.child.try_wait(), Ok(Some(_))) {
            return;
        }
        thread::sleep(Duration::from_millis(100));
    }
    #[cfg(unix)]
    unsafe {
        libc::kill(-process.process_group, libc::SIGTERM);
    }
    #[cfg(not(unix))]
    let _ = process.child.kill();
    let deadline = Instant::now() + Duration::from_secs(2);
    while Instant::now() < deadline {
        if matches!(process.child.try_wait(), Ok(Some(_))) {
            return;
        }
        thread::sleep(Duration::from_millis(100));
    }
    #[cfg(unix)]
    unsafe {
        libc::kill(-process.process_group, libc::SIGKILL);
    }
    #[cfg(not(unix))]
    let _ = process.child.kill();
    let _ = process.child.wait();
}

fn startup_url() -> tauri::Url {
    tauri::Url::parse("dairr-startup://localhost/").expect("valid startup protocol URL")
}

fn startup_html() -> &'static str {
    r#"<!doctype html><html><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'><title>DAIRR</title><style>body{margin:0;background:#f4f0e8;color:#24322d;font:16px -apple-system,BlinkMacSystemFont,sans-serif;display:grid;place-items:center;height:100vh}.card{width:min(560px,calc(100% - 64px));background:#fff;padding:34px;border-radius:20px;box-shadow:0 18px 60px #20352b22}h1{margin:0 0 12px;font-size:30px}p{line-height:1.65;margin:8px 0}.muted{color:#66716c}.error{color:#9b3428}</style><main class=card><h1>DAIRR</h1><p id=status>正在启动本地服务，首次启动可能需要一些时间…</p><p class=muted id=detail>应用窗口已经就绪；后端将在验证身份后自动连接。</p></main><script>window.setStartupState=function(kind,message){var s=document.getElementById('status'),d=document.getElementById('detail');s.className=kind==='error'?'error':'';s.textContent=message;if(kind==='error')d.textContent='请关闭并重新打开 DAIRR。诊断信息已写入标准日志目录。';};</script></html>"#
}

fn set_startup_state(window: &tauri::WebviewWindow, kind: &str, message: &str) {
    let kind = serde_json::to_string(kind).unwrap_or_else(|_| "\"error\"".into());
    let message =
        serde_json::to_string(message).unwrap_or_else(|_| "\"DAIRR backend failed\"".into());
    let _ = window.eval(format!(
        "window.setStartupState && window.setStartupState({kind},{message});"
    ));
}

fn update_description(version: &str, notes: Option<&str>) -> String {
    let mut description = format!("发现 DAIRR {version}。下载并安装更新后，应用会自动重新启动。");
    if let Some(notes) = notes.map(str::trim).filter(|notes| !notes.is_empty()) {
        description.push_str("\n\n更新说明：\n");
        description.push_str(notes);
    }
    description
}

async fn check_and_install_update(app: tauri::AppHandle, logger: Arc<ShellLogger>) {
    if cfg!(debug_assertions) {
        logger.log("Skipping automatic update check in a debug build");
        return;
    }

    let updater = match app.updater() {
        Ok(updater) => updater,
        Err(exc) => {
            logger.log(&format!("Automatic updater initialization failed: {exc}"));
            return;
        }
    };
    let update = match updater.check().await {
        Ok(update) => update,
        Err(exc) => {
            logger.log(&format!("Automatic update check failed: {exc}"));
            return;
        }
    };

    let Some(update) = update else {
        logger.log("No DAIRR update is available");
        return;
    };

    logger.log(&format!("DAIRR update {} is available", update.version));
    let install = rfd::MessageDialog::new()
        .set_level(rfd::MessageLevel::Info)
        .set_title("DAIRR 有可用更新")
        .set_description(update_description(&update.version, update.body.as_deref()))
        .set_buttons(rfd::MessageButtons::YesNo)
        .show();
    if install != rfd::MessageDialogResult::Yes {
        logger.log("User deferred the DAIRR update");
        return;
    }

    logger.log(&format!("Downloading DAIRR update {}", update.version));
    let mut downloaded = 0_usize;
    let result = update
        .download_and_install(
            |chunk_length, content_length| {
                downloaded += chunk_length;
                match content_length {
                    Some(total) => eprintln!("DAIRR update download: {downloaded}/{total} bytes"),
                    None => eprintln!("DAIRR update download: {downloaded} bytes"),
                }
            },
            || eprintln!("DAIRR update download finished; installing"),
        )
        .await;
    if let Err(exc) = result {
        logger.log(&format!("DAIRR update installation failed: {exc}"));
        let _ = rfd::MessageDialog::new()
            .set_level(rfd::MessageLevel::Error)
            .set_title("DAIRR 更新未完成")
            .set_description("更新下载或验证失败；当前版本没有被更改。请稍后重试。")
            .set_buttons(rfd::MessageButtons::Ok)
            .show();
        return;
    }

    logger.log("DAIRR update installed; restarting application");
    app.restart();
}

fn main() {
    let backend_state: BackendState = Arc::new(Mutex::new(None));
    let shutting_down = Arc::new(AtomicBool::new(false));
    let setup_state = Arc::clone(&backend_state);
    let setup_shutdown = Arc::clone(&shutting_down);
    let logger_slot: Arc<Mutex<Option<Arc<ShellLogger>>>> = Arc::new(Mutex::new(None));
    let setup_logger_slot = Arc::clone(&logger_slot);

    let app = tauri::Builder::default()
        .plugin(tauri_plugin_updater::Builder::new().build())
        .register_uri_scheme_protocol("dairr-startup", |_context, _request| {
            tauri::http::Response::builder()
                .header("Content-Type", "text/html; charset=utf-8")
                .body(startup_html().as_bytes().to_vec())
                .expect("static startup response")
        })
        .setup(move |app| {
            let logger = Arc::new(ShellLogger::new(app));
            logger.log("DAIRR shell launched; creating startup window before backend wait");
            if let Ok(mut slot) = setup_logger_slot.lock() {
                *slot = Some(Arc::clone(&logger));
            }
            let window = match tauri::WebviewWindowBuilder::new(
                app,
                "main",
                tauri::WebviewUrl::CustomProtocol(startup_url()),
            )
            .title("Daily AI Reading Reinforcement")
            .inner_size(1280.0, 860.0)
            .min_inner_size(900.0, 640.0)
            .resizable(true)
            .build()
            {
                Ok(window) => window,
                Err(exc) => {
                    logger.log(&format!("Startup window creation failed: {exc}"));
                    return Ok(());
                }
            };

            let handle = app.handle().clone();
            thread::spawn(move || {
                if setup_shutdown.load(Ordering::SeqCst) {
                    return;
                }
                let process = match start_backend(&handle, &logger) {
                    Ok(process) => process,
                    Err(exc) => {
                        logger.log(&format!("Backend start failed: {exc}"));
                        set_startup_state(&window, "error", "本地服务启动失败，DAIRR 没有崩溃。");
                        return;
                    }
                };
                let instance_id = process.instance_id.clone();
                if let Ok(mut slot) = setup_state.lock() {
                    *slot = Some(process);
                }
                if setup_shutdown.load(Ordering::SeqCst) {
                    stop_backend(&setup_state, &logger);
                    return;
                }
                match wait_for_backend_health(BACKEND_WAIT, &instance_id) {
                    Ok(health) => {
                        logger.log(&format!(
                            "Backend ready (mode={}, provider={})",
                            health.mode, health.provider
                        ));
                        match backend_url().parse() {
                            Ok(url) => {
                                if let Err(exc) = window.navigate(url) {
                                    logger.log(&format!("Backend navigation failed: {exc}"));
                                    set_startup_state(
                                        &window,
                                        "error",
                                        "本地服务已启动，但页面加载失败。",
                                    );
                                }
                            }
                            Err(exc) => logger.log(&format!("Invalid backend URL: {exc}")),
                        }
                        let update_app = handle.clone();
                        let update_logger = Arc::clone(&logger);
                        tauri::async_runtime::spawn(async move {
                            check_and_install_update(update_app, update_logger).await;
                        });
                    }
                    Err(exc) => {
                        logger.log(&format!("Backend readiness failed: {exc}"));
                        stop_backend(&setup_state, &logger);
                        set_startup_state(
                            &window,
                            "error",
                            "本地服务未能及时启动，DAIRR 没有崩溃。",
                        );
                    }
                }
            });
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("failed to build DAIRR Tauri app");

    app.run(move |_handle, event| match event {
        tauri::RunEvent::ExitRequested { .. } | tauri::RunEvent::Exit => {
            shutting_down.store(true, Ordering::SeqCst);
            if let Some(logger) = logger_slot.lock().ok().and_then(|slot| slot.clone()) {
                stop_backend(&backend_state, &logger);
            }
        }
        _ => {}
    });
}
