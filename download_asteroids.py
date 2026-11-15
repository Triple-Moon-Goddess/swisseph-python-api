#!/usr/bin/env python3
"""
Make sure the numbered-asteroid ephemeris files are real Swiss Ephemeris data.

Ceres, Pallas, Juno, Vesta and Chiron as /api/planets computes them (bodies
15 and 17-20) come from ephe/seas_18.se1, not from these files. Astrodienst
publishes no separate se00001-se00004 files; those bodies only exist inside
seas_*.se1. The one numbered file kept here is Chiron's se02060.se1, used for
asteroid number 2060 (AST_OFFSET + 2060).

A file counts as real only if it starts with the SWISSEPH header and names
itself in its second line. Anything else (an HTML page saved by an earlier
download, an error body, a truncated file) is removed and fetched again.
Downloads are HTTPS only, from the official location Astrodienst links at
https://www.astro.com/ftp/swisseph/ephe/ (Alois Treindl's public Dropbox).
A failed download is reported, never fatal: the server still starts.
"""
import os
import sys
import tempfile
import urllib.error
import urllib.request

EPHE_DIR = '/app/ephe'

# Official numbered-asteroid folder 'all_ast' linked from astro.com/ftp/swisseph/ephe/
SOURCE = ('https://www.dropbox.com/scl/fo/y3naz62gy6f6qfrhquu7u/h/all_ast/{subdir}/{filename}'
          '?rlkey=ejltdhb262zglm7eo6yfj2940&dl=1')

# (asteroid number, subdirectory, filename)
ASTEROIDS = [
    (2060, 'ast2', 'se02060.se1'),   # Chiron
]

MAGIC = b'SWISSEPH'
MIN_SIZE = 1024


def ephemeris_problem(path, name=None):
    """Return why the file at path is not real Swiss Ephemeris data, or None if it is.

    name is the filename the header must carry (defaults to path's own name).
    """
    name = name or os.path.basename(path)
    try:
        size = os.path.getsize(path)
        with open(path, 'rb') as f:
            head = f.read(256)
    except OSError as e:
        return f'unreadable: {e}'
    if head.lstrip()[:1] == b'<':
        return 'HTML/markup, not ephemeris data'
    if not head.startswith(MAGIC):
        return 'no SWISSEPH header'
    lines = head.split(b'\n')
    if len(lines) < 2 or lines[1].strip().decode('ascii', 'replace') != name:
        return 'header does not name this file'
    if size < MIN_SIZE:
        return f'too small ({size} bytes)'
    return None


class _HttpsOnlyRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not newurl.lower().startswith('https://'):
            raise urllib.error.URLError(f'refusing non-HTTPS redirect to {newurl}')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch(url, dest):
    """Download url to dest over HTTPS only (redirects included)."""
    if not url.lower().startswith('https://'):
        raise ValueError(f'refusing non-HTTPS URL {url}')
    opener = urllib.request.build_opener(_HttpsOnlyRedirects)
    with opener.open(url, timeout=60) as r, open(dest, 'wb') as out:
        while chunk := r.read(65536):
            out.write(chunk)


def ensure_file(ephe_dir, subdir, filename, fetch=fetch):
    """Keep a valid file, otherwise download it; True when a valid file is in place."""
    ast_dir = os.path.join(ephe_dir, subdir)
    os.makedirs(ast_dir, exist_ok=True)
    path = os.path.join(ast_dir, filename)

    if os.path.exists(path):
        problem = ephemeris_problem(path)
        if problem is None:
            print(f'✓ {filename} present and valid')
            return True
        print(f'  {filename} is not ephemeris data ({problem}); replacing it')
        os.remove(path)

    url = SOURCE.format(subdir=subdir, filename=filename)
    fd, tmp = tempfile.mkstemp(dir=ast_dir, prefix=f'.{filename}.')
    os.close(fd)
    try:
        print(f'Downloading {filename}...')
        fetch(url, tmp)
        problem = ephemeris_problem(tmp, filename)
        if problem:
            print(f'✗ {filename}: download is not ephemeris data ({problem})')
            return False
        os.replace(tmp, path)
        print(f'✓ Downloaded {filename}')
        return True
    except Exception as e:
        print(f'✗ Could not download {filename}: {e}')
        return False
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def download_asteroid_files(ephe_dir=EPHE_DIR, fetch=fetch):
    return all([ensure_file(ephe_dir, subdir, filename, fetch) for _, subdir, filename in ASTEROIDS])


if __name__ == '__main__':
    download_asteroid_files()
    sys.exit(0)
