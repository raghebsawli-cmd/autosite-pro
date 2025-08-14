import os, json, random, datetime
from pathlib import Path
from utils import slugify, read_env, load_config, approx_read_mins, today_iso, now_rfc2822, ensure_dir

def generate_text(api_key:str, model:str, system_prompt:str, user_prompt:str)->str:
    import requests
    url = "https://api.openai.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type":"application/json"}
    payload = {"model": model, "messages":[{"role":"system","content":system_prompt},{"role":"user","content":user_prompt}], "temperature":0.7}
    r = requests.post(url, headers=headers, json=payload, timeout=120)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]

def english_prompt(theme, topic):
    return f"""You are a careful, factual writer. Create an original, SEO-friendly article (600-800 words) in English.
Topic: {topic}
Theme: {theme}
Structure:
- A punchy title (max 60 chars)
- 1-paragraph intro (40-60 words) with a clear hook
- 6-8 short sections, each with a bold heading and 2-3 sentences
- One "Myth vs Reality" section if relevant
- A final "Bottom line" summary (20-40 words)
Tone: authoritative but accessible. Avoid fluff. Use plain paragraphs and headings prefixed with '## '."""

def arabic_prompt(theme, topic):
    return f"""اكتب مقالة أصلية ومناسبة للسيو باللغة العربية (٦٠٠–٨٠٠ كلمة).
الموضوع: {topic}
الثيمة: {theme}
البنية:
- عنوان جذاب (حتى ٦٠ حرفًا)
- مقدمة فقرة واحدة (٤٠–٦٠ كلمة) مع خطاف واضح
- ٦–٨ أقسام قصيرة، لكل منها عنوان بارز وفقرتان قصيرتان
- قسم "خرافة مقابل حقيقة" إن أمكن
- خاتمة "الخلاصة" (٢٠–٤٠ كلمة)
الأسلوب: موثوق وسلس. فقرات عادية وعناوين تبدأ بـ '## '."""

def parse_article(raw:str):
    lines = [l.strip() for l in raw.splitlines() if l.strip()]
    title, rest = "", []
    for ln in lines:
        if ln.startswith("## "): rest.append(ln)
        elif not title: title = ln
        else: rest.append(ln)
    body = "\n".join(rest)
    paragraphs = [p for p in body.split("\n") if not p.startswith("##")]
    excerpt = paragraphs[0] if paragraphs else ""
    return title[:90], excerpt[:180], body

def body_to_html(body:str):
    html_lines = []
    for ln in body.splitlines():
        if ln.startswith("## "): html_lines.append(f"<h3>{ln[3:].strip()}</h3>")
        else: html_lines.append(f"<p>{ln}</p>")
    return "\n".join(html_lines)

def build_post_html(base_tpl, post_tpl, site_name, base_url, title, excerpt, html_body, slug):
    canonical = f"{base_url}/posts/{slug}/"
    json_ld = {"@context":"https://schema.org","@type":"Article","headline":title,"datePublished":today_iso(),"dateModified":today_iso(),"author":{"@type":"Organization","name":site_name},"mainEntityOfPage":{"@type":"WebPage","@id":canonical},"publisher":{"@type":"Organization","name":site_name}}
    year = datetime.datetime.utcnow().year
    content = post_tpl.format(title=title, date=today_iso(), read_mins=approx_read_mins(html_body), excerpt=excerpt, html_body=html_body, theme="facts")
    return base_tpl.format(title=title, site_name=site_name, description=excerpt, canonical=canonical, json_ld=json.dumps(json_ld, ensure_ascii=False), content=content, year=year)

def build_index_html(base_tpl, index_tpl, site_name, base_url, posts, lang_code):
    items = []
    for p in posts[:50]:
        url = f"/posts/{p['slug']}/"
        items.append(f'<li class="list-item"><a href="{url}">{p["title"]}</a> <span class="meta">— {p["date"]}</span></li>')
    canonical = f"{base_url}/index_{lang_code}.html"
    content = index_tpl.format(items="\n    ".join(items))
    return base_tpl.format(title=site_name, site_name=site_name, description=f"{site_name} – latest posts", canonical=canonical, json_ld=json.dumps({"@context":"https://schema.org","@type":"WebSite","name":site_name,"url":base_url}, ensure_ascii=False), content=content, year=datetime.datetime.utcnow().year)

def main():
    cfg = load_config()
    env = read_env()
    api_key = env.get("OPENAI_API_KEY","")
    model = env.get("OPENAI_MODEL","gpt-4o-mini")  # cheap & fine; can change later
    if not api_key: print("ERROR: OPENAI_API_KEY not set"); return

    site_name = cfg["site_name"]; base_url = cfg["base_url"]
    posts_per_run = int(cfg.get("posts_per_run",10))
    lang_mix = cfg.get("language_mix", ["en","ar"])

    base_en = open("templates/base_en.html","r",encoding="utf-8").read()
    base_ar = open("templates/base_ar.html","r",encoding="utf-8").read()
    post_en = open("templates/post_en.html","r",encoding="utf-8").read()
    post_ar = open("templates/post_ar.html","r",encoding="utf-8").read()
    index_en = open("templates/index_en.html","r",encoding="utf-8").read()
    index_ar = open("templates/index_ar.html","r",encoding="utf-8").read()

    ensure_dir("site/posts"); ensure_dir("site/assets")
    import shutil; shutil.copyfile("assets/style.css", "site/assets/style.css")

    seed_en = [x.strip() for x in open("topics/seed_en.txt","r",encoding="utf-8").read().splitlines() if x.strip()]
    seed_ar = [x.strip() for x in open("topics/seed_ar.txt","r",encoding="utf-8").read().splitlines() if x.strip()]

    per_lang = max(1, posts_per_run // max(1, len(lang_mix)))
    new_posts = []
    for lang in lang_mix:
        for _ in range(per_lang):
            if lang=="en":
                topic = random.choice(seed_en)
                raw = generate_text(api_key, model, "You are a careful web writer.", english_prompt(cfg["theme"], topic))
                title, excerpt, body = parse_article(raw)
                html_body = body_to_html(body)
                slug = slugify(title + "-" + topic); out_dir = f"site/posts/{slug}"; ensure_dir(out_dir)
                open(f"{out_dir}/index.html","w",encoding="utf-8").write(build_post_html(base_en, post_en, site_name, base_url, title, excerpt, html_body, slug))
                new_posts.append({"lang":"en","title":title,"slug":slug,"date":today_iso()})
            else:
                topic = random.choice(seed_ar)
                raw = generate_text(api_key, model, "اكتب بأسلوب عربي واضح وموثوق.", arabic_prompt(cfg["theme"], topic))
                title, excerpt, body = parse_article(raw)
                html_body = body_to_html(body)
                slug = slugify(title + "-" + topic); out_dir = f"site/posts/{slug}"; ensure_dir(out_dir)
                open(f"{out_dir}/index.html","w",encoding="utf-8").write(build_post_html(base_ar, post_ar, site_name, base_url, title, excerpt, html_body, slug))
                new_posts.append({"lang":"ar","title":title,"slug":slug,"date":today_iso()})

    dbp = "site/posts_index.json"
    all_posts = json.load(open(dbp,"r",encoding="utf-8")) if os.path.exists(dbp) else []
    all_posts = new_posts + all_posts
    json.dump(all_posts, open(dbp,"w",encoding="utf-8"), ensure_ascii=False, indent=2)

    en_posts = [p for p in all_posts if p["lang"]=="en"]
    ar_posts = [p for p in all_posts if p["lang"]=="ar"]
    open("site/index_en.html","w",encoding="utf-8").write(build_index_html(base_en, index_en, site_name, base_url, en_posts, "en"))
    open("site/index_ar.html","w",encoding="utf-8").write(build_index_html(base_ar, index_ar, site_name, base_url, ar_posts, "ar"))

    rss = ["<?xml version='1.0' encoding='UTF-8' ?>","<rss version='2.0'>","<channel>",
           f"<title>{site_name
