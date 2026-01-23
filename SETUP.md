# 🚀 Guía de Instalación - Creador de Videos V3

Esta guía te ayudará a configurar el proyecto en una nueva máquina después de clonarlo desde GitHub.

## Requisitos del Sistema

| Software | Versión Mínima | Propósito |
|----------|---------------|-----------|
| Python | 3.10+ | Runtime principal |
| FFmpeg | 6.0+ | Procesamiento de video |
| Node.js | 18+ | Generadores de arte (P5.js) |
| rclone | 1.60+ | Sincronización con la nube |

---

## 📋 Instalación Paso a Paso

### 1. Clonar el Repositorio

```bash
git clone https://github.com/halbares/Creador_videos_v2.git
cd Creador_videos_v2
```

### 2. Instalar Dependencias del Sistema

#### Arch Linux / Manjaro
```bash
sudo pacman -S ffmpeg nodejs npm rclone
```

#### Debian / Ubuntu
```bash
sudo apt update
sudo apt install ffmpeg nodejs npm rclone
```

#### Fedora
```bash
sudo dnf install ffmpeg nodejs npm rclone
```

### 3. Crear Entorno Virtual Python

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

### 4. Configurar Variables de Entorno

Crear archivo `.env` en la raíz del proyecto:

```bash
cp .env.example .env   # Si existe
# O crear manualmente:
nano .env
```

#### Variables Requeridas

```env
# API Keys (OBLIGATORIAS)
OPENROUTER_API_KEY=sk-or-v1-xxxxx
PEXELS_API_KEY=xxxxx

# Reddit (opcional, para scraping)
REDDIT_CLIENT_ID=xxxxx
REDDIT_CLIENT_SECRET=xxxxx
REDDIT_USER_AGENT=CreadorVideos/1.0

# Modelos LLM
LLM_MODEL_PRIMARY=qwen/qwen3-235b-a22b-2507
LLM_MODEL_BACKUP=meta-llama/llama-4-scout

# Video
VIDEO_DURATION_MIN=45
VIDEO_DURATION_MAX=60
VIDEO_WIDTH=1080
VIDEO_HEIGHT=1920

# Paths
OUTPUT_DIR=./output
TEMP_DIR=./temp
CACHE_DIR=./cache

# Publicación en la nube (opcional)
GDRIVE_REMOTE=dropbox
GDRIVE_FOLDER=Videos/Creador
MAKE_WEBHOOK_URL=https://hook.us2.make.com/xxxxx
PUBLISH_MODE=automatic
```

### 5. Configurar rclone (Para Publicación)

```bash
rclone config
```

Sigue el asistente para configurar tu remote (Dropbox, Google Drive, etc.).
El nombre del remote debe coincidir con `GDRIVE_REMOTE` en tu `.env`.

### 6. Verificar Instalación

```bash
# Verificar FFmpeg
ffmpeg -version

# Verificar Node.js
node --version

# Verificar rclone
rclone version

# Verificar Python
python --version
```

---

## 🔑 Dónde Obtener las API Keys

| Servicio | URL | Notas |
|----------|-----|-------|
| OpenRouter | https://openrouter.ai/keys | Requiere cuenta, créditos de pago |
| Pexels | https://www.pexels.com/api/ | Gratis, límite de requests |
| Reddit | https://www.reddit.com/prefs/apps | Crear "script" app |

---

## 📁 Estructura de Directorios (Auto-creados)

Estos directorios se crean automáticamente al ejecutar:

```
cache/          # Stickers descargados, modelos
temp/           # Archivos temporales de video
output/         # Videos finalizados
```

---

## 🎬 Primera Ejecución

```bash
source .venv/bin/activate
./menu.sh
```

> **Nota:** La primera ejecución descargará el modelo de Whisper (~1.5GB).
> Asegúrate de tener buena conexión a internet.

---

## ❓ Solución de Problemas

### Error: "ffmpeg not found"
```bash
# Verificar que ffmpeg está en PATH
which ffmpeg
# Si no está, reinstalar o agregar al PATH
```

### Error: "OPENROUTER_API_KEY not set"
```bash
# Verificar que .env existe y tiene content
cat .env | grep OPENROUTER
```

### Error: "rclone: command not found"
```bash
# Instalar rclone manualmente
curl https://rclone.org/install.sh | sudo bash
```

---

## 🔄 Actualizar el Proyecto

```bash
git pull origin main
pip install -e .  # Por si hay nuevas dependencias
```
