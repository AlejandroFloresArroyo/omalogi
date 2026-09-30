# MVP de Omalogi

Actualizado: 2026-09-29. Alcance confirmado en la conversación: MX Master 3 conectado mediante Bolt; incluir gestos, DPI, botones laterales y ruedas. La identidad detectada es MX Master 3S. La arquitectura descrita está implementada e instalada; [VALIDATION.md](VALIDATION.md) separa las pruebas completadas de las pendientes.

## Entrega

Una versión usable en el equipo del usuario, con CLI, panel integrado en Omarchy, instalación reproducible, restauración de cambios y pruebas sobre el mouse real.

## Alcance confirmado

- Botón de gestos: clic y cuatro direcciones, con acciones asignables.
- DPI: ajustar la resolución real del sensor dentro de los valores que exponga el dispositivo.
- Botones laterales: asignar acciones a atrás y adelante; conservar su comportamiento habitual cuando no se personalicen.
- Rueda vertical y rueda horizontal: controles de configuración acordes con las capacidades detectadas del dispositivo.

## Comportamiento propuesto para las ruedas

La rueda vertical ofrecerá dirección, resolución y modo de giro/SmartShift cuando el dispositivo los permita. La horizontal ofrecerá dirección y desplazamiento habitual. La asignación de acciones a los giros de cada rueda se contempla como opción explícita: activar esa opción puede sustituir el desplazamiento normal. No se desviarán ruedas o botones que permanezcan en su comportamiento habitual.

## Arquitectura implementada

- Solaar externo como gestor del dispositivo y capturador de eventos; no copiar su implementación.
- CLI `omalogi` en Rust para configuración, validación, ejecución de acciones y aplicar/restaurar cambios.
- Panel QML dentro del shell de Omarchy, con tema nativo y widget opcional.
- Usar comandos oficiales de Omarchy e invocaciones Lua compatibles para las acciones del escritorio.
- Detectar capacidades e identificadores reales; no inferirlos únicamente del nombre comercial o del receptor.

## Criterios de terminado

1. Identificar el mouse conectado y sus controles soportados; mostrar fallos de conexión o dependencias con instrucciones útiles.
2. Leer y modificar DPI, botones laterales y ambas ruedas dentro de las capacidades detectadas.
3. Guardar asignaciones desde el panel y comprobar su ejecución en hardware.
4. Preservar las reglas ajenas de Solaar y los archivos del escritorio; guardar el estado previo y poder restaurarlo.
5. Mantener la configuración al reconectar el mouse y al reiniciar la sesión; comprobar el arranque del proceso que captura los eventos.
6. Entregar código compilable, instalación/desinstalación documentada y resultados de pruebas automatizadas y de hardware. Una simulación no sustituye la validación del mouse conectado.

## Decisiones de implementación

- Valores iniciales editables: clic Aplicaciones; arriba Menú; abajo Scratchpad; izquierda/derecha cambian espacio. Ruedas y botones laterales conservan su comportamiento habitual por defecto.
- Plugin `omalogi.mouse`; binario en `~/.local/bin/omalogi`; instalación local reproducible, con servicio de Solaar vinculado a la sesión gráfica. Publicar el paquete es una etapa posterior.
- Compatibilidad validada en Omarchy 4.0.4 / Quickshell 0.3.1 / Solaar 1.1.20. Las fuentes upstream actualizadas se consultaron para respetar el contrato; no se declara una versión mínima universal sin probarla.
- El daemon HID++ nativo sigue previsto para una V2.

## Evidencia

- [Integración actualizada con Omarchy](research/omarchy-integration.md).
- [Ruta Solaar para gestos](research/solaar-integration.md).
- [Viabilidad del backend nativo futuro](research/hidpp-native-path.md).
- Inspección de solo lectura del equipo: el receptor USB Logitech con producto `c548` aparece en `/proc/bus/input/devices`; el acceso a hidraw y al compositor debe verificarse fuera del entorno restringido para las pruebas reales.
