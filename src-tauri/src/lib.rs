#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_process::init())
        .plugin(tauri_plugin_shell::init())
        .setup(|app| {
            #[cfg(any(target_os = "macos", windows, target_os = "linux"))]
            app.handle()
                .plugin(tauri_plugin_updater::Builder::new().build())?;

            // Windows 上 titleBarStyle: "Overlay" 不生效，系统会保留原生标题栏，
            // 与前端自绘标题栏叠加成两个标题栏。这里关闭原生装饰，只保留自绘标题栏。
            // macOS 仍走 Overlay（保留原生红绿灯按钮），不在此处理。
            #[cfg(windows)]
            {
                use tauri::Manager;
                if let Some(window) = app.get_webview_window("main") {
                    let _ = window.set_decorations(false);
                }
            }

            #[cfg(desktop)]
            {
                use tauri::{
                    menu::{MenuBuilder, MenuItemBuilder},
                    tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent},
                };

                let show = MenuItemBuilder::with_id("show", "显示窗口").build(app)?;
                let quit = MenuItemBuilder::with_id("quit", "退出").build(app)?;
                let menu = MenuBuilder::new(app).items(&[&show, &quit]).build()?;

                TrayIconBuilder::with_id("main-tray")
                    .tooltip("cotton-filter")
                    .menu(&menu)
                    .show_menu_on_left_click(false)
                    .on_menu_event(|app, event| match event.id().as_ref() {
                        "show" => show_main_window(app),
                        "quit" => app.exit(0),
                        _ => {}
                    })
                    .on_tray_icon_event(|tray, event| {
                        if let TrayIconEvent::Click {
                            button: MouseButton::Left,
                            button_state: MouseButtonState::Up,
                            ..
                        } = event
                        {
                            show_main_window(&tray.app_handle());
                        }
                    })
                    .build(app)?;
            }

            Ok(())
        })
        .on_window_event(|window, event| {
            #[cfg(desktop)]
            if let tauri::WindowEvent::CloseRequested { api, .. } = event {
                api.prevent_close();
                let _ = window.hide();
            }
        })
        .build(tauri::generate_context!())
        .expect("error while running tauri application")
        .run(|_app_handle, event| {
            // 应用退出时回收 Python sidecar：托盘“退出”走 app.exit(0)，
            // 前端 cleanup 来不及执行，必须在这里跨平台兜底，否则后端
            // 残留进程会一直占用端口、并锁住 cotton-filter-backend.exe
            // 导致下次安装/更新报“无法写入文件”。
            if let tauri::RunEvent::Exit = event {
                kill_backend_process();
            }
        });
}

#[cfg(windows)]
fn kill_backend_process() {
    use std::os::windows::process::CommandExt;
    use std::process::Command;

    // CREATE_NO_WINDOW: 不要为 taskkill 再弹一个黑窗。
    const CREATE_NO_WINDOW: u32 = 0x0800_0000;
    let _ = Command::new("taskkill")
        .args(["/F", "/T", "/IM", "cotton-filter-backend.exe"])
        .creation_flags(CREATE_NO_WINDOW)
        .status();
}

#[cfg(not(windows))]
fn kill_backend_process() {
    use std::process::Command;

    // 按命令行特征匹配 sidecar；主程序名为 cotton-filter（不含
    // -backend），不会被误杀。
    let _ = Command::new("pkill")
        .args(["-f", "cotton-filter-backend"])
        .status();
}

#[cfg(desktop)]
fn show_main_window(app: &tauri::AppHandle) {
    use tauri::Manager;

    if let Some(window) = app.get_webview_window("main") {
        let _ = window.unminimize();
        let _ = window.show();
        let _ = window.set_focus();
    }
}
