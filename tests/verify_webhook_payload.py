
import os
import logging
from dotenv import load_dotenv
from src.publisher.make_webhook import MakeWebhookClient

logging.basicConfig(level=logging.INFO)
load_dotenv()

def test_webhook_payload():
    print("🚀 Iniciando prueba de envío a Make.com...")
    
    # 1. Instanciar cliente
    client = MakeWebhookClient()
    if not client.is_configured():
        print("❌ Error: Webhook URL no configurada en .env")
        return

    # 2. Datos simulados (coincidentes con el video subido anteriormente)
    # URL real de Dropbox obtenida en el paso anterior
    dropbox_url = "https://www.dropbox.com/scl/fi/aoy7kssv5tmhddtjz9x7p/video.mp4?rlkey=3xxyexwbnmt2gbjwpmiqd6y1q&raw=1"
    
    dummy_script = {
        "title": "Prueba de Integración: Deje de decir perdon",
        "keywords": ["hábitos", "productividad", "mindset", "test"], # Esto se convierte en hashtags
        "narration_text": "Esta es una narración de prueba para verificar que la descripción llega completa a Make.com...",
        "hooks_alternativos": ["¿Sigues pidiendo perdón?", "Esto cambiará tu vida"]
    }

    # 3. Enviar
    print(f"📡 Enviando payload a: {client.webhook_url}")
    print(f"📎 Video URL: {dropbox_url}")
    
    result = client.publish_from_metadata(
        video_url=dropbox_url,
        script=dummy_script,
        destinations=["facebook", "youtube"]
    )
    
    # 4. Verificar respuesta
    if result["success"]:
        print("\n✅ ¡ENVÍO EXITOSO!")
        print("Status Code:", result.get("status_code"))
        print("Response:", result.get("response"))
        print("\n👉 POR FAVOR REVISA TU 'Data Store' EN MAKE.COM")
        print("Deberías ver una nueva entrada con el título 'Prueba de Integración: Deje de decir perdon'")
    else:
        print("\n❌ FALLO EL ENVÍO")
        print("Error:", result.get("error"))

if __name__ == "__main__":
    test_webhook_payload()
