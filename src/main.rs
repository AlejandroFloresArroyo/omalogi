use clap::{Parser, Subcommand};
use omalogi::{backend, config::Config, engine::Engine};
use serde_json::{Value, json};
use std::io::{self, Read};

#[derive(Parser)]
#[command(version, about = "Controles Logitech integrados con Omarchy")]
struct Cli {
    #[command(subcommand)]
    command: Commands,
}
#[derive(Subcommand)]
enum Commands {
    /// Estado real del mouse y perfil editable, en JSON
    Status,
    /// Perfil actual; --stdin guarda JSON sin aplicarlo
    Config {
        #[arg(long)]
        stdin: bool,
    },
    /// Aplicar y verificar el perfil guardado; --stdin recibe JSON
    Apply {
        #[arg(long)]
        stdin: bool,
    },
    /// Recuperar ajustes y reglas previas
    Restore,
    /// Eventos observados por Solaar (manuales se etiquetan aparte)
    Events,
    /// Invocado por las reglas de Solaar
    Trigger {
        event: String,
        #[arg(long)]
        manual: bool,
    },
    /// Abrir el panel del escritorio
    Panel,
    /// Comprobar dependencias sin modificar ajustes
    Doctor,
}
fn input() -> Result<Config, String> {
    let mut text = String::new();
    io::stdin()
        .take(128 * 1024)
        .read_to_string(&mut text)
        .map_err(|e| e.to_string())?;
    serde_json::from_str(&text).map_err(|e| format!("JSON de configuración inválido: {e}"))
}
fn execute(cli: Cli) -> Result<Value, String> {
    let engine = Engine::new()?;
    match cli.command {
        Commands::Status => engine.status(),
        Commands::Config { stdin } => {
            if stdin {
                let c = input()?;
                engine.save(&c)?;
                Ok(json!({"ok":true,"config":c}))
            } else {
                Ok(json!({"ok":true,"config":engine.draft()?}))
            }
        }
        Commands::Apply { stdin } => engine.apply(
            if stdin { input()? } else { engine.draft()? },
            &std::env::current_exe().map_err(|e| e.to_string())?,
        ),
        Commands::Restore => engine.restore(),
        Commands::Events => Ok(json!({"ok":true,"events":engine.events()?})),
        Commands::Trigger { event, manual } => engine.trigger(&event, manual),
        Commands::Panel => {
            backend::run("omarchy-shell", &["shell", "toggle", "omalogi.mouse"], None)
                .map(|_| json!({"ok":true}))
        }
        Commands::Doctor => {
            let version = backend::run("solaar", &["--version"], None)?;
            let shell = backend::run("omarchy", &["version"], None)?;
            backend::run("python3", &["-c", "import yaml"], None)?;
            Ok(
                json!({"ok":true,"solaar":version.trim(),"omarchy":shell.trim(),"status":engine.status()?}),
            )
        }
    }
}
fn main() {
    match execute(Cli::parse()) {
        Ok(value) => println!("{}", serde_json::to_string(&value).unwrap()),
        Err(error) => {
            println!("{}", json!({"ok":false,"error":error}));
            std::process::exit(1);
        }
    }
}
