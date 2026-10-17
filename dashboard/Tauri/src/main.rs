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

/// Owns the FastAPI child process so it terminates with the app.
struct ApiGuard(Mutex<Option<Child>>);

/// Spawn dashboard/api.py using MURMUR_HOME / MURMUR_PYTHON env config.
/// Fail-open: returns None when config is missing, the dashboard then
/// shows empty data instead of crashing the shell.
fn spawn_api() -> Option<Child> {
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

/// Kill and reap the child to avoid zombie processes and leaked OS handles.
fn kill_api(guard: &ApiGuard) {
    if let Ok(mut slot) = guard.0.lock() {
        if let Some(mut child) = slot.take() {
            let _ = child.kill();
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
        .setup(|app| {
            // Start Python API before the UI issues its first fetch
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