import os
import urllib.request
import json
import re
from datetime import datetime, timezone

def fetch_json(url):
    req = urllib.request.Request(url)
    token = os.environ.get('GITHUB_TOKEN')
    if token:
        req.add_header('Authorization', f'Bearer {token}')
    req.add_header('Accept', 'application/vnd.github.v3+json')
    req.add_header('User-Agent', 'yuvanharshaj-profile-updater')
    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode())
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return None

def get_uptime(created_at_str):
    created_at = datetime.strptime(created_at_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    days = (now - created_at).days
    years = days // 365
    remaining_days = days % 365
    months = remaining_days // 30
    remaining_days = remaining_days % 30
    
    parts = []
    if years > 0:
        parts.append(f"{years} year{'s' if years > 1 else ''}")
    if months > 0:
        parts.append(f"{months} month{'s' if months > 1 else ''}")
    if remaining_days > 0 and len(parts) < 2:
        parts.append(f"{remaining_days} day{'s' if remaining_days > 1 else ''}")
    if not parts:
        parts.append("0 days")
    
    return ", ".join(parts[:2])

def update_svg_line(svg_content, label, new_value, total_len):
    pattern = r'(<text[^>]*>\s*<tspan[^>]*>)' + re.escape(label) + r'(</tspan>\s*<tspan[^>]*>)\.+(\s*</tspan>\s*<tspan[^>]*> )[^<]*(</tspan>\s*</text>)'
    
    def repl(m):
        prefix1 = m.group(1)
        prefix2 = m.group(2)
        prefix3 = m.group(3)
        suffix = m.group(4)
        
        l_len = len(label)
        v_len = len(f" {new_value}")
        dots_count = total_len - l_len - v_len
        if dots_count < 1:
            dots_count = 1
        dots = "." * dots_count
        
        return f"{prefix1}{label}{prefix2}{dots}{prefix3}{new_value}{suffix}"
        
    new_content, count = re.subn(pattern, repl, svg_content)
    if count == 0:
        print(f"Warning: Label {label} not found.")
    return new_content

def ensure_updated_line(svg_content, updated_val):
    if ". Updated: " in svg_content:
        return update_svg_line(svg_content, ". Updated: ", updated_val, 35)
    
    # We need to add it after . Commits: 
    # Let's find the Commits line to copy its style and increment Y
    commits_pattern = r'(<text[^>]*y=")(\d+)("[^>]*>\s*<tspan[^>]*fill=")([^"]+)(">)\. Commits: (</tspan>\s*<tspan[^>]*fill=")([^"]+)(">\.+</tspan>\s*<tspan[^>]*fill=")([^"]+)("> )[^<]*(</tspan>\s*</text>)'
    
    match = re.search(commits_pattern, svg_content)
    if not match:
        print("Warning: Commits line not found, cannot append Updated line.")
        return svg_content
    
    full_commits_line = match.group(0)
    y_val = int(match.group(2))
    new_y = y_val + 20
    label_color = match.group(4)
    dots_color = match.group(7)
    val_color = match.group(9)
    
    label_str = ". Updated: "
    total_len = 35
    dots_count = total_len - len(label_str) - len(f" {updated_val}")
    if dots_count < 1:
        dots_count = 1
    dots = "." * dots_count
    
    # Extract x and other attributes from the text tag
    text_tag_match = re.search(r'<text([^>]*)>', full_commits_line)
    text_attrs = text_tag_match.group(1)
    # replace y value
    text_attrs = re.sub(r'y="\d+"', f'y="{new_y}"', text_attrs)
    
    new_line = f'\n  <text{text_attrs}><tspan fill="{label_color}">{label_str}</tspan><tspan fill="{dots_color}">{dots}</tspan><tspan fill="{val_color}"> {updated_val}</tspan></text>'
    
    # Insert new line after full_commits_line
    return svg_content.replace(full_commits_line, full_commits_line + new_line)

def main():
    username = "yuvanharshaj"
    
    # 1. Fetch user data
    user_data = fetch_json(f"https://api.github.com/users/{username}")
    if not user_data:
        return
    
    repos_count = user_data.get("public_repos", 0)
    uptime_str = get_uptime(user_data.get("created_at", "2020-01-01T00:00:00Z"))
    
    # 2. Fetch commits
    commits_data = fetch_json(f"https://api.github.com/search/commits?q=author:{username}")
    commits_count = commits_data.get("total_count", 0) if commits_data else 0
    
    # 3. Fetch languages
    repos = fetch_json(f"https://api.github.com/users/{username}/repos?per_page=100")
    langs = {}
    if repos:
        for r in repos:
            lang = r.get("language")
            if lang:
                langs[lang] = langs.get(lang, 0) + 1
                
    sorted_langs = sorted(langs.items(), key=lambda x: x[1], reverse=True)
    top_langs = [l[0] for l in sorted_langs[:5]]
    langs_str = ", ".join(top_langs) if top_langs else "None"
    
    # 4. Last updated
    # In Asia/Kolkata
    # Python datetime doesn't have ZoneInfo without importing zoneinfo (python 3.9+)
    # We can just use UTC + 5:30
    from datetime import timedelta
    ist = timezone(timedelta(hours=5, minutes=30))
    updated_str = datetime.now(ist).strftime("%d %b %Y")
    
    # 5. Update SVGs
    for filename in ["light_mode.svg", "dark_mode.svg"]:
        filepath = os.path.join(os.path.dirname(__file__), '..', filename)
        if not os.path.exists(filepath):
            filepath = filename # Try local if running in the same dir
        
        if not os.path.exists(filepath):
            print(f"Skipping {filename}, not found.")
            continue
            
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            
        content = update_svg_line(content, ". Uptime: ", uptime_str, 57)
        content = update_svg_line(content, ". Languages: ", langs_str, 57)
        content = update_svg_line(content, ". Repos: ", str(repos_count), 35)
        content = update_svg_line(content, ". Commits: ", str(commits_count), 35)
        content = ensure_updated_line(content, updated_str)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
            
    print("Profile SVGs updated successfully.")

if __name__ == "__main__":
    main()
