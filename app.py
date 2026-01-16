import os
import re
import json
from pathlib import Path
import requests
from bs4 import BeautifulSoup
from flask import Flask, render_template, send_from_directory, request, jsonify
from email.message import EmailMessage
import smtplib
import ssl
from PyPDF2 import PdfReader

app = Flask(__name__)

BASE_DIR = Path(__file__).parent
STATIC_DIR = BASE_DIR / "static"
IMG_DIR = STATIC_DIR / "images"
PROJECT_IMG_DIR = IMG_DIR / "projects"
RESUME_PATH = BASE_DIR / "Zuber_Resume_09.pdf"
PHOTO_PATH = BASE_DIR / "phottoo.jpg"
DATA_CACHE = BASE_DIR / "data.json"

KNOWN_SKILLS = [
    "JavaScript",
    "TypeScript",
    "React",
    "Next.js",
    "Node.js",
    "Express",
    "MongoDB",
    "Mongoose",
    "PostgreSQL",
    "MySQL",
    "Python",
    "Flask",
    "Django",
    "HTML",
    "CSS",
    "Tailwind",
    "Bootstrap",
    "Git",
    "Docker",
    "AWS",
    "Google Cloud",
]

TECH_CATEGORIES = [
    "Languages",
    "Frameworks",
    "Databases",
    "Machine Learning",
    "Concepts",
    "Tools",
]

HEADINGS = [
    "Summary",
    "Objective",
    "About",
    "Education",
    "Experience",
    "Internship",
    "Internships",
    "Projects",
    "Skills",
    "Technical Skills",
    "Languages",
    "Certifications",
    "Achievements",
    "Contact",
]


def read_pdf_text(path: Path) -> str:
    reader = PdfReader(str(path))
    pages = []
    for p in reader.pages:
        pages.append(p.extract_text() or "")
    text = "\n".join(pages)
    text = re.sub(r"[ \t]+", " ", text)
    return text


def find_name(text: str) -> str:
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    for i, line in enumerate(lines[:5]):
        if re.match(r"^[A-Za-z][A-Za-z .'-]{2,}$", line):
            return line
    return "Zuber"


def extract_section(text: str, title: str) -> str:
    pattern = re.compile(rf"(?i)\b{re.escape(title)}\b:?[\s\S]*?", re.IGNORECASE)
    matches = list(pattern.finditer(text))
    if not matches:
        return ""
    idx = matches[0].end()
    next_titles = [t for t in HEADINGS if t.lower() != title.lower()]
    end_positions = []
    for t in next_titles:
        m = re.search(rf"(?i)\b{re.escape(t)}\b", text[idx:])
        if m:
            end_positions.append(idx + m.start())
    end = min(end_positions) if end_positions else len(text)
    return text[idx:end].strip()


def extract_urls(text: str) -> list:
    urls = re.findall(r"(https?://[^\s)]+)", text)
    tlds = ["com","net","org","io","dev","app","ai","co","in","me","tech","xyz","site","blog","gov","edu","render.com","vercel.app","onrender.com","github.io"]
    tld_pattern = "(?:" + "|".join([re.escape(t) for t in tlds]) + ")"
    bare = re.findall(rf"\b([a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)+(?:/[^\s)]+)?)\b", text)
    clean = []
    for u in urls + bare:
        u = u.rstrip(").,;\"'")
        # ensure protocol
        if not u.startswith("http"):
            # only accept if ends with known TLDs
            if re.search(rf"\.(?:{tld_pattern})(?:/|$)", u):
                u = "https://" + u
            else:
                continue
        if u not in clean and re.search(r"https?://", u):
            clean.append(u)
    return clean


def extract_contacts(text: str) -> dict:
    # robust email matching with optional spaces around '@' and '.'
    email_match = re.search(r"([A-Za-z0-9._%+-]+)\s*@\s*([A-Za-z0-9.-]+)\s*\.\s*([A-Za-z]{2,})", text)
    if email_match:
        email = f"{email_match.group(1)}@{email_match.group(2)}.{email_match.group(3)}"
    else:
        email_simple = re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text)
        email = email_simple.group(0) if email_simple else None
    linkedin = None
    github = None
    for u in extract_urls(text):
        if "linkedin.com" in u and linkedin is None:
            linkedin = u
        if "github.com" in u and github is None:
            github = u
    return {
        "email": email,
        "linkedin": linkedin,
        "github": github,
    }


def extract_skills(text: str) -> dict:
    skills_found = []
    for s in KNOWN_SKILLS:
        pattern = re.compile(rf"(?i)\b{s}\b")
        if pattern.search(text):
            skills_found.append(s)
    groups = {
        "frontend": [],
        "backend": [],
        "database": [],
        "tools": [],
    }
    for s in skills_found:
        sl = s.lower()
        if sl in {"javascript", "typescript", "react", "next.js", "html", "css", "tailwind", "bootstrap"}:
            groups["frontend"].append(s)
        elif sl in {"node.js", "express", "python", "flask", "django"}:
            groups["backend"].append(s)
        elif sl in {"mongodb", "mongoose", "postgresql", "mysql"}:
            groups["database"].append(s)
        elif sl in {"git", "docker", "aws", "google cloud"}:
            groups["tools"].append(s)
    return groups


def extract_technical_skills(text: str) -> dict:
    section = extract_section(text, "Technical Skills") or extract_section(text, "Skills") or ""
    result = { "languages": [], "frameworks": [], "databases": [], "machine_learning": [], "concepts": [], "tools": [] }
    sec = re.sub(r"\s{2,}", " ", section)
    # Primary: parse explicit category blocks
    found_any = False
    for i, cat in enumerate(TECH_CATEGORIES):
        start = re.search(rf"(?i)\b{re.escape(cat)}\b\s*:", sec)
        if not start:
            continue
        sidx = start.end()
        # stop at next category OR next global heading to prevent bleeding into other sections
        stops = []
        for nxt in TECH_CATEGORIES[i+1:]:
            m = re.search(rf"(?i)\b{re.escape(nxt)}\b\s*:", sec[sidx:])
            if m:
                stops.append(sidx + m.start())
        for head in HEADINGS:
            m = re.search(rf"(?i)\b{re.escape(head)}\b", sec[sidx:])
            if m:
                stops.append(sidx + m.start())
        eidx = min(stops) if stops else None
        chunk = sec[sidx:eidx] if eidx else sec[sidx:sidx+600]
        tokens = [t.strip() for t in re.split(r"[,\n;•/]+", chunk) if t.strip()]
        key = cat.lower().replace(" ", "_")
        clean = []
        for t in tokens:
            t = re.sub(r"\([^)]*\)", "", t).strip()
            t = re.sub(r"\s{2,}", " ", t)
            if t and t.lower() not in {c.lower() for c in clean}:
                clean.append(t)
        if clean:
            result[key] = clean
            found_any = True
    if found_any:
        return result
    # Fallback: token-based detection across entire resume text
    catalog = {
        "languages": ["Python","C++","JavaScript","SQL","C"],
        "frameworks": ["Django","Flask","React.js","React","Tailwind CSS","Bootstrap","Next.js"],
        "databases": ["PostgreSQL","MySQL","SQLite","MongoDB","Mongoose"],
        "machine_learning": ["Pandas","NumPy","Scikit-learn","Seaborn","Matplotlib"],
        "concepts": ["Data Structures & Algorithms","DSA","OOP","DBMS","OS","Computer Networks"],
        "tools": ["Git","GitHub","VS Code","Linux","Docker","AWS","Google Cloud"]
    }
    low = text.lower()
    for key, toks in catalog.items():
        vals = []
        for t in toks:
            pattern = re.escape(t.lower()).replace("react\\.js","react")
            if re.search(rf"\b{pattern}\b", low):
                # normalize names
                name = t
                if t.lower() in {"react.js","react"}: name = "React.js"
                if t.lower()=="dsa": name = "Data Structures & Algorithms"
                if name not in vals:
                    vals.append(name)
        result[key] = vals
    return result


def extract_education(text: str) -> list:
    section = extract_section(text, "Education")
    items = []
    for line in section.splitlines():
        l = line.strip()
        if not l:
            continue
        if re.search(r"\b(20\d{2}|19\d{2})\b", l):
            items.append(l)
    return items


def extract_internships(text: str) -> list:
    section = extract_section(text, "Internship") or extract_section(text, "Internships") or extract_section(text, "Experience")
    items = []
    for para in re.split(r"\n{2,}", section):
        p = para.strip()
        if not p:
            continue
        if re.search(r"(?i)\bIntern", p) or re.search(r"\b(20\d{2}|19\d{2})\b", p):
            items.append(p)
    return items


def extract_current_job(text: str) -> str | None:
    exp = extract_section(text, "Experience")
    lines = [l.strip() for l in exp.splitlines() if l.strip()]
    for l in lines:
        if re.search(r"(?i)\b(Developer|Engineer|Software|SDE|Data)\b", l) and not re.search(r"(?i)\bIntern\b", l):
            return l
    # Fallback: look across entire resume
    for l in [l.strip() for l in text.splitlines() if l.strip()]:
        if re.search(r"(?i)\b(Developer|Engineer|Software|SDE|Data)\b", l) and not re.search(r"(?i)\bIntern\b", l):
            return l
    return None


def structure_education(education_lines: list) -> list:
    structured = []
    for l in education_lines:
        title = "Education"
        tl = l.lower()
        if any(k in tl for k in ["b.tech", "btech", "bachelor", "b.sc", "bsc", "be "]):
            title = "Bachelor"
        elif any(k in tl for k in ["m.tech", "mtech", "master", "m.sc", "msc", "mba"]):
            title = "Masters"
        elif any(k in tl for k in ["high school", "hsc", "pcm", "12th", "10th"]):
            title = "High School"
        # Extract period
        m = re.search(r"((Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4}\s*-\s*(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4}|\d{4}\s*-\s*\d{4}|\d{4})", l)
        period = m.group(0) if m else ""
        structured.append({"type": title, "text": l, "period": period})
    return structured


def build_journey(education: list, internships: list, current_job: str | None) -> list:
    items = []
    for e in education:
        items.append({"title": e["type"], "text": e["text"], "period": e.get("period")})
    if current_job:
        items.append({"title": "Current Job", "text": current_job, "period": None})
    for it in internships:
        items.append({"title": "Internship", "text": it, "period": None})
    return items


def extract_projects(text: str) -> list:
    base = extract_section(text, "Projects") or text
    lines = [l.strip() for l in base.splitlines()]
    global_lines = [l.strip() for l in text.splitlines()]
    items = []
    seen_urls = set()
    seen_names = set()

    def infer_name(idx: int) -> str:
        # Prefer previous non-empty line containing a dash or colon
        for j in range(idx - 1, max(0, idx - 4), -1):
            cand = lines[j]
            if not cand:
                continue
            if "—" in cand or "-" in cand or ":" in cand:
                head = re.split(r"[—:-]", cand)[0].strip()
                if len(head) >= 3:
                    return head
            if cand.startswith("•"):
                return cand.lstrip("•").strip()
        # fallback to domain host
        return ""

    def clean_name(name: str) -> str:
        name = re.sub(r"\(.*?\)", "", name).strip()
        name = re.sub(r"\bTech\b.*", "", name).strip()
        name = re.sub(r"[^A-Za-z0-9 +._-]", " ", name)
        name = re.sub(r"\s{2,}", " ", name)
        name = name[:60].strip()
        # title-case words
        return " ".join(w.capitalize() for w in name.split())

    for i, l in enumerate(lines):
        if re.search(r"(?i)\bLink\b\s*:", l):
            # extract the first URL or domain on this line
            cand_urls = extract_urls(l)
            url = cand_urls[0] if cand_urls else None
            if not url:
                # try next lines
                for k in range(i + 1, min(i + 3, len(lines))):
                    cand_urls = extract_urls(lines[k])
                    if cand_urls:
                        url = cand_urls[0]
                        break
            name = infer_name(i) or (re.sub(r"https?://(www\.)?", "", url).split("/")[0].split(".")[0].title() if url else "Project")
            name = clean_name(name) or "Project"
            # description: merge previous bullets and next lines until blank
            prev = " ".join([x for x in lines[max(0, i - 3):i] if x and not re.search(r"(?i)\bLink\b", x)])
            nxt = []
            for k in range(i + 1, min(i + 6, len(lines))):
                if not lines[k]:
                    break
                if re.search(r"(?i)\bLink\b", lines[k]):
                    break
                nxt.append(lines[k])
            desc = (prev + " " + " ".join(nxt)).strip()
            desc = re.sub(r"\s{2,}", " ", desc)[:300]
            key = (name.lower(), (url or ""))
            if key in seen_urls:
                continue
            seen_urls.add(key)
            items.append({"name": name, "url": url, "description": desc or "Project", "image": None})

    # Also parse bullet-style projects even without explicit links
    def parse_bullets(src_lines):
        result = []
        i = 0
        while i < len(src_lines):
            line = src_lines[i]
            if line.startswith("•") or re.match(r"^[-*]\s+", line):
                text_line = line.lstrip("•-* ").strip()
                if "—" in text_line or ":" in text_line or "-" in text_line:
                    name_candidate = re.split(r"[—:-]", text_line)[0].strip()
                    name_candidate = clean_name(name_candidate)
                    desc_parts = [text_line]
                    j = i + 1
                    while j < len(src_lines) and src_lines[j] and not src_lines[j].startswith("•") and not re.match(r"^[-*]\s+", src_lines[j]) and not re.search(r"(?i)\bLink\b", src_lines[j]):
                        desc_parts.append(src_lines[j])
                        j += 1
                    desc = " ".join(desc_parts)
                    desc = re.sub(r"\s{2,}", " ", desc)[:300]
                    # find link near bullets
                    url = None
                    for k in range(i, min(i + 12, len(src_lines))):
                        if re.search(r"(?i)\bLink\b", src_lines[k]):
                            found = extract_urls(src_lines[k])
                            if found:
                                url = found[0]
                                break
                    if name_candidate and name_candidate.lower() not in seen_names:
                        seen_names.add(name_candidate.lower())
                        result.append({"name": name_candidate, "url": url, "description": desc or "Project", "image": None})
                    i = j
                    continue
            i += 1
        return result

    items += parse_bullets(lines)
    # Parse bullets within Internship/Experience sections, but skip non-project bullets
    internship_section = extract_section(text, "Internship") or extract_section(text, "Internships") or extract_section(text, "Experience")
    internship_lines = [l.strip() for l in internship_section.splitlines()]

    def is_valid_project_name(name: str) -> bool:
        lowered = name.lower()
        banned_starts = [
            "developed", "designed", "integrated", "implemented", "build", "built",
            "github", "coursera", "kaggle", "udemy", "certification", "link", "languages",
            "soft skills", "tech stack", "teamwork"
        ]
        return not any(lowered.startswith(b) for b in banned_starts) and len(name) >= 3

    intern_projects = []
    tmp = parse_bullets(internship_lines)
    for it in tmp:
        if is_valid_project_name(it["name"]) and it["name"].lower() not in {x["name"].lower() for x in items}:
            intern_projects.append(it)
    items += intern_projects
    # Ensure known projects exist
    def ensure_known(name_key: str, alias_list: list[str], url_hints: list[str]):
        exists = any(name_key.lower() == p["name"].lower() for p in items)
        if exists:
            return
        found_line = None
        found_url = None
        for i, l in enumerate(global_lines):
            if any(a.lower() in l.lower() for a in alias_list):
                found_line = l
                for j in range(i, min(i + 8, len(global_lines))):
                    u = extract_urls(global_lines[j])
                    if u:
                        found_url = u[0]
                        break
                break
        if not found_url:
            for hint in url_hints:
                for u in extract_urls(text):
                    if hint in u:
                        found_url = u
                        break
        if found_line or found_url:
            desc = found_line or name_key
            items.append({"name": name_key, "url": found_url, "description": desc, "image": None})

    ensure_known("MyPrepSpot", ["MyPrepSpot"], ["myprepspot.com"])
    ensure_known("Career-F-Crawler", ["Career-F-Crawler","Career F Crawler"], ["career-f-crawler.onrender.com"])

    # If still empty, fall back to any URLs and make items
    if not items:
        urls = extract_urls(base)
        for u in urls:
            host = re.sub(r"https?://(www\.)?", "", u).split("/")[0]
            name = host.split(".")[0].title()
            if u in seen_urls:
                continue
            seen_urls.add(u)
            items.append({"name": name, "url": u, "description": "Project", "image": None})
    return items


def fetch_og_image(url: str) -> str | None:
    try:
        r = requests.get(url, timeout=10)
        if r.status_code != 200:
            # fallback to screenshot service
            return f"https://image.thum.io/get/width/1200/noanimate/{url}"
        soup = BeautifulSoup(r.text, "html.parser")
        og = soup.find("meta", property="og:image")
        if og and og.get("content"):
            return og.get("content")
        img = soup.find("img")
        if img and img.get("src"):
            src = img.get("src")
            if src.startswith("http"):
                return src
        # fallback to screenshot service
        return f"https://image.thum.io/get/width/1200/noanimate/{url}"
    except Exception:
        return f"https://image.thum.io/get/width/1200/noanimate/{url}"


def download_image(src_url: str, dest_path: Path) -> bool:
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"}
        r = requests.get(src_url, timeout=15, headers=headers)
        if r.status_code == 200:
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            with open(dest_path, "wb") as f:
                f.write(r.content)
            return True
        return False
    except Exception:
        return False


def build_data() -> dict:
    text = read_pdf_text(RESUME_PATH) if RESUME_PATH.exists() else ""
    name = find_name(text) if text else "Zuber"
    about = extract_section(text, "Summary") or extract_section(text, "Objective") or extract_section(text, "About")
    contacts = extract_contacts(text)
    if not contacts.get("email"):
        contacts["email"] = "zubekhan7301@gmail.com"
    tech_skills = extract_technical_skills(text)
    # if we captured at least one category item, use the technical skills; else fallback
    if any(len(v) > 0 for v in tech_skills.values()):
        skills = tech_skills
    else:
        skills = extract_skills(text)
    education_lines = extract_education(text)
    education = structure_education(education_lines)
    internships = extract_internships(text)
    current_job = extract_current_job(text)
    projects = extract_projects(text)
    tagline = "An aspiring Full Stack Developer passionate about building sleek web experiences."
    # ensure profile photo under static/images
    profile_photo = None
    src_candidates = [BASE_DIR / "photoo.jpg", BASE_DIR / "phottoo.jpg"]
    for src in src_candidates:
        if src.exists():
            IMG_DIR.mkdir(parents=True, exist_ok=True)
            dest = IMG_DIR / "profile.jpg"
            try:
                with open(src, "rb") as rf, open(dest, "wb") as wf:
                    wf.write(rf.read())
                profile_photo = "profile.jpg"
            except Exception:
                profile_photo = None
            break

    tech_tag_map = {
        "React": ["react", "react.js"],
        "Next.js": ["next.js"],
        "Node.js": ["node", "node.js"],
        "Django": ["django"],
        "Flask": ["flask"],
        "Tailwind CSS": ["tailwind"],
        "Bootstrap": ["bootstrap"],
        "MongoDB": ["mongodb"],
        "PostgreSQL": ["postgresql", "postgres"],
        "MySQL": ["mysql"],
        "Python": ["python"],
        "TypeScript": ["typescript"],
        "JavaScript": ["javascript"],
    }
    for p in projects:
        if p["url"]:
            src = fetch_og_image(p["url"])
            if src:
                slug = re.sub(r"[^a-z0-9]+", "-", p["name"].lower()).strip("-")
                dest = PROJECT_IMG_DIR / f"{slug}.jpg"
                ok = download_image(src, dest)
                if ok:
                    p["image"] = f"projects/{dest.name}"
                else:
                    p["image_remote"] = src
        # derive tags from description text
        tags = []
        desc_low = (p.get("description") or "").lower()
        for tag, keys in tech_tag_map.items():
            if any(k in desc_low for k in keys):
                tags.append(tag)
        p["tags"] = tags
    journey = build_journey(education, internships, current_job)
    roles = ["Full Stack Developer", "Machine Learning", "Data Engineer"]
    data = {
        "name": name,
        "tagline": tagline,
        "about": about,
        "contacts": contacts,
        "contact_email": contacts.get("email"),
        "skills": skills,
        "education": education,
        "internships": internships,
        "current_job": current_job,
        "journey": journey,
        "projects": projects,
        "photo": profile_photo,
        "roles": roles,
    }
    return data


def load_data() -> dict:
    if DATA_CACHE.exists():
        try:
            with open(DATA_CACHE, "r", encoding="utf-8") as rf:
                return json.load(rf)
        except Exception:
            pass
    data = build_data()
    try:
        DATA_CACHE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass
    return data


@app.route("/")
def index():
    data = load_data()
    return render_template("index.html", data=data)


@app.route("/images/<path:filename>")
def images(filename: str):
    return send_from_directory(IMG_DIR, filename)

@app.route("/resume")
def download_resume():
    if RESUME_PATH.exists():
        return send_from_directory(BASE_DIR, RESUME_PATH.name, as_attachment=True, download_name="Zuber_Resume_09.pdf")
    return ("Resume not found", 404)

def send_email(to_email: str, subject: str, body: str) -> bool:
    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASS")
    if not smtp_user or not smtp_pass or not to_email:
        return False
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = smtp_user
    msg["To"] = to_email
    msg.set_content(body)
    try:
        ctx = ssl.create_default_context()
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ctx) as server:
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
        return True
    except Exception:
        return False

@app.post("/contact")
def contact_submit():
    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip()
    message = request.form.get("message", "").strip()
    if not name or not email or not message:
        return jsonify({"ok": False, "error": "Missing fields"}), 400
    body = f"New portfolio contact:\n\nName: {name}\nEmail: {email}\n\nMessage:\n{message}"
    to_email = load_data().get("contact_email") or "zubekhan7301@gmail.com"
    sent = send_email(to_email, "Portfolio Contact", body)
    if sent:
        return jsonify({"ok": True})
    # Fallback store
    print(f"EMAIL SIMULATION:\nTo: {to_email}\nSubject: Portfolio Contact\nBody:\n{body}\n----------------")
    store_path = BASE_DIR / "messages.json"
    try:
        existing = []
        if store_path.exists():
            with open(store_path, "r", encoding="utf-8") as rf:
                existing = json.load(rf)
        existing.append({"name": name, "email": email, "message": message})
        with open(store_path, "w", encoding="utf-8") as wf:
            json.dump(existing, wf, indent=2)
        return jsonify({"ok": True, "stored": True})
    except Exception as e:
        print(f"Storage failed: {e}")
        return jsonify({"ok": False, "error": "Email not configured and storage read-only."}), 500


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
