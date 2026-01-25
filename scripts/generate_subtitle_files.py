
import os
from pathlib import Path

def create_defaults():
    intros_dir = Path("assets/intros")
    outros_dir = Path("assets/outros")
    
    # Textos por defecto
    intro_text = "¡Bienvenidos a Tiempo de Vida!"
    outro_text = "¡Suscríbete para más consejos!"
    
    # Intros
    if intros_dir.exists():
        for vid in intros_dir.glob("*.mp4"):
            txt_path = vid.with_suffix(".txt")
            if not txt_path.exists():
                with open(txt_path, "w") as f:
                    f.write(intro_text)
                print(f"Created: {txt_path}")

    # Outros
    if outros_dir.exists():
        for vid in outros_dir.glob("*.mp4"):
            txt_path = vid.with_suffix(".txt")
            if not txt_path.exists():
                with open(txt_path, "w") as f:
                    f.write(outro_text)
                print(f"Created: {txt_path}")

if __name__ == "__main__":
    create_defaults()
