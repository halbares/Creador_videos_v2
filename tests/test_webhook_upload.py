
import os
import requests
from dotenv import load_dotenv

load_dotenv()

def test_upload():
    url = os.getenv("MAKE_WEBHOOK_URL")
    if not url:
        print("No URL found")
        return

    video_path = "output/20260124_deje_de_decir_perdon_y_mi_vida/video.mp4"
    if not os.path.exists(video_path):
        print(f"Video {video_path} not found")
        return

    print(f"Testing upload to {url}...")
    
    try:
        with open(video_path, 'rb') as f:
            files = {'video': ('video.mp4', f, 'video/mp4')}
            # Also send metadata as data
            data = {
                "title": "Test Upload",
                "description": "Attempting file upload via webhook"
            }
            response = requests.post(url, files=files, data=data, timeout=60)
            
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 200:
            print("SUCCESS! The webhook accepts file uploads.")
        else:
            print("FAILED. Webhook might not support files.")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_upload()
