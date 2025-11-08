from __future__ import annotations

import os
import sys
import json
import time
import io
import base64
import tempfile
import logging
import argparse
import shutil
import requests
from pathlib import Path
from flask import Blueprint, request, jsonify, current_app, send_file, after_this_request
from PIL import Image
from dotenv import load_dotenv


def _logger() -> logging.Logger:
    try:
        return current_app.logger
    except Exception:
        return logging.getLogger("ad_gen")


logging.getLogger("ad_gen").setLevel(logging.INFO)
def _ensure_site_packages():
    """Add local virtualenv site-packages to sys.path when running outside the venv."""

    project_root = Path(__file__).resolve().parents[2]
    python_version = f"python{sys.version_info.major}{sys.version_info.minor}"

    candidates = [
        project_root / ".venv" / "Lib" / "site-packages",
        project_root / ".venv" / "lib" / python_version / "site-packages",
    ]

    for candidate in candidates:
        if candidate.exists() and str(candidate) not in sys.path:
            sys.path.insert(0, str(candidate))


_ensure_site_packages()
load_dotenv()

def _configure_ffmpeg() -> Path | None:
    """Ensure MoviePy can locate an ffmpeg binary for video processing."""

    existing = os.getenv("IMAGEIO_FFMPEG_EXE") or os.getenv("FFMPEG_BINARY")
    if existing and Path(existing).is_file():
        return Path(existing)

    candidates = []
    script_dir = Path(__file__).resolve().parent
    candidates.append(script_dir / "bin" / ("ffmpeg.exe" if os.name == "nt" else "ffmpeg"))
    candidates.append(script_dir / ("ffmpeg.exe" if os.name == "nt" else "ffmpeg"))
    candidates.append(Path.cwd() / "bin" / ("ffmpeg.exe" if os.name == "nt" else "ffmpeg"))

    for candidate in candidates:
        if candidate.is_file():
            os.environ.setdefault("IMAGEIO_FFMPEG_EXE", str(candidate))
            os.environ.setdefault("FFMPEG_BINARY", str(candidate))
            return candidate

    return Path(existing) if existing else None


_FFMPEG_PATH = _configure_ffmpeg()

try:
    from moviepy import VideoFileClip, AudioFileClip
    from moviepy.audio.fx import AudioLoop
    if _FFMPEG_PATH:
        try:
            from moviepy.config import change_settings

            change_settings({"FFMPEG_BINARY": str(_FFMPEG_PATH)})
        except ImportError:
            pass
except ImportError as moviepy_err:
    print(f"Import error: moviepy not available; video merge disabled ({moviepy_err!r})")
    VideoFileClip = None
    AudioFileClip = None
    AudioLoop = None

try:
    import google.genai as genai
    from google.genai import types as genai_types
except ImportError:
    import google.generativeai as genai
    from google.generativeai import types as genai_types


_HAS_GENAI_GENERATIVE_MODEL = hasattr(genai, "GenerativeModel")
_HAS_GENAI_CONFIGURE = hasattr(genai, "configure")
_HAS_GENAI_CLIENT = hasattr(genai, "Client")

ad_gen_bp = Blueprint('ad_gen_bp', __name__, url_prefix='/ads')

media_client = None
genai_llm = None

job_store = {}

VEO_MODEL = "veo-3.1-generate-preview"
LYRIA_MODEL = "lyria-2.0-preview"
IMAGE_MODEL = "gemini-2.5-flash-image"
LLM_MODEL = "gemini-2.5-flash-preview-09-2025"


def _resolve_video_duration() -> int:
    raw_value = os.getenv("AD_VIDEO_DURATION", "6")
    try:
        value = int(raw_value)
    except ValueError:
        value = 6

    if value < 4 or value > 8:
        _logger().warning(
            "Requested video duration %s out of bounds (4-8); clamping.", raw_value
        )
    return max(4, min(8, value))


VIDEO_DURATION_SECONDS = _resolve_video_duration()

def init_ad_gen_services(app: object | None = None) -> None:
    global media_client, genai_llm
    _logger().info("Initializing Ad Generation Services (Google)...")
    try:
        GOOGLE_API_KEY = os.getenv('VITE_GOOGLE_API_KEY') or os.getenv('GOOGLE_API_KEY')
        if not GOOGLE_API_KEY:
            raise ValueError("GOOGLE_API_KEY not set in environment or .env file")

        client_instance = None
        if _HAS_GENAI_CLIENT:
            client_instance = genai.Client(api_key=GOOGLE_API_KEY)
            media_client = client_instance
        else:
            media_client = None

        if _HAS_GENAI_GENERATIVE_MODEL:
            if _HAS_GENAI_CONFIGURE:
                genai.configure(api_key=GOOGLE_API_KEY)
            genai_llm = genai.GenerativeModel(LLM_MODEL)
        elif client_instance:
            genai_llm = client_instance
        else:
            raise RuntimeError("Installed google-genai library does not expose a usable client")

        if media_client is None:
            _logger().warning("Media client unavailable; video/image generation may be disabled")

        _logger().info("Google GenAI Clients initialized successfully.")
    except Exception as e:
        _logger().error(f"Error initializing Google clients: {e}")


def ensure_ad_gen_clients() -> None:
    """Initialize API clients when running outside the Flask lifecycle."""

    if media_client and genai_llm:
        return

    _logger().info("Ad generation clients not initialized; attempting standalone setup.")
    init_ad_gen_services(None)


def _build_operation_resource(name: str, *, kind: str = "generic"):
    if kind == "video" and hasattr(genai_types, "GenerateVideosOperation"):
        return genai_types.GenerateVideosOperation(name=name)
    if hasattr(genai_types, "Operation"):
        return genai_types.Operation(name=name)
    return name


def _call_operations_get(resource):
    if isinstance(resource, str):
        return media_client.operations.get(resource)
    return media_client.operations.get(resource)


def generate_prompts_for_idea(idea: str) -> dict[str, str]:
    ensure_ad_gen_clients()

    if not genai_llm:
        raise RuntimeError("LLM client not initialized")

    system_prompt = f"""
    You are a world-class creative director for a marketing agency.
    A user will provide a startup idea. Your job is to generate two distinct prompts for AI models, formatted as a JSON object.
    1. "video_prompt": A {VIDEO_DURATION_SECONDS}-second, visually descriptive video prompt for Veo 3.1. It should describe scenes, camera movements, and any spoken dialogue (e.g., "Man says: 'This is amazing!'").
    2. "music_prompt": A prompt for Lyria (music model) describing the background music for a {VIDEO_DURATION_SECONDS}-second ad (e.g., "upbeat, hopeful, electronic track").

    Ensure the JSON is valid.
    """

    response_schema = {
        "type": "OBJECT",
        "properties": {
            "video_prompt": {"type": "STRING"},
            "music_prompt": {"type": "STRING"}
        },
        "required": ["video_prompt", "music_prompt"]
    }

    if _HAS_GENAI_GENERATIVE_MODEL:
        generation_config = genai_types.GenerationConfig(
            response_mime_type="application/json",
            response_schema=response_schema
        )

        llm_with_schema = genai.GenerativeModel(
            LLM_MODEL,
            generation_config=generation_config,
            system_instruction=system_prompt
        )

        response = llm_with_schema.generate_content(idea)
        payload = response.text
    else:
        if not hasattr(genai_llm, "models"):
            raise RuntimeError("Google GenAI client does not expose model endpoints")

        config = genai_types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=response_schema,
            system_instruction=system_prompt
        )
        response = genai_llm.models.generate_content(
            model=LLM_MODEL,
            contents=idea,
            config=config
        )
        payload = response.text if hasattr(response, "text") else response.candidates[0].content.parts[0].text

    return json.loads(payload)


def generate_image_base64(prompt: str) -> str:
    ensure_ad_gen_clients()

    if not media_client:
        raise RuntimeError("Media client not initialized")

    config = genai_types.GenerateContentConfig(  # type: ignore[attr-defined]
        response_modalities=["IMAGE"]
    ) if hasattr(genai_types, "GenerateContentConfig") else {"response_modalities": ["IMAGE"]}

    image_response = media_client.models.generate_content(
        model=IMAGE_MODEL,
        contents=prompt,
        config=config
    )

    pil_image = image_response.parts[0].as_image()
    buf = io.BytesIO()
    pil_image.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")

def merge_ad(video_path, music_path, video_duration):
    if not VideoFileClip or not AudioLoop:
        _logger().error("MoviePy is not imported. Cannot merge files.")
        raise ImportError("MoviePy library not found")

    if _FFMPEG_PATH:
        _logger().debug(f"Using ffmpeg at {_FFMPEG_PATH}")

    video_clip = None
    audio_clip = None
    final_clip = None
    try:
        _logger().info(f"Merging video {video_path} and audio {music_path}")
        video_clip = VideoFileClip(video_path)
        audio_clip = AudioFileClip(music_path)

        if audio_clip.duration > video_duration:
            audio_clip = audio_clip.subclip(0, video_duration)
        elif audio_clip.duration < video_duration:
            audio_clip = audio_clip.with_effects([AudioLoop(duration=video_duration)])
        
        final_clip = video_clip.set_audio(audio_clip)

        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as temp_final:
            final_path = temp_final.name
            _logger().info(f"Writing merged file to {final_path}")
            final_clip.write_videofile(final_path, codec="libx264", audio_codec="aac", bitrate="5000k", preset="medium", logger=None)
        
        return final_path
    except Exception as e:
        _logger().exception(f"Error during video/audio merge: {e}")
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
                _logger().info(f"Cleaned up temp file: {f}")
            except Exception as e:
                _logger().warning(f"Failed to clean up temp file {f}: {e}")

def start_ad_generation_jobs(video_prompt, music_prompt, image=None):
    ensure_ad_gen_clients()

    if not media_client:
        _logger().error("Media client not initialized")
        raise Exception("Media client not initialized")

    _logger().info("Starting Veo job...")
    if _HAS_GENAI_GENERATIVE_MODEL:
        video_args = {
            "model": VEO_MODEL,
            "prompt": video_prompt,
            "duration_seconds": VIDEO_DURATION_SECONDS
        }
    else:
        video_args = {
            "model": VEO_MODEL,
            "prompt": video_prompt,
            "config": {"durationSeconds": VIDEO_DURATION_SECONDS}
        }
    if image:
        video_args["image"] = image
        
    video_operation = media_client.models.generate_videos(**video_args)
    op_container = getattr(video_operation, "operation", None)
    video_op_name = None
    if op_container is not None:
        if isinstance(op_container, dict):
            video_op_name = op_container.get("name")
        elif hasattr(op_container, "name"):
            video_op_name = op_container.name
        else:
            video_op_name = op_container
    if not video_op_name and hasattr(video_operation, "name"):
        video_op_name = video_operation.name

    if not video_op_name:
        raise RuntimeError("Video generation did not return an operation name")

    video_operation_resource = _build_operation_resource(video_op_name, kind="video")

    _logger().info(f"Veo job started. Operation name: {video_op_name}")

    music_op_name = None
    music_operation_resource = None
    if music_prompt:
        try:
            _logger().info("Starting Lyria job...")
            if hasattr(media_client.models, "generate_music"):
                music_operation = media_client.models.generate_music(
                    model=LYRIA_MODEL,
                    prompt=music_prompt,
                    duration_seconds=VIDEO_DURATION_SECONDS
                )
                music_container = getattr(music_operation, "operation", None)
                if music_container is not None:
                    if isinstance(music_container, dict):
                        music_op_name = music_container.get("name")
                    elif hasattr(music_container, "name"):
                        music_op_name = music_container.name
                    else:
                        music_op_name = music_container
                elif hasattr(music_operation, "name"):
                    music_op_name = music_operation.name

                if music_op_name:
                    music_operation_resource = _build_operation_resource(music_op_name)
            else:
                _logger().warning("Music generation not supported by current Google GenAI SDK; skipping audio track")
                music_op_name = None
            _logger().info(f"Lyria job started. Operation name: {music_op_name}")
        except Exception as e:
            _logger().error(f"Failed to start Lyria job, continuing with video only: {e}")
            music_op_name = None
    
    job_data = {
        'video_prompt': video_prompt,
        'video_op_name': video_op_name,
        'video_operation': video_operation_resource,
        'video_status': 'processing',
        'final_status': 'processing',
        'created_at': time.time(),
        'has_image_input': (image is not None)
    }
    if music_op_name:
        job_data['music_prompt'] = music_prompt
        job_data['music_op_name'] = music_op_name
        if music_operation_resource is None:
            music_operation_resource = _build_operation_resource(music_op_name)
        job_data['music_operation'] = music_operation_resource
        job_data['music_status'] = 'processing'
    else:
        job_data['music_status'] = 'skipped'
        
    job_store[video_op_name] = job_data
    
    return video_op_name


def _refresh_job_status(operation_name: str) -> dict:
    if not media_client:
        raise RuntimeError("Media client not initialized")

    job_data = job_store.get(operation_name)
    if not job_data:
        raise KeyError(operation_name)

    final_status = job_data.get('final_status')
    if final_status in ['complete', 'failed']:
        return job_data

    video_status = job_data.get('video_status')
    music_status = job_data.get('music_status')

    if video_status == 'processing':
        video_op_name = job_data.get('video_op_name')
        _logger().info(f"Polling Veo op: {video_op_name}")
        video_operation_resource = job_data.get('video_operation')
        if not video_operation_resource:
            video_operation_resource = _build_operation_resource(video_op_name, kind="video")
            job_data['video_operation'] = video_operation_resource

        video_op_raw = _call_operations_get(video_operation_resource)
        video_op = getattr(video_op_raw, "operation", video_op_raw)

        if video_op.done:
            error_obj = getattr(video_op, "error", None)
            if error_obj:
                message = getattr(error_obj, "message", str(error_obj))
                _logger().error(f"Veo job {video_op_name} failed: {message}")
                job_data['video_status'] = 'failed'
                job_data['final_status'] = 'failed'
                job_data['error_message'] = f"Video generation failed: {message}"
            else:
                _logger().info(f"Veo job {video_op_name} complete. Downloading...")
                response_obj = getattr(video_op, "response", video_op)
                generated_videos = getattr(response_obj, "generated_videos", None)
                if not generated_videos:
                    raise RuntimeError("Veo response did not include generated videos")
                primary_video_container = generated_videos[0]
                primary_video = getattr(primary_video_container, "video", primary_video_container)

                with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as temp_video:
                    video_uri = getattr(primary_video, "uri", None)
                    video_bytes = getattr(primary_video, "video_bytes", None)

                    if video_bytes:
                        temp_video.write(video_bytes)
                        temp_video.flush()
                    elif video_uri:
                        _logger().info(f"Downloading video from {video_uri}")
                        GOOGLE_API_KEY = os.getenv('VITE_GOOGLE_API_KEY') or os.getenv('GOOGLE_API_KEY')
                        headers = {}
                        if GOOGLE_API_KEY:
                            headers['x-goog-api-key'] = GOOGLE_API_KEY
                        resp = requests.get(video_uri, headers=headers, stream=True, timeout=300)
                        resp.raise_for_status()
                        for chunk in resp.iter_content(chunk_size=8192):
                            temp_video.write(chunk)
                        temp_video.flush()
                    elif hasattr(primary_video, "save"):
                        primary_video.save(temp_video.name)
                    else:
                        raise RuntimeError("Video object has no usable data or save method")

                    temp_video_path = temp_video.name

                job_data['video_status'] = 'downloaded'
                job_data['video_temp_path'] = temp_video_path
                _logger().info(f"Veo video saved to {temp_video_path}")

    if music_status == 'processing' and hasattr(media_client.models, "generate_music"):
        music_op_name = job_data.get('music_op_name')
        _logger().info(f"Polling Lyria op: {music_op_name}")
        music_operation_resource = job_data.get('music_operation')
        if not music_operation_resource:
            music_operation_resource = _build_operation_resource(music_op_name)
            job_data['music_operation'] = music_operation_resource

        music_op_raw = _call_operations_get(music_operation_resource)
        music_op = getattr(music_op_raw, "operation", music_op_raw)

        if music_op.done:
            error_obj = getattr(music_op, "error", None)
            if error_obj:
                message = getattr(error_obj, "message", str(error_obj))
                _logger().error(f"Lyria job {music_op_name} failed: {message}")
                job_data['music_status'] = 'failed'
            else:
                _logger().info(f"Lyria job {music_op_name} complete. Downloading...")
                response_obj = getattr(music_op, "response", music_op)
                generated_music = getattr(response_obj, "generated_music", None)
                if not generated_music:
                    _logger().warning("Music response missing generated_music; marking as failed")
                    job_data['music_status'] = 'failed'
                else:
                    music_container = generated_music[0]
                    music_asset = getattr(music_container, "music", music_container)

                    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_music:
                        audio_uri = getattr(music_asset, "uri", None)
                        audio_bytes = getattr(music_asset, "audio_bytes", None) or getattr(music_asset, "music_bytes", None)

                        if audio_bytes:
                            temp_music.write(audio_bytes)
                        elif audio_uri:
                            _logger().info(f"Downloading audio from {audio_uri}")
                            GOOGLE_API_KEY = os.getenv('VITE_GOOGLE_API_KEY') or os.getenv('GOOGLE_API_KEY')
                            headers = {}
                            if GOOGLE_API_KEY:
                                headers['x-goog-api-key'] = GOOGLE_API_KEY
                            resp = requests.get(audio_uri, headers=headers, stream=True, timeout=300)
                            resp.raise_for_status()
                            for chunk in resp.iter_content(chunk_size=8192):
                                temp_music.write(chunk)
                        elif hasattr(music_asset, "save"):
                            music_asset.save(temp_music.name)
                        else:
                            _logger().warning("Music object has no usable data or save method; marking as failed")
                            job_data['music_status'] = 'failed'
                            return job_data

                        job_data['music_status'] = 'downloaded'
                        job_data['music_temp_path'] = temp_music.name
                        _logger().info(f"Lyria music saved to {temp_music.name}")

    video_status = job_data.get('video_status')
    music_status = job_data.get('music_status')

    if (video_status == 'downloaded' and
            music_status in ['downloaded', 'skipped', 'failed']):

        job_data['final_status'] = 'merging'
        video_path = job_data.get('video_temp_path')
        music_path = job_data.get('music_temp_path')

        try:
            if music_path and os.path.exists(music_path):
                final_ad_path = merge_ad(video_path, music_path, VIDEO_DURATION_SECONDS)
            else:
                final_ad_path = video_path

            job_data['final_ad_path'] = final_ad_path
            job_data['final_status'] = 'complete'

            cleanup_temp_files(video_path, music_path)
            if music_path and final_ad_path != video_path:
                cleanup_temp_files(video_path)

        except Exception as e:
            job_data['final_status'] = 'failed'
            job_data['error_message'] = f"Ad merging failed: {str(e)}"
            cleanup_temp_files(video_path, music_path)

    return job_data


def _poll_job_until_complete(operation_name: str, poll_interval: int = 15, timeout: int = 900) -> dict:
    deadline = time.time() + timeout if timeout else None

    while True:
        job_data = _refresh_job_status(operation_name)
        final_status = job_data.get('final_status')

        if final_status == 'complete':
            return job_data
        if final_status == 'failed':
            raise RuntimeError(job_data.get('error_message') or "Video generation failed")

        if deadline and time.time() > deadline:
            raise TimeoutError("Video generation timed out")

        time.sleep(poll_interval)

@ad_gen_bp.route('/generate-prompt', methods=['POST'])
def generate_prompt():
    data = request.json or {}
    if 'idea' not in data:
        return jsonify({"error": "Missing 'idea' in request body"}), 400

    try:
        prompt_data = generate_prompts_for_idea(data['idea'])
        return jsonify(prompt_data), 200
    except RuntimeError as err:
        _logger().error(str(err))
        return jsonify({"error": str(err)}), 500
    except Exception as e:
        _logger().exception(f"Error in /ads/generate-prompt: {e}")
        return jsonify({"error": f"Failed to generate prompt: {str(e)}"}), 500

@ad_gen_bp.route('/generate-image', methods=['POST'])
def generate_image_api():
    data = request.json or {}
    if 'prompt' not in data:
        return jsonify({"error": "Missing 'prompt' in request body"}), 400

    try:
        _logger().info(f"Generating image with prompt: {data['prompt'][:50]}...")
        img_b64 = generate_image_base64(data['prompt'])
        _logger().info("Image generated successfully.")
        return jsonify({"image_b64": img_b64}), 200
    except RuntimeError as err:
        _logger().error(str(err))
        return jsonify({"error": str(err)}), 500
    except Exception as e:
        _logger().exception(f"Error in /ads/generate-image: {e}")
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
        _logger().exception(f"Error in /ads/generate-video-text: {e}")
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
        _logger().exception(f"Error in /ads/generate-video-image: {e}")
        return jsonify({"error": f"Failed to start video generation: {str(e)}"}), 500

@ad_gen_bp.route('/video-status/<operation_name>', methods=['GET'])
def get_video_status(operation_name):
    try:
        job_data = _refresh_job_status(operation_name)

        final_status = job_data.get('final_status')
        if final_status == 'complete':
            return jsonify({"status": "complete"}), 200
        if final_status == 'failed':
            return jsonify({"status": "failed", "error": job_data.get("error_message")}), 200
        if final_status == 'merging':
            return jsonify({"status": "merging"}), 200

        return jsonify({"status": "processing"}), 200
    except KeyError:
        _logger().warning(f"Job not found in local store: {operation_name}")
        return jsonify({"error": "Job not found or server restarted"}), 404
    except Exception as e:
        _logger().exception(f"Error in /ads/video-status for op {operation_name}: {e}")
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
            _logger().error(f"Final ad path not found for job {operation_name}")
            return jsonify({"error": "File not found on server"}), 404

        @after_this_request
        def cleanup(response):
            cleanup_temp_files(final_ad_path)
            try:
                del job_store[operation_name]
                _logger().info(f"Cleaned up job store for {operation_name}")
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
        _logger().exception(f"Error in /ads/download-video for op {operation_name}: {e}")
        return jsonify({"error": "Failed to download video"}), 500


def _build_cli_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Standalone helpers for ad generation utilities")
    subparsers = parser.add_subparsers(dest="command")

    prompts_parser = subparsers.add_parser("prompts", help="Generate Veo and Lyria prompts from an idea")
    prompts_parser.add_argument("idea", help="Startup idea or marketing concept")

    image_parser = subparsers.add_parser("image", help="Generate an image and save to disk")
    image_parser.add_argument("prompt", help="Text prompt describing the desired hero image")
    image_parser.add_argument("--output", default="generated_image.png", help="Path to save the PNG output")
    image_parser.add_argument("--show-b64", action="store_true", help="Print the base64 output to stdout")

    video_parser = subparsers.add_parser("video", help="Generate a short video ad and save the MP4")
    video_parser.add_argument("--video-prompt", required=True, help="Prompt describing the Veo video")
    video_parser.add_argument("--music-prompt", help="Optional prompt for the music track")
    video_parser.add_argument("--image", help="Optional path to an image to guide the video")
    video_parser.add_argument("--output", default="generated_ad.mp4", help="Path to save the final MP4")
    video_parser.add_argument("--poll-interval", type=int, default=20, help="Seconds between status checks")
    video_parser.add_argument("--timeout", type=int, default=900, help="Max seconds to wait before giving up (0 for no timeout)")

    return parser


def _run_cli() -> None:
    parser = _build_cli_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    try:
        if args.command == "prompts":
            prompts = generate_prompts_for_idea(args.idea)
            print(json.dumps(prompts, indent=2))
            return

        if args.command == "image":
            img_b64 = generate_image_base64(args.prompt)
            if args.show_b64:
                print(img_b64)
            output_path = Path(args.output)
            output_path.write_bytes(base64.b64decode(img_b64))
            print(f"Saved image to {output_path.resolve()}")
            return

        if args.command == "video":
            image_input = None
            if args.image:
                with Image.open(args.image) as img_source:
                    image_input = img_source.copy()

            operation_name = start_ad_generation_jobs(
                video_prompt=args.video_prompt,
                music_prompt=args.music_prompt,
                image=image_input
            )

            print(f"Started Veo operation {operation_name}; polling for completion...")
            job_data = _poll_job_until_complete(
                operation_name,
                poll_interval=args.poll_interval,
                timeout=args.timeout
            )

            final_ad_path = job_data.get('final_ad_path')
            if not final_ad_path or not os.path.exists(final_ad_path):
                raise RuntimeError("Video reported complete but file is missing")

            output_path = Path(args.output)
            shutil.copyfile(final_ad_path, output_path)
            print(f"Saved video to {output_path.resolve()}")

            cleanup_temp_files(final_ad_path)
            try:
                del job_store[operation_name]
            except KeyError:
                pass
            return
    except Exception as exc:  # pragma: no cover - CLI convenience
        parser.exit(status=1, message=f"Error: {exc}\n")

    parser.error(f"Unknown command {args.command}")


if __name__ == "__main__":
    _run_cli()
