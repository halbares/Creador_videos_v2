"""
Generador de subtítulos en formato ASS.
Optimizado para videos cortos con alta retención.
"""

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class SubtitleGenerator:
    """Genera archivos de subtítulos ASS optimizados para Shorts/Reels."""
    
    # Estilo por defecto para MÁXIMA legibilidad en móvil
    # Fuente grande, outline grueso, posición centrada
    DEFAULT_STYLE = {
        "name": "Default",
        "fontname": "Arial Black",
        "fontsize": 85,  # Grande para móvil
        "primary_color": "&H00FFFFFF",  # Blanco puro
        "secondary_color": "&H00FFFFFF",
        "outline_color": "&H00000000",  # Negro
        "back_color": "&H80000000",  # Negro semi-transparente
        "bold": -1,  # Bold activo
        "italic": 0,
        "underline": 0,
        "strikeout": 0,
        "scale_x": 100,
        "scale_y": 100,
        "spacing": 1,  # Un poco de espaciado
        "angle": 0,
        "border_style": 1,  # Outline + shadow
        "outline": 4,  # Outline grueso
        "shadow": 3,  # Sombra para profundidad
        "alignment": 2,  # Centrado abajo
        "margin_l": 40,
        "margin_r": 40,
        "margin_v": 180,  # Margen vertical para zona segura
        "encoding": 1,
    }
    
    # Estilo para HOOK (primer subtítulo) - Máximo impacto
    HIGHLIGHT_STYLE = {
        **DEFAULT_STYLE,
        "name": "Highlight",
        "fontsize": 95,  # Aún más grande
        "primary_color": "&H0000FFFF",  # Amarillo vibrante
        "outline_color": "&H00000000",  # Negro
        "outline": 5,
        "shadow": 4,
    }
    
    # Estilo para palabras clave/énfasis
    EMPHASIS_STYLE = {
        **DEFAULT_STYLE,
        "name": "Emphasis",
        "fontsize": 90,
        "primary_color": "&H0080FF00",  # Verde vibrante
        "outline": 5,
    }
    
    def __init__(self, output_dir: str = "./temp"):
        """
        Inicializa el generador de subtítulos.
        
        Args:
            output_dir: Directorio para archivos de salida
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def _format_time(self, seconds: float) -> str:
        """
        Formatea segundos a formato ASS (H:MM:SS.cc).
        
        Args:
            seconds: Tiempo en segundos
            
        Returns:
            Tiempo formateado
        """
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        centisecs = int((seconds % 1) * 100)
        
        return f"{hours}:{minutes:02d}:{secs:02d}.{centisecs:02d}"
    
    def _style_to_line(self, style: dict) -> str:
        """Convierte un dict de estilo a línea ASS."""
        return (
            f"Style: {style['name']},"
            f"{style['fontname']},"
            f"{style['fontsize']},"
            f"{style['primary_color']},"
            f"{style['secondary_color']},"
            f"{style['outline_color']},"
            f"{style['back_color']},"
            f"{style['bold']},"
            f"{style['italic']},"
            f"{style['underline']},"
            f"{style['strikeout']},"
            f"{style['scale_x']},"
            f"{style['scale_y']},"
            f"{style['spacing']},"
            f"{style['angle']},"
            f"{style['border_style']},"
            f"{style['outline']},"
            f"{style['shadow']},"
            f"{style['alignment']},"
            f"{style['margin_l']},"
            f"{style['margin_r']},"
            f"{style['margin_v']},"
            f"{style['encoding']}"
        )
    
    def _create_header(
        self,
        title: str = "Subtitles",
        width: int = 1080,
        height: int = 1920,
        styles: Optional[list[dict]] = None
    ) -> str:
        """
        Crea el header del archivo ASS.
        
        Args:
            title: Título del script
            width: Ancho del video
            height: Alto del video
            styles: Lista de estilos personalizados
            
        Returns:
            Header ASS formateado
        """
        if styles is None:
            styles = [self.DEFAULT_STYLE, self.HIGHLIGHT_STYLE, self.EMPHASIS_STYLE]
        
        style_lines = "\n".join(self._style_to_line(s) for s in styles)
        
        header = f"""[Script Info]
Title: {title}
ScriptType: v4.00+
WrapStyle: 0
ScaledBorderAndShadow: yes
YCbCr Matrix: TV.709
PlayResX: {width}
PlayResY: {height}

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
{style_lines}

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
        return header
    
    def _format_text_for_ass(self, text: str) -> str:
        """
        Formatea texto para ASS (escapa caracteres especiales).
        
        Args:
            text: Texto original
            
        Returns:
            Texto formateado para ASS
        """
        # Reemplazar saltos de línea
        text = text.replace("\n", "\\N")
        
        # Escapar llaves (usadas para tags)
        # Solo si no son parte de tags ASS válidos
        
        return text
    
    def generate_from_subtitles(
        self,
        subtitles: list[dict],
        output_filename: str,
        title: str = "Video Script",
        highlight_first: bool = True
    ) -> Optional[str]:
        """
        Genera archivo ASS desde lista de subtítulos.
        
        Args:
            subtitles: Lista de dicts con start, end, text
            output_filename: Nombre del archivo de salida (sin extensión)
            title: Título del script
            highlight_first: Si resaltar el primer subtítulo (hook)
            
        Returns:
            Ruta al archivo generado o None
        """
        if not subtitles:
            logger.error("No hay subtítulos para generar")
            return None
        
        output_path = self.output_dir / f"{output_filename}.ass"
        
        # Crear header
        content = self._create_header(title=title)
        
        # Agregar eventos (subtítulos)
        for i, sub in enumerate(subtitles):
            start = self._format_time(sub["start"])
            end = self._format_time(sub["end"])
            text = self._format_text_for_ass(sub["text"])
            
            # Usar estilo destacado para el primer subtítulo (hook)
            style = "Highlight" if (i == 0 and highlight_first) else "Default"
            
            # Formato: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
            line = f"Dialogue: 0,{start},{end},{style},,0,0,0,,{text}"
            content += line + "\n"
        
        # Escribir archivo
        try:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(content)
            
            logger.info(f"Subtítulos generados: {output_path}")
            return str(output_path)
            
        except Exception as e:
            logger.error(f"Error escribiendo subtítulos: {e}")
            return None
    
    def generate_animated(
        self,
        subtitles: list[dict],
        output_filename: str,
        animation: str = "fade"
    ) -> Optional[str]:
        """
        Genera subtítulos con animaciones para mayor retención.
        
        Args:
            subtitles: Lista de subtítulos
            output_filename: Nombre del archivo
            animation: Tipo de animación (fade, pop, slide)
            
        Returns:
            Ruta al archivo generado
        """
        if not subtitles:
            return None
        
        output_path = self.output_dir / f"{output_filename}.ass"
        content = self._create_header(title=f"{output_filename} - Animated")
        
        for i, sub in enumerate(subtitles):
            start = sub["start"]
            end = sub["end"]
            text = self._format_text_for_ass(sub["text"])
            duration_ms = int((end - start) * 1000)
            
            # Estilo base
            style = "Highlight" if i == 0 else "Default"
            
            # Agregar efectos de animación
            if animation == "fade":
                # Fade in al inicio, fade out al final
                effect = f"{{\\fad(200,150)}}"
            elif animation == "pop":
                # Efecto pop (escala)
                effect = f"{{\\t(0,100,\\fscx110\\fscy110)\\t(100,200,\\fscx100\\fscy100)}}"
            elif animation == "slide":
                # Slide desde abajo
                effect = f"{{\\move(540,1800,540,1720,0,150)}}"
            else:
                effect = ""
            
            start_fmt = self._format_time(start)
            end_fmt = self._format_time(end)
            
            line = f"Dialogue: 0,{start_fmt},{end_fmt},{style},,0,0,0,,{effect}{text}"
            content += line + "\n"
        
        try:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(content)
            
            logger.info(f"Subtítulos animados generados: {output_path}")
            return str(output_path)
            
        except Exception as e:
            logger.error(f"Error: {e}")
            return None
    
    def generate_word_by_word(
        self,
        narration: str,
        total_duration: float,
        output_filename: str
    ) -> Optional[str]:
        """
        Genera subtítulos palabra por palabra para máxima retención.
        
        Args:
            narration: Texto de narración
            total_duration: Duración total en segundos
            output_filename: Nombre del archivo
            
        Returns:
            Ruta al archivo generado
        """
        words = narration.split()
        if not words:
            return None
        
        # Calcular duración por palabra
        word_duration = total_duration / len(words)
        
        subtitles = []
        current_time = 0
        
        # Agrupar en frases de 3-4 palabras
        chunk_size = 3
        for i in range(0, len(words), chunk_size):
            chunk = " ".join(words[i:i + chunk_size])
            chunk_duration = word_duration * min(chunk_size, len(words) - i)
            
            subtitles.append({
                "start": current_time,
                "end": current_time + chunk_duration,
                "text": chunk
            })
            
            current_time += chunk_duration
        
        return self.generate_animated(subtitles, output_filename, animation="fade")


def main():
    """Función principal para testing."""
    import argparse
    from rich.console import Console
    
    parser = argparse.ArgumentParser(description="Subtitle Generator")
    parser.add_argument("--test", action="store_true", help="Generar subtítulos de prueba")
    args = parser.parse_args()
    
    console = Console()
    generator = SubtitleGenerator()
    
    # Subtítulos de prueba
    test_subtitles = [
        {"start": 0.0, "end": 3.0, "text": "¿Sabías este secreto sobre el sueño?"},
        {"start": 3.0, "end": 6.0, "text": "Hoy te lo cuento todo."},
        {"start": 6.0, "end": 12.0, "text": "Dormir bien mejora tu concentración un 40%."},
        {"start": 12.0, "end": 18.0, "text": "Y reduce el estrés significativamente."},
        {"start": 18.0, "end": 24.0, "text": "El secreto está en la consistencia."},
        {"start": 24.0, "end": 30.0, "text": "Duerme a la misma hora cada día."},
    ]
    
    console.print("[cyan]Generando subtítulos de prueba...[/cyan]")
    
    # Versión normal
    path1 = generator.generate_from_subtitles(test_subtitles, "test_subtitles")
    if path1:
        console.print(f"[green]✓ Normal: {path1}[/green]")
    
    # Versión animada
    path2 = generator.generate_animated(test_subtitles, "test_subtitles_animated", "fade")
    if path2:
        console.print(f"[green]✓ Animado: {path2}[/green]")


if __name__ == "__main__":
    main()
