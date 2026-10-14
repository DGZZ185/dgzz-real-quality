import os
import shutil
import subprocess
import uuid
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).parent.resolve()
WORK = ROOT / "work"
WORK.mkdir(exist_ok=True)
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "250"))
ALLOWED = {".mp4", ".mov", ".mkv", ".webm", ".m4v"}

app = FastAPI(title="DGZZ REAL QUALITY")
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")


def has_ffmpeg():
    return shutil.which("ffmpeg") and shutil.which("ffprobe")


@app.get("/", response_class=HTMLResponse)
def home():
    return (ROOT / "static" / "index.html").read_text(encoding="utf-8")


@app.get("/api/status")
def status():
    return {"ffmpeg_available": bool(has_ffmpeg()), "max_upload_mb": MAX_UPLOAD_MB}


@app.get("/api/tiktok/status")
def tiktok_status():
    # TikTok OAuth is deliberately not faked: real publishing requires an approved
    # TikTok developer app, OAuth callback URL, and video.publish permission.
    configured = bool(os.getenv("TIKTOK_CLIENT_KEY") and os.getenv("TIKTOK_CLIENT_SECRET") and os.getenv("TIKTOK_REDIRECT_URI"))
    return {"configured": configured, "connected": False, "username": None}


@app.get("/auth/tiktok", response_class=HTMLResponse)
def tiktok_connect_info():
    return HTMLResponse("""<!doctype html><html lang='pt-BR'><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>Conectar TikTok — DGZZ</title><body style='background:#09090b;color:#f7f7f8;font:16px system-ui;max-width:620px;margin:12vh auto;padding:24px'><h1 style='color:#ef3038'>Conectar TikTok</h1><p>Para conectar uma conta de verdade, o DGZZ precisa de um aplicativo no TikTok for Developers com OAuth e permissão de publicação de vídeos aprovados.</p><p>Configure <code>TIKTOK_CLIENT_KEY</code>, <code>TIKTOK_CLIENT_SECRET</code> e <code>TIKTOK_REDIRECT_URI</code> no servidor. Não coloque segredos no navegador nem compartilhe sua senha do TikTok.</p><p>Esta versão já processa e baixa vídeos, mas a publicação direta ainda não está ativada até a integração OAuth ser configurada e aprovada.</p><p><a style='color:#ef3038' href='/'>Voltar ao DGZZ REAL QUALITY</a></p></body></html>""")


@app.post("/api/tiktok/publish")
async def tiktok_publish():
    raise HTTPException(501, "A publicação direta ainda não está ativada. É necessário configurar OAuth e obter aprovação para a API Content Posting do TikTok.")


@app.post("/api/process")
async def process_video(
    file: UploadFile = File(...),
    resolution: str = Form("1080p"),
    fps: str = Form("60"),
    sharpen: bool = Form(False),
):
    if not has_ffmpeg():
        raise HTTPException(503, "FFmpeg não está instalado no servidor.")
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED:
        raise HTTPException(400, "Formato não aceito. Use MP4, MOV, MKV ou WebM.")
    if resolution not in {"1080p", "4K", "original"}:
        raise HTTPException(400, "Resolução inválida.")
    if fps not in {"original", "60", "120"}:
        raise HTTPException(400, "FPS inválido.")

    job = uuid.uuid4().hex
    in_path = WORK / f"{job}_input{ext}"
    out_path = WORK / f"{job}_output.mp4"
    size = 0
    try:
        with in_path.open("wb") as out:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > MAX_UPLOAD_MB * 1024 * 1024:
                    raise HTTPException(413, f"Vídeo excede o limite de {MAX_UPLOAD_MB} MB.")
                out.write(chunk)

        vf = []
        if resolution == "1080p":
            vf.append("scale=w=1920:h=1080:force_original_aspect_ratio=decrease:force_divisible_by=2")
        elif resolution == "4K":
            vf.append("scale=w=3840:h=2160:force_original_aspect_ratio=decrease:force_divisible_by=2")
        if fps != "original":
            vf.append(f"minterpolate=fps={fps}:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1")
        if sharpen:
            vf.append("unsharp=5:5:0.8:3:3:0.4")

        cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(in_path),
               "-map", "0:v:0", "-map", "0:a?", "-vf", ",".join(vf) if vf else "null",
               "-c:v", "libx264", "-preset", "veryfast", "-crf", "19",
               "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
               "-movflags", "+faststart", str(out_path)]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60 * 60)
        if result.returncode != 0 or not out_path.exists():
            detail = (result.stderr or "Falha ao processar o vídeo.")[-1800:]
            raise HTTPException(500, detail)
        return FileResponse(
            out_path,
            media_type="video/mp4",
            filename="dgzz_real_quality.mp4",
            background=None,
        )
    except subprocess.TimeoutExpired:
        raise HTTPException(504, "O processamento passou do limite de 60 minutos.")
    finally:
        await file.close()
        try:
            in_path.unlink(missing_ok=True)
        except Exception:
            pass
