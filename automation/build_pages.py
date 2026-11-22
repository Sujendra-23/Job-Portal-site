"""Stage the existing public site, excluding exports, tests, and credentials."""
import argparse
import json
from pathlib import Path
import shutil

PUBLIC_DATA = ('roles_top.json', 'roles_midsize.json', 'roles_growth.json', 'roles_startup.json',
               'roles_linkedin_posts.json', 'roles_unverified.json', 'roles_jobright.json',
               'jobright_sync.json', 'roles_jobright_public.json', 'jobright_public_sync.json', 'emails.json', 'resumes.json', 'top_companies.json')

def build(root):
    out = root / '_site'
    if out.exists():
        shutil.rmtree(out)
    out.mkdir()
    for name in PUBLIC_DATA:
        p = root / name
        json.loads(p.read_text())
        shutil.copy2(p, out / name)
    for pattern in ('*.html', '*.css', '*.js', '*.png', '*.jpg', '*.svg', '*.ico', 'CNAME', '.nojekyll'):
        for p in root.glob(pattern):
            shutil.copy2(p, out / p.name)
    (out / 'automation').mkdir()
    shutil.copy2(root / 'automation/portal-automation.js', out / 'automation/portal-automation.js')
    (out / '.nojekyll').touch()
    return out

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    build(parser.parse_args().root)
