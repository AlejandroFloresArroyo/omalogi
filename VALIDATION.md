# Validación del MVP

Fecha: 2026-09-29. Estado: instalado; controles físicos, restauración y acciones del escritorio comprobados; cierre de validación pendiente. Este documento distingue resultados observados de pasos pendientes.

## Equipo observado

- Omarchy 4.0.4-1, Hyprland 0.56.2-2, Quickshell 0.3.1-1.
- Solaar 1.1.20-2 y Rust 1.98.1.
- MX Master **3S**, HID++ 4.5, serial `[omitido]`, Bolt USB `046d:C548`.
- DPI: 200–8000, pasos de 50. Estado previo: 1000 DPI, Ratcheted, SmartShift 10, inversiones/resolución/diversion de ruedas desactivadas; botones habituales.

## Comprobaciones completadas

- Compilación Rust release y pruebas de contratos: 6 aprobadas.
- Pruebas Python: 6 aprobadas. Incluyen preservación selectiva, rollback tras persistir un valor fallido, varias aplicaciones, modo software, giro libre con umbral guardado y recuperación de lectura transitoria al arrancar.
- Clippy en todos los targets con advertencias como errores: aprobado.
- Validación de manifest con `omarchy plugin validate .`: aprobada.
- Instalación local y habilitación del plugin por comandos oficiales: completadas.
- Servicio `omalogi-solaar.service`: arrancó; `graphical-session.target` estaba activo.
- Primera aplicación física detectó lectura derivada SmartShift 1 en Freespinning. El rollback recuperó los ajustes previos (lectura posterior SmartShift 10). La implementación verifica ahora el umbral con Ratcheted antes de seleccionar Freespinning.
- Una recuperación explícita completó un registro pendiente con mensaje “Estado original restaurado y verificado”. El panel protege ahora el cierre durante una operación y la actualización de archivos adquiere el mismo lock.
- Aplicación física de diagnóstico completada: 1200 DPI, inversión/resolución vertical activas, inversión horizontal activa, Freespinning y umbral SmartShift guardado 12; once asignaciones de diagnóstico. La CLI verificó hardware y arranque del servicio. Evidencia: `artifacts/hardware-apply.json`.
- Once eventos físicos con origen `solaar` y resultado correcto: cinco gestos, atrás/adelante, arriba/abajo vertical e izquierda/derecha horizontal. `scripts/validate-hardware.py verify` devolvió `missing: []`; evidencia `artifacts/hardware-after.json`.
- El usuario confirmó apagar/encender el mouse y volver a probar un gesto y un giro. Las lecturas posteriores conservaron DPI y desviaciones. Se observó un cambio de modo de giro durante la interacción; el reinicio aislado del servicio después de seleccionar Freespinning **no** reprodujo ese cambio (`artifacts/probe-scroll.json`). No se atribuye a un fallo de persistencia sin evidencia.
- Restauración completa comparada con el estado previo: 1000 DPI, Ratcheted, SmartShift 10, inversiones/resolución/diversion de ruedas desactivadas y botones originales. `scripts/validate-hardware.py restore` devolvió `restoration_verified: true`; evidencia `artifacts/hardware-restored.json`.
- Antes del rediseño del panel: revisión visual independiente de las cinco pestañas en ventana nativa 855×1408. El revisor indicó dos correcciones; su segundo pase calificó ambas como resueltas: contraste del texto secundario (aproximadamente 5.1:1) y preservación del borrador con descarte explícito. El segundo veredicto cubre esas correcciones, no certifica interacciones no ejercitadas.

## Pendiente de evidencia física

- Arranque en una nueva sesión real (la reconexión física del mouse ya fue confirmada). El usuario decidió realizar esta comprobación más tarde; el objetivo completo permanece pendiente de esa evidencia.

La prueba del panel guardó «Menú de Omarchy» para el clic y la aplicación terminó con `applied: true`, `pending: false` y el servicio activo. El usuario informó que no abrió Aplicaciones; el perfil observado todavía asignaba Menú y no había un evento físico nuevo en el registro. Una ejecución manual de la acción Menú devolvió resultado correcto, identificada como `source: manual`; no sustituye comprobar el clic físico ni confirma la selección de Aplicaciones desde el panel.

Después de reiniciar Solaar para obtener una traza temporal, se registraron clics y gestos con acciones Menú y cambio de espacio. Se retiró la traza y se restauró el servicio normal. El usuario confirmó entonces que el clic abría Menú y el gesto hacia la derecha cambiaba de espacio; el registro contiene ambas acciones con `source: solaar` y `ok: true`. Esto comprueba la ejecución física del perfil guardado desde el panel. El reinicio resolvió el síntoma observado; no se declara una causa demostrada ni una corrección permanente basada solo en ese resultado. Se aplicó posteriormente el perfil normal (`artifacts/hardware-normal.json`).

El usuario confirmó que el clic con el perfil normal recién aplicado abría Aplicaciones. El registro del servicio mostró `gesture.click → apps`, `gesture.up → menu` y `gesture.right → workspace.next`, todos con origen `solaar` y resultado correcto. En esta aplicación posterior el fallo anterior no se reprodujo. El perfil final conserva 1000 DPI, Ratcheted/SmartShift 10, ruedas y botones laterales habituales, y los cinco gestos iniciales definidos en el alcance.

La última consulta de estado de esta sesión devolvió `applied: true`, `pending: false` y `daemon: true`; `systemctl --user is-enabled omalogi-solaar.service` devolvió `enabled`. La habilitación y los reinicios comprobados no sustituyen el inicio en una sesión nueva.

Los artefactos JSON de las operaciones reales se guardan en `artifacts/hardware-*.json`. Las pruebas con el backend simulado no satisfacen los pasos pendientes.


## Rediseño del panel

- `omalogi.mouse` funciona como widget con `Panel`/`KeyboardPanel` anclado a la barra. Se capturaron Mouse y Extras en el escritorio real a 920×690; evidencia `.impeccable/review/{mouse,extras}.png` y sus geometrías JSON. La lista de clientes de Hyprland no contiene una ventana Omalogi en mosaico.
- Mouse muestra simultáneamente DPI, cinco gestos, dos botones laterales y cuatro acciones de rueda alrededor del diagrama vectorial. Extras contiene las inversiones, resolución, ratchet, SmartShift y diagnóstico.
- El dibujo sigue la foto cenital del MX Master 3S aportada después por el usuario: cuerpo ancho, apoyo del pulgar, rueda recta y botones superiores separados. Los puntos interactivos y conexiones se actualizaron con ese contorno.
- Instalación actualizada, validación del manifest aprobada y sin errores QML de Omalogi en el registro del shell.
- Revisión visual independiente final: `ship`, sin correcciones materiales. Aprobó ambas capturas y la correspondencia del dibujo con la foto. Las interacciones del dibujo y la conservación del borrador se revisaron por código; no se declaran probadas por esa revisión. Un recorrido automático de Tab/flecha no generó un borrador, por lo que no certifica edición ni descarte al reabrir.
- Esta revisión cambia la interfaz y la organización; no repite ni sustituye las pruebas físicas anteriores o la prueba pendiente de una sesión nueva.


## Aplicación automática y corrección del bloqueo

- La prueba aislada del widget nativo reprodujo dos veces el cierre bloqueado: con una aplicación simulada en curso, `OmalogiWidget.close()` dejaba `opened: true`. Al quitar la protección de cierre, ocultó la capa del panel (`closed: true`) mientras el proceso seguía ejecutándose. Esa ruta es la que usa el cierre exterior de `KeyboardPanel`.
- `scripts/test-panel.py` prueba agrupación de cambios, último valor en cola, cierre/reapertura durante una aplicación, finalización en segundo plano y fallo sin bucle de reintentos. Usa QML nativo y un CLI lento simulado, no entradas físicas.
- El usuario confirmó desde la versión instalada que puede usar mouse/teclado fuera del panel y que los ajustes se aplican automáticamente. Después informó lentitud; se investigó y corrigió la ruta de actualización.
- Medición de la ruta anterior: reaplicar el mismo perfil tardó 12,104 s; las tres consultas completas de Solaar consumieron 3,617, 3,869 y 3,986 s. Con actualización incremental, la misma operación tardó 0,429 s y no consultó HID.
- Cambio real de DPI 1300 → 1350 → 1300, conservando las asignaciones del usuario: ambas operaciones se verificaron físicamente y tardaron 2,637 y 2,739 s. Evidencia `artifacts/fast-apply-timing.json`. Son tiempos de CLI; la UI añade una pausa de agrupación de 450 ms y puede tener un ajuste anterior en cola.
- Con un perfil activo, DPI e inversiones usan el adaptador de la biblioteca Solaar instalada en una conexión: valores previos, validación, escritura sin persistencia interna, lectura posterior y rollback. Rust persiste selectivamente después de verificar. Una caída del adaptador deja el registro pendiente y exige Restaurar. Las acciones con el mismo modo de captura actualizan reglas sin consultas físicas; cambiar ratchet/SmartShift, modos de captura o aplicar por primera vez conserva la transacción completa.
- La revisión visual puntuó como resuelta su única corrección: documentación del flujo automático y del cierre. Ese veredicto no certifica todas las rutas físicas del nuevo adaptador.

## Preparación de Omalogi para distribución — 2026-09-29

El proyecto se renombró a Omalogi, con CLI `omalogi`, plugin `omalogi.mouse`, configuración en `~/.config/omalogi/` y servicio `omalogi-solaar.service`. Los nombres usados arriba siguen la nomenclatura actual; las pruebas físicas históricas se realizaron antes del cambio de nombre. El código conserva referencias al nombre anterior únicamente para migración y recuperación.

- Manifiesto único en la raíz, autor y versión `0.1.0-beta.1` compartida con Cargo y Cargo.lock; validación oficial de Omarchy y comprobación de metadatos aprobadas.
- Siete contratos Rust y 28 pruebas Python aprobadas. Nueve pruebas nuevas cubren instalación, reinstalación, archivos ajenos, checkout nativo de Git, migración, operación pendiente, directorios de configuración en conflicto, rollback ante fallo de escritura y restricciones de desinstalación.
- Formato Rust y Clippy sin advertencias aprobados. La prueba nativa QML aislada aprobó agrupación, cola, cierre/reapertura, finalización en segundo plano y error/reintento. La ejecución requiere acceso a una sesión gráfica; un intento dentro del sandbox no pudo abrir Wayland y no se cuenta como resultado del producto.
- Migración real mediante el instalador desde fuentes: el perfil y el snapshot original se conservaron; las reglas propias cambiaron de marcadores y ruta de ejecutable. El servicio anterior se retiró y `omalogi-solaar.service` quedó activo y habilitado. La consulta posterior devolvió `ok: true`, `applied: true`, `pending: false`, `daemon: true`. El shell descubrió el plugin con nombre Omalogi y `enabled: true`.
- Archivo local de distribución generado y checksum comprobado con el binario GNU del equipo. La release pública usa un build musl separado en GitHub Actions; ese workflow estaba pendiente al cerrar la preparación; su resultado se registra abajo.
- Vista previa pública de los componentes nativos generada con datos de dispositivo simulados y fondo opaco; no se incluyen el serial real ni los registros locales.

Esta preparación no certifica una sesión nueva, una instalación en otro equipo, el workflow remoto ni pruebas físicas adicionales de gestos y ruedas después de la migración. Los pasos de publicación están en [docs/PUBLISHING.md](docs/PUBLISHING.md).

## Publicación en GitHub — 2026-09-29

- Código en `main` y etiqueta `v0.1.0-beta.1` publicados. La beta está disponible en [GitHub Releases](https://github.com/AlejandroFloresArroyo/omalogi/releases/tag/v0.1.0-beta.1).
- GitHub Actions aprobó [Checks en main](https://github.com/AlejandroFloresArroyo/omalogi/actions/runs/36650398640), [Checks en la etiqueta](https://github.com/AlejandroFloresArroyo/omalogi/actions/runs/36650399307) y [Release](https://github.com/AlejandroFloresArroyo/omalogi/actions/runs/36650399296).
- El binario Linux x86_64 musl de la release se descargó y verificó localmente: versión correcta, ausencia de intérprete ELF, contenido del archivo limitado al ejecutable y licencia, checksum correcto y coincidencia con los digests de los assets subidos a GitHub.
- Doce pruebas de transacciones aprobaron usando ese binario y procesos de Solaar simulados. No se escribió al hardware.
- Tras publicar, el archivo y su checksum se descargaron sin autenticación por las mismas URLs que usa el instalador; la verificación aprobó.

La publicación en GitHub no constituye una admisión al catálogo de Omarchy Plugins. La nueva sesión gráfica real y la instalación en un segundo entorno limpio continúan pendientes.

## Soporte Bluetooth — 2026-10-01

Estado: implementado y cubierto por pruebas simuladas. Una primera prueba física confirmó detección, gestos, DPI y restauración por Bluetooth y terminó con un **incidente sin causa demostrada**. Tras añadir una espera al arranque del servicio, una segunda prueba repitió esa secuencia cinco veces sin incidente y cubrió aplicación completa, ruedas y reconexión. Bluetooth queda como experimental mientras la causa siga siendo una hipótesis. Esta sección describe lo comprobado antes de emparejar el mouse por Bluetooth.

Hechos comprobados leyendo Solaar 1.1.20 instalado (`/usr/lib/python3.14/site-packages`):

- Un dispositivo directo no tiene registro de emparejamiento: `Device.serial` devuelve cadena vacía (`logitech_receiver/device.py`, `_serial = pairing_info["serial"] if pairing_info else None`). `solaar show` lo imprime como encabezado sin número de ranura, con `Serial number:` vacío y `Unit ID:` (`solaar/cli/show.py`, `_print_device`).
- `solaar config <dispositivo>` compara serie, codename, tipo y nombre (`solaar/cli/__init__.py`, `_find_device`); el Unit ID no selecciona nada. Las reglas (`Device:`) y la persistencia (`_modelId` + `_unitId`) sí lo aceptan.
- La regla udev de Solaar concede acceso a `hidraw` Bluetooth de Logitech (`KERNELS == "0005:046D:*"` en `42-logitech-unify-permissions.rules`).

Comprobaciones completadas:

- 10 contratos Rust y 57 pruebas Python aprobadas. Las transacciones (aplicar, restaurar, rollback, ruta incremental, operación interrumpida) se ejecutan dos veces: con el backend simulado como Bolt y como Bluetooth. El simulado Bluetooth rechaza la selección por Unit ID cuando se invoca `solaar config` sin el adaptador, igual que Solaar real.
- `tests/test_solaar_cli.py` ejecuta los seis casos del adaptador contra el `_find_device` real de Solaar 1.1.20 con dispositivos simulados, además de una copia de referencia de sus reglas para entornos sin Solaar.
- Mutation check: quitar la identificación por Unit ID, aceptar el Unit ID anidado en las features, quitar el valor por defecto de `transport` en estados guardados, saltarse el adaptador o quitar su coincidencia por Unit ID hace fallar al menos una prueba en cada caso.
- Bolt real, solo lectura: la salida de `solaar config <serie>` y la del adaptador fueron idénticas salvo la línea final `# transport: Bolt` (53 y 54 líneas). `omalogi status` con el binario nuevo devolvió `ok: true`, `transport: Bolt`, 11 ajustes, 5 botones, `applied: true`, `pending: false`, `daemon: true`.
- `scripts/test-panel.py` aprobó con el QML real, incluido el encabezado `Bluetooth · TEST1234 · Connected` con CLI simulado.

### Prueba física por Bluetooth — 2026-10-01, 22:15–22:23

El usuario emparejó el MX Master 3S por Bluetooth; el emparejamiento Bolt quedó en el receptor. Build instalado desde esta rama (`8550aaa`) con `scripts/install.sh --from-source`. El perfil activo se había aplicado días antes por Bolt.

Observado:

- Kernel, 22:15:45: `BLUETOOTH HID v0.06 Mouse [Logitech MX Master 3S]`, `hidraw11`, `HID++ 4.5 device connected`. La regla udev concedió acceso al usuario (ACL presente en el nodo).
- `solaar show` imprimió el mouse como encabezado sin ranura, con `Serial number:` vacío y `Unit ID:` a nivel de dispositivo, y el emparejamiento Bolt como `Device is offline.`: la misma forma que los fixtures.
- `solaar config <Unit ID>` de fábrica falló con `no online device found matching`; el binario anterior instalado falló igual. El adaptador devolvió los ajustes y `# transport: Bluetooth`; `omalogi status` con el binario nuevo devolvió `ok: true`, `transport: Bluetooth`, 11 ajustes.
- El identificador del perfil aplicado por Bolt coincidió con el Unit ID por Bluetooth. Solaar usó la misma entrada de persistencia (el archivo tenía dos entradas: este mouse y otro dispositivo).
- Gestos por Bluetooth con origen `solaar` y `ok: true`: los cinco a las 22:16:20–22 con las reglas ya existentes, y seis más a las 22:18:52–57, después de dos reinicios del servicio.
- DPI incremental 1300 → 1350 → 1300 por Bluetooth: 0,97 s y 0,89 s, cada uno con lectura posterior correcta y `applied: true`, `pending: false`, `daemon: true`.
- `omalogi restore` por Bluetooth, sobre un snapshot tomado por Bolt: 11,4 s, «restored y verificado» según la verificación de la propia CLI.

Incidente:

- La restauración arrancó el servicio a las 22:19:13,5 y se lanzó `omalogi status` de inmediato, que es también lo que hace el panel tras restaurar. El servicio registró lecturas inválidas desde las 22:19:14,66 (`AttributeError` al leer batería) y 14 errores en 17 s; los tres arranques anteriores de la sesión no registraron ninguno.
- 22:19:15,99: `bluetoothd` registró `Write output report failed`. El nodo `hidraw11` desapareció y el mouse respondió después por Bolt. `status` devolvió «The mouse is not responding» durante el cambio.
- Por Bolt, la lectura siguiente mostró `scroll-ratchet: Freespinning` aunque la restauración acababa de verificar `Ratcheted`.
- Solaar dejó en su persistencia ajustes ajenos a un mouse (`headset-*`, `analog-button-tuning_*`, `crown-smooth`, `logivoice-nr-state`), `_NAME: BL` y una segunda entrada para el mismo Unit ID con `dpi` y `divert-keys` marcados como ausentes. El respaldo previo a la prueba ya contenía una clave de ese tipo (`logivoice-ng-state`), de fecha desconocida.

Causa: **no demostrada**. Hipótesis: el servicio recién arrancado y la CLI consultaron HID++ a la vez sobre el mismo nodo `hidraw` Bluetooth y cada proceso interpretó respuestas del otro; una escritura mal dirigida explicaría el cambio de canal y de modo de giro. No se descarta que el canal se cambiara a mano con Easy-Switch. No se intentó reproducir.

Recuperación:

- Perfil reaplicado por Bolt a través del adaptador: transacción completa, 26,9 s, verificada (1300 DPI, Ratcheted, SmartShift 10, botón de gestos desviado). Esto cubre también la escritura por Bolt con el adaptador, que antes solo tenía lectura. `rules.yaml` quedó idéntico byte a byte al previo a la prueba.
- Esa reaplicación tomó como baseline el estado con Freespinning. Con el servicio detenido se repusieron `~/.config/solaar/config.yaml` y `~/.config/omalogi/state.json` desde el respaldo tomado antes de la prueba, cuyo perfil y valores coinciden con los aplicados. Estado final: `transport: Bolt`, `applied: true`, `pending: false`, `daemon: true`, baseline original, sin errores nuevos en el registro del servicio.
- Tiempo de una lectura por Bolt, tres pares: Solaar de fábrica 2,57/2,20/2,21 s; adaptador 2,19/2,22/2,21 s.

### Espera al arranque del servicio y segunda prueba — 2026-10-01, 23:18–23:33

Medición pasiva (lectura de los nodos `hidraw` de Logitech, sin enviar nada), tres reinicios del servicio sin ninguna consulta de la CLI, con el mouse por Bluetooth desde las 23:18:02:

- Nodo Bluetooth del mouse: 121 respuestas HID++ en cada reinicio, la primera a 0,36–0,47 s del arranque y la última a 2,55–2,88 s, sin pausas mayores de 0,5 s.
- Otro mouse Logitech por receptor Lightspeed: 202–208 respuestas, hasta 2,96–3,10 s. Nodo del receptor Bolt: 9.
- El incidente ocurrió 2,46 s después de un arranque, dentro de esa ventana y con una consulta de la CLI solapada. Es coherente con la hipótesis de lecturas cruzadas; no la demuestra.

Cambio: antes de cualquier consulta HID++, la CLI pregunta a systemd cuánto lleva activo el servicio y espera hasta completar 6 s. Las transacciones detienen el servicio y no esperan. Pruebas: 11 contratos Rust y 60 pruebas Python; tres de ellas comprueban que ninguna consulta llega al mouse durante los primeros 3 s, con y sin perfil guardado, y que un servicio asentado no añade demora. Mutation check: quitar la espera en `config`, quitarla en el descubrimiento, ignorar la antigüedad del servicio o esperar con el servicio detenido hace fallar una prueba en cada caso.

Con el build `2b653a4` instalado y el mouse por Bluetooth:

- La secuencia del incidente, cinco veces seguidas: `restore`, `status` inmediato, `apply` del perfil, `status` inmediato. Las diez consultas inmediatas tardaron 7,4–8,7 s (espera incluida) y devolvieron `transport: Bluetooth` con los valores esperados (1000 DPI y botón de gestos normal tras restaurar; 1300 DPI y desviado tras aplicar). Cero errores en el registro del servicio, una sola entrada de Solaar para el mouse, sin claves nuevas ni perdidas.
- Diez transacciones completas por Bluetooth en esos ciclos: `restore` 10,6–11,6 s y `apply` 10,2–11,1 s, todas verificadas por la CLI.
- Perfil de diagnóstico (once eventos, ambas ruedas y botones laterales desviados) aplicado y verificado en 11,3 s. Eventos físicos del usuario con origen `solaar` y `ok: true`: `gesture.click` (3), `gesture.right` (2), `wheel.up` (10), `wheel.down` (27), `thumb.left` (1), `thumb.right` (1).
- No se registraron `button.back`, `button.forward`, `gesture.up`, `gesture.down` ni `gesture.left` en esa ventana de 150 s. No se sabe si no se pulsaron o si no se capturaron. Los tres gestos sí se registraron por Bluetooth en la primera prueba; los botones laterales no tienen evidencia por Bluetooth.
- Reconexión: apagado y encendido físico, nodo Bluetooth ausente 2,5 s. Después de reconectar se registró `wheel.down` con origen `solaar`: Solaar repuso el desvío de la rueda. Se esperaron 10 s tras la reconexión antes de la siguiente consulta de la CLI.
- Cierre: perfil del usuario reaplicado y verificado por Bluetooth; `applied: true`, `pending: false`, `daemon: true`; cero errores del servicio durante toda la ventana.

Pendiente:

- La causa del incidente sigue sin demostrar. No se reprodujo a propósito sin la espera; el resultado es 1 incidente en 3 consultas inmediatas sin espera frente a 0 en 10 con ella.
- La espera cubre el arranque del servicio, no el escaneo que Solaar repite cuando el mouse reconecta con el servicio ya activo. Una consulta de la CLI en esos segundos no está protegida.
- Botones laterales por Bluetooth, y reconexión tras una suspensión larga del mouse o del equipo.
- Continuidad del perfil entre Bolt y Bluetooth en otros modelos. Depende de que la serie informada por Bolt coincida con el Unit ID; coincide en el 3S observado.

