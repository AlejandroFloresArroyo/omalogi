---
name: Omalogi
description: Configuración nativa del MX Master dentro del sistema visual de Omarchy.
---

# Design System: Omalogi

## Overview

**Creative North Star: "El escritorio habitual de Omarchy"**

Extensión nativa en modo **Operate**: consultar, editar, aplicar y comprobar automáticamente, y restaurar. La interfaz densa y directa, en español, utiliza los componentes existentes de `qs.Ui` y los tokens de `qs.Commons`. La autoridad visual es externa al proyecto; este documento registra su uso, sin definir una nueva identidad.

Fuentes comprobadas: `plugin/{OmalogiPanel,OmalogiWidget,MouseDiagram,MouseBinding,ActionRow}.qml` y `manifest.json`, coincidentes con la instalación en `~/.config/omarchy/plugins/omalogi.mouse/`; `/usr/share/omarchy/shell/Commons/{Color,Style}.qml` y los controles citados abajo. Las capturas `.impeccable/review/{mouse,extras}.png` muestran las dos vistas del popup nativo de 920 × 690 px con el tema actual del usuario. La revisión independiente señaló únicamente las descripciones obsoletas de guardado manual y cierre bloqueado en este documento, corregidas aquí. `scripts/test-panel.py` prueba los componentes nativos con un CLI simulado lento: agrupación de cambios, cola del último perfil, cierre/reapertura durante una operación y error/reintento. Esa prueba no certifica clics físicos ni escrituras en el mouse real. El usuario confirmó que puede usar el escritorio durante la aplicación y que el ajuste se aplica automáticamente. Después informó lentitud, investigada con mediciones reales de CLI; la prueba del MVP en una sesión de inicio nueva sigue diferida por el usuario. Las capturas registran el tema y la composición observados, sin fijar una paleta propia.

La superficie sigue el panel flotante anclado a la barra de AI Usage. La referencia OpenLogi fija la composición y la foto del MX Master 3S aportada por el usuario (la imagen de referencia local) fija el dibujo casi cenital: cuerpo ancho, apoyo lateral del pulgar, rueda vertical recta y separación de los botones superiores. Es una actualización de composición y comportamiento dentro del sistema externo de Omarchy.

El frontmatter incluye únicamente identidad documental. Los valores de color, fuente, escala, borde y radio dependen del tema activo y se enlazan en QML. Congelarlos como primitivas CSS crearía otra fuente de verdad. No se genera un catálogo HTML/CSS ni sidecar para esta extensión ordinaria.

**Key Characteristics:**

- Controles y estados del shell existente.
- Popup anclado a la barra con cabecera, dos vistas y estado automático persistente.
- DPI, dos botones laterales, cuatro direcciones de rueda y cinco gestos visibles junto al dibujo.
- Cambios automáticos agrupados y mensajes de operación visibles; reintento o recuperación cuando hay errores.
- Evidencia de lectura del hardware separada del registro de entradas físicas.

## Colors

La paleta la proporciona el tema activo de Omarchy, a través de `Color`; sus valores cambian sin modificaciones del plugin.

### Primary

- `Color.accent`: cambios pendientes de aplicación, control físico resaltado y acento heredado de los controles. La pestaña activa utiliza el estado seleccionado del kit; no recibe un color local adicional.

### Neutral

- `Color.popups.background`: superficie del `KeyboardPanel` y de las listas desplegables.
- `Color.popups.text`: nombre del dispositivo, estado normal, etiquetas de asignación y eventos correctos; también base de los trazos y rellenos con alfa del dibujo.
- `Color.popups.border`: borde de los popups, interpretado por el kit mediante `Border.surfaceSpec` en `KeyboardPanel` y el tratamiento externo de los desplegables.
- `Color.foreground`: texto predeterminado de `Button`, `Toggle` y `NumberField`; también base del separador. No asumir que equivale a `Color.popups.text` en todos los temas.
- `root.secondary`: RGB de `Color.popups.text` con alfa (0.78), utilizado en metadatos, instrucciones y ayudas locales. La revisión anterior documentó aproximadamente 5.1:1 para el texto secundario heredado; ese resultado corresponde al tema y composición entonces observados y no constituye una nueva medición de estas capturas.
- Los rótulos y descripciones internos de los componentes conservan sus tratamientos externos, como `Qt.darker(foreground, 1.4)` en desplegables y `Qt.darker(foreground, 1.5)` en la descripción de `Toggle`.

### Semantic status

- `Color.urgent`: errores de consulta o mutación, operación pendiente y entradas fallidas del registro.

**The External Authority Rule.** Enlazar colores a los roles de `qs.Commons`; la captura no autoriza copiar su paleta ni ajustar el tema del usuario.

## Typography

**Body Font:** `Style.font.family`, alias gestionado por Omarchy. El singleton utiliza `monospace` como valor inicial y permite que el tema y fontconfig determinen la familia concreta. El plugin conserva ese enlace.

La jerarquía observada utiliza la escala del shell; los valores entre paréntesis son sus valores predeterminados a tamaño base (12 px), sujetos a overrides del tema:

- `Style.font.display` (24 px): rol disponible en la escala externa; la cabecera actual muestra el nombre del dispositivo sin pictograma.
- `Style.font.heading` (16 px), negrita: nombre del dispositivo.
- `Style.font.subtitle` (13 px): títulos de Ruedas y Pruebas del mouse, y títulos internos de `Toggle`.
- `Style.font.body` (12 px): mensajes, ayudas principales, etiquetas de acciones, valores de controles y botones.
- `Style.font.bodySmall` (11 px): rótulo interno de `NumberField` y tooltip del botón estándar.
- `Style.font.caption` (10 px): metadatos, ayuda breve, registros y rótulos de desplegables.

Los componentes aportan su propia jerarquía: los botones seleccionados y los títulos de `Toggle` usan negrita. Mensajes y ayudas extensas ajustan líneas; las opciones y títulos internos del kit pueden elidir. Los datos de estado y eventos se muestran como texto plano.

## Layout

`OmalogiWidget` usa el host `Panel` y contiene el `BarIconButton` que ancla `KeyboardPanel`. El panel usa la superficie layer-shell, el foco y la coordinación de popups nativos de Omarchy. Declara `fittedContentWidth(Style.space(920))` y `cappedContentHeight(Style.space(690))`; el kit limita la tarjeta al espacio disponible de la pantalla y la coloca respecto a la barra. La captura aprobada muestra 920 × 690 px. No hay breakpoints web ni una composición móvil independiente.

El kit aporta padding y borde mediante su `BorderSurface`; el `ColumnLayout` ocupa el contenido disponible. La cabecera presenta dispositivo y metadatos. Debajo están Mouse/Extras, el estado automático del perfil y un `PanelSeparator`. Mouse coloca la sensibilidad horizontal sobre una composición de tres columnas: botones y cuatro acciones de rueda a la izquierda (28% del área), dibujo escalable al centro y cinco gestos a la derecha (30%). El área del dibujo tiene una altura mínima de `Style.space(380)`; la columna central, un ancho mínimo de `Style.space(180)`. Las líneas conectan los seis selectores de botones y ruedas con sus controles físicos. Extras ocupa el mismo espacio central mediante `QQC.ScrollView`, con `contentWidth: availableWidth` y recorte activado; contiene diagnóstico y Restaurar original. El mensaje de operación permanece debajo de ambas vistas. Allí aparecen Reintentar cambios o Restaurar para recuperar cuando el estado requiere resolver un error. La cabecera carece de Actualizar/Cerrar y el pie de Guardar/Aplicar/Descartar.

Tokens externos reutilizados, con valores iniciales antes de escala u overrides:

| Token | Uso | Predeterminado |
| --- | --- | --- |
| `Style.spacing.popupPadding` | Padding heredado de `KeyboardPanel` | 14 px |
| `Style.spacing.panelPadding` | Token externo disponible para paneles | 18 px |
| `Style.spacing.panelGap` | Secciones y filas de acciones | 14 px |
| `Style.spacing.controlGap` | Navegación y pie | 8 px |
| `Style.spacing.labelGap` | Nombre/metadatos y etiqueta/selector | 4 px |
| `Style.spacing.dropdownWidth` | Selector en `ActionRow` | 240 px |
| `Style.spacing.numberFieldWidth` | Campo numérico | 120 px |
| `Style.spacing.controlHeight` | Altura base de campos | 28 px |
| `Style.spacing.controlPaddingX` / `controlPaddingY` | Botones y controles | 10 / 6 px |

`Style.space()` aplica la escala externa; no convertir estos valores iniciales en constantes locales. La composición de asignaciones usa separaciones locales escaladas de 18 px entre columnas y 10 px entre campos. Las filas de navegación, cabecera y pie no implementan envoltura propia. Verificar su ajuste con el tamaño y la fuente reales cuando se añadan acciones.

## Elevation & Depth

El plugin no añade sombras. La separación proviene de superficie, bordes, reglas finas y rellenos de estado del kit. Los desplegables se superponen mediante popups nativos. La transparencia, el wallpaper visible y la composición del escritorio en las capturas pertenecen al tema y al compositor del usuario; no son imágenes ni tratamientos creados por Omalogi.

Los cambios de color heredados duran (120 ms) en `Button` y (100 ms) en `Toggle`; `KeyboardPanel` aporta su transición de opacidad de (140 ms). No existe una gramática de animación adicional del plugin.

## Shapes

Los controles enlazan su radio a `Style.cornerRadius`, obtenido de la configuración externa de Hyprland. `Toggle` adapta su interruptor a esquinas redondeadas o rectas según ese token. Los bordes los resuelven `Border.controlSpec` y los tokens de estado del shell; no aplicar un radio o grosor uniforme local. `PanelSeparator` mantiene una regla horizontal de (1 px), con alfa predeterminado (0.12) de `Color.foreground`.

## Components

### Controles nativos reutilizados

- **`Button`**: texto con padding y radio externos; todos los botones del panel tienen `focusable: true`. Tab establece foco; Enter/Espacio activa. La pintura sigue presión, foco, hover, selección y reposo. `Style.pressedFillFor`, `focusFillFor`, `hoverFillFor`, `selectedFillFor` y `Border.controlSpec` conservan la autoridad del kit. La pestaña actual usa `selected`; diagnóstico, restauración y resolución de errores son acciones explícitas.
- **`Dropdown`**: selector de una opción con trigger y popup externos. Tab enfoca; Enter/Espacio abre; flechas o j/k recorren; Enter elige; Escape cierra el popup. Las opciones conservan `value` y `label` separados.
- **`SearchableDropdown`**: DPI utiliza la misma superficie con filtro integrado. Abrir enfoca la búsqueda; filtra etiquetas/descripciones sin distinguir mayúsculas; al cerrar borra el filtro. El panel configura “Buscar DPI…” y “Sin coincidencias”, y el rótulo del trigger con el valor de DPI.
- **`PanelSlider`**: sensibilidad horizontal con límites derivados de las opciones reales del sensor, paso de 50 y nombre accesible “Sensibilidad DPI”. El cambio selecciona el valor soportado más cercano; las flechas izquierda/derecha recorren ese mismo ajuste. El arrastre actualiza el valor visible, pero la aplicación espera a soltarlo y a la pausa de agrupación.
- **`NumberField`**: SpinBox editable de SmartShift, limitado a (1–50). Conserva validación, selección de texto y foco del kit.
- **`Toggle`**: fila completa activable por clic o Enter/Espacio, con título y descripción opcional. `checked` refleja el modelo; el panel decide la modificación. Conserva los estados `Style.controlFill`, `Style.controlBorder` y el switch externo.
- **`PanelSeparator`**: divide contenido y acciones sin crear tarjetas adicionales.

### Componentes locales

- **`ActionRow.qml`**: composición de `RowLayout`, etiqueta de cuerpo que ocupa el espacio disponible y `Dropdown` sin rótulo interno de ancho `Style.spacing.dropdownWidth`. Expone `label`, `value`, `options` y señal `changed(value)`. Selecciona el modo de giro vertical en Extras.
- **`MouseBinding.qml`**: etiqueta sobre un `Dropdown` de ancho disponible, con `Style.spacing.labelGap`. Expone `label`, `value`, `options`, señales `changed(value)`/`hovered(bool)` y `openEditor()`. Reúne asignaciones de botones, ruedas y gestos sin introducir controles propios.
- **`MouseDiagram.qml`**: vector QML trazado desde la foto del usuario sobre un lienzo de 320 × 420, escalado uniformemente al espacio central. Conserva la asimetría del apoyo del pulgar, los botones superiores, las dos ruedas, los botones laterales y el interruptor de gestos. Trazos y rellenos derivan de `Color.popups.text`; el control resaltado usa `Color.accent`. Hover sobre un selector resalta la región física. Pulsar adelante/atrás abre su selector; pulsar una rueda abre su primera dirección. Pulsar gestos activa su personalización si hace falta y abre el selector de clic sin mover. Las regiones físicas incluyen nombres y acción accesibles.
- **`OmalogiWidget.qml`**: extiende `Panel`, contiene el `BarIconButton` y mantiene perfil, cambios y proceso en su `OmalogiPanel`. Clic izquierdo invoca el toggle oficial del shell para `omalogi.mouse`. `close()` llama incondicionalmente a `controller.hide()` para liberar la capa de entrada del popup, incluso durante una aplicación. Tooltip: “Omalogi · configurar MX Master”. El pictograma, fuente y dimensiones ópticas proceden del mecanismo nativo del bar. El manifiesto lo declara `bar-widget` con `keepLoaded: true`, de modo que ocultar el popup conserva el componente que ejecuta la operación.
- **`OmalogiPanel.qml`**: host del popup anclado, navegación, perfil deseado, estado automático y procesos. Agrupa ediciones y serializa la aplicación del perfil más reciente. No extrae ni sustituye los componentes compartidos del shell.

### Dos vistas

| Vista | Controles y comportamiento revisado por fuente |
| --- | --- |
| Mouse | Sensibilidad por slider y selector de DPI soportados, dibujo central, Adelante/Atrás con “Comportamiento habitual”, cuatro direcciones de rueda y cinco gestos visibles simultáneamente. Los selectores de rueda ofrecen “Desplazamiento habitual”: elegirlo devuelve ambas direcciones de esa rueda a `native`; personalizar una dirección convierte su compañera todavía nativa en `none`. La ayuda explica la sustitución del desplazamiento y la conservación del clic central. El toggle Gestos asigna valores iniciales al activarse y devuelve las cinco vinculaciones a `native` al desactivarse; sus cinco selectores permanecen visibles y se deshabilitan sin personalización. Ajustes no soportados se deshabilitan. |
| Extras | Inversión vertical/horizontal, resolución vertical, modo Con pasos/Giro libre y SmartShift (1–50). SmartShift se deshabilita en giro libre y explica que el umbral guardado se reutiliza al volver a pasos. El registro temporal aplica diagnóstico a todas las vinculaciones mediante el mismo flujo automático y explica cómo reasignar controles o restaurar después. Restaurar original es una acción explícita en esta vista. Presenta los últimos ocho eventos en orden inverso, con evento, acción, origen y resultado; estado vacío sin registros. Consulta eventos cada (1200 ms) mientras el popup está abierto en Extras. |

### Aplicación automática, foco y operaciones

Un cambio efectivo modifica `profile`, incrementa `revision`, marca `dirty` y reinicia una pausa de (450 ms). Al terminar la pausa se envía el perfil completo para aplicar y comprobar. El slider no inicia una aplicación mientras se arrastra; soltarlo reinicia la pausa. Navegar entre páginas conserva el valor deseado. No se requiere Guardar ni Aplicar y las ediciones sin diferencias no generan otra operación.

Solo hay una mutación en curso. `sentRevision` identifica el perfil enviado; las ediciones posteriores permanecen en `profile` y en espera. Al completar una aplicación, la comparación de revisiones decide si siguen pendientes cambios: una respuesta anterior no sustituye el perfil más reciente. Si queda una edición, se reinicia la pausa para enviar su último valor. El contenido sigue editable durante una aplicación; se deshabilita antes de disponer de perfil, durante la consulta de estado y durante Restaurar. `busy` evita iniciar operaciones simultáneas y también protege restauración y diagnóstico.

Escape y el cierre nativo del popup pasan por `OmalogiWidget.close()` y ocultan el panel durante cualquier operación. El cierre libera la capa de entrada para usar el escritorio, mientras el componente persistente mantiene la operación y los cambios siguientes. Al reabrir se conservan página y perfil; solo se consulta estado cuando no hay cambios pendientes ni una operación en curso. El `FocusScope` raíz gestiona Escape y los controles externos gestionan sus propios popups y foco. La prueba nativa con CLI simulado cubre cierre/reapertura durante una mutación; el usuario también confirmó que el clic exterior ya permite seguir usando el escritorio.

Los mensajes de consulta, guardado/comprobación y restauración aparecen en la región inferior visible. El estado superior distingue “Guardando…”, “Aplicando…”, “Revisa el error”, perfil activo y ajustes originales. Una aplicación correcta muestra “Guardado · perfil activo” si corresponde a la última revisión; con ediciones posteriores muestra “Cambios siguientes en espera…”. La restauración correcta limpia los cambios y solicita una nueva lectura.

Una respuesta fallida se muestra en `Color.urgent` y conserva el valor deseado. No hay bucle de reintentos: Reintentar cambios o una nueva edición vuelve a solicitar la aplicación. Si el backend indica una operación incompleta, `recoveryRequired` bloquea la aplicación automática y ofrece Restaurar para recuperar; Restaurar original también está disponible en Extras. El éxito de una transacción y los eventos registrados son evidencia distinta de la selección visible.

**The Latest Edit Rule.** Agrupar cambios, serializar aplicaciones y conservar el último perfil deseado al completar una operación o cerrar el popup. Conservarlo en el componente cargado no equivale a persistencia después de reiniciar el shell.

**The Evidence Rule.** Mostrar lectura verificada y eventos con su origen. El registro de Extras, las capturas, la revisión de código y la prueba nativa con CLI simulado no sustituyen las pruebas físicas solicitadas ni la prueba pendiente en una sesión de inicio nueva.

## Do's and Don'ts

### Do:

- **Do** conservar las dependencias `qs.Ui` y `qs.Commons`, sus tokens y los estados de foco reales.
- **Do** reutilizar `MouseBinding` para asignaciones junto al dibujo, `ActionRow` para filas de ajustes y los controles externos para nuevos campos compatibles.
- **Do** mantener visibles el estado automático y las acciones de resolución cuando haya errores, y permitir cerrar el popup durante la operación.
- **Do** comprobar legibilidad con el tema y la composición nativos reales, incluidos textos secundarios.
- **Do** distinguir acción configurada, aplicación verificada y evento físico registrado.

### Don't:

- **Don't** introducir una paleta, fuente, kit de controles o activos decorativos que compitan con Omarchy.
- **Don't** convertir dimensiones, opacidad o wallpaper de las capturas en reglas propias del plugin.
- **Don't** modificar el escritorio, los componentes compartidos o el tema para corregir la composición local.
- **Don't** presentar las capturas o el CLI simulado como prueba de escrituras o clics físicos en el mouse real; distinguir la confirmación del usuario sobre cierre/aplicación automática de las mediciones de CLI; la prueba de inicio nuevo sigue diferida por el usuario.
- **Don't** convertir tratamientos internos observados del kit en recomendaciones generales para otras plataformas.
