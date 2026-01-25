"""
Motor XTTS v2 para generación de voz.
Optimizado para español con chunking automático.
"""

import logging
import os

# Aceptar licencia de Coqui XTTS automáticamente
# Aceptar licencia de Coqui XTTS automáticamente
os.environ["COQUI_TOS_AGREED"] = "1"
os.environ["TORCHAUDIO_BACKEND"] = "soundfile"

import re
import time
from pathlib import Path
from typing import Optional

from pydub import AudioSegment
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn, TaskProgressColumn
from rich.panel import Panel

logger = logging.getLogger(__name__)
console = Console()

# Constantes
MAX_CHUNK_LENGTH = 250  # Caracteres máximos por chunk para XTTS
DEFAULT_SPEAKER_WAV = None  # Usar voz por defecto


# Regex de limpieza agresiva
def clean_text_for_tts(text: str) -> str:
    """
    Limpia texto para síntesis TTS, removiendo elementos problemáticos.
    """
    import re
    
    # 1. Eliminar instrucciones de guión entre paréntesis o corchetes
    # Ej: (Pausa dramática), [Risa], [Música de fondo]
    text = re.sub(r'\[.*?\]', '', text)
    text = re.sub(r'\(.*?\)', '', text)
    
    # 2. Eliminar líneas de metadata o dirección técnica
    # Ej: "Scene 1:", "Visual:", "Cut to:", "Camera:", "Narrator:"
    text = re.sub(r'(?mi)^(Scene|Visual|Cut to|Camera|Narrator|Angle|Shot).*?[:\n]', '', text)
    
    # 3. Eliminar URLs
    text = re.sub(r'https?://\S+', '', text)
    text = re.sub(r'www\.\S+', '', text)
    
    # 4. Eliminar menciones y hashtags
    text = re.sub(r'[@#]\w+', '', text)
    
    # 5. Eliminar emojis
    emoji_pattern = re.compile("["
        u"\U0001F600-\U0001F64F"
        u"\U0001F300-\U0001F5FF"
        u"\U0001F680-\U0001F6FF"
        u"\U0001F1E0-\U0001F1FF"
        u"\U00002702-\U000027B0"
        u"\U000024C2-\U0001F251"
        "]+", flags=re.UNICODE)
    text = emoji_pattern.sub('', text)
    
    # 6. Limpieza final de caracteres y espacios
    text = re.sub(r'[*_~`|<>{}[\]\\]', '', text)
    text = re.sub(r'^\d+\.\s*', '', text, flags=re.MULTILINE) # Listas numeradas
    text = re.sub(r'^[-•]\s*', '', text, flags=re.MULTILINE) # Viñetas
    text = re.sub(r'\s+', ' ', text) # Espacios múltiples
    
    # Puntuación
    text = re.sub(r'[.]{2,}', '.', text)
    text = re.sub(r'([.!?])([A-ZÁÉÍÓÚa-záéíóú])', r'\1 \2', text)
    
    return text.strip()


class XTTSEngine:
    """Motor de Text-to-Speech usando XTTS v2."""
    
    def __init__(
        self,
        output_dir: str = "./temp",
        language: str = "es",
        speaker_wav: Optional[str] = None
    ):
        """
        Inicializa el motor XTTS.
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Crear directorio de voces personalizadas
        self.voices_dir = Path("assets/voices")
        self.voices_dir.mkdir(parents=True, exist_ok=True)
        
        self.language = language
        self.speaker_wav = speaker_wav
        self.model = None
        self._initialized = False
        
        # Buscar voz configurada o usar default
        if speaker_wav and os.path.exists(speaker_wav):
            self.speaker_wav = speaker_wav
        else:
            # Buscar si hay alguna voz en assets/voices
            voices = self.list_voices()
            if voices:
                self.speaker_wav = str(voices[0])
                logger.info(f"Usando primera voz encontrada: {self.speaker_wav}")
    
    def list_voices(self) -> list[Path]:
        """Lista archivos de audio en assets/voices."""
        extensions = {".wav", ".mp3", ".m4a", ".flac"}
        return [f for f in self.voices_dir.iterdir() if f.suffix.lower() in extensions]
    
    def _ensure_initialized(self):
        """Inicializa el modelo XTTS si no está cargado."""
        if self._initialized:
            return
        
        try:
            # FIX: Monkeypatch torch.load para compatibilidad con PyTorch 2.6+
            # XTTS carga pickles antiguos que requieren weights_only=False
            import torch
            _original_load = torch.load
            
            def _safe_load(*args, **kwargs):
                if "weights_only" not in kwargs:
                    kwargs["weights_only"] = False
                return _original_load(*args, **kwargs)
                
            torch.load = _safe_load
            
            from TTS.api import TTS
            
            logger.info("Cargando modelo XTTS v2... (esto puede tardar)")
            
            # Usar XTTS v2 multilingual
            self.model = TTS("tts_models/multilingual/multi-dataset/xtts_v2")
            
            # Mover a GPU si está disponible
            if self._check_cuda():
                self.model.to("cuda")
                logger.info("Modelo cargado en GPU")
            else:
                logger.info("Modelo cargado en CPU (será más lento)")
            
            self._initialized = True
            
        except ImportError:
            logger.error("TTS no está instalado. Ejecuta: uv sync")
            raise
        except Exception as e:
            logger.error(f"Error inicializando XTTS: {e}")
            raise
    
    def _check_cuda(self) -> bool:
        """Verifica si CUDA está disponible."""
        try:
            import torch
            return torch.cuda.is_available()
        except ImportError:
            return False
    
    def _split_into_chunks(self, text: str) -> list[str]:
        """
        Divide el texto en chunks manejables para XTTS.
        
        Mantiene oraciones completas y respeta la puntuación.
        """
        # Normalizar espacios
        text = re.sub(r"\s+", " ", text).strip()
        
        # Dividir por oraciones
        sentences = re.split(r"(?<=[.!?])\s+", text)
        
        chunks = []
        current_chunk = ""
        
        for sentence in sentences:
            # Si la oración sola es muy larga, dividirla por comas
            if len(sentence) > MAX_CHUNK_LENGTH:
                parts = sentence.split(",")
                for part in parts:
                    part = part.strip()
                    if not part:
                        continue
                    
                    if len(current_chunk) + len(part) + 2 <= MAX_CHUNK_LENGTH:
                        current_chunk = f"{current_chunk}, {part}" if current_chunk else part
                    else:
                        if current_chunk:
                            chunks.append(current_chunk.strip())
                        current_chunk = part
            else:
                # Agregar oración al chunk actual si cabe
                if len(current_chunk) + len(sentence) + 1 <= MAX_CHUNK_LENGTH:
                    current_chunk = f"{current_chunk} {sentence}" if current_chunk else sentence
                else:
                    if current_chunk:
                        chunks.append(current_chunk.strip())
                    current_chunk = sentence
        
        # Agregar último chunk
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        logger.info(f"Texto dividido en {len(chunks)} chunks")
        return chunks
    
    def _get_default_speaker_wav(self) -> str:
        """
        Obtiene o crea un archivo WAV de referencia para el speaker.
        XTTS v2 lo requiere obligatoriamente.
        """
        default_wav = self.output_dir / "default_speaker.wav"
        
        if default_wav.exists():
            return str(default_wav)
        
        # Crear un audio de referencia simple usando pyttsx3 o silencio
        # Por ahora, buscamos samples de TTS
        try:
            import importlib.resources
            # Intentar encontrar un sample de voz de la librería
            tts_path = Path(importlib.import_module("TTS").__file__).parent
            samples_dir = tts_path / "tts" / "utils" / "assets"
            
            for sample in ["ljspeech", "sample", "reference"]:
                for ext in [".wav", ".mp3"]:
                    sample_path = samples_dir / f"{sample}{ext}"
                    if sample_path.exists():
                        logger.info(f"Usando sample de referencia: {sample_path}")
                        return str(sample_path)
        except Exception:
            pass
        
        # Crear un audio sintético de referencia usando otro TTS simple
        logger.info("Generando audio de referencia para XTTS...")
        try:
            # Usar un modelo TTS más simple para generar el reference
            from TTS.api import TTS as TTSSimple
            simple_tts = TTSSimple("tts_models/es/css10/vits")
            simple_tts.tts_to_file(
                text="Hola, esta es una voz de referencia para el sistema.",
                file_path=str(default_wav)
            )
            logger.info(f"Audio de referencia creado: {default_wav}")
            return str(default_wav)
        except Exception as e:
            logger.warning(f"No se pudo crear referencia con vits: {e}")
        
        # Último recurso: crear silencio con tono
        try:
            from pydub.generators import Sine
            tone = Sine(440).to_audio_segment(duration=3000)  # 3 segundos de tono
            tone = tone - 20  # Reducir volumen
            tone.export(str(default_wav), format="wav")
            logger.warning("Usando tono como referencia (calidad reducida)")
            return str(default_wav)
        except Exception as e:
            logger.error(f"No se pudo crear audio de referencia: {e}")
            return ""
    
    def _synthesize_chunk(self, text: str, output_path: str) -> bool:
        """
        Sintetiza un chunk de texto a audio.
        
        Args:
            text: Texto a sintetizar
            output_path: Ruta del archivo de salida
            
        Returns:
            True si fue exitoso
        """
        try:
            # XTTS v2 SIEMPRE requiere speaker_wav
            speaker = self.speaker_wav
            if not speaker or not os.path.exists(speaker):
                speaker = self._get_default_speaker_wav()
            
            if not speaker:
                logger.error("No hay archivo de referencia de voz disponible")
                return False
            
            self.model.tts_to_file(
                text=text,
                speaker_wav=speaker,
                language=self.language,
                file_path=output_path
            )
            
            return os.path.exists(output_path)
            
        except Exception as e:
            logger.error(f"Error sintetizando chunk: {e}")
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
            output_filename: Nombre del archivo de salida (sin extensión)
            show_progress: Si mostrar barra de progreso
            
        Returns:
            Ruta al archivo de audio o None si hay error
        """
        self._ensure_initialized()
        
        # Limpiar texto antes de sintetizar
        text = clean_text_for_tts(text)
        
        if not text.strip():
            logger.error("Texto vacío después de limpieza")
            return None
        
        # Generar nombre de archivo si no se proporciona
        if not output_filename:
            import hashlib
            hash_id = hashlib.sha256(text.encode()).hexdigest()[:8]
            output_filename = f"audio_{hash_id}"
        
        output_path = self.output_dir / f"{output_filename}.wav"
        
        # Dividir en chunks
        chunks = self._split_into_chunks(text)
        total_chunks = len(chunks)
        
        if show_progress:
            console.print(Panel(
                f"[bold cyan]SÍNTESIS DE VOZ[/bold cyan]\n"
                f"Texto: {len(text)} caracteres\n"
                f"Chunks: {total_chunks}\n"
                f"Estimado: ~{total_chunks * 25}s en CPU",
                title="XTTS v2"
            ))
        
        if total_chunks == 1:
            # Texto corto, sintetizar directamente
            if show_progress:
                console.print("[dim]Sintetizando chunk único...[/dim]")
            
            start_time = time.time()
            if self._synthesize_chunk(chunks[0], str(output_path)):
                elapsed = time.time() - start_time
                if show_progress:
                    console.print(f"[green]✓ Audio generado en {elapsed:.1f}s[/green]")
                return str(output_path)
            return None
        
        # Múltiples chunks: sintetizar y concatenar con progreso
        temp_files = []
        combined = None
        chunk_times = []
        
        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(bar_width=30),
                TaskProgressColumn(),
                TimeElapsedColumn(),
                console=console,
                refresh_per_second=2
            ) as progress:
                
                main_task = progress.add_task(
                    f"[cyan]Sintetizando {total_chunks} chunks...",
                    total=total_chunks
                )
                
                for i, chunk in enumerate(chunks):
                    temp_path = self.output_dir / f"temp_chunk_{i}.wav"
                    
                    # Actualizar descripción con info del chunk actual
                    chunk_preview = chunk[:40] + "..." if len(chunk) > 40 else chunk
                    progress.update(
                        main_task,
                        description=f"[cyan]Chunk {i+1}/{total_chunks}: {chunk_preview}"
                    )
                    
                    chunk_start = time.time()
                    
                    if self._synthesize_chunk(chunk, str(temp_path)):
                        chunk_time = time.time() - chunk_start
                        chunk_times.append(chunk_time)
                        
                        temp_files.append(temp_path)
                        
                        # Cargar y concatenar
                        segment = AudioSegment.from_wav(str(temp_path))
                        
                        if combined is None:
                            combined = segment
                        else:
                            pause = AudioSegment.silent(duration=200)
                            combined = combined + pause + segment
                        
                        # Mostrar tiempo restante estimado
                        avg_time = sum(chunk_times) / len(chunk_times)
                        remaining = (total_chunks - i - 1) * avg_time
                        
                        progress.update(
                            main_task,
                            completed=i + 1,
                            description=f"[green]✓ Chunk {i+1} ({chunk_time:.1f}s) - Restante: ~{remaining:.0f}s"
                        )
                    else:
                        progress.update(
                            main_task,
                            completed=i + 1,
                            description=f"[red]✗ Chunk {i+1} falló[/red]"
                        )
            
            if combined:
                # Exportar audio combinado
                if show_progress:
                    console.print("[dim]Combinando audio...[/dim]")
                
                combined.export(str(output_path), format="wav")
                
                total_time = sum(chunk_times)
                audio_duration = len(combined) / 1000.0
                
                if show_progress:
                    console.print(Panel(
                        f"[bold green]✓ AUDIO GENERADO[/bold green]\n"
                        f"Archivo: {output_path.name}\n"
                        f"Duración: {audio_duration:.1f}s\n"
                        f"Tiempo de proceso: {total_time:.1f}s\n"
                        f"Ratio: {audio_duration/total_time:.2f}x",
                        title="Completado",
                        style="green"
                    ))
                
                return str(output_path)
            
            return None
            
        finally:
            # Limpiar archivos temporales
            for temp_file in temp_files:
                try:
                    os.unlink(temp_file)
                except Exception:
                    pass
    
    def synthesize_with_timing(
        self,
        narration: str,
        subtitles: list[dict],
        output_filename: str
    ) -> Optional[dict]:
        """
        Sintetiza audio Y genera subtítulos sincronizados basados en tiempos reales.
        
        Esta versión genera los subtítulos basándose en la duración real de cada
        chunk de audio, no en estimaciones del LLM.
        
        Args:
            narration: Texto completo de narración
            subtitles: Lista de subtítulos originales (se usa solo el texto)
            output_filename: Nombre del archivo de salida
            
        Returns:
            Dict con path de audio y subtítulos sincronizados
        """
        self._ensure_initialized()
        
        # Limpiar texto
        narration = clean_text_for_tts(narration)
        
        if not narration.strip():
            logger.error("Narración vacía después de limpieza")
            return None
        
        output_path = self.output_dir / f"{output_filename}.wav"
        
        # Dividir en chunks
        chunks = self._split_into_chunks(narration)
        total_chunks = len(chunks)
        
        console.print(Panel(
            f"[bold cyan]SÍNTESIS DE VOZ SINCRONIZADA[/bold cyan]\n"
            f"Texto: {len(narration)} caracteres\n"
            f"Chunks: {total_chunks}\n"
            f"Estimado: ~{total_chunks * 25}s en CPU",
            title="XTTS v2"
        ))
        
        # Almacenar información de cada chunk
        chunk_info = []  # Lista de {text, start, end, duration}
        temp_files = []
        combined = None
        current_time = 0.0
        pause_duration = 0.15  # 150ms de pausa entre chunks
        
        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(bar_width=30),
                TaskProgressColumn(),
                TimeElapsedColumn(),
                console=console,
                refresh_per_second=2
            ) as progress:
                
                main_task = progress.add_task(
                    f"[cyan]Sintetizando {total_chunks} chunks...",
                    total=total_chunks
                )
                
                for i, chunk in enumerate(chunks):
                    temp_path = self.output_dir / f"temp_chunk_{i}.wav"
                    
                    # Actualizar descripción
                    chunk_preview = chunk[:40] + "..." if len(chunk) > 40 else chunk
                    progress.update(
                        main_task,
                        description=f"[cyan]Chunk {i+1}/{total_chunks}: {chunk_preview}"
                    )
                    
                    process_start = time.time()
                    
                    if self._synthesize_chunk(chunk, str(temp_path)):
                        process_time = time.time() - process_start
                        temp_files.append(temp_path)
                        
                        # Cargar y obtener duración REAL del audio
                        segment = AudioSegment.from_wav(str(temp_path))
                        chunk_duration = len(segment) / 1000.0  # En segundos
                        
                        # Guardar info del chunk para subtítulos
                        chunk_info.append({
                            "text": chunk,
                            "start": round(current_time, 2),
                            "end": round(current_time + chunk_duration, 2),
                            "duration": chunk_duration
                        })
                        
                        # Concatenar audio
                        if combined is None:
                            combined = segment
                        else:
                            pause = AudioSegment.silent(duration=int(pause_duration * 1000))
                            combined = combined + pause + segment
                            current_time += pause_duration  # Añadir tiempo de pausa
                        
                        current_time += chunk_duration
                        
                        progress.update(
                            main_task,
                            completed=i + 1,
                            description=f"[green]✓ Chunk {i+1} ({chunk_duration:.1f}s audio)"
                        )
                    else:
                        progress.update(
                            main_task,
                            completed=i + 1,
                            description=f"[red]✗ Chunk {i+1} falló[/red]"
                        )
            
            if not combined:
                logger.error("No se pudo generar ningún chunk de audio")
                return None
            
            # Exportar audio combinado
            console.print("[dim]Exportando audio final...[/dim]")
            combined.export(str(output_path), format="wav")
            
            total_duration = len(combined) / 1000.0
            
            # Generar subtítulos sincronizados desde chunk_info
            synced_subtitles = []
            for info in chunk_info:
                synced_subtitles.append({
                    "start": info["start"],
                    "end": info["end"],
                    "text": info["text"]
                })
            
            console.print(Panel(
                f"[bold green]✓ AUDIO SINCRONIZADO[/bold green]\n"
                f"Archivo: {output_path.name}\n"
                f"Duración: {total_duration:.1f}s\n"
                f"Subtítulos: {len(synced_subtitles)} sincronizados",
                title="Completado",
                style="green"
            ))
            
            return {
                "audio_path": str(output_path),
                "duration": total_duration,
                "subtitles": synced_subtitles
            }
            
        finally:
            # Limpiar archivos temporales
            for temp_file in temp_files:
                try:
                    os.unlink(temp_file)
                except Exception:
                    pass
    
    def get_available_speakers(self) -> list[str]:
        """Obtiene lista de voces disponibles."""
        if not self._initialized:
            return []
        
        try:
            return self.model.speakers or []
        except Exception:
            return []
    
    def set_speaker_reference(self, wav_path: str) -> bool:
        """
        Establece un archivo WAV como referencia para clonar voz.
        
        Args:
            wav_path: Ruta al archivo WAV de referencia
            
        Returns:
            True si el archivo es válido
        """
        if not os.path.exists(wav_path):
            logger.error(f"Archivo no encontrado: {wav_path}")
            return False
        
        # Verificar que es un WAV válido
        try:
            audio = AudioSegment.from_wav(wav_path)
            duration = len(audio) / 1000.0
            
            if duration < 3:
                logger.warning("El audio de referencia es muy corto (mínimo 3 segundos)")
            elif duration > 30:
                logger.warning("El audio de referencia es muy largo (máximo recomendado 30 segundos)")
            
            self.speaker_wav = wav_path
            logger.info(f"Voz de referencia establecida: {wav_path} ({duration:.1f}s)")
            return True
            
        except Exception as e:
            logger.error(f"Error leyendo archivo WAV: {e}")
            return False


def main():
    """Función principal para testing."""
    import argparse
    from rich.console import Console
    from rich.progress import Progress
    
    parser = argparse.ArgumentParser(description="XTTS Engine")
    parser.add_argument("--test", action="store_true", help="Ejecutar test básico")
    parser.add_argument("--text", type=str, help="Texto a sintetizar")
    parser.add_argument("--from-script", action="store_true", help="Sintetizar desde guión en cache")
    parser.add_argument("--configure", action="store_true", help="Configurar voz")
    parser.add_argument("--output", type=str, default="test_audio", help="Nombre del archivo de salida")
    args = parser.parse_args()
    
    console = Console()
    
    if args.configure:
        console.print("[cyan]Configuración de voz XTTS[/cyan]")
        console.print("\nPara clonar una voz, proporciona un archivo WAV de 5-15 segundos")
        console.print("con la voz que quieres imitar (sin ruido de fondo).\n")
        
        wav_path = input("Ruta al archivo WAV (Enter para usar voz por defecto): ").strip()
        
        if wav_path:
            engine = XTTSEngine()
            if engine.set_speaker_reference(wav_path):
                console.print("[green]✓ Voz configurada[/green]")
            else:
                console.print("[red]✗ Error configurando voz[/red]")
        else:
            console.print("[yellow]Usando voz por defecto[/yellow]")
        return
    
    if args.text:
        console.print(f"[cyan]Sintetizando: {args.text[:50]}...[/cyan]")
        
        engine = XTTSEngine()
        
        with Progress() as progress:
            task = progress.add_task("Generando audio...", total=100)
            
            audio_path = engine.synthesize(args.text, args.output)
            progress.update(task, completed=100)
        
        if audio_path:
            console.print(f"[green]✓ Audio generado: {audio_path}[/green]")
        else:
            console.print("[red]✗ Error generando audio[/red]")
        return
    
    # Test básico
    console.print("[cyan]Test de XTTS v2...[/cyan]")
    
    test_text = "Hola, esto es una prueba del sistema de síntesis de voz. La calidad debe ser natural y clara."
    
    engine = XTTSEngine()
    audio_path = engine.synthesize(test_text, "test_output")
    
    if audio_path:
        console.print(f"[green]✓ Test exitoso: {audio_path}[/green]")
    else:
        console.print("[red]✗ Test fallido[/red]")


if __name__ == "__main__":
    main()
