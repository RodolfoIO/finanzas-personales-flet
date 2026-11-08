# Pulso financiero

Aplicación de escritorio/web en Flet para consolidar cuentas bancarias y tarjetas, importar movimientos, clasificar gastos y controlar presupuestos mensuales.

## Inicio rápido

```bash
uv run flet run
```

La primera ejecución crea una base SQLite en `~/.finanzas_personales/finanzas.sqlite3`. Para usar la sincronización con Supabase:

1. Ejecuta [`supabase/schema.sql`](supabase/schema.sql) en el SQL Editor de tu proyecto.
2. Configura `SUPABASE_URL` y `SUPABASE_KEY` en el entorno donde ejecutas la app.
3. Inicia la aplicación. Los cambios se guardan localmente y se envían a Supabase cuando la conexión está disponible.

La app acepta CSV de cuentas/tarjetas BAC y archivos TXT tabulados de G&T. Los archivos se importan de forma idempotente usando un hash de fecha, descripción, cuenta y monto.

## Pruebas

```bash
uv run pytest
```

## Run the app

### uv

Run as a desktop app:

```bash
uv run flet run
```

Run as a web app:

```bash
uv run flet run --web
```

For more details on running the app, refer to the [Getting Started Guide](https://flet.dev/docs/).

## Build the app

### Android

```bash
flet build apk -v
```

For more details on building and signing `.apk` or `.aab`, refer to the [Android Packaging Guide](https://flet.dev/docs/publish/android/).

### iOS

```bash
flet build ipa -v
```

For more details on building and signing `.ipa`, refer to the [iOS Packaging Guide](https://flet.dev/docs/publish/ios/).

### macOS

```bash
flet build macos -v
```

For more details on building macOS package, refer to the [macOS Packaging Guide](https://flet.dev/docs/publish/macos/).

### Linux

```bash
flet build linux -v
```

For more details on building Linux package, refer to the [Linux Packaging Guide](https://flet.dev/docs/publish/linux/).

### Windows

```bash
flet build windows -v
```

For more details on building Windows package, refer to the [Windows Packaging Guide](https://flet.dev/docs/publish/windows/).

### Web

```bash
flet build web -v
```

For more details on building Web app, refer to the [Web Packaging Guide](https://flet.dev/docs/publish/web/).
# finanzas-personales-flet
