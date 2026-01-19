"""
Script de Verificación de Hardware para V3
Ejecutar este script en el nuevo equipo (Core Ultra) para confirmar acceso a la NPU.
"""
import torch
import whisper
import sys
import platform
import os

def check_system():
    print(f"🖥️  Sistema: {platform.system()} {platform.release()}")
    print(f"🐍 Python: {sys.version.split()[0]}")
    
    # 1. Chequeo de Torch (CUDA/CPU)
    print("\n--- 1. PyTorch Backend ---")
    if torch.cuda.is_available():
        print(f"✅ CUDA Disponible: {torch.cuda.get_device_name(0)}")
        print(f"   VRAM: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.2f} GB")
        device = "cuda"
    else:
        print("⚠️  CUDA no detectado (Usando CPU)")
        device = "cpu"
        
        # Chequeo específico para Intel Extensions for PyTorch (IPEX) - Futuro
        try:
            import intel_extension_for_pytorch as ipex
            print(f"✅ IPEX Detectado (Soporte Intel XPU/NPU)")
        except ImportError:
            print("ℹ️  IPEX no instalado (Normal si no estás en Core Ultra aún)")

    # 2. Chequeo de Whisper
    print("\n--- 2. OpenAI Whisper ---")
    try:
        # Intentar cargar modelo tiny para ver si explota
        print("⏳ Probando carga de modelo 'tiny'...")
        model = whisper.load_model("tiny", device=device)
        print(f"✅ Modelo cargado exitosamente en: {model.device}")
    except Exception as e:
        print(f"❌ Error cargando Whisper: {e}")

    print("\n---------------------------------------------------")
    if device == "cpu":
        print("💡 TIP: En el Intel Core Ultra, asegúrate de instalar los drivers NPU")
        print("   y considerar usar el backend 'openvino' para máxima velocidad.")
    else:
        print(f"🚀 ¡Todo listo para volar en {device}!")
        
if __name__ == "__main__":
    check_system()
