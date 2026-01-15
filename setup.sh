#!/bin/bash
# =============================================================================
# Creador de Videos Virales - Script de Instalación Automática
# =============================================================================
# Este script prepara el entorno de desarrollo completo.
# Ejecutar: chmod +x setup.sh && ./setup.sh
# =============================================================================

set -e  # Salir si hay errores

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # Sin color

echo -e "${CYAN}"
echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║       🎬 Creador de Videos Virales - Instalación              ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# -----------------------------------------------------------------------------
# Función para verificar comandos
# -----------------------------------------------------------------------------
check_command() {
    if command -v "$1" &> /dev/null; then
        echo -e "${GREEN}✓${NC} $1 encontrado: $(command -v $1)"
        return 0
    else
        echo -e "${RED}✗${NC} $1 no encontrado"
        return 1
    fi
}

# -----------------------------------------------------------------------------
# 1. Verificar requisitos del sistema
# -----------------------------------------------------------------------------
echo -e "\n${YELLOW}[1/6] Verificando requisitos del sistema...${NC}\n"

# Python 3.11+
if check_command python3; then
    PYTHON_VERSION=$(python3 --version 2>&1 | cut -d' ' -f2)
    PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d'.' -f1)
    PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d'.' -f2)
    
    if [ "$PYTHON_MAJOR" -ge 3 ] && [ "$PYTHON_MINOR" -ge 11 ]; then
        echo -e "${GREEN}✓${NC} Python $PYTHON_VERSION (✓ >= 3.11)"
    else
        echo -e "${YELLOW}!${NC} Python $PYTHON_VERSION detectado. Se recomienda Python 3.11+"
        echo -e "  Puedes continuar, pero algunas librerías podrían tener problemas."
    fi
else
    echo -e "${RED}✗ Python 3 no encontrado. Por favor instala Python 3.11+${NC}"
    echo "  En Arch Linux: sudo pacman -S python"
    echo "  En Ubuntu/Debian: sudo apt install python3.11"
    exit 1
fi

# FFmpeg
if check_command ffmpeg; then
    FFMPEG_VERSION=$(ffmpeg -version 2>&1 | head -1 | cut -d' ' -f3)
    echo -e "${GREEN}✓${NC} FFmpeg $FFMPEG_VERSION"
else
    echo -e "${RED}✗ FFmpeg no encontrado${NC}"
    echo "  FFmpeg es necesario para renderizar videos."
    echo "  En Arch Linux: sudo pacman -S ffmpeg"
    echo "  En Ubuntu/Debian: sudo apt install ffmpeg"
    echo ""
    read -p "¿Deseas continuar sin FFmpeg? (s/n): " CONTINUE
    if [[ ! "$CONTINUE" =~ ^[Ss]$ ]]; then
        exit 1
    fi
fi

# Git
check_command git || echo -e "${YELLOW}  Git es recomendado para actualizaciones${NC}"

# -----------------------------------------------------------------------------
# 2. Instalar uv (gestor de paquetes Python)
# -----------------------------------------------------------------------------
echo -e "\n${YELLOW}[2/6] Configurando gestor de paquetes uv...${NC}\n"

if check_command uv; then
    echo -e "${GREEN}✓${NC} uv ya está instalado"
else
    echo "Instalando uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    
    # Agregar al PATH de la sesión actual
    export PATH="$HOME/.local/bin:$PATH"
    
    if check_command uv; then
        echo -e "${GREEN}✓${NC} uv instalado correctamente"
    else
        echo -e "${RED}✗ Error instalando uv${NC}"
        echo "  Intenta manualmente: curl -LsSf https://astral.sh/uv/install.sh | sh"
        exit 1
    fi
fi

# -----------------------------------------------------------------------------
# 3. Crear entorno virtual e instalar dependencias
# -----------------------------------------------------------------------------
echo -e "\n${YELLOW}[3/6] Creando entorno virtual e instalando dependencias...${NC}\n"

# Crear entorno con Python 3.11 si está disponible
if command -v python3.11 &> /dev/null; then
    echo "Usando Python 3.11..."
    uv venv --python python3.11
else
    echo "Usando Python por defecto..."
    uv venv
fi

# Activar e instalar
echo "Instalando dependencias (esto puede tomar unos minutos)..."
source .venv/bin/activate
uv sync

echo -e "${GREEN}✓${NC} Dependencias instaladas"

# -----------------------------------------------------------------------------
# 4. Configurar archivo .env
# -----------------------------------------------------------------------------
echo -e "\n${YELLOW}[4/6] Configurando archivo de entorno...${NC}\n"

if [ -f ".env" ]; then
    echo -e "${YELLOW}!${NC} El archivo .env ya existe."
    read -p "¿Deseas sobrescribirlo? (s/n): " OVERWRITE
    if [[ ! "$OVERWRITE" =~ ^[Ss]$ ]]; then
        echo "Manteniendo .env existente."
    else
        cp .env.example .env
        echo -e "${GREEN}✓${NC} .env creado desde template"
    fi
else
    cp .env.example .env
    echo -e "${GREEN}✓${NC} .env creado desde template"
fi

# -----------------------------------------------------------------------------
# 5. Crear directorios necesarios
# -----------------------------------------------------------------------------
echo -e "\n${YELLOW}[5/6] Creando directorios...${NC}\n"

mkdir -p output temp cache assets
echo -e "${GREEN}✓${NC} Directorios creados: output/, temp/, cache/, assets/"

# -----------------------------------------------------------------------------
# 6. Verificación final
# -----------------------------------------------------------------------------
echo -e "\n${YELLOW}[6/6] Verificación final...${NC}\n"

# Test de importación
source .venv/bin/activate
python -c "from src.pipeline import VideoPipeline; print('✓ Módulos importados correctamente')" 2>/dev/null || {
    echo -e "${RED}✗ Error importando módulos${NC}"
    echo "  Revisa que todas las dependencias estén instaladas."
}

# -----------------------------------------------------------------------------
# Resumen final
# -----------------------------------------------------------------------------
echo -e "\n${CYAN}"
echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║              ✅ INSTALACIÓN COMPLETADA                        ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

echo -e "${GREEN}Próximos pasos:${NC}"
echo ""
echo "  1. ${YELLOW}Configura tus API keys${NC} en el archivo .env:"
echo "     - OPENROUTER_API_KEY (requerido para generar guiones)"
echo "     - PEXELS_API_KEY (requerido para fondos de video)"
echo "     - REDDIT_CLIENT_ID y REDDIT_CLIENT_SECRET (opcional)"
echo ""
echo "  2. ${YELLOW}Ejecuta el menú principal:${NC}"
echo "     ./menu.sh"
echo ""
echo "  3. ${YELLOW}O ejecuta el pipeline directamente:${NC}"
echo "     source .venv/bin/activate"
echo "     python -m src.pipeline --full"
echo ""
echo -e "${CYAN}¡Listo para crear videos virales! 🚀${NC}"
echo ""
