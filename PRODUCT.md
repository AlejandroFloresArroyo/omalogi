# Omalogi

Configurador local para el MX Master del usuario en Omarchy. La entrega confirmada está en [MVP_SCOPE.md](MVP_SCOPE.md): DPI, cinco gestos, botones laterales y ambas ruedas; aplicación verificable, persistencia y restauración.

El dispositivo consultado es MX Master 3S por Bolt. El usuario quiere controlar su mouse desde su escritorio habitual y conservar el desplazamiento y los botones que no personalice. El servicio Solaar sigue externo; la CLI propia usa Rust y el panel usa QML dentro del shell existente.

Plataforma: Linux/Wayland, Omarchy 4.0.4 y Quickshell. Superficie en modo **Operate**: editar, aplicar, verificar y restaurar. Español es el idioma inicial.

La identidad visual está fijada por el sistema existente: componentes `qs.Ui`, colores y tipografía `qs.Commons`, estados de foco y escalado de Omarchy. No se crea un tema independiente ni se sustituye el shell del usuario.

Las lecturas y las pruebas físicas son evidencia separada. Un mensaje de éxito solo se muestra después de una escritura y lectura posterior verificadas. Las invocaciones manuales se etiquetan y no se cuentan como entradas del hardware.
