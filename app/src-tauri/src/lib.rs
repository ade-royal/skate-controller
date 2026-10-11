// The window hosts the SvelteKit UI; the Python backend (backend/server.py) does
// the Pi, keys and Xbox bridge work. We start it with the app and ask it to shut
// down cleanly on exit so keys are released and the Pi agent is stopped.

use std::io::Write;
use std::net::TcpStream;
use std::path::PathBuf;
use std::process::{Child, Command};
use std::sync::Mutex;
use std::time::{Duration, Instant};
use tauri::{Manager, RunEvent};

const BACKEND_ADDR: &str = "127.0.0.1:8765";

struct Backend(Mutex<Option<Child>>);

fn repo_root() -> PathBuf {
    // app/src-tauri -> repository root
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("..").join("..")
}

fn spawn_backend() -> Option<Child> {
    let mut cmd = Command::new("python");
    cmd.args(["-m", "backend.server"]).current_dir(repo_root());
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        cmd.creation_flags(0x0800_0000); // CREATE_NO_WINDOW
    }
    cmd.spawn().ok()
}

fn stop_backend(child: &mut Child) {
    if let Ok(mut stream) = TcpStream::connect_timeout(&BACKEND_ADDR.parse().unwrap(), Duration::from_millis(500)) {
        let _ = stream.write_all(b"POST /shutdown HTTP/1.1\r\nHost: 127.0.0.1\r\nContent-Length: 0\r\n\r\n");
    }
    let deadline = Instant::now() + Duration::from_secs(5);
    while Instant::now() < deadline {
        if let Ok(Some(_)) = child.try_wait() {
            return;
        }
        std::thread::sleep(Duration::from_millis(100));
    }
    let _ = child.kill();
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let app = tauri::Builder::default()
        .manage(Backend(Mutex::new(spawn_backend())))
        .build(tauri::generate_context!())
        .expect("error while building tauri application");

    app.run(|handle, event| {
        if let RunEvent::Exit = event {
            if let Some(mut child) = handle.state::<Backend>().0.lock().unwrap().take() {
                stop_backend(&mut child);
            }
        }
    });
}
