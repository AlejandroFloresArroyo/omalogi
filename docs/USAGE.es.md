# Omalogi

MVP local para configurar un Logitech MX Master conectado por Bolt o por Bluetooth: DPI, botón de gestos, botones laterales y ambas ruedas. CLI en Rust, panel QML en el shell de Omarchy y Solaar externo para HID++ y eventos.

La compatibilidad física validada corresponde al **MX Master 3S conectado por Bolt**. Los ajustes se limitan al dispositivo seleccionado; se conserva la configuración de los demás dispositivos.

**Bluetooth:** empareja y conecta el mouse desde el panel Bluetooth de Omarchy; Omalogi lo detecta al abrir su panel y el encabezado indica `Bluetooth`. Por Bluetooth Solaar no informa número de serie, así que el mouse se identifica por su Unit ID. Si Solaar informa el mismo valor como serie por Bolt (ocurre en el 3S observado), el perfil sigue al mouse al cambiar de conexión. Esta ruta es experimental: una primera prueba física confirmó detección, gestos, DPI y restauración, y terminó con el mouse abandonando su canal Bluetooth por una causa no establecida; consulta [VALIDATION.md](../VALIDATION.md).

## Instalar

Sigue [README.md](../README.md) para instalar desde Omarchy Plugins o desde fuentes. El instalador resuelve Solaar, instala el binario y prepara el servicio del usuario. La versión precompilada no requiere Rust.

El cambio de nombre migra los perfiles, respaldos, reglas propias y el widget de la instalación local anterior. Se detiene si hay una operación pendiente o archivos ajenos en las rutas de destino.

## Usar

El widget abre un panel flotante anclado a la barra, con dos vistas. **Mouse** reúne el dibujo vectorial del dispositivo, DPI, gestos, botones laterales y acciones de ambas ruedas. **Extras** contiene inversión, resolución, ratchet, SmartShift y pruebas del mouse.

Los ajustes se guardan y aplican automáticamente tras una pausa de 450 ms. El slider muestra el valor mientras lo arrastras y comienza la aplicación al soltarlo. Los cambios rápidos se agrupan; si editas mientras se verifica el anterior, se conserva el último valor para la siguiente operación. El estado distingue «Guardando…», «Aplicando…» y «Perfil activo».

Escape, clic fuera o el widget de la barra cierran el panel incluso durante la aplicación. La operación y los cambios en cola continúan en segundo plano; cerrar libera la capa de entrada del popup. Al reabrir se conserva el valor en espera. No hay botones de Actualizar, Cerrar, Guardar o Aplicar. **Restaurar original**, en Extras, recupera el estado anterior a la primera aplicación. Si una operación falla, el valor deseado se conserva y aparece **Reintentar cambios**; una recuperación incompleta pide Restaurar. No se reintenta indefinidamente.

- **DPI:** valores que expone el sensor; en este 3S son 200–8000 en pasos de 50.
- **Gestos:** clic sin movimiento y cuatro direcciones al mantener el botón, mover el mouse y soltar. Se asignan los cinco cuando se personaliza; “Sin acción” permite desactivar uno.
- **Botones:** “Comportamiento habitual” conserva atrás y adelante. También pueden cambiar DPI, volumen, espacios, reproducción o abrir paneles.
- **Ruedas:** inversión, resolución, ratchet y SmartShift según capacidades. Las acciones de giro son optativas y reemplazan el desplazamiento normal de esa rueda en ambas direcciones. Elegir “Desplazamiento habitual” en cualquier dirección devuelve ambas direcciones al comportamiento habitual. Al personalizar una dirección, la otra pasa a “Sin acción” si todavía era habitual; puedes asignarle otra acción.
- **Pruebas:** registra eventos físicos con origen `solaar`; una ejecución manual queda marcada `manual` y no cuenta como prueba del hardware. El modo de registro temporal sustituye las acciones de todos los controles hasta volver a asignarlas o restaurar.

Perfil inicial: clic abre aplicaciones; arriba abre el menú; abajo muestra Scratchpad; izquierda/derecha cambian espacio. Botones laterales y ruedas mantienen su comportamiento habitual.

## CLI

Todas las respuestas de las operaciones son JSON, incluidos los errores (código de salida 1).

```bash
omalogi status
omalogi doctor
omalogi config
omalogi config --stdin < perfil.json
omalogi apply --stdin < perfil.json
omalogi apply
omalogi events
omalogi trigger gesture.click --manual
omalogi restore
```

El perfil es un documento de versión 1. `config` devuelve un objeto con `config`: extrae ese campo antes de usarlo como entrada, por ejemplo `omalogi config | jq .config > perfil.json`.

## Persistencia y restauración

El servicio se inicia con `graphical-session.target` y termina con la sesión. Solaar reaplica los ajustes al reconectar el dispositivo. La configuración gestionada deja de ignorar los controles verticales correspondientes; la restauración recupera sus flags originales.

El respaldo y el registro de operaciones viven en `~/.config/omalogi/`. Las reglas propias se agregan al comienzo de `~/.config/solaar/rules.yaml` con marcadores; se preserva literalmente el resto del archivo. La persistencia de Solaar se modifica por dispositivo y por clave, manteniendo los demás dispositivos y ajustes. Se conserva el modo software “Mouse Gestures”, que una lectura física por sí sola no distingue de “Diverted”.

La CLI valida antes de escribir, detiene el servicio propio durante la transacción, comprueba las lecturas físicas de los ajustes modificados y recupera el estado anterior si falla. Una operación interrumpida deja un registro pendiente: ejecuta **Restaurar** antes de volver a aplicar. Mantén el mouse conectado durante aplicar/restaurar. Si tienes otra instancia de Solaar abierta fuera del servicio, ciérrala para evitar que sobrescriba la persistencia.

Si el perfil está activo pero un gesto no añade eventos en las pruebas de Extras, revisa el registro del servicio y prueba `systemctl --user restart omalogi-solaar.service`. Durante la validación se observó una captura detenida que se recuperó así; una aplicación posterior funcionó normalmente. Su causa no está demostrada. Evita lanzar consultas HID++ paralelas al mismo dispositivo.

```bash
systemctl --user status omalogi-solaar.service
journalctl --user -u omalogi-solaar.service --no-pager
bash scripts/uninstall.sh
```

La desinstalación restaura primero el mouse y retira los archivos propios. Conserva Solaar, respaldos y registros; si no puede restaurar, se detiene para no eliminar la herramienta de recuperación.

## Verificar

```bash
cargo test --locked --offline
cargo clippy --locked --offline --all-targets -- -D warnings
python3 -m unittest discover -s tests -p 'test_*.py'
omarchy plugin validate .
python3 scripts/test-panel.py
```

La prueba `test-panel.py` ejecuta el widget QML real en una instancia aislada de Quickshell con un CLI lento simulado: agrupación, cola, cierre durante aplicación, reapertura, error y reintento. No escribe al hardware.

Las pruebas Python de transacciones usan `target/debug/omalogi`, producido por `cargo test`. Incluyen fallo de escritura después de persistir un valor intentado, varias aplicaciones seguidas, restauración de modo software y preservación de reglas ajenas.

La validación real se registra en [VALIDATION.md](../VALIDATION.md). Los scripts `scripts/validate-hardware.py` preparan y verifican una prueba local; los giros, gestos, reconexión y nueva sesión requieren interacción física. Las pruebas simuladas no certifican esos pasos.

## Límites del MVP

Se valida este equipo y mouse; no se promete soporte universal de modelos/versiones. Solaar sigue siendo una dependencia y la escritura y la verificación siguen dependiendo de consultas HID++. Con un perfil activo, DPI e inversiones leen, escriben y verifican solo los ajustes modificados en una conexión de Solaar; las acciones que conservan el modo de captura actualizan solo las reglas. Cambios de modo, ratchet/SmartShift y la primera aplicación usan la transacción completa. Todas las rutas conservan el respaldo, registro pendiente y rollback; el tiempo real depende del dispositivo. Las acciones disponibles están predefinidas y se invocan sin shell; los comandos arbitrarios y el daemon HID++ propio quedan para una versión posterior.

Fuentes y decisiones: [alcance](../MVP_SCOPE.md), [Omarchy](../research/omarchy-integration.md), [contrato Solaar](../research/device-controls.md), [ruta HID++ futura](../research/hidpp-native-path.md).
