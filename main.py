import os
import requests
import json
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from dotenv import load_dotenv
import uvicorn

# Load environment variables from .env
load_dotenv()
API_KEY = os.getenv("AI_BUILDER_API_KEY") or os.getenv("AI_BUILDER_TOKEN")
API_BASE_URL = os.getenv("API_GATEWAY_URL", "https://space.ai-builders.com/backend/v1")

# Initialize FastAPI application
app = FastAPI(
    title="SuperMind Engine - Phase A & B Agentic Core",
    description="Agentic Engine with Tool Calling, Multi-Step Reasoning, Web GUI, and Aha Catcher Ambient MVP",
    version="0.2.0"
)

# Mount static folder for Web GUI and Ambient Simulator
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/gui")
def redirect_to_gui():
    """Redirect /gui to the standalone ChatGPT-style Web UI."""
    return RedirectResponse(url="/static/index.html")

@app.get("/ambient")
def redirect_to_ambient():
    """Redirect /ambient to the Aha Catcher Ambient Web MVP Simulator."""
    return RedirectResponse(url="/static/ambient.html")


# Define Request / Response Models
class ChatRequest(BaseModel):
    prompt: str
    model: Optional[str] = "grok-4-fast"
    image_data: Optional[str] = None

class ToolExecutionTrace(BaseModel):
    tool_name: str
    arguments: Dict[str, Any]
    output_snippet: str

class ChatResponse(BaseModel):
    reply: str
    tool_calls_executed: Optional[List[ToolExecutionTrace]] = []

# Tool 1 Definition: Web Search API Function
def web_search(query: str) -> str:
    """Executes a real-time web search via AI Builder Space API Gateway."""
    search_url = "https://space.ai-builders.com/backend/v1/search/"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "keywords": [query],
        "max_results": 3
    }
    try:
        res = requests.post(search_url, json=payload, headers=headers, timeout=25)
        if res.status_code == 200:
            data = res.json()
            # Format snippets into readable text for the LLM
            if isinstance(data, list):
                snippets = []
                for idx, item in enumerate(data, 1):
                    title = item.get("title", "No Title")
                    snippet = item.get("snippet") or item.get("content") or str(item)
                    snippets.append(f"[{idx}] {title}: {snippet}")
                return "\n".join(snippets)
            return json.dumps(data)
        return f"Search failed with status code {res.status_code}: {res.text}"
    except Exception as e:
        return f"Search error: {str(e)}"

# OpenAPI Tool Definition Schema for LLM
WEB_SEARCH_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": "Perform real-time web search for current events, weather, stock prices, breaking news, or unknown facts.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query string (e.g. 'Toronto weather today', 'NVIDIA stock price')"
                }
            },
            "required": ["query"]
        }
    }
}

# Tool 2 Definition: Page Reader Function
def read_page(url: str) -> str:
    """Fetch URL and extract main clean text content from HTML."""
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(res.text, "html.parser")
            for elem in soup(["script", "style", "nav", "header", "footer", "svg", "iframe"]):
                elem.decompose()
            text = soup.get_text(separator=" ", strip=True)
            return text[:4000] if text else "Page returned empty text."
        return f"Failed to fetch URL {url}: HTTP status {res.status_code}"
    except Exception as e:
        return f"Error reading page {url}: {str(e)}"

READ_PAGE_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "read_page",
        "description": "Fetch and read full main text content from a web page URL when search snippets are not detailed enough.",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The exact target web page HTTP/HTTPS URL to read"
                }
            },
            "required": ["url"]
        }
    }
}

ALL_TOOLS_SCHEMAS = [WEB_SEARCH_TOOL_SCHEMA, READ_PAGE_TOOL_SCHEMA]

# Chapter 2: Direct Passthrough Chat Endpoint
@app.post("/chat", response_model=ChatResponse)
def direct_chat(req: ChatRequest):
    """Direct passthrough LLM chat endpoint without tool calling."""
    if not API_KEY:
        raise HTTPException(status_code=500, detail="AI_BUILDER_API_KEY not configured in .env file.")

    url = "https://space.ai-builders.com/backend/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": req.model or "grok-4-fast",
        "messages": [{"role": "user", "content": req.prompt}]
    }

    try:
        res = requests.post(url, json=payload, headers=headers, timeout=30)
        if res.status_code != 200:
            raise HTTPException(status_code=res.status_code, detail=f"LLM API Error: {res.text}")
        
        reply_text = res.json()["choices"][0]["message"]["content"]
        return ChatResponse(reply=reply_text, tool_calls_executed=[])
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Chapter 3: Full Agentic Loop Endpoint with Tool Calling & Logging
@app.post("/agent/chat", response_model=ChatResponse)
def agentic_chat(req: ChatRequest):
    """Agentic endpoint with autonomous tool calling and 3-turn multi-step reasoning loop."""
    if not API_KEY:
        raise HTTPException(status_code=500, detail="AI_BUILDER_API_KEY not configured in .env file.")

    url = "https://space.ai-builders.com/backend/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }

    messages = [{"role": "user", "content": req.prompt}]
    executed_traces = []
    max_turns = 3

    print(f"\n>>> [Agentic Loop Started] User Prompt: '{req.prompt}'")

    for turn in range(max_turns):
        payload = {
            "model": req.model or "grok-4-fast",
            "messages": messages,
            "tools": ALL_TOOLS_SCHEMAS
        }

        try:
            res = requests.post(url, json=payload, headers=headers, timeout=30)
            if res.status_code != 200:
                raise HTTPException(status_code=res.status_code, detail=f"LLM API Error ({res.status_code}): {res.text}")
        except requests.exceptions.Timeout:
            raise HTTPException(status_code=504, detail="Connection to AI Gateway timed out (30s limit). The upstream model may be busy. Please resubmit your message.")
        except requests.exceptions.RequestException as req_err:
            raise HTTPException(status_code=502, detail=f"Network error connecting to AI Gateway: {str(req_err)}")

        msg_data = res.json()["choices"][0]["message"]
        tool_calls = msg_data.get("tool_calls")

        if tool_calls:
            # LLM requested a tool execution!
            messages.append(msg_data)

            for call in tool_calls:
                fn_name = call["function"]["name"]
                args_raw = call["function"]["arguments"]
                args = json.loads(args_raw) if isinstance(args_raw, str) else args_raw

                if fn_name == "web_search":
                    query_str = args.get("query", req.prompt)
                    print(f"  [Agent Turn {turn+1}] Decided to call tool: 'web_search' with query: '{query_str}'")
                    raw_result = web_search(query_str)
                    clean_snippet = raw_result.encode('ascii', 'ignore').decode('ascii')[:150]
                    print(f"  [System] Tool Output Snippet: {clean_snippet}...")

                    messages.append({
                        "role": "tool",
                        "tool_call_id": call["id"],
                        "content": raw_result
                    })

                    executed_traces.append(ToolExecutionTrace(
                        tool_name="web_search",
                        arguments={"keywords": [query_str]},
                        output_snippet=raw_result[:250] + ("..." if len(raw_result) > 250 else "")
                    ))

                elif fn_name == "read_page":
                    target_url = args.get("url", "")
                    print(f"  [Agent Turn {turn+1}] Decided to call tool: 'read_page' with URL: '{target_url}'")
                    raw_result = read_page(target_url)
                    clean_snippet = raw_result.encode('ascii', 'ignore').decode('ascii')[:150]
                    print(f"  [System] Page Content Snippet: {clean_snippet}...")

                    messages.append({
                        "role": "tool",
                        "tool_call_id": call["id"],
                        "content": raw_result
                    })

                    executed_traces.append(ToolExecutionTrace(
                        tool_name="read_page",
                        arguments={"url": target_url},
                        output_snippet=raw_result[:250] + ("..." if len(raw_result) > 250 else "")
                    ))
        else:
            # LLM provided final answer!
            final_text = msg_data.get("content", "")
            messages.append({"role": "assistant", "content": final_text})

            # Print Full Log Detective Forensics Trail (as specified in "Manually Debugging the Agent's Mind")
            print("\n" + "="*60)
            print("LOG DETECTIVE FORENSICS - Complete Chain of Thought History:")
            print("="*60)
            for idx, msg in enumerate(messages, 1):
                role = msg.get("role")
                if role == "user":
                    print(f"1. [User Message]: {msg.get('content')}")
                elif role == "assistant" and msg.get("tool_calls"):
                    calls_summary = [f"{c['function']['name']}({c['function']['arguments']})" for c in msg.get("tool_calls")]
                    print(f"2. [Assistant Tool Calls]: {calls_summary}")
                elif role == "tool":
                    snippet = msg.get('content', '').encode('ascii', 'ignore').decode('ascii')[:200]
                    print(f"3. [Tool Result ({msg.get('tool_call_id')})]: {snippet}...")
                elif role == "assistant" and msg.get("content"):
                    snippet = msg.get('content', '').encode('ascii', 'ignore').decode('ascii')[:200]
                    print(f"4. [Final Assistant Message]: {snippet}...")
            print("="*60 + "\n")

            return ChatResponse(reply=final_text, tool_calls_executed=executed_traces)

    # Fallback if max_turns reached
    final_text = messages[-1].get("content", "Completed max reasoning loops.")
    return ChatResponse(reply=final_text, tool_calls_executed=executed_traces)

# ==============================================================================
# Phase B: Pillar 1 — Aha Catcher Ambient Audio Capture Endpoint
# ==============================================================================
class AmbientCaptureResponse(BaseModel):
    transcript: str
    summary: str

@app.post("/api/ambient/capture", response_model=AmbientCaptureResponse)
async def ambient_capture(file: UploadFile = File(...)):
    """
    Aha Catcher MVP Endpoint:
    1. Receives 30-second rolling audio buffer from browser.
    2. Transcribes audio via Grok/Whisper STT.
    3. Triggers Agentic Reasoning + Web Search loop to synthesize a research summary.
    4. Returns clean transcript and summary.
    """
    if not API_KEY:
        raise HTTPException(status_code=500, detail="AI_BUILDER_API_KEY / AI_BUILDER_TOKEN is not configured.")

    try:
        audio_bytes = await file.read()
        if not audio_bytes or len(audio_bytes) < 100:
            return AmbientCaptureResponse(
                transcript="(No audio detected)",
                summary="Audio buffer was empty or too short. Please speak an idea and click Capture Aha! again."
            )

        # Step 1: Transcribe via AI Builder Space STT
        stt_url = f"{API_BASE_URL}/audio/transcriptions"
        files = {
            "file": (file.filename or "ambient_audio.webm", audio_bytes, file.content_type or "audio/webm")
        }
        form_data = {"model": "whisper-1"}
        headers = {"Authorization": f"Bearer {API_KEY}"}

        stt_response = requests.post(stt_url, files=files, data=form_data, headers=headers, timeout=20)
        
        if stt_response.status_code != 200:
            print(f"[STT Error] Status {stt_response.status_code}: {stt_response.text}")
            raise HTTPException(status_code=502, detail=f"STT service error: {stt_response.text}")

        transcript_data = stt_response.json()
        transcript = transcript_data.get("text", "").strip()

        if not transcript:
            return AmbientCaptureResponse(
                transcript="(Silence / Unintelligible)",
                summary="No clear speech was recognized in the audio buffer. Try speaking a bit louder or closer to the microphone."
            )

        print(f"[Aha Catcher] Transcribed Speech: \"{transcript}\"")

        # Step 2: Agentic Synthesis & Background Web Search
        agent_prompt = (
            f"The user just captured an Aha! idea / insight via ambient audio.\n\n"
            f"Transcribed Audio: \"{transcript}\"\n\n"
            f"As the Aha Catcher AI:\n"
            f"1. Extract the core insight or hypothesis.\n"
            f"2. Use web_search if relevant to find relevant technologies, facts, or references.\n"
            f"3. Provide a concise, high-impact research summary with 2-3 concrete actionable takeaways."
        )

        agent_result = agentic_chat(ChatRequest(prompt=agent_prompt, model="grok-4-fast"))
        
        return AmbientCaptureResponse(
            transcript=transcript,
            summary=agent_result.reply
        )

    except HTTPException:
        raise
    except Exception as e:
        print(f"[Aha Catcher Exception]: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to process ambient audio: {str(e)}")

class RefineSpeechRequest(BaseModel):
    transcript: str

@app.post("/api/refine-speech")
def refine_speech(req: RefineSpeechRequest):
    """
    Semantic Speech Refiner (Antigravity Quality).
    Transforms raw speech transcriptions into clean, well-spaced,
    properly punctuated, and disfluency-free prompts using grok-4-fast.
    """
    if not req.transcript or not req.transcript.strip():
        return {"refined_text": ""}

    if not API_KEY:
        return {"refined_text": req.transcript}

    system_prompt = (
        "You are a real-time voice speech refiner for an AI assistant. "
        "Your job is to transform raw, messy speech-to-text transcriptions into clean, well-spaced, "
        "properly punctuated, and grammatically correct prompts. "
        "Strict Rules:\n"
        "1. Insert missing spaces between jammed words (e.g. 'knowUh' -> 'know. Uh' or clean text).\n"
        "2. Remove filler words (uh, um, like, you know, okay) and repetitive self-corrections.\n"
        "3. Keep the user's exact semantic intent and core request.\n"
        "4. Return ONLY the refined prompt text without any introductory conversational text or quotes."
    )

    url = f"{API_BASE_URL}/chat/completions"
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": "grok-4-fast",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": req.transcript}
        ],
        "temperature": 0.2
    }

    try:
        res = requests.post(url, json=payload, headers=headers, timeout=5)
        if res.status_code == 200:
            cleaned = res.json()["choices"][0]["message"]["content"].strip()
            return {"refined_text": cleaned}
        return {"refined_text": req.transcript}
    except Exception as e:
        print(f"[Refine Speech Error]: {e}")
        return {"refined_text": req.transcript}


@app.post("/api/transcribe")
async def transcribe_audio(file: UploadFile = File(...)):
    """
    High-Speed xAI Grok STT Endpoint.
    Transcribes WebRTC noise-suppressed audio files via AI Builder Space Grok STT API
    with technical domain terms ('FastAPI, SuperMind, Grok, Pydantic, Docker, Antigravity, Koyeb').
    """
    if not API_KEY:
        raise HTTPException(status_code=500, detail="AI_BUILDER_API_KEY environment variable is not configured.")

    try:
        audio_content = await file.read()
        filename = file.filename or "audio.webm"
        content_type = file.content_type or "audio/webm"

        files = {
            "audio_file": (filename, audio_content, content_type)
        }
        data = {
            "diarize": "true",
            "terms": "FastAPI, SuperMind, Pydantic, Grok, Docker, Antigravity, Koyeb"
        }
        headers = {
            "Authorization": f"Bearer {API_KEY}"
        }

        # Route to xAI Grok STT endpoint for ultra-fast response time
        stt_url = f"{API_BASE_URL}/audio/grok-transcription"
        stt_response = requests.post(stt_url, files=files, data=data, headers=headers)

        if stt_response.status_code != 200:
            # Fallback to standard transcriptions if needed
            fallback_url = f"{API_BASE_URL}/audio/transcriptions"
            stt_response = requests.post(fallback_url, files=files, data={"model": "whisper-1", "terms": data["terms"]}, headers=headers)

        if stt_response.status_code != 200:
            raise HTTPException(status_code=stt_response.status_code, detail=f"AI Builder STT Error: {stt_response.text}")

        res_json = stt_response.json()
        transcript = res_json.get("text", "").strip() or res_json.get("transcript", "").strip()
        return {"text": transcript}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Speech transcription failed: {str(e)}")


# Chapter 1: Root Health Check
@app.get("/")
def root():
    """Root health check endpoint."""
    return {
        "message": "SuperMind Agentic Core & Aha Catcher MVP is Live!",
        "gui": "http://127.0.0.1:8000/gui",
        "ambient_mvp": "http://127.0.0.1:8000/ambient",
        "docs": "http://127.0.0.1:8000/docs"
    }


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
