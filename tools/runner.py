#!/usr/bin/env python3
"""AI 第二大脑 · 视频队列处理器（在 Mac 本机由 launchd 运行）。
Claude 往 inbox/queue/ 放 <名字>.url（一行 YouTube/视频链接，可选第二行 "--start 10:00 --end 40:00"）。
本脚本用开源 claude-watch 的 watch.py 下载视频、按场景截图、取字幕；没有字幕时用本机 mlx-whisper 转写。
结果写到 inbox/<slug>/，处理完把 .url 改名为 .done（失败为 .failed），日志在 inbox/logs/。"""
import json, os, re, subprocess, sys, time, glob, shlex
from pathlib import Path
BRAIN = Path.home() / "LLM" / "AI第二大脑"
INBOX = BRAIN / "inbox"; QUEUE = INBOX / "queue"; LOGS = INBOX / "logs"
TOOLS = BRAIN / "tools"; CW = TOOLS / "claude-watch"; VENV = TOOLS / ".venv"
PY = str(VENV / "bin" / "python3")
URL_OK = re.compile(r"^https://(www\.|m\.)?(youtube\.com|youtu\.be|vimeo\.com|x\.com|twitter\.com|loom\.com)/[\w\-./?=&%#:+~]+$")
ALLOWED_FLAGS = {"--start", "--end", "--max-frames", "--resolution", "--scene-threshold", "--max-gap"}
os.environ["PATH"] = f"{VENV/'bin'}:/opt/homebrew/bin:/usr/local/bin:" + os.environ.get("PATH", "")

def log(f, msg):
    f.write(time.strftime("%H:%M:%S ") + msg + "\n"); f.flush()

def whisper_fallback(libdir: Path, f):
    vids = sorted([p for p in libdir.rglob("*") if p.suffix.lower() in (".mp4", ".webm", ".mkv", ".mov", ".m4a")], key=lambda p: p.stat().st_size, reverse=True)
    if not vids: log(f, "no media file found for whisper"); return False
    wav = libdir / "audio16k.wav"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(vids[0]), "-ac", "1", "-ar", "16000", str(wav)], check=True)
    log(f, "transcribing locally with mlx-whisper ...")
    code = ("import json,sys,mlx_whisper; r=mlx_whisper.transcribe(sys.argv[1], path_or_hf_repo='mlx-community/whisper-large-v3-turbo');"
            "json.dump([{'t_start':s['start'],'t_end':s['end'],'text':s['text'].strip(),'speaker_break':False} for s in r['segments']],open(sys.argv[2],'w'),ensure_ascii=False,indent=1)")
    subprocess.run([PY, "-c", code, str(wav), str(libdir / "transcript.json")], check=True)
    wav.unlink(missing_ok=True)
    m = libdir / "meta.json"
    if m.exists():
        meta = json.loads(m.read_text()); meta["transcript_source"] = "mlx-whisper"; m.write_text(json.dumps(meta, ensure_ascii=False, indent=2))
    return True

MEDIA = (".mp4", ".webm", ".mkv", ".mov", ".m4a", ".mp3", ".wav", ".opus", ".part", ".ytdl")

def ensure_deps():
    """YouTube 要求解 JS 验证：需要 deno 运行环境 + yt-dlp 的 EJS 组件（yt-dlp[default]）。缺了就自动装。"""
    with open(LOGS / "update.log", "a") as f:
        if not any(Path(d, "deno").exists() for d in ("/opt/homebrew/bin", "/usr/local/bin")):
            brew = next((b for b in ("/opt/homebrew/bin/brew", "/usr/local/bin/brew") if Path(b).exists()), None)
            if brew:
                r = subprocess.run([brew, "install", "deno"], capture_output=True, text=True)
                f.write(time.ctime() + f" brew install deno rc={r.returncode} {r.stderr[-300:]}\n")
        stamp = TOOLS / ".ejs_installed"
        if not stamp.exists():
            r = subprocess.run([PY, "-m", "pip", "install", "-q", "--upgrade", "yt-dlp[default]"], capture_output=True, text=True)
            f.write(time.ctime() + f" pip yt-dlp[default] rc={r.returncode} {r.stderr[-300:]}\n")
            if r.returncode == 0: stamp.write_text(time.ctime())
    conf = CW / "yt-dlp.conf"   # yt-dlp 在当前目录读取这个配置；只影响本工具
    if not conf.exists():
        conf.write_text("--remote-components ejs:github\n")

def update_ytdlp():
    """每天最多一次：把 yt-dlp 升级到最新版（YouTube 改接口时旧版会下载失败）。"""
    stamp = TOOLS / ".ytdlp_updated"
    if stamp.exists() and time.time() - stamp.stat().st_mtime < 86400: return
    with open(LOGS / "update.log", "a") as f:
        r = subprocess.run([PY, "-m", "pip", "install", "-q", "--upgrade", "yt-dlp[default]"], capture_output=True, text=True)
        f.write(time.ctime() + f" yt-dlp update rc={r.returncode} {r.stderr[-300:]}\n")
    if r.returncode == 0: stamp.write_text(time.ctime())

def cleanup_media(libdir: Path, f):
    """截图和字幕提取完后删除下载的视频/音频文件，只保留 frames/、字幕和元数据。"""
    freed = 0
    for q in libdir.rglob("*"):
        if q.is_file() and q.suffix.lower() in MEDIA:
            freed += q.stat().st_size; q.unlink()
    log(f, f"deleted video files, freed {freed/1e6:.0f} MB")

def process(job: Path):
    lines = [l.strip() for l in job.read_text().splitlines() if l.strip()]
    url = lines[0] if lines else ""
    logf = open(LOGS / (job.stem + ".log"), "a")
    if not URL_OK.match(url):
        log(logf, f"rejected url: {url!r}"); job.rename(job.with_suffix(".failed")); return
    extra = []
    if len(lines) > 1:
        toks = shlex.split(lines[1])
        for i, t in enumerate(toks):
            if t in ALLOWED_FLAGS and i + 1 < len(toks) and re.fullmatch(r"[\d:.]+", toks[i + 1]): extra += [t, toks[i + 1]]
    job = job.rename(job.with_suffix(".running"))
    log(logf, f"start {url} {extra}")
    cmd = [PY, str(CW / "scripts" / "watch.py"), url, "--no-whisper", "--out-dir", str(INBOX), "--resolution", "1024", *extra]
    p = subprocess.run(cmd, cwd=str(CW), capture_output=True, text=True, env={**os.environ, "PYTHONPATH": str(CW)})
    logf.write(p.stdout + "\n" + p.stderr + "\n")
    m = re.search(r"^library_dir: (.+)$", p.stdout, re.M)
    if p.returncode != 0 or not m:
        log(logf, f"watch.py failed rc={p.returncode}"); job.rename(job.with_suffix(".failed")); return
    libdir = Path(m.group(1).strip())
    if re.search(r"^transcript_source: none$", p.stdout, re.M):
        try: whisper_fallback(libdir, logf)
        except Exception as e: log(logf, f"whisper failed: {e}")
    (libdir / "watch_stdout.txt").write_text(p.stdout)
    try: cleanup_media(libdir, logf)
    except Exception as e: log(logf, f"cleanup failed: {e}")
    (libdir / ".ready").write_text(url + "\n")
    log(logf, f"done → {libdir}")
    job.rename(job.with_suffix(".done"))

def process_tts(job: Path):
    """配音任务：queue/<名字>.tts（JSON），只允许读写第二大脑 video/ 目录，调用 tools/tts.py。"""
    job = job.rename(job.with_suffix(".ttsrun"))
    spec = json.loads(job.read_text())
    vroot = (BRAIN / "video").resolve()
    for k in ("lines_dir", "out_dir"):
        p = Path(spec[k]).resolve()
        if p != vroot and vroot not in p.parents:
            job.rename(job.with_suffix(".ttsfailed")); return
    with open(LOGS / (job.stem + ".tts.log"), "a") as f:
        r = subprocess.run([PY, str(TOOLS / "tts.py"), str(job)], capture_output=True, text=True, timeout=5400)
        f.write(r.stdout[-3000:] + "\n" + r.stderr[-3000:] + f"\nrc={r.returncode}\n")
    job.rename(job.with_suffix(".ttsdone" if r.returncode == 0 else ".ttsfailed"))

def main():
    QUEUE.mkdir(parents=True, exist_ok=True); LOGS.mkdir(parents=True, exist_ok=True)
    for tj in sorted(QUEUE.glob("*.tts")):
        try: process_tts(tj)
        except Exception as e:
            with open(LOGS / "runner-errors.log", "a") as f: f.write(f"{time.ctime()} {tj.name}: {e}\n")
    jobs = sorted(QUEUE.glob("*.url"))
    if not jobs: return
    try: ensure_deps()
    except Exception as e:
        with open(LOGS / "update.log", "a") as f: f.write(f"{time.ctime()} deps error: {e}\n")
    try: update_ytdlp()
    except Exception as e:
        with open(LOGS / "update.log", "a") as f: f.write(f"{time.ctime()} update error: {e}\n")
    for job in jobs:
        try: process(job)
        except Exception as e:
            with open(LOGS / "runner-errors.log", "a") as f: f.write(f"{time.ctime()} {job.name}: {e}\n")
            for s in (".running", ".url"):
                q = job.with_suffix(s)
                if q.exists(): q.rename(job.with_suffix(".failed"))
if __name__ == "__main__": main()
