use serde::{Serialize, de::DeserializeOwned};
use std::{
    env,
    fs::{self, File, OpenOptions},
    io::Write,
    path::{Path, PathBuf},
    time::{SystemTime, UNIX_EPOCH},
};

#[derive(Clone)]
pub struct Paths {
    pub app: PathBuf,
    pub solaar: PathBuf,
}

impl Paths {
    pub fn system() -> Result<Self, String> {
        let root = env::var_os("XDG_CONFIG_HOME")
            .map(PathBuf::from)
            .or_else(|| env::var_os("HOME").map(|v| PathBuf::from(v).join(".config")))
            .ok_or("No se encuentra HOME ni XDG_CONFIG_HOME")?;
        if root.join("omarchy-logi/install.json").exists() {
            return Err("La instalación local anterior necesita migración. Ejecuta el instalador de Omalogi antes de usar la nueva CLI".into());
        }
        Ok(Self {
            app: root.join("omalogi"),
            solaar: root.join("solaar"),
        })
    }
    pub fn file(&self, name: &str) -> PathBuf {
        self.app.join(name)
    }
    pub fn lock(&self) -> Result<File, String> {
        fs::create_dir_all(&self.app).map_err(|e| e.to_string())?;
        let f = OpenOptions::new()
            .create(true)
            .truncate(false)
            .read(true)
            .write(true)
            .open(self.file("operation.lock"))
            .map_err(|e| e.to_string())?;
        f.lock().map_err(|e| e.to_string())?;
        Ok(f)
    }
    pub fn try_lock(&self) -> Result<Option<File>, String> {
        fs::create_dir_all(&self.app).map_err(|e| e.to_string())?;
        let file = OpenOptions::new()
            .create(true)
            .truncate(false)
            .read(true)
            .write(true)
            .open(self.file("operation.lock"))
            .map_err(|e| e.to_string())?;
        match file.try_lock() {
            Ok(()) => Ok(Some(file)),
            Err(std::fs::TryLockError::WouldBlock) => Ok(None),
            Err(e) => Err(e.to_string()),
        }
    }
}

pub fn read<T: DeserializeOwned>(path: &Path) -> Result<T, String> {
    serde_json::from_slice(&fs::read(path).map_err(|e| format!("{}: {e}", path.display()))?)
        .map_err(|e| e.to_string())
}
pub fn save<T: Serialize>(path: &Path, value: &T) -> Result<(), String> {
    atomic(
        path,
        &serde_json::to_vec_pretty(value).map_err(|e| e.to_string())?,
    )
}
pub fn atomic(path: &Path, bytes: &[u8]) -> Result<(), String> {
    let parent = path.parent().ok_or("Ruta sin directorio")?;
    fs::create_dir_all(parent).map_err(|e| e.to_string())?;
    let tmp = path.with_extension(format!("tmp-{}", std::process::id()));
    let mut f = OpenOptions::new()
        .create_new(true)
        .write(true)
        .open(&tmp)
        .map_err(|e| e.to_string())?;
    let result = (|| {
        #[cfg(unix)]
        {
            use std::os::unix::fs::PermissionsExt;
            f.set_permissions(fs::Permissions::from_mode(0o600))
                .map_err(|e| e.to_string())?;
        }
        f.write_all(bytes).map_err(|e| e.to_string())?;
        f.sync_all().map_err(|e| e.to_string())?;
        fs::rename(&tmp, path).map_err(|e| e.to_string())?;
        File::open(parent)
            .and_then(|f| f.sync_all())
            .map_err(|e| e.to_string())
    })();
    if result.is_err() {
        let _ = fs::remove_file(tmp);
    }
    result
}
pub fn now() -> u128 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_millis()
}
