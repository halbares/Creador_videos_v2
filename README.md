# 🎬 Creador de Videos Virales

Sistema automatizado para crear **videos cortos (Shorts/Reels)** de 45-60 segundos sobre **vida saludable y bienestar**, optimizados para máxima **retención de audiencia**.

## ✨ Características

- 🔍 **Scraping automático** de contenido desde RSS, Reddit, YouTube y blogs
- 🤖 **Generación de guiones** con LLM (OpenRouter) optimizados para retención
- 🎤 **Text-to-Speech neural** con Edge-TTS (voces en español de alta calidad)
- 🎥 **Renderizado de video** con FFmpeg, subtítulos animados y fondos de Pexels
- 📁 **Organización automática** con metadatos para redes sociales

## 🚀 Instalación Rápida

```bash
# Clonar el repositorio
git clone https://github.com/halbares/Creador_videos_v2.git
cd Creador_videos_v2

# Ejecutar script de instalación
chmod +x setup.sh
./setup.sh
```

El script automáticamente:
- ✅ Verifica Python 3.11+ y FFmpeg
- ✅ Instala `uv` (gestor de paquetes)
- ✅ Crea entorno virtual
- ✅ Instala dependencias
- ✅ Configura archivo `.env`

## ⚙️ Configuración

Edita el archivo `.env` con tus API keys:

```bash
# Requeridas
OPENROUTER_API_KEY=tu_key_aquí   # https://openrouter.ai/keys
PEXELS_API_KEY=tu_key_aquí       # https://www.pexels.com/api/

# Opcionales
REDDIT_CLIENT_ID=                 # https://www.reddit.com/prefs/apps
REDDIT_CLIENT_SECRET=
```

## 📖 Uso

### Menú Interactivo
```bash
./menu.sh
```

### Comandos Directos
```bash
# Activar entorno
source .venv/bin/activate

# Pipeline completo (1 video)
python -m src.pipeline --full

# Generar múltiples videos
python -m src.pipeline --full --count 5

# Solo scraping
python -m src.pipeline --scrape

# Ver contenido pendiente
python -m src.pipeline --pending
```

### 📤 Publicación en la Nube
```bash
# Publicar un video existente
python -m src.pipeline --publish output/mi_video/video.mp4

# Pipeline sin publicar (solo generar localmente)
python -m src.pipeline --full --no-publish

# Publicar automáticamente (sin confirmación)
python -m src.pipeline --full --publish-mode automatic

# Ver cola de publicaciones pendientes
python -m src.pipeline --publish-queue

# Reintentar publicaciones fallidas
python -m src.pipeline --retry-failed
```

## 📂 Estructura del Proyecto

```
Creador_videos_v2/
├── src/
│   ├── scraper/      # Obtención de contenido
│   ├── llm/          # Generación de guiones
│   ├── tts/          # Text-to-Speech (Edge-TTS)
│   ├── video/        # Renderizado y subtítulos
│   ├── publisher/    # Publicación a la nube
│   │   ├── cloud_uploader.py  # Wrapper rclone
│   │   ├── make_webhook.py    # Cliente Make.com
│   │   └── retry_queue.py     # Cola de reintentos
│   └── pipeline.py   # Orquestador principal
├── config/
│   ├── prompts.yaml  # Prompts para el LLM
│   └── sources.yaml  # Fuentes de contenido
├── output/           # Videos generados
│   └── {tema}_{fecha}/
│       ├── video.mp4
│       └── metadata.md  # Info para redes sociales
├── setup.sh          # Instalación automática
├── menu.sh           # Menú interactivo
└── .env              # Configuración (no en repo)
```

## 🎯 Output

Cada video se guarda en su propia carpeta con:
- **Video MP4** (1080x1920, formato vertical)
- **metadata.md** con:
  - Título optimizado
  - Descripción SEO
  - Hashtags para TikTok/Instagram
  - Hooks alternativos
  - Keywords

## 📋 Requisitos del Sistema

| Requisito | Versión | Notas |
|-----------|---------|-------|
| Python | 3.11+ | Requerido |
| FFmpeg | 4.0+ | Para renderizado |
| RAM | 4GB+ | Recomendado 8GB |
| Disco | 5GB+ | Para modelos y videos |

### Instalación de FFmpeg

```bash
# Arch Linux
sudo pacman -S ffmpeg

# Ubuntu/Debian
sudo apt install ffmpeg

# macOS
brew install ffmpeg
```

## 🔧 Tecnologías

- **LLM**: OpenRouter (Qwen, Llama)
- **TTS**: Edge-TTS (Microsoft Neural Voices)
- **Video**: FFmpeg
- **Backgrounds**: Pexels API
- **Python**: uv, pydub, rich

## 📄 Licencia

MIT License - Ver [LICENSE](LICENSE)

## 🤝 Contribuir

1. Fork el repositorio
2. Crea una rama (`git checkout -b feature/nueva-funcion`)
3. Commit cambios (`git commit -m 'Agregar nueva función'`)
4. Push (`git push origin feature/nueva-funcion`)
5. Abre un Pull Request

---

**Creado con ❤️ para automatizar la creación de contenido viral**
