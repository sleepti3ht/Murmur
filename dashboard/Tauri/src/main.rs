// dashboard/Tauri/src/main.rs
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::process::{Child, Command};
use std::sync::Mutex;

use tauri::{
    menu::{Menu, MenuItem},
    tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent},
    Manager, RunEvent,
};

#[cfg(windows)]
use std::os::windows::process::CommandExt;

/// Hidden console flag for spawned child processes on Windows.
#[cfg(windows)]
const CREATE_NO_WINDOW: u32 = 0x08000000;

/// Owns the API child process so it terminates together with the app.
struct ApiGuard(Mutex<Option<Child>>);

/// Spawn the FastAPI backend.
/// Priority 1: bundled sidecar next to the executable (onefile or onedir layout).
/// Priority 2: MURMUR_HOME + MURMUR_PYTHON env config (development mode).
/// Fail-open: returns None when neither source exists.
fn spawn_api() -> Option<Child> {
    // Portable mode: sidecar next to the executable
    if let Ok(exe) = std::env::current_exe() {
        let parent = exe.parent()?;
        let candidates = [
            parent.join("murmur-api.exe"),
            parent.join("murmur-api").join("murmur-api.exe"),
        ];
        for sidecar in candidates {
            if sidecar.exists() {
                let mut cmd = Command::new(sidecar);
                #[cfg(windows)]
                cmd.creation_flags(CREATE_NO_WINDOW);
                return cmd.spawn().ok();
            }
        }
    }

    // Development mode: venv interpreter + project root from env
    let home = std::env::var("MURMUR_HOME").ok()?;
    let script = std::path::Path::new(&home).join("dashboard").join("api.py");
    if !script.exists() {
        return None;
    }
    let python = std::env::var("MURMUR_PYTHON").unwrap_or_else(|_| "python".to_string());

    let mut cmd = Command::new(python);
    cmd.arg(&script).env("PYTHONPATH", &home);
    #[cfg(windows)]
    cmd.creation_flags(CREATE_NO_WINDOW);

    cmd.spawn().ok()
}

/// Kill the child and its entire process tree.
/// PyInstaller --onefile binaries spawn a bootloader + real child on Windows;
/// killing only the direct child would orphan the real server holding port 8000.
fn kill_api(guard: &ApiGuard) {
    if let Ok(mut slot) = guard.0.lock() {
        if let Some(mut child) = slot.take() { // FIXED: added mut
            let pid = child.id();

            #[cfg(windows)]
            {
                // /T = kill entire tree, /F = force
                let _ = Command::new("taskkill")
                    .args(["/PID", &pid.to_string(), "/T", "/F"])
                    .creation_flags(CREATE_NO_WINDOW)
                    .output();
            }

            #[cfg(not(windows))]
            {
                let _ = child.kill();
            }

            // Reap the direct child to release the OS handle
            let _ = child.wait();
        }
    }
}

/// Toggle main window visibility (hide keeps webview in RAM by design).
fn toggle_window(app: &tauri::AppHandle) {
    if let Some(window) = app.get_webview_window("main") {
        let is_visible = window.is_visible().unwrap_or(false);
        if is_visible {
            let _ = window.hide();
        } else {
            let _ = window.show();
            let _ = window.set_focus();
        }
    }
}

fn main() {
    let app = tauri::Builder::default()
        // Prevent duplicate instances: second launch focuses the existing window
        .plugin(tauri_plugin_single_instance::init(|app, _argv, _cwd| {
            if let Some(window) = app.get_webview_window("main") {
                let _ = window.show();
                let _ = window.set_focus();
            }
        }))
        .setup(|app| {
            // Start the API before the UI issues its first fetch
            app.manage(ApiGuard(Mutex::new(spawn_api())));

            let toggle_i = MenuItem::with_id(app, "toggle", "Show/Hide", true, None::<&str>)?;
            let quit_i = MenuItem::with_id(app, "quit", "Quit", true, None::<&str>)?;
            let menu = Menu::with_items(app, &[&toggle_i, &quit_i])?;

            let _tray = TrayIconBuilder::new()
                .icon(app.default_window_icon().unwrap().clone())
                .menu(&menu)
                .on_menu_event(|app, event| match event.id.as_ref() {
                    "quit" => app.exit(0),
                    "toggle" => toggle_window(app),
                    _ => {}
                })
                .on_tray_icon_event(|tray, event| {
                    if let TrayIconEvent::Click {
                        button: MouseButton::Left,
                        button_state: MouseButtonState::Up,
                        ..
                    } = event
                    {
                        toggle_window(tray.app_handle());
                    }
                })
                .build(app)?;

            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while building tauri application");

    app.run(|app_handle, event| {
        if let RunEvent::Exit = event {
            if let Some(guard) = app_handle.try_state::<ApiGuard>() {
                kill_api(guard.inner());
            }
        }
    });
}