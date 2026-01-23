"""
Generador de filtros FFmpeg para overlay de stickers animados.
"""

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class StickerOverlay:
    """Genera comandos FFmpeg para overlay de stickers con animación."""
    
    # Tamaño del sticker (ancho, altura se escala proporcionalmente)
    STICKER_WIDTH = 700  # 15% más grande
    
    # Posición vertical del sticker (centrado un poco arriba para no tapar subtítulos)
    # En un video 1920px de alto, el centro es 960. Subtítulos ocupan ~200px abajo.
    # Posición Y del centro del sticker: ~700-800px desde arriba
    STICKER_Y_CENTER = 750
    
    def __init__(self, video_width: int = 1080, video_height: int = 1920):
        self.width = video_width
        self.height = video_height
    
    def generate_overlay_filter(
        self,
        stickers: list[dict],
        animation: str = "float"
    ) -> tuple[list[str], str]:
        """
        Genera el filtro FFmpeg para overlay de múltiples stickers.
        
        Args:
            stickers: Lista de dicts con path, start, end
            animation: Tipo de animación (float, zoom_pulse, static)
            
        Returns:
            Tuple de (lista de inputs adicionales, string del filter_complex)
        """
        if not stickers:
            return [], ""
        
        inputs = []
        filter_parts = []
        
        # El video base es input 0
        # Cada sticker es input 1, 2, 3...
        last_stream = "[0:v]"
        
        for i, sticker in enumerate(stickers):
            path = sticker.get("path", "")
            start = sticker.get("start", 0)
            end = sticker.get("end", 5)
            
            if not path or not Path(path).exists():
                continue
            
            inputs.extend(["-i", path])
            sticker_idx = i + 1  # +1 porque video base es 0
            
            # Escalar sticker
            scale_filter = f"[{sticker_idx}:v]scale={self.STICKER_WIDTH}:-1,format=rgba[sticker{i}];"
            filter_parts.append(scale_filter)
            
            # Generar expresión de posición con animación
            x_pos, y_pos = self._get_animated_position(animation)
            
            # Overlay con enable para timing
            overlay_filter = (
                f"{last_stream}[sticker{i}]overlay="
                f"x='{x_pos}':"
                f"y='{y_pos}':"
                f"enable='between(t,{start},{end})'[v{i}];"
            )
            filter_parts.append(overlay_filter)
            last_stream = f"[v{i}]"
        
        # Remover último punto y coma
        if filter_parts:
            filter_parts[-1] = filter_parts[-1].rstrip(";")
        
        # El stream final necesita un nombre para mapeo
        if filter_parts:
            filter_parts[-1] = filter_parts[-1].replace(f"[v{len(stickers)-1}]", "[stickered]")
        
        filter_string = "".join(filter_parts)
        return inputs, filter_string
    
    def _get_animated_position(self, animation: str) -> tuple[str, str]:
        """
        Genera expresiones FFmpeg para posición animada.
        
        Args:
            animation: Tipo de animación
            
        Returns:
            Tuple de (x_expression, y_expression)
        """
        # Centro horizontal
        x_center = f"(W-w)/2"
        
        # Centro vertical (ajustado para no tapar subtítulos)
        y_center = str(self.STICKER_Y_CENTER)
        
        if animation == "float":
            # Movimiento vertical suave (seno)
            # Amplitud: 20 píxeles, frecuencia: 0.5 Hz
            y_expr = f"{y_center}+20*sin(t*3.14)"
            return x_center, y_expr
        
        elif animation == "zoom_pulse":
            # Para zoom necesitamos modificar scale, no posición
            # Por ahora usamos float como fallback
            y_expr = f"{y_center}+15*sin(t*2)"
            return x_center, y_expr
        
        elif animation == "gentle_rotate":
            # Rotación requiere filtro rotate separado
            # Por ahora usamos float
            y_expr = f"{y_center}+10*sin(t*2.5)"
            return x_center, y_expr
        
        else:  # static
            return x_center, y_center
    
    def build_complete_filter(
        self,
        stickers: list[dict],
        subtitles_path: str,
        animation: str = "float"
    ) -> tuple[list[str], str]:
        """
        Construye el filter_complex completo incluyendo stickers y subtítulos.
        
        Args:
            stickers: Lista de stickers con path, start, end
            subtitles_path: Ruta al archivo ASS
            animation: Tipo de animación
            
        Returns:
            Tuple de (inputs adicionales, filter_complex string)
        """
        inputs, sticker_filter = self.generate_overlay_filter(stickers, animation)
        
        # Si hay stickers, agregar subtítulos después
        if sticker_filter:
            # Reemplazar el output final del sticker filter
            sticker_filter = sticker_filter.replace(
                "[stickered]",
                "[stickered];"
            )
            # Agregar subtítulos
            sub_filter = (
                f"[stickered]subtitles={subtitles_path}:"
                f"force_style='Fontsize=98,PrimaryColour=&H00FFFFFF,"
                f"OutlineColour=&H00000000,BorderStyle=1,Outline=4,Shadow=2'[final]"
            )
            full_filter = sticker_filter + sub_filter
        else:
            # Solo subtítulos si no hay stickers
            full_filter = (
                f"[0:v]subtitles={subtitles_path}:"
                f"force_style='Fontsize=98,PrimaryColour=&H00FFFFFF,"
                f"OutlineColour=&H00000000,BorderStyle=1,Outline=4,Shadow=2'[final]"
            )
        
        return inputs, full_filter
