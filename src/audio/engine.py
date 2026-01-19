"""
Motor de Audio V3
Encargado de la síntesis de voz (TTS) y la alineación precisa (Whisper).
"""
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
import torch
import whisper

logger = logging.getLogger(__name__)

class AudioEngine:
    """
    Motor de procesamiento de audio que combina TTS y alineación por IA.
    """
    
    def __init__(self, model_size: str = "base", device: Optional[str] = None):
        """
        Inicializa el motor de audio y carga el modelo Whisper.
        
        Args:
            model_size: Tamaño del modelo Whisper ('tiny', 'base', 'small', 'medium', 'large')
            device: Dispositivo ('cpu', 'cuda'). Si es None, se detecta automáticamente.
        """
        self.model_size = model_size
        
        if device:
            self.device = device
        else:
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
            
        logger.info(f"Inicializando AudioEngine en {self.device} con modelo {model_size}...")
        print(f"⏳ Cargando modelo Whisper '{model_size}' en {self.device}...")
        
        try:
            self.model = whisper.load_model(model_size, device=self.device)
            print(f"✅ Modelo cargado correctamente.")
        except Exception as e:
            logger.error(f"Error cargando Whisper: {e}")
            raise e

    def align_audio(self, audio_path: str) -> List[Dict[str, Any]]:
        """
        Transcribe y alinea un archivo de audio para obtener timestamps precisos.
        
        Args:
            audio_path: Ruta al archivo de audio.
            
        Returns:
            Lista de segmentos con palabras y tiempos exactos.
        """
        path = Path(audio_path)
        if not path.exists():
            raise FileNotFoundError(f"No se encuentra el archivo: {audio_path}")

        print(f"🎙️ Analizando audio con Whisper: {path.name}...")
        
        # Transcripción con timestamps a nivel de palabra
        result = self.model.transcribe(
            str(path),
            word_timestamps=True,
            language="es"
        )
        
        segments = result.get("segments", [])
        print(f"✅ Alineación completada: {len(segments)} segmentos detectados.")
        
        return segments

    def get_word_timings(self, segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Extrae una lista plana de palabras con sus tiempos (start, end, word).
        Útil para animaciones de subtítulos estilo karaoke.
        """
        words = []
        for segment in segments:
            for word_info in segment.get("words", []):
                words.append({
                    "word": word_info["word"].strip(),
                    "start": word_info["start"],
                    "end": word_info["end"],
                    "confidence": word_info.get("probability", 0.0)
                })
        return words

if __name__ == "__main__":
    # Test rápido
    import sys
    logging.basicConfig(level=logging.INFO)
    
    if len(sys.argv) > 1:
        audio_file = sys.argv[1]
        engine = AudioEngine(model_size="tiny")  # Tiny para test rápido
        segments = engine.align_audio(audio_file)
        
        print("\n--- Resultado (Primeros 3 segmentos) ---")
        for seg in segments[:3]:
            print(f"[{seg['start']:.2f}s - {seg['end']:.2f}s]: {seg['text']}")
            if 'words' in seg:
                print(f"  Words: {[w['word'] for w in seg['words']]}")
    else:
        print("Uso: python -m src.audio.engine <ruta_audio>")
