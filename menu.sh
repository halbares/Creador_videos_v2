#!/usr/bin/env bash
#===============================================================================
#  CREADOR DE VIDEOS VIRALES - MENÚ PRINCIPAL
#  Sistema automatizado para crear videos cortos sobre vida saludable
#===============================================================================

set -e

# Colores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
WHITE='\033[1;37m'
NC='\033[0m' # Sin color

# Directorio del script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Función para mostrar el banner
show_banner() {
    clear
    echo -e "${PURPLE}"
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║                                                              ║"
    echo "║   🎬  CREADOR DE VIDEOS VIRALES                              ║"
    echo "║   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━                              ║"
    echo "║   Sistema de generación automática de contenido              ║"
    echo "║   Enfoque: RETENCIÓN máxima para Shorts/Reels                ║"
    echo "║                                                              ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

# Función para verificar entorno virtual
check_venv() {
    if [ ! -d ".venv" ]; then
        echo -e "${YELLOW}⚠ Entorno virtual no encontrado. Creando...${NC}"
        uv venv
        uv sync
        echo -e "${GREEN}✓ Entorno virtual creado${NC}"
    fi
}

# Función para activar entorno virtual
activate_venv() {
    source .venv/bin/activate
}

# Verificar dependencias del sistema
check_dependencies() {
    echo -e "${CYAN}Verificando dependencias del sistema...${NC}"
    
    # FFmpeg
    if command -v ffmpeg &> /dev/null; then
        echo -e "${GREEN}✓ FFmpeg instalado${NC}"
    else
        echo -e "${RED}✗ FFmpeg no encontrado. Instálalo con: sudo pacman -S ffmpeg${NC}"
        return 1
    fi
    
    # uv
    if command -v uv &> /dev/null; then
        echo -e "${GREEN}✓ uv instalado${NC}"
    else
        echo -e "${RED}✗ uv no encontrado. Instálalo con: curl -LsSf https://astral.sh/uv/install.sh | sh${NC}"
        return 1
    fi
    
    # .env
    if [ -f ".env" ]; then
        echo -e "${GREEN}✓ Archivo .env encontrado${NC}"
    else
        echo -e "${YELLOW}⚠ Archivo .env no encontrado. Copiando desde .env.example...${NC}"
        cp .env.example .env
        echo -e "${YELLOW}  → Edita .env con tus API keys${NC}"
    fi
    
    echo ""
}

# Menú de obtención de contenido
menu_scraping() {
    show_banner
    echo -e "${CYAN}📥 OBTENER CONTENIDO${NC}"
    echo ""
    echo -e "  ${WHITE}1.${NC} Obtener de RSS feeds"
    echo -e "  ${WHITE}2.${NC} Obtener de Reddit"
    echo -e "  ${WHITE}3.${NC} Obtener de YouTube"
    echo -e "  ${WHITE}4.${NC} Obtener de blogs/URLs"
    echo -e "  ${WHITE}5.${NC} Obtener de TODAS las fuentes"
    echo -e "  ${WHITE}0.${NC} Volver al menú principal"
    echo ""
    read -p "Selecciona una opción: " choice
    
    case $choice in
        1) activate_venv && python -m src.scraper.rss ;;
        2) activate_venv && python -m src.scraper.reddit ;;
        3) activate_venv && python -m src.scraper.youtube ;;
        4) activate_venv && python -m src.scraper.blogs ;;
        5) activate_venv && python -m src.scraper --all ;;
        0) return ;;
        *) echo -e "${RED}Opción inválida${NC}" ;;
    esac
    
    read -p "Presiona Enter para continuar..."
}

# Menú de generación de guión
menu_script() {
    show_banner
    echo -e "${CYAN}✍️  GENERAR GUIÓN${NC}"
    echo ""
    echo -e "  ${WHITE}1.${NC} Generar guión desde contenido guardado"
    echo -e "  ${WHITE}2.${NC} Generar guión desde texto manual"
    echo -e "  ${WHITE}3.${NC} Ver guiones generados"
    echo -e "  ${WHITE}4.${NC} Regenerar hooks (3 opciones)"
    echo -e "  ${WHITE}0.${NC} Volver al menú principal"
    echo ""
    read -p "Selecciona una opción: " choice
    
    case $choice in
        1) activate_venv && python -m src.llm --from-cache ;;
        2) 
            echo ""
            echo "Ingresa el texto (Enter dos veces para terminar):"
            text=""
            while IFS= read -r line; do
                [ -z "$line" ] && break
                text+="$line "
            done
            activate_venv && python -m src.llm --text "$text"
            ;;
        3) activate_venv && python -m src.llm --list ;;
        4) activate_venv && python -m src.llm.hooks --regenerate ;;
        0) return ;;
        *) echo -e "${RED}Opción inválida${NC}" ;;
    esac
    
    read -p "Presiona Enter para continuar..."
}

# Menú de generación de audio
menu_audio() {
    show_banner
    echo -e "${CYAN}🔊 GENERAR AUDIO (XTTS)${NC}"
    echo ""
    echo -e "  ${WHITE}1.${NC} Generar audio desde guión guardado"
    echo -e "  ${WHITE}2.${NC} Generar audio desde texto manual"
    echo -e "  ${WHITE}3.${NC} Ver audios generados"
    echo -e "  ${WHITE}4.${NC} Configurar voz"
    echo -e "  ${WHITE}0.${NC} Volver al menú principal"
    echo ""
    read -p "Selecciona una opción: " choice
    
    case $choice in
        1) activate_venv && python -m src.tts --from-script ;;
        2) 
            echo ""
            read -p "Ingresa el texto: " text
            activate_venv && python -m src.tts --text "$text"
            ;;
        3) ls -la temp/*.wav 2>/dev/null || echo "No hay audios generados" ;;
        4) activate_venv && python -m src.tts --configure ;;
        0) return ;;
        *) echo -e "${RED}Opción inválida${NC}" ;;
    esac
    
    read -p "Presiona Enter para continuar..."
}

# Menú de renderizado de video
menu_video() {
    show_banner
    echo -e "${CYAN}🎬 RENDERIZAR VIDEO${NC}"
    echo ""
    echo -e "  ${WHITE}1.${NC} Renderizar video completo"
    echo -e "  ${WHITE}2.${NC} Solo generar subtítulos ASS"
    echo -e "  ${WHITE}3.${NC} Obtener background de Pexels"
    echo -e "  ${WHITE}4.${NC} Previsualizar video (sin audio)"
    echo -e "  ${WHITE}5.${NC} Ver videos generados"
    echo -e "  ${WHITE}0.${NC} Volver al menú principal"
    echo ""
    read -p "Selecciona una opción: " choice
    
    case $choice in
        1) activate_venv && python -m src.video.renderer ;;
        2) activate_venv && python -m src.video.subtitles ;;
        3) activate_venv && python -m src.video.pexels ;;
        4) activate_venv && python -m src.video.renderer --preview ;;
        5) 
            echo ""
            echo -e "${CYAN}Videos en output/:${NC}"
            ls -lah output/*.mp4 2>/dev/null || echo "No hay videos generados"
            ;;
        0) return ;;
        *) echo -e "${RED}Opción inválida${NC}" ;;
    esac
    
    read -p "Presiona Enter para continuar..."
}

# Pipeline completo
run_pipeline() {
    show_banner
    echo -e "${GREEN}🚀 PIPELINE COMPLETO${NC}"
    echo ""
    
    # Mostrar contenido pendiente
    activate_venv
    pending=$(python -c "from src.pipeline import VideoPipeline; p = VideoPipeline(); print(p.get_pending_count()); p.close()" 2>/dev/null || echo "0")
    echo -e "${CYAN}Contenido pendiente en cache: ${pending} items${NC}"
    echo ""
    
    echo -e "${WHITE}Opciones:${NC}"
    echo -e "  ${CYAN}1.${NC} Generar 1 video"
    echo -e "  ${CYAN}2.${NC} Generar múltiples videos (especificar cantidad)"
    echo -e "  ${CYAN}3.${NC} Modo BATCH: procesar TODO el cache pendiente"
    echo -e "  ${RED}0.${NC} Cancelar"
    echo ""
    read -p "Selecciona una opción: " choice
    
    case $choice in
        1)
            echo ""
            echo -e "${YELLOW}Este proceso ejecutará:${NC}"
            echo "  1. Obtener contenido de fuentes"
            echo "  2. Generar guión con LLM"
            echo "  3. Generar audio con XTTS"
            echo "  4. Obtener background de Pexels"
            echo "  5. Renderizar video final"
            echo ""
            echo -e "${YELLOW}⚠ El proceso puede tardar varios minutos${NC}"
            echo ""
            read -p "¿Continuar? (s/n): " confirm
            
            if [[ "$confirm" =~ ^[Ss]$ ]]; then
                python -m src.pipeline --full
            fi
            ;;
        2)
            echo ""
            read -p "¿Cuántos videos generar? (1-50): " count
            
            if [[ "$count" =~ ^[0-9]+$ ]] && [ "$count" -ge 1 ] && [ "$count" -le 50 ]; then
                echo ""
                echo -e "${YELLOW}Generando ${count} videos...${NC}"
                echo -e "${YELLOW}⚠ Esto puede tardar MUCHO tiempo${NC}"
                echo ""
                read -p "¿Continuar? (s/n): " confirm
                
                if [[ "$confirm" =~ ^[Ss]$ ]]; then
                    python -m src.pipeline --count "$count"
                fi
            else
                echo -e "${RED}Número inválido${NC}"
            fi
            ;;
        3)
            echo ""
            echo -e "${YELLOW}⚠ MODO BATCH: Procesará TODO el cache pendiente${NC}"
            echo -e "${YELLOW}⚠ Esto puede tardar MUCHAS HORAS${NC}"
            echo ""
            read -p "¿Estás seguro? (s/n): " confirm
            
            if [[ "$confirm" =~ ^[Ss]$ ]]; then
                python -m src.pipeline --batch
            fi
            ;;
        0) return ;;
        *) echo -e "${RED}Opción inválida${NC}" ;;
    esac
    
    read -p "Presiona Enter para continuar..."
}

# Menú de configuración
menu_config() {
    show_banner
    echo -e "${CYAN}⚙️  CONFIGURACIÓN${NC}"
    echo ""
    echo -e "  ${WHITE}1.${NC} Editar fuentes (sources.yaml)"
    echo -e "  ${WHITE}2.${NC} Editar prompts (prompts.yaml)"
    echo -e "  ${WHITE}3.${NC} Editar variables de entorno (.env)"
    echo -e "  ${WHITE}4.${NC} Verificar dependencias"
    echo -e "  ${WHITE}5.${NC} Reinstalar dependencias Python"
    echo -e "  ${WHITE}6.${NC} Ver estado del sistema"
    echo -e "  ${WHITE}0.${NC} Volver al menú principal"
    echo ""
    read -p "Selecciona una opción: " choice
    
    case $choice in
        1) ${EDITOR:-nano} config/sources.yaml ;;
        2) ${EDITOR:-nano} config/prompts.yaml ;;
        3) ${EDITOR:-nano} .env ;;
        4) check_dependencies ;;
        5) 
            echo -e "${CYAN}Reinstalando dependencias...${NC}"
            uv sync --reinstall
            echo -e "${GREEN}✓ Dependencias reinstaladas${NC}"
            ;;
        6)
            echo ""
            echo -e "${CYAN}Estado del sistema:${NC}"
            echo "  Python: $(python --version 2>&1)"
            echo "  uv: $(uv --version 2>&1)"
            echo "  FFmpeg: $(ffmpeg -version 2>&1 | head -1)"
            echo "  Espacio en disco:"
            df -h . | tail -1
            echo ""
            echo -e "${CYAN}Contenido en directorios:${NC}"
            echo "  cache/: $(ls cache/ 2>/dev/null | wc -l) archivos"
            echo "  temp/: $(ls temp/ 2>/dev/null | wc -l) archivos"
            echo "  output/: $(ls output/ 2>/dev/null | wc -l) archivos"
            ;;
        0) return ;;
        *) echo -e "${RED}Opción inválida${NC}" ;;
    esac
    
    read -p "Presiona Enter para continuar..."
}

# Limpiar archivos temporales
clean_temp() {
    show_banner
    echo -e "${CYAN}🧹 LIMPIAR ARCHIVOS TEMPORALES${NC}"
    echo ""
    echo -e "  ${WHITE}1.${NC} Limpiar solo temp/"
    echo -e "  ${WHITE}2.${NC} Limpiar cache/"
    echo -e "  ${WHITE}3.${NC} Limpiar temp/ y cache/"
    echo -e "  ${RED}4.${NC} Limpiar TODO (incluye output/)"
    echo -e "  ${WHITE}0.${NC} Volver al menú principal"
    echo ""
    read -p "Selecciona una opción: " choice
    
    case $choice in
        1) 
            rm -rf temp/*
            echo -e "${GREEN}✓ Directorio temp/ limpiado${NC}"
            ;;
        2)
            rm -rf cache/*
            echo -e "${GREEN}✓ Directorio cache/ limpiado${NC}"
            ;;
        3)
            rm -rf temp/* cache/*
            echo -e "${GREEN}✓ Directorios temp/ y cache/ limpiados${NC}"
            ;;
        4)
            read -p "¿Estás seguro? Esto borrará todos los videos (s/n): " confirm
            if [[ "$confirm" =~ ^[Ss]$ ]]; then
                rm -rf temp/* cache/* output/*
                echo -e "${GREEN}✓ Todos los directorios limpiados${NC}"
            fi
            ;;
        0) return ;;
        *) echo -e "${RED}Opción inválida${NC}" ;;
    esac
    
    read -p "Presiona Enter para continuar..."
}

# Menú principal
main_menu() {
    while true; do
        show_banner
        check_venv
        
        echo -e "${WHITE}MENÚ PRINCIPAL${NC}"
        echo ""
        echo -e "  ${CYAN}1.${NC} 📥 Obtener contenido (RSS/Reddit/YouTube)"
        echo -e "  ${CYAN}2.${NC} ✍️  Generar guión con LLM"
        echo -e "  ${CYAN}3.${NC} 🔊 Generar audio (XTTS)"
        echo -e "  ${CYAN}4.${NC} 🎬 Renderizar video (FFmpeg)"
        echo -e "  ${GREEN}5.${NC} 🚀 Pipeline completo (automático)"
        echo -e "  ${WHITE}6.${NC} 📂 Ver videos generados"
        echo -e "  ${WHITE}7.${NC} ⚙️  Configuración"
        echo -e "  ${WHITE}8.${NC} 🧹 Limpiar archivos temporales"
        echo -e "  ${RED}0.${NC} ❌ Salir"
        echo ""
        read -p "Selecciona una opción: " choice
        
        case $choice in
            1) menu_scraping ;;
            2) menu_script ;;
            3) menu_audio ;;
            4) menu_video ;;
            5) run_pipeline ;;
            6) 
                echo ""
                echo -e "${CYAN}Videos generados:${NC}"
                ls -lah output/*.mp4 2>/dev/null || echo "No hay videos generados"
                read -p "Presiona Enter para continuar..."
                ;;
            7) menu_config ;;
            8) clean_temp ;;
            0) 
                echo -e "${GREEN}¡Hasta luego!${NC}"
                exit 0
                ;;
            *) 
                echo -e "${RED}Opción inválida${NC}"
                sleep 1
                ;;
        esac
    done
}

# Punto de entrada
main() {
    # Verificar dependencias del sistema
    check_dependencies || exit 1
    
    # Mostrar menú principal
    main_menu
}

main "$@"
