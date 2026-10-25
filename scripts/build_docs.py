"""Generate/check offline HTML for every source module with standard-library pydoc.

Run ``python scripts/build_docs.py`` from any directory. Use ``--check`` for
read-only verification of source coverage, source/page hashes and local links.
No dataset, network access or third-party documentation generator is required.
"""
from pathlib import Path
import argparse
import hashlib
from html import escape
from html.parser import HTMLParser
import json
import os
import re
import subprocess
import sys
from urllib.parse import unquote, urlsplit


def source_modules(root):
    """Return module names and paths, including package initialisers recursively."""
    modules = {}
    for source in sorted((root / 'src/apple_tree_project').rglob('*.py')):
        parts = list(source.relative_to(root / 'src').with_suffix('').parts)
        if parts[-1] == '__init__':
            parts.pop()
        modules['.'.join(parts)] = source
    return modules


def sha256(path):
    """Hash text with CRLF normalised to LF for Windows/Linux checkouts."""
    return hashlib.sha256(path.read_bytes().replace(b'\r\n', b'\n')).hexdigest()


def local_links(page):
    """Return local file targets; imported dependencies are not packaged docs."""
    class Links(HTMLParser):
        def __init__(self):
            super().__init__()
            self.targets = []

        def handle_starttag(self, tag, attrs):
            for key, value in attrs:
                if key not in ('href', 'src') or not value:
                    continue
                url = urlsplit(value)
                if not url.scheme and not url.netloc and url.path:
                    self.targets.append(page.parent / unquote(url.path))
    parser = Links()
    parser.feed(page.read_text(encoding='utf-8'))
    return parser.targets


def check(root, target, modules):
    """Raise on missing/stale module pages or broken local file links."""
    manifest = json.loads((target / 'api_manifest.json').read_text(encoding='utf-8'))
    if set(manifest['modules']) != set(modules):
        raise ValueError('API module coverage is stale; regenerate documentation')
    for name, source in modules.items():
        row = manifest['modules'][name]
        if row['source'] != source.relative_to(root).as_posix():
            raise ValueError(f'Source path changed: {name}')
        if row['source_sha256'] != sha256(source):
            raise ValueError(f'Source changed: {name}; regenerate documentation')
        if row['html_sha256'] != sha256(target / (name + '.html')):
            raise ValueError(f'HTML changed: {name}; regenerate documentation')
    if manifest['index_sha256'] != sha256(target / 'index.html'):
        raise ValueError('API index changed; regenerate documentation')
    for page in [target / 'index.html'] + [target / (n + '.html') for n in modules]:
        for link in local_links(page):
            if not link.exists():
                raise ValueError(f'Broken local link from {page.name}: {link}')
    print(f'API check passed: {len(modules)} modules, source/page hashes and local links')


def build(root, target, modules):
    """Render current docstrings, portable source links and a complete API index."""
    target.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    env['PYTHONPATH'] = str(root / 'src') + os.pathsep + env.get('PYTHONPATH', '')
    manifest = {'generator': 'Python standard-library pydoc',
                'hash_policy': 'Text bytes with CRLF normalised to LF', 'modules': {}}
    for name, source in modules.items():
        subprocess.run([sys.executable, '-m', 'pydoc', '-w', name],
                       cwd=target, env=env, check=True)
        page = target / (name + '.html')
        content = page.read_text(encoding='utf-8')
        relative = '../../' + source.relative_to(root).as_posix()
        content = re.sub(r'<a href="file:[^"]*">[^<]*</a>',
                         f'<a href="{relative}">{relative}</a>', content)

        def dependency_link(match):
            href, label = match.group(1), match.group(2)
            path = urlsplit(href)
            if (not path.scheme and path.path.endswith('.html')
                    and not path.path.startswith('apple_tree_project')):
                return label
            return match.group(0)
        # pydoc links imported modules to nonexistent local numpy.html/math.html.
        # Keep their names, while retaining every project-module/source hyperlink.
        content = re.sub(r'<a href="([^"]+)">(.*?)</a>', dependency_link, content)
        page.write_text(content, encoding='utf-8')
        manifest['modules'][name] = dict(source=source.relative_to(root).as_posix(),
                                        source_sha256=sha256(source),html_sha256=sha256(page))
    links = '\n'.join(f'<li><a href="{n}.html">{escape(n)}</a></li>' for n in modules)
    index = ('<!doctype html><html lang="en"><meta charset="utf-8">'
             '<title>Apple Tree Project API</title><h1>Source API documentation</h1>'
             '<p>All current package modules. Generated with standard-library pydoc. '
             'Imported third-party APIs are outside this offline documentation.</p>'
             '<p><a href="../../README.md">README</a> | '
             '<a href="../20_reproducibility.md">Reproduction guide</a></p>'
             f'<ul>{links}</ul></html>\n')
    (target / 'index.html').write_text(index, encoding='utf-8')
    manifest['index_sha256'] = sha256(target / 'index.html')
    (target / 'api_manifest.json').write_text(json.dumps(manifest, indent=2)+'\n',encoding='utf-8')
    check(root, target, modules)


def main():
    """Build pages by default; ``--check`` verifies existing pages without writes."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Read-only freshness/link check')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    modules = source_modules(root)
    target = root / 'docs/api'
    (check if args.check else build)(root, target, modules)


if __name__ == '__main__':
    main()
