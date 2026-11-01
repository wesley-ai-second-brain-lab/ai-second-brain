#!/usr/bin/env python3
"""AI 第二大脑 · 本机神经网络配音（开源 Kokoro-82M，Apache-2.0，通过 mlx-audio 在 Apple 芯片上运行）。
用法（由 runner.py 调用）：tts.py <job.json>
job: {"lines_dir": ".../video/lines_tts", "out_dir": ".../video/voice_nn", "voices": ["zf_xiaoxiao"], "speed": 1.0, "check": true}
每个 voice 在 out_dir/<voice>/NN.wav 生成一句；check=true 时再用 mlx-whisper 把第一句转写回来写到 check.txt，方便核对发音。"""
import json, subprocess, sys, glob, os, shutil
from pathlib import Path
PY = sys.executable
job = json.loads(Path(sys.argv[1]).read_text())
lines = sorted(Path(job["lines_dir"]).glob("*.txt"))
out = Path(job["out_dir"]); out.mkdir(parents=True, exist_ok=True)
log = open(out / "tts.log", "a")
def run(cmd, **kw):
    r = subprocess.run(cmd, capture_output=True, text=True, **kw)
    log.write(" ".join(map(str, cmd))[:300] + f"\n rc={r.returncode}\n{r.stdout[-1500:]}\n{r.stderr[-3000:]}\n"); log.flush()
    return r
stamp = Path(__file__).with_name(".tts_installed")
if not stamp.exists():
    r = run([PY, "-m", "pip", "install", "-q", "--upgrade", "mlx-audio", "misaki[zh]", "soundfile"])
    if r.returncode == 0: stamp.write_text("ok")
model = job.get("model", "mlx-community/Kokoro-82M-bf16")
for v in job["voices"]:
    vd = out / v; vd.mkdir(exist_ok=True)
    for f in lines:
        tmp = vd / f"_tmp_{f.stem}"; tmp.mkdir(exist_ok=True)
        r = run([PY, "-m", "mlx_audio.tts.generate", "--model", model, "--text", f.read_text().strip(),
                 "--voice", v, "--lang_code", "z", "--speed", str(job.get("speed", 1.0)),
                 "--file_prefix", str(tmp / "a"), "--audio_format", "wav", "--join_audio"], cwd=str(tmp))
        wavs = sorted(tmp.rglob("*.wav")) or sorted(Path(tmp).parent.glob(f"_tmp_{f.stem}*.wav"))
        if wavs:
            shutil.move(str(wavs[-1]), vd / f"{f.stem}.wav")
        shutil.rmtree(tmp, ignore_errors=True)
    if job.get("check") and (vd / "00.wav").exists():
        code = ("import sys,mlx_whisper;r=mlx_whisper.transcribe(sys.argv[1],path_or_hf_repo='mlx-community/whisper-large-v3-turbo',language='zh');"
                "open(sys.argv[2],'w').write(r['text'])")
        run([PY, "-c", code, str(vd / "00.wav"), str(vd / "check.txt")])
(out / ".done").write_text("ok")
