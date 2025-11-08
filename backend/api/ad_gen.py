# -*- coding: utf-8 -*-
import time
from google import genai
import os
from dotenv import load_dotenv

load_dotenv()

def generate_video(startup_idea: str, output_path: str = "startup_ad_video.mp4"):
    """
    Generate a video advertisement using Google Veo based on a startup idea.
    
    Args:
        startup_idea: The startup idea to create a video for
        output_path: Path where the video file will be saved
        
    Returns:
        str: Path to the generated video file
        
    Raises:
        RuntimeError: If API key is not set or video generation fails
    """
    api_key = os.getenv("VITE_GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set. Add it to your environment or .env file.")
    
    client = genai.Client(api_key=api_key)
    
    # Step 1: Generate optimized video prompt using Gemini
    prompt_content = f"""Create a single, concise 8-second video prompt for Google Veo to generate a video advertisement for this startup: {startup_idea}

Requirements:
- ONE paragraph, 2-3 sentences maximum
- Describe visual scenes, camera movements, and key actions
- Include any dialogue in single quotes
- Make it cinematic and engaging
- Focus on the core value proposition
- Be specific about visuals (people, settings, objects, lighting)

Example format: "A modern office space with natural lighting. A professional woman in her 30s opens a sleek mobile app on her phone, smiling as she navigates through colorful data visualizations. Camera zooms into the phone screen showing an intuitive dashboard. Text overlay appears: 'Transform Your Business Today.' She looks up confidently at the camera."

Generate ONLY the video prompt, nothing else."""

    response = client.models.generate_content(
        model="gemini-2.0-flash-exp",
        contents=prompt_content
    )
    
    video_prompt = response.text.strip()
    
    # Step 2: Generate video using Veo 2.0
    operation = client.models.generate_videos(
        model="veo-2.0-generate-001",
        prompt=video_prompt,
        config={
            "duration_seconds": 8,
            "aspect_ratio": "16:9"
        }
    )
    
    # Poll the operation status until the video is ready
    while not operation.done:
        time.sleep(10)
        operation = client.operations.get(operation)
    
    # Download the generated video
    generated_video = operation.response.generated_videos[0]
    
    # Download video file data
    video_data = client.files.download(file=generated_video.video)
    
    # Save to file
    with open(output_path, 'wb') as f:
        f.write(video_data)
    
    return output_path


if __name__ == "__main__":
    # For testing purposes
    userPrompt = input("Enter Idea: ")
    try:
        video_path = generate_video(userPrompt)
        print(f"Generated video saved to {video_path}")
    except Exception as e:
        print(f"Error: {e}")