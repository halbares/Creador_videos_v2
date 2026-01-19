# Guía de Conexión MCP a Antigravity

> **Fecha:** 2026-01-14  
> **Autor:** Generado durante sesión de configuración de mcp-n8n

---

## Resumen

Esta guía documenta el proceso correcto para conectar un servidor MCP (Model Context Protocol) a **Antigravity** (el IDE basado en VS Code de Google).

## Archivo de Configuración Correcto

> [!IMPORTANT]
> Antigravity **NO** usa `~/.config/Antigravity/User/mcp.json` para cargar servidores MCP.

El archivo correcto es:

```
~/.gemini/antigravity/mcp_config.json
```

## Formato de Configuración

```json
{
  "mcpServers": {
    "nombre-del-servidor": {
      "command": "comando",
      "args": ["arg1", "arg2", "..."],
      "env": {
        "VARIABLE": "valor"
      },
      "disabled": false
    }
  }
}
```

### Ejemplo Real (Obsidian + n8n)

```json
{
  "mcpServers": {
    "obsidian": {
      "command": "uv",
      "args": [
        "--directory",
        "/home/pablo/Proyectos/mcp-obsidian",
        "run",
        "src/server.py"
      ],
      "env": {
        "OBSIDIAN_VAULT_PATH": "/home/pablo/Baul_Obsidian"
      },
      "disabled": false
    },
    "n8n": {
      "command": "uv",
      "args": [
        "--directory",
        "/home/pablo/Proyectos/mcp-n8n",
        "run",
        "python",
        "-m",
        "src.server"
      ],
      "disabled": false
    }
  }
}
```

## Pasos para Agregar un Nuevo Servidor MCP

1. **Desarrolla tu servidor MCP** usando el SDK de Python (`mcp` package).

2. **Edita el archivo de configuración:**
   ```bash
   nano ~/.gemini/antigravity/mcp_config.json
   ```

3. **Agrega tu servidor** siguiendo el formato anterior.

4. **Recarga Antigravity:**
   - `Ctrl+Shift+P` → `Reload Window`
   - O cierra y abre completamente si no funciona

5. **Verifica** preguntando al asistente si tiene acceso a las herramientas.

## Notas Importantes

### Sobre el comando `uv`
- Usa `"command": "uv"` (sin ruta absoluta) — Antigravity lo encuentra en el PATH.
- El orden de argumentos es: `["--directory", "/ruta", "run", "archivo.py"]`

### Sobre servidores como módulo Python
- Si tu servidor se ejecuta como módulo (`python -m src.server`), usa:
  ```json
  "args": ["--directory", "/ruta", "run", "python", "-m", "src.server"]
  ```

### Sobre variables de entorno
- Usa el campo `"env"` para pasar variables como API keys o rutas.
- También puedes usar un archivo `.env` en el proyecto del servidor.

### Archivos que NO funcionan (redundantes)
- `~/.config/Antigravity/User/mcp.json` — No se usa para MCP
- `~/.gemini/settings.json` — Solo para configuración general de Gemini CLI

## Solución de Problemas

| Problema | Solución |
|----------|----------|
| Servidor no aparece | Verificar que el archivo correcto está editado |
| Error de conexión | Revisar logs con `pgrep -f "tu-servidor" -a` |
| Servidor no arranca | Probar el comando manualmente en terminal |
| Herramientas no disponibles | Cerrar y reabrir Antigravity completamente |
| "server name X not found" | Ver sección "Migrar de venv a uv" abajo |

## ⚠️ CRÍTICO: Usar `uv`, NO `venv`

> [!CAUTION]
> Antigravity **NO funciona bien con paths absolutos a Python**. Los servidores MCP DEBEN usar `uv` como comando.

### ❌ Configuración que NO funciona
```json
"make": {
  "command": "/home/pablo/Proyectos/MCP-MAKE/venv/bin/python",
  "args": ["/home/pablo/Proyectos/MCP-MAKE/server.py"]
}
```

### ✅ Configuración que SÍ funciona
```json
"make": {
  "command": "uv",
  "args": ["--directory", "/home/pablo/Proyectos/MCP-MAKE", "run", "server.py"]
}
```

## Migrar un Servidor MCP de `venv` a `uv`

Si tu servidor MCP usa `venv` y Antigravity no lo reconoce, sigue estos pasos:

### 1. Crea `pyproject.toml` en el proyecto

```toml
[project]
name = "tu-servidor-mcp"
version = "1.0.0"
description = "Tu servidor MCP"
requires-python = ">=3.11"
dependencies = [
    "mcp>=1.0.0",
    # ... otras dependencias de requirements.txt
]
```

### 2. Sincroniza con uv

```bash
cd /ruta/al/proyecto
uv sync
```

### 3. Actualiza la configuración MCP

Cambia de:
```json
"command": "/ruta/venv/bin/python",
"args": ["/ruta/server.py"]
```

A:
```json
"command": "uv",
"args": ["--directory", "/ruta/al/proyecto", "run", "server.py"]
```

### 4. Recarga Antigravity

- `Ctrl+Shift+P` → `Developer: Reload Window`
- O cierra y abre completamente

## Verificación Rápida

Para verificar que un servidor MCP está funcionando:

1. Pregunta al asistente: *"¿Tienes acceso a [nombre-servidor]?"*
2. O usa una herramienta específica, ej: *"Lista mis workflows de n8n"*

### Probar servidor manualmente

```bash
echo '{"jsonrpc": "2.0", "method": "initialize", "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "test", "version": "1.0"}}, "id": 1}' | uv --directory /ruta/proyecto run server.py
```

Si responde con JSON conteniendo `"serverInfo"`, el servidor funciona.

---

> **Última actualización:** 2026-01-16  
> *Documento generado para referencia futura. Actualizar según cambios en Antigravity.*

