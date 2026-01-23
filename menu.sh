#!/usr/bin/env bash
#===============================================================================
#  CREADOR DE VIDEOS - LAUNCHER UNIFICADO
#  Selecciona entre la versión V3 (NextGen) y V2 (Legacy)
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

show_banner() {
    clear
    echo -e "${PURPLE}"
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║                                                              ║"
    echo "║   🚀  CREADOR DE VIDEOS - NEXT GEN LAUNCHER                  ║"
    echo "║   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━              ║"
    echo "║                                                              ║"
    echo "║   Selecciona tu motor de generación:                         ║"
    echo "║                                                              ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

main_menu() {
    while true; do
        show_banner
        
        echo -e "${WHITE}VERSIONES DISPONIBLES:${NC}"
        echo ""
        echo -e "  ${GREEN}1.${NC} 🤖 [V3] NEXT GEN ENGINE (Beta)"
        echo -e "     ${CYAN}↳ Sincronización Whisper + Escenas Dinámicas + Batch Download${NC}"
        echo -e "     ${CYAN}↳ (Recomendado probar con: uv run src/main.py)${NC}"
        echo ""
        echo -e "  ${YELLOW}2.${NC} 🏛️  [V2] LEGACY SUITE"
        echo -e "     ${CYAN}↳ El menú clásico con opciones 5 y 6 (Estable)${NC}"
        echo -e "     ${CYAN}↳ (Ejecuta el menú antiguo desde /legacy)${NC}"
        echo ""
        echo -e "  ${RED}0.${NC} ❌ Salir"
        echo ""
        read -p "Selecciona una opción: " choice
        
        case $choice in
            1)
                echo ""
                echo -e "${GREEN}Iniciando Motor V3 (Demo)...${NC}"
                uv run src/main.py
                read -p "Presiona Enter para continuar..."
                ;;
            2)
                echo ""
                echo -e "${YELLOW}Cambiando a entorno Legacy...${NC}"
                cd legacy
                if [ -f "menu.sh" ]; then
                    ./menu.sh
                else
                    echo -e "${RED}Error: No se encuentra legacy/menu.sh${NC}"
                    read -p "Presiona Enter..."
                fi
                # Regresar al root al salir del legacy
                cd ..
                ;;
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

# Verificar dependencias básicas
if ! command -v uv &> /dev/null; then
    echo -e "${YELLOW}⚠ 'uv' no encontrado. Intentando instalar...${NC}"
    curl -LsSf https://astral.sh/uv/install.sh | sh
    source $HOME/.cargo/env 2>/dev/null || true
fi

# Iniciar
main_menu
