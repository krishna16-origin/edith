from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException
from uuid import UUID
import structlog
import base64
import io

from app.auth import validate_session
from app.core.config import settings
from app.services.orchestrator import orchestrator
from app.storage.local_store import session_store

logger = structlog.get_logger()
router = APIRouter(prefix="/api/voice", tags=["voice"])


@router.websocket("/ws/{session_id}")
async def voice_websocket(
    websocket: WebSocket,
    session_id: str,
):
    await websocket.accept()
    
    session = await validate_session(session_id)
    if not session:
        await websocket.send_json({"type": "error", "content": "Invalid session"})
        await websocket.close()
        return
    
    logger.info("voice_ws_connected", session_id=session_id, user_id=str(session.user_id))
    
    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")
            
            if msg_type == "audio_start":
                await websocket.send_json({"type": "ready", "config": {
                    "stt_model": settings.VOICE_STT_MODEL,
                    "tts_model": settings.VOICE_TTS_MODEL,
                    "tts_voice": settings.VOICE_TTS_VOICE,
                }})
            
            elif msg_type == "audio_chunk":
                audio_b64 = data.get("audio")
                if audio_b64:
                    audio_bytes = base64.b64decode(audio_b64)
                    await process_audio_stream(websocket, session.user_id, session_id, audio_bytes)
            
            elif msg_type == "audio_end":
                await websocket.send_json({"type": "processing"})
            
            elif msg_type == "text":
                text = data.get("text", "")
                async for chunk in orchestrator.process_message(
                    user_id=session.user_id,
                    message=text,
                    session_id=session_id,
                    stream=True
                ):
                    if chunk.get("type") == "token":
                        await websocket.send_json({"type": "token", "content": chunk["content"]})
                    elif chunk.get("type") == "complete":
                        await websocket.send_json({"type": "complete", "data": chunk["data"]})
            
            elif msg_type == "ping":
                await websocket.send_json({"type": "pong"})
    
    except WebSocketDisconnect:
        logger.info("voice_ws_disconnected", session_id=session_id)
    except Exception as e:
        logger.error("voice_ws_error", session_id=session_id, error=str(e))
        await websocket.send_json({"type": "error", "content": str(e)})


async def process_audio_stream(websocket: WebSocket, user_id: UUID, session_id: str, audio_bytes: bytes):
    if not settings.OPENAI_API_KEY:
        await websocket.send_json({"type": "error", "content": "Voice requires OPENAI_API_KEY for STT/TTS"})
        return
    
    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    
    try:
        audio_file = io.BytesIO(audio_bytes)
        audio_file.name = "audio.webm"
        
        transcript = await client.audio.transcriptions.create(
            model=settings.VOICE_STT_MODEL,
            file=audio_file,
            response_format="text",
        )
        
        await websocket.send_json({"type": "transcript", "text": transcript})
        
        async for chunk in orchestrator.process_message(
            user_id=user_id,
            message=transcript,
            session_id=session_id,
            stream=True
        ):
            if chunk.get("type") == "token":
                await websocket.send_json({"type": "token", "content": chunk["content"]})
            elif chunk.get("type") == "complete":
                response_text = chunk["data"].get("response", "")
                
                if response_text:
                    tts_response = await client.audio.speech.create(
                        model=settings.VOICE_TTS_MODEL,
                        voice=settings.VOICE_TTS_VOICE,
                        input=response_text,
                        response_format="mp3",
                    )
                    
                    audio_b64 = base64.b64encode(tts_response.content).decode()
                    await websocket.send_json({
                        "type": "audio",
                        "audio": audio_b64,
                        "format": "mp3",
                    })
                
                await websocket.send_json({"type": "complete", "data": chunk["data"]})
    
    except Exception as e:
        logger.error("voice_processing_error", error=str(e))
        await websocket.send_json({"type": "error", "content": str(e)})


@router.post("/config")
async def get_voice_config():
    return {
        "stt_model": settings.VOICE_STT_MODEL,
        "tts_model": settings.VOICE_TTS_MODEL,
        "tts_voice": settings.VOICE_TTS_VOICE,
        "sample_rate": 24000,
    }