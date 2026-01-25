
import os
import warnings
import whisper
from pathlib import Path
from rich.console import Console

# Filtrar warnings de torch/whisper
warnings.filterwarnings("ignore")

console = Console()

def transcribe_all():
    console.print("[bold cyan]Iniciando transcripción de assets con Whisper...[/bold cyan]")
    
    # Cargar modelo (base es rápido y decente para esto)
    try:
        model = whisper.load_model("base")
    except Exception as e:
        console.print(f"[red]Error cargando modelo Whisper: {e}[/red]")
        return

    folders = ["assets/intros", "assets/outros"]
    
    for folder in folders:
        folder_path = Path(folder)
        if not folder_path.exists():
            continue
            
        console.print(f"\n[yellow]Procesando carpeta: {folder}[/yellow]")
        
        videos = list(folder_path.glob("*.mp4"))
        for video in videos:
            txt_path = video.with_suffix(".txt")
            
            console.print(f"  🎤 Transcribiendo {video.name}...", end=" ")
            try:
                result = model.transcribe(str(video), fp16=False) # fp16=False para CPU safety
                text = result["text"].strip()
                
                # Escribir solo si hay texto, si no usar default
                if not text:
                    text = "..."
                
                with open(txt_path, "w", encoding="utf-8") as f:
                    f.write(text)
                
                console.print(f"[green]✓ OK: '{text}'[/green]")
                
            except Exception as e:
                console.print(f"[red]✗ Error: {e}[/red]")

if __name__ == "__main__":
    transcribe_all()
