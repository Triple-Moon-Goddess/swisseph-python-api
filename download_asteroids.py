#!/usr/bin/env python3
"""
Download asteroid ephemeris files for Swiss Ephemeris
"""
import urllib.request
import os

# Asteroid numbers and their subdirectories
asteroids = [
    (1, 'ast0', 'se00001.se1'),      # Ceres
    (2, 'ast0', 'se00002.se1'),      # Pallas
    (3, 'ast0', 'se00003.se1'),      # Juno
    (4, 'ast0', 'se00004.se1'),      # Vesta
    (2060, 'ast2', 'se02060.se1'),   # Chiron
]

def download_asteroid_files():
    """Download asteroid ephemeris files"""
    ephe_dir = '/app/ephe'

    # Try different base URLs (GitHub is currently working)
    base_urls = [
        'https://github.com/aloistr/swisseph/raw/master/ephe',
        'http://www.astro.com/ftp/swisseph/ephe',
    ]

    for num, subdir, filename in asteroids:
        ast_dir = os.path.join(ephe_dir, subdir)
        os.makedirs(ast_dir, exist_ok=True)

        output_file = os.path.join(ast_dir, filename)

        # Skip if already exists
        if os.path.exists(output_file):
            print(f"✓ {filename} already exists")
            continue

        # Try each base URL
        for base_url in base_urls:
            url = f"{base_url}/{subdir}/{filename}"

            try:
                print(f"Downloading {filename} from {base_url}...")
                urllib.request.urlretrieve(url, output_file)

                # Check if file is valid (not HTML error page)
                if os.path.getsize(output_file) < 100:
                    os.remove(output_file)
                    print(f"  Invalid file, trying next source...")
                    continue

                print(f"✓ Downloaded {filename}")
                break

            except Exception as e:
                print(f"  Failed: {e}")
                continue

        if not os.path.exists(output_file):
            print(f"✗ Could not download {filename}")

if __name__ == '__main__':
    download_asteroid_files()
