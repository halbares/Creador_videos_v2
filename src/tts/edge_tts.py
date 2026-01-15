"""
Motor Edge-TTS para generación de voz.
Usa voces neurales de Microsoft Edge - rápido, estable, gratuito.
"""

import asyncio
import logging
import os
import re
import time
from pathlib import Path
from typing import Optional

from pydub import AudioSegment
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, TimeElapsedColumn
from rich.panel import Panel

logger = logging.getLogger(__name__)
console = Console()

# Voces disponibles para español
SPANISH_VOICES = {
    # Colombia
    "es-CO-GonzaloNeural": "Gonzalo (Colombia, masculino)",
    "es-CO-SalomeNeural": "Salomé (Colombia, femenino)",
    # Chile  
    "es-CL-LorenzoNeural": "Lorenzo (Chile, masculino)",
    "es-CL-CatalinaNeural": "Catalina (Chile, femenino)",
    # México
    "es-MX-JorgeNeural": "Jorge (México, masculino)",
    "es-MX-DaliaNeural": "Dalia (México, femenino)",
    # España
    "es-ES-AlvaroNeural": "Álvaro (España, masculino)",
    "es-ES-ElviraNeural": "Elvira (España, femenino)",
    # Argentina
    "es-AR-TomasNeural": "Tomás (Argentina, masculino)",
    "es-AR-ElenaNeural": "Elena (Argentina, femenino)",
}

# Voz por defecto: Gonzalo de Colombia (masculino, natural)
DEFAULT_VOICE = "es-CO-GonzaloNeural"


def clean_text_for_tts(text: str) -> str:
    """
    Limpia texto para síntesis TTS, removiendo elementos problemáticos.
    """
    # Remover URLs
    text = re.sub(r'https?://\S+', '', text)
    text = re.sub(r'www\.\S+', '', text)
    
    # Remover menciones y hashtags
    text = re.sub(r'[@#]\w+', '', text)
    
    # Remover emojis
    emoji_pattern = re.compile("["
        u"\U0001F600-\U0001F64F"
        u"\U0001F300-\U0001F5FF"
        u"\U0001F680-\U0001F6FF"
        u"\U0001F1E0-\U0001F1FF"
        u"\U00002702-\U000027B0"
        u"\U000024C2-\U0001F251"
        "]+", flags=re.UNICODE)
    text = emoji_pattern.sub('', text)
    
    # Remover caracteres especiales
    text = re.sub(r'[*_~`|<>{}[\]\\]', '', text)
    
    # Remover números de lista
    text = re.sub(r'^\d+\.\s*', '', text, flags=re.MULTILINE)
    text = re.sub(r'^[-•]\s*', '', text, flags=re.MULTILINE)
    
    # Normalizar espacios y puntuación
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'[.]{2,}', '.', text)
    text = re.sub(r'[!]{2,}', '!', text)
    text = re.sub(r'[?]{2,}', '?', text)
    
    return text.strip()


class EdgeTTSEngine:
    """Motor de Text-to-Speech usando Edge-TTS (Microsoft Neural Voices)."""
    
    def __init__(
        self,
        output_dir: str = "./temp",
        voice: str = DEFAULT_VOICE,
        rate: str = "+0%",
        pitch: str = "+0Hz"
    ):
        """
        Inicializa el motor Edge-TTS.
        
        Args:
            output_dir: Directorio para archivos de audio
            voice: Voz a usar (ej: es-CO-GonzaloNeural)
            rate: Velocidad del habla (ej: "+10%", "-5%")
            pitch: Tono de voz (ej: "+5Hz", "-10Hz")
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.voice = voice
        self.rate = rate
        self.pitch = pitch
    
    def _split_into_sentences(self, text: str) -> list[str]:
        """
        Divide el texto en oraciones para mejor control de timing.
        """
        # Dividir por puntuación final
        sentences = re.split(r'(?<=[.!?])\s+', text)
        
        # Filtrar vacías y muy cortas
        sentences = [s.strip() for s in sentences if s.strip() and len(s.strip()) > 2]
        
        return sentences
    
    async def _synthesize_async(self, text: str, output_path: str) -> bool:
        """
        Sintetiza texto a audio de forma asíncrona.
        """
        try:
            import edge_tts
            
            communicate = edge_tts.Communicate(
                text=text,
                voice=self.voice,
                rate=self.rate,
                pitch=self.pitch
            )
            
            await communicate.save(output_path)
            return os.path.exists(output_path)
            
        except Exception as e:
            logger.error(f"Error en Edge-TTS: {e}")
            return False
    
    def synthesize(
        self,
        text: str,
        output_filename: Optional[str] = None,
        show_progress: bool = True
    ) -> Optional[str]:
        """
        Sintetiza texto completo a audio.
        
        Args:
            text: Texto a sintetizar
            output_filename: Nombre del archivo de salida
            show_progress: Si mostrar progreso
            
        Returns:
            Ruta al archivo de audio o None
        """
        # Limpiar texto
        text = clean_text_for_tts(text)
        
        if not text.strip():
            logger.error("Texto vacío después de limpieza")
            return None
        
        # Generar nombre de archivo
        if not output_filename:
            import hashlib
            hash_id = hashlib.sha256(text.encode()).hexdigest()[:8]
            output_filename = f"audio_{hash_id}"
        
        output_path = self.output_dir / f"{output_filename}.mp3"
        
        if show_progress:
            console.print(Panel(
                f"[bold cyan]SÍNTESIS DE VOZ[/bold cyan]\n"
                f"Motor: Edge-TTS (Microsoft Neural)\n"
                f"Voz: {SPANISH_VOICES.get(self.voice, self.voice)}\n"
                f"Texto: {len(text)} caracteres",
                title="Edge-TTS"
            ))
        
        start_time = time.time()
        
        # Ejecutar síntesis
        success = asyncio.run(self._synthesize_async(text, str(output_path)))
        
        if success:
            elapsed = time.time() - start_time
            if show_progress:
                console.print(f"[green]✓ Audio generado en {elapsed:.1f}s[/green]")
            return str(output_path)
        
        return None
    
    def synthesize_with_timing(
        self,
        narration: str,
        subtitles: list[dict],
        output_filename: str
    ) -> Optional[dict]:
        """
        Sintetiza audio y genera subtítulos sincronizados.
        
        Genera el audio completo y luego calcula tiempos de subtítulos
        basándose en la longitud de cada oración.
        """
        # Limpiar texto
        narration = clean_text_for_tts(narration)
        
        if not narration.strip():
            logger.error("Narración vacía después de limpieza")
            return None
        
        output_path = self.output_dir / f"{output_filename}.mp3"
        
        # Dividir en oraciones para subtítulos
        sentences = self._split_into_sentences(narration)
        
        console.print(Panel(
            f"[bold cyan]SÍNTESIS DE VOZ SINCRONIZADA[/bold cyan]\n"
            f"Motor: Edge-TTS (Microsoft Neural)\n"
            f"Voz: {SPANISH_VOICES.get(self.voice, self.voice)}\n"
            f"Texto: {len(narration)} caracteres\n"
            f"Oraciones: {len(sentences)}",
            title="Edge-TTS"
        ))
        
        start_time = time.time()
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("[cyan]Generando audio...", total=None)
            
            # Generar audio completo (Edge-TTS es muy rápido)
            success = asyncio.run(self._synthesize_async(narration, str(output_path)))
            
            if not success:
                progress.update(task, description="[red]✗ Error generando audio[/red]")
                return None
            
            progress.update(task, description="[green]✓ Audio generado[/green]")
        
        # Obtener duración total del audio
        try:
            audio = AudioSegment.from_mp3(str(output_path))
            total_duration = len(audio) / 1000.0
        except Exception as e:
            logger.error(f"Error leyendo duración: {e}")
            total_duration = 60.0
        
        elapsed = time.time() - start_time
        
        # Calcular tiempos de subtítulos basándose en longitud de texto
        # Esto da una aproximación bastante precisa para Edge-TTS
        total_chars = sum(len(s) for s in sentences)
        
        synced_subtitles = []
        current_time = 0.0
        
        for sentence in sentences:
            # Duración proporcional al número de caracteres
            sentence_duration = (len(sentence) / total_chars) * total_duration
            
            synced_subtitles.append({
                "start": round(current_time, 2),
                "end": round(current_time + sentence_duration, 2),
                "text": sentence
            })
            
            current_time += sentence_duration
        
        console.print(Panel(
            f"[bold green]✓ AUDIO GENERADO[/bold green]\n"
            f"Archivo: {output_path.name}\n"
            f"Duración: {total_duration:.1f}s\n"
            f"Tiempo de proceso: {elapsed:.1f}s\n"
            f"Subtítulos: {len(synced_subtitles)} sincronizados",
            title="Completado",
            style="green"
        ))
        
        return {
            "audio_path": str(output_path),
            "duration": total_duration,
            "subtitles": synced_subtitles
        }
    
    def set_voice(self, voice: str) -> bool:
        """Cambia la voz a usar."""
        if voice in SPANISH_VOICES:
            self.voice = voice
            logger.info(f"Voz cambiada a: {SPANISH_VOICES[voice]}")
            return True
        else:
            logger.warning(f"Voz no reconocida: {voice}")
            return False
    
    def set_rate(self, rate: str):
        """Cambia la velocidad del habla (ej: '+10%', '-5%')."""
        self.rate = rate
    
    def set_pitch(self, pitch: str):
        """Cambia el tono de voz (ej: '+5Hz', '-10Hz')."""
        self.pitch = pitch
    
    @staticmethod
    def list_voices() -> dict:
        """Retorna las voces disponibles en español."""
        return SPANISH_VOICES


def main():
    """Función principal para testing."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Edge-TTS Engine")
    parser.add_argument("--test", action="store_true", help="Ejecutar test básico")
    parser.add_argument("--text", type=str, help="Texto a sintetizar")
    parser.add_argument("--voice", type=str, default=DEFAULT_VOICE, help="Voz a usar")
    parser.add_argument("--list-voices", action="store_true", help="Listar voces disponibles")
    args = parser.parse_args()
    
    if args.list_voices:
        console.print("[cyan]Voces disponibles en español:[/cyan]\n")
        for voice_id, description in SPANISH_VOICES.items():
            console.print(f"  {voice_id}: {description}")
        return
    
    if args.text:
        engine = EdgeTTSEngine(voice=args.voice)
        audio_path = engine.synthesize(args.text, "test_edge")
        
        if audio_path:
            console.print(f"[green]✓ Audio: {audio_path}[/green]")
        return
    
    # Test básico
    console.print("[cyan]Test de Edge-TTS...[/cyan]")
    
    test_text = "Hola, esto es una prueba del sistema Edge TTS. La calidad debe ser natural y fluida."
    
    engine = EdgeTTSEngine()
    audio_path = engine.synthesize(test_text, "test_edge_output")
    
    if audio_path:
        console.print(f"[green]✓ Test exitoso: {audio_path}[/green]")
    else:
        console.print("[red]✗ Test fallido[/red]")


if __name__ == "__main__":
    main()
