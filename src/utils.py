import os, re, json, datetime
from pathlib import Path

def slugify(text:str)->str:
    text = re.sub(r"[^\w\s-]", "", text, flags=re.U).strip().lower()
    text = re.sub(r"[\s_-]+", "-", text, flags=re.U)
    return text[:80] or "post"

def read_env():
    env = {}
    for k in ("OPENAI_API_KEY","OPENAI_MODEL"):
        v = os.getenv(k)
        if v: env[k]=v
    # local .env fallback (not needed on GitHub, but handy if you test locally)
    if not env.get("OPENAI_API_KEY") and os.path.exists(".env"):
        for line in open(".env","r",encoding="utf-8").read().splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k,v=line.split("=",1)
                if k.strip()=="OPENAI_API_KEY" and v.strip():
                    env["OPENAI_API_KEY"]=v.strip()
                if k.strip()=="OPENAI_MODEL" and v.strip():
                    env["OPENAI_MODEL"]=v.strip()
    return env

def load_config(path="config.yaml"):
    cfg = {"site_name":"Site","base_url":"https://example.com","posts_per_run":10,"theme":"facts","language_mix":["en","ar"]}
    if os.path.exists(path):
        content = open(path,"r",encoding="utf-8").read()
        data = {}
        for line in content.splitlines():
            line=line.strip()
            if not line or line.startswith("#"): continue
            if ":" in line:
                k,v = line.split(":",1)
                data[k.strip()] = v.strip().strip('"\'')
        import re as _re
        m = _re.search(r'language_mix:\s*\[(.*?)\]', content, _re.S)
        if m:
            items = [x.strip().strip('"\'') for x in m.group(1).split(",") if x.strip()]
            data["language_mix"] = items or ["en","ar"]
        cfg.update(data)
    return cfg

def approx_read_mins(text:str)->int:
    import re
    words = len(re.findall(r"\w+", text))
    return max(1, words//180)

def today_iso():
    return datetime.datetime.utcnow().strftime("%Y-%m-%d")

def now_rfc2822():
    from email.utils import formatdate
    return formatdate(usegmt=True)

def ensure_dir(p):
    Path(p).mkdir(parents=True, exist_ok=True)
