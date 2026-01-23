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
        animation: str = "float",
        mood_color: str = "#ffffff"
    ) -> tuple[list[str], str]:
        """
        Genera el filtro FFmpeg para overlay de múltiples stickers.
        
        Args:
            stickers: Lista de dicts con path, start, end
            animation: Tipo ("float", "neon_contour")
            mood_color: Color hex para el efecto neon
            
        Returns:
            Tuple de (lista de inputs adicionales, string del filter_complex)
        """
        if not stickers:
            return [], ""
        
        # Mapa de colores para Neon
        # Convertir hex simple a expresión de FFmpeg
        # Esto es complejo en FFmpeg puro sin filtros complejos
        # Usaremos "colorize" o "colorchannelmixer" para teñir el blanco
        
        inputs = []
        filter_parts = []
        
        last_stream = "[0:v]"
        
        for i, sticker in enumerate(stickers):
            path = sticker.get("path", "")
            start = sticker.get("start", 0)
            end = sticker.get("end", 5)
            
            if not path or not Path(path).exists():
                continue
            
            inputs.extend(["-i", path])
            sticker_idx = i + 1
            
            if animation == "neon_contour":
                # Cadena de filtros para Neon Zen
                # 1. Escalar
                # 2. Edgedetect (detecta bordes, fondo negro)
                # 3. Colorkey (quita el negro)
                # 4. Colorize (tiñe) - Simplificado: Usamos split y tint
                
                # Nota: edgedetect funciona sobre RGB.
                # Si el input tiene alpha, lo perdemos parcialmente o debemos usarlo.
                # Asumimos que stickers de Pexels/rembg tienen alpha transparente.
                
                # Paso 1: Escalar y preparar (nombres únicos con índice i)
                s_prep = f"[{sticker_idx}:v]scale={self.STICKER_WIDTH}:-1,format=rgba,split[s_rgb{i}][s_alpha{i}];"
                filter_parts.append(s_prep)
                
                # Paso 2: Edgedetect sobre RGB (fondo transparente se ve negro en edgedetect usualmente)
                # Usamos background negro explícito para mejorar detección
                s_edge = (
                    f"[s_rgb{i}]drawbox=t=fill:c=black@1[s_blackbg{i}];"  
                    f"[s_blackbg{i}][s_rgb{i}]overlay[s_flat{i}];"
                    f"[s_flat{i}]edgedetect=low=0.1:high=0.4,colorkey=black:0.1:0.1[s_edges{i}];"
                )
                filter_parts.append(s_edge)

                # Nombre del stream final del sticker
                sticker_out = f"sticker_processed{i}"
                
                # Paso 3: Combinar edges y usarlo
                # El resultado de edgedetect son lineas blancas sobre transparente (por colorkey)
                # Eso es perfecto. White Neon.
                # Si quisieramos color, podriamos usar colorchannelmixer, pero White es elegante.
                filter_parts.append(f"[s_edges{i}]null[{sticker_out}];")

            else:
                # Estilo clásico (Float)
                filter_parts.append(f"[{sticker_idx}:v]scale={self.STICKER_WIDTH}:-1,format=rgba[sticker_processed{i}];")
                sticker_out = f"sticker_processed{i}"
            
            # Generar expresión de posición y movimiento
            x_pos, y_pos = self._get_animated_position(animation)
            
            # Overlay final
            overlay_filter = (
                f"{last_stream}[{sticker_out}]overlay="
                f"x='{x_pos}':"
                f"y='{y_pos}':"
                f"enable='between(t,{start},{end})'[v{i}];"
            )
            filter_parts.append(overlay_filter)
            last_stream = f"[v{i}]"
        
        if filter_parts:
            filter_parts[-1] = filter_parts[-1].rstrip(";")
            filter_parts[-1] = filter_parts[-1].replace(f"[v{len(stickers)-1}]", "[stickered]")
        
        filter_string = "".join(filter_parts)
        return inputs, filter_string
    
    def _get_animated_position(self, animation: str) -> tuple[str, str]:
        """
        Genera expresiones FFmpeg para posición animada.
        """
        # Centro
        x_center = f"(W-w)/2"
        y_center = f"(H-h)/2" # Centrado puro para focus
        
        if animation == "float":
            # Movimiento relajado original
            y_expr = f"{self.STICKER_Y_CENTER}+20*sin(t*3.14)"
            return x_center, y_expr
        
        elif animation == "neon_contour":
            # Movimiento "Psychological Float" (Respiración en 2 ejes)
            # X: Oscilación lenta (periodo 6s)
            # Y: Oscilación más lenta (periodo 8s)
            # + Zoom sutil simulado con escala si fuera posible, pero aqui es pos
            
            x_expr = f"{x_center}+15*sin(t*1.0)"
            y_expr = f"{self.STICKER_Y_CENTER}+20*cos(t*0.8)" 
            # Nota: Usamos STICKER_Y_CENTER para mantener consistencia con subtitulos,
            # pero el usuario pidio 'centrado'. El centro real es H/2 = 960 (en 1080x1920)
            # STICKER_Y_CENTER es 750.
            # Para 'neon_contour' usaremos 850, un poco mas abajo, mas centrado.
            y_expr = f"850+20*cos(t*0.8)" 
            
            return x_expr, y_expr
    
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
