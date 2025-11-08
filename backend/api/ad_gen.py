import os
import json
import time
import io
import base64
import tempfile
from functools import wraps
from flask import Blueprint, request, jsonify, g, current_app, send_file
from PIL import Image

try:
    from moviepy.editor import VideoFileClip, AudioFileClip
    from moviepy.video.fx.all import loop as moviepy_loop
except ImportError:
    VideoFileClip = None
    AudioFileClip = None
    moviepy_loop = None

import google.generativeai as genai
from google.generativeai import types

ad_gen_bp = Blueprint('ad_gen_bp', __name__, url_prefix='/ads')

media_client = None
genai_llm = None

job_store = {}

VEO_MODEL = "veo-3.1-generate-preview"
LYRIA_MODEL = "lyria-2.0-preview"
IMAGE_MODEL = "gemini-2.5-flash-image"
LLM_MODEL = "gemini-2.5-flash-preview-09-2025"
VIDEO_DURATION_SECONDS = 15

def init_ad_gen_services(app):
    global media_client, genai_llm
    app.logger.info("Initializing Ad Generation Services (Google)...")
    try:
        GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
        if not GOOGLE_API_KEY:
            raise ValueError("GOOGLE_API_KEY not set in .env file")
        
        media_client = genai.Client(api_key=GOOGLE_API_KEY)
        genai.configure(api_key=GOOGLE_API_KEY)
        genai_llm = genai.GenerativeModel(LLM_MODEL)
        
        app.logger.info("Google GenAI Clients initialized successfully.")
    except Exception as e:
        app.logger.error(f"Error initializing Google clients: {e}")

def merge_ad(video_path, music_path, video_duration):
    if not VideoFileClip or not moviepy_loop:
        current_app.logger.error("MoviePy is not imported. Cannot merge files.")
        raise ImportError("MoviePy library not found")

    video_clip = None
    audio_clip = None
    final_clip = None
    try:
        current_app.logger.info(f"Merging video {video_path} and audio {music_path}")
        video_clip = VideoFileClip(video_path)
        audio_clip = AudioFileClip(music_path)

        if audio_clip.duration > video_duration:
            audio_clip = audio_clip.subclip(0, video_duration)
        elif audio_clip.duration < video_duration:
            audio_clip = audio_clip.fx(moviepy_loop, duration=video_duration)
        
        final_clip = video_clip.set_audio(audio_clip)

        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as temp_final:
            final_path = temp_final.name
            current_app.logger.info(f"Writing merged file to {final_path}")
            final_clip.write_videofile(final_path, codec="libx264", audio_codec="aac", bitrate="5000k", preset="medium", logger=None)
        
        return final_path
    except Exception as e:
        current_app.logger.exception(f"Error during video/audio merge: {e}")
        raise
    finally:
        if video_clip: video_clip.close()
        if audio_clip: audio_clip.close()
        if final_clip: final_clip.close()

def cleanup_temp_files(*files):
    for f in files:
        if f and os.path.exists(f):
            try:
                os.remove(f)
                current_app.logger.info(f"Cleaned up temp file: {f}")
            except Exception as e:
                current_app.logger.warning(f"Failed to clean up temp file {f}: {e}")

def start_ad_generation_jobs(video_prompt, music_prompt, image=None):
    if not media_client:
         current_app.logger.error("Media client not initialized")
         raise Exception("Media client not initialized")

    current_app.logger.info(f"Starting Veo job...")
    video_args = {
        "model": VEO_MODEL,
        "prompt": video_prompt,
        "duration_seconds": VIDEO_DURATION_SECONDS
    }
    if image:
        video_args["image"] = image
        
    video_operation = media_client.models.generate_videos(**video_args)
    video_op_name = video_operation.operation.name
    current_app.logger.info(f"Veo job started. Operation name: {video_op_name}")

    music_op_name = None
    if music_prompt:
        try:
            current_app.logger.info(f"Starting Lyria job...")
            music_operation = media_client.models.generate_music(
                model=LYRIA_MODEL,
                prompt=music_prompt,
                duration_seconds=VIDEO_DURATION_SECONDS
            )
            music_op_name = music_operation.operation.name
            current_app.logger.info(f"Lyria job started. Operation name: {music_op_name}")
        except Exception as e:
            current_app.logger.error(f"Failed to start Lyria job, continuing with video only: {e}")
            music_op_name = None
    
    job_data = {
        'video_prompt': video_prompt,
        'video_op_name': video_op_name,
        'video_status': 'processing', 
        'final_status': 'processing', 
        'created_at': time.time(),
        'has_image_input': (image is not None)
    }
    if music_op_name:
        job_data['music_prompt'] = music_prompt
        job_data['music_op_name'] = music_op_name
        job_data['music_status'] = 'processing'
    else:
        job_data['music_status'] = 'skipped'
        
    job_store[video_op_name] = job_data
    
    return video_op_name

@ad_gen_bp.route('/generate-prompt', methods=['POST'])
def generate_prompt():
    if not genai_llm:
         current_app.logger.error("LLM client not initialized")
         return jsonify({"error": "LLM client not initialized"}), 500

    data = request.json
    if 'idea' not in data:
        return jsonify({"error": "Missing 'idea' in request body"}), 400
    user_idea = data['idea']

    system_prompt = f"""
    You are a world-class creative director for a marketing agency.
    A user will provide a startup idea. Your job is to generate two distinct prompts for AI models, formatted as a JSON object.
    1. "video_prompt": A {VIDEO_DURATION_SECONDS}-second, visually descriptive video prompt for Veo 3.1. It should describe scenes, camera movements, and any spoken dialogue (e.g., "Man says: 'This is amazing!'").
    2. "music_prompt": A prompt for Lyria (music model) describing the background music for a {VIDEO_DURATION_SECONDS}-second ad (e.g., "upbeat, hopeful, electronic track").
    
    Ensure the JSON is valid.
    """
    
    generation_config = types.GenerationConfig(
        response_mime_type="application/json",
        response_schema={
            "type": "OBJECT",
            "properties": {
                "video_prompt": {"type": "STRING"},
                "music_prompt": {"type": "STRING"}
            },
            "required": ["video_prompt", "music_prompt"]
        }
    )
    
    try:
        llm_with_schema = genai.GenerativeModel(
            LLM_MODEL,
            generation_config=generation_config,
            system_instruction=system_prompt
        )
        response = llm_with_schema.generate_content(user_idea)
        prompt_data = json.loads(response.text)
        return jsonify(prompt_data), 200
    except Exception as e:
        current_app.logger.exception(f"Error in /ads/generate-prompt: {e}")
        return jsonify({"error": f"Failed to generate prompt: {str(e)}"}), 500

@ad_gen_bp.route('/generate-image', methods=['POST'])
def generate_image_api():
    if not media_client:
         current_app.logger.error("Media client not initialized")
         return jsonify({"error": "Media client not initialized"}), 500

    data = request.json
    if 'prompt' not in data:
        return jsonify({"error": "Missing 'prompt' in request body"}), 400
    prompt = data['prompt']

    try:
        current_app.logger.info(f"Generating image with prompt: {prompt[:50]}...")
        image_response = media_client.models.generate_content(
            model=IMAGE_MODEL,
            contents=prompt,
            config={"response_modalities":['IMAGE']}
        )
        
        pil_image = image_response.parts[0].as_image()
        
        buf = io.BytesIO()
        pil_image.save(buf, format="PNG")
        img_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
        
        current_app.logger.info("Image generated successfully.")
        return jsonify({"image_b64": img_b64}), 200
    except Exception as e:
        current_app.logger.exception(f"Error in /ads/generate-image: {e}")
        return jsonify({"error": f"Failed to generate image: {str(e)}"}), 500

@ad_gen_bp.route('/generate-video-text', methods=['POST'])
def generate_video_from_text():
    data = request.json
    if 'video_prompt' not in data:
        return jsonify({"error": "Missing 'video_prompt' in request body"}), 400
    
    video_prompt = data['video_prompt']
    music_prompt = data.get('music_prompt')
    
    try:
        operation_name = start_ad_generation_jobs(video_prompt, music_prompt, image=None)
        return jsonify({"status": "processing", "operation_name": operation_name}), 202
    except Exception as e:
        current_app.logger.exception(f"Error in /ads/generate-video-text: {e}")
        return jsonify({"error": f"Failed to start video generation: {str(e)}"}), 500

@ad_gen_bp.route('/generate-video-image', methods=['POST'])
def generate_video_from_image():
    data = request.json
    if 'prompt' not in data or 'image_b64' not in data:
        return jsonify({"error": "Missing 'prompt' or 'image_b64' in request body"}), 400
    
    video_prompt = data['prompt']
    image_b64 = data['image_b64']
    music_prompt = data.get('music_prompt')

    try:
        img_data = base64.b64decode(image_b64)
        pil_image = Image.open(io.BytesIO(img_data))
        
        operation_name = start_ad_generation_jobs(video_prompt, music_prompt, image=pil_image)
        return jsonify({"status": "processing", "operation_name": operation_name}), 202
    except Exception as e:
        current_app.logger.exception(f"Error in /ads/generate-video-image: {e}")
        return jsonify({"error": f"Failed to start video generation: {str(e)}"}), 500

@ad_gen_bp.route('/video-status/<operation_name>', methods=['GET'])
def get_video_status(operation_name):
    if not media_client:
         current_app.logger.error("Services not initialized (Media)")
         return jsonify({"error": "Server services not initialized"}), 500

    try:
        job_data = job_store.get(operation_name)
        
        if not job_data:
            current_app.logger.warning(f"Job not found in local store: {operation_name}")
            return jsonify({"error": "Job not found or server restarted"}), 404
        
        final_status = job_data.get('final_status')
        if final_status == 'complete':
            return jsonify({"status": "complete"}), 200
        if final_status in ['merging', 'failed']:
            return jsonify({"status": final_status, "error": job_data.get("error_message")}), 200

        video_status = job_data.get('video_status')
        music_status = job_data.get('music_status')

        if video_status == 'processing':
            video_op_name = job_data.get('video_op_name')
            current_app.logger.info(f"Polling Veo op: {video_op_name}")
            video_op = media_client.operations.get(video_op_name)
            
            if video_op.done:
                if video_op.error:
                    current_app.logger.error(f"Veo job {video_op_name} failed: {video_op.error.message}")
                    job_data['video_status'] = 'failed'
                    job_data['final_status'] = 'failed'
                    job_data['error_message'] = f"Video generation failed: {video_op.error.message}"
                else:
                    current_app.logger.info(f"Veo job {video_op_name} complete. Downloading...")
                    video_file = video_op.response.generated_videos[0]
                    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as temp_video:
                        video_file.video.save(temp_video.name)
                        job_data['video_status'] = 'downloaded'
                        job_data['video_temp_path'] = temp_video.name
                        current_app.logger.info(f"Veo video saved to {temp_video.name}")
        
        if music_status == 'processing':
            music_op_name = job_data.get('music_op_name')
            current_app.logger.info(f"Polling Lyria op: {music_op_name}")
            music_op = media_client.operations.get(music_op_name)

            if music_op.done:
                if music_op.error:
                    current_app.logger.error(f"Lyria job {music_op_name} failed: {music_op.error.message}")
                    job_data['music_status'] = 'failed'
                else:
                    current_app.logger.info(f"Lyria job {music_op_name} complete. Downloading...")
                    music_file = music_op.response.generated_music[0]
                    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_music:
                        music_file.music.save(temp_music.name)
                        job_data['music_status'] = 'downloaded'
                        job_data['music_temp_path'] = temp_music.name
                        current_app.logger.info(f"Lyria music saved to {temp_music.name}")
        
        video_status = job_data.get('video_status')
        music_status = job_data.get('music_status')

        if (video_status == 'downloaded' and 
            music_status in ['downloaded', 'skipped', 'failed']):
            
            job_data['final_status'] = 'merging'
            video_path = job_data.get('video_temp_path')
            music_path = job_data.get('music_temp_path')

            try:
                if music_path:
                    final_ad_path = merge_ad(video_path, music_path, VIDEO_DURATION_SECONDS)
                else:
                    final_ad_path = video_path
                
                job_data['final_ad_path'] = final_ad_path
                job_data['final_status'] = 'complete'
                
                cleanup_temp_files(video_path, music_path)
                if music_path and final_ad_path != video_path:
                    cleanup_temp_files(video_path)
                
                return jsonify({"status": "complete"}), 200

            except Exception as e:
                job_data['final_status'] = 'failed'
                job_data['error_message'] = f"Ad merging failed: {str(e)}"
                cleanup_temp_files(video_path, music_path)
                return jsonify({"status": "failed", "error": f"Ad merging failed: {str(e)}"}), 500

        return jsonify({"status": "processing"}), 200

    except Exception as e:
        current_app.logger.exception(f"Error in /ads/video-status for op {operation_name}: {e}")
        if operation_name in job_store:
            job_store[operation_name]['final_status'] = 'failed'
            job_store[operation_name]['error_message'] = f"Unhandled server error: {str(e)}"
            
        return jsonify({"error": f"Failed to get video status: {str(e)}"}), 500

@ad_gen_bp.route('/download-video/<operation_name>', methods=['GET'])
def download_video(operation_name):
    try:
        job_data = job_store.get(operation_name)
        if not job_data:
            return jsonify({"error": "Job not found or server restarted"}), 404
        
        if job_data.get('final_status') != 'complete':
            return jsonify({"error": "Video is not ready for download"}), 425
        
        final_ad_path = job_data.get('final_ad_path')
        if not final_ad_path or not os.path.exists(final_ad_path):
            current_app.logger.error(f"Final ad path not found for job {operation_name}")
            return jsonify({"error": "File not found on server"}), 404

        @after_this_request
        def cleanup(response):
            cleanup_temp_files(final_ad_path)
            try:
                del job_store[operation_name]
                current_app.logger.info(f"Cleaned up job store for {operation_name}")
            except KeyError:
                pass
            return response

        return send_file(
            final_ad_path,
            as_attachment=True,
            download_name='generated_ad.mp4',
            mimetype='video/mp4'
        )

    except Exception as e:
        current_app.logger.exception(f"Error in /ads/download-video for op {operation_name}: {e}")
        return jsonify({"error": "Failed to download video"}), 500
