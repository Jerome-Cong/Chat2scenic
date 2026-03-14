import requests
from pathlib import Path
from urllib.parse import urlparse
import time
from bs4 import BeautifulSoup

URLS = [
    "https://docs.scenic-lang.org/en/latest/syntax_guide.html",
    "https://docs.scenic-lang.org/en/latest/tutorials/fundamentals.html",
    "https://docs.scenic-lang.org/en/latest/tutorials/dynamics.html",
    "https://docs.scenic-lang.org/en/latest/tutorials/composition.html",
    "https://docs.scenic-lang.org/en/latest/reference/general.html",
    "https://docs.scenic-lang.org/en/latest/reference/data.html",
    "https://docs.scenic-lang.org/en/latest/reference/region_types.html",
    "https://docs.scenic-lang.org/en/latest/reference/distributions.html",
    "https://docs.scenic-lang.org/en/latest/reference/statements.html",
    "https://docs.scenic-lang.org/en/latest/reference/classes.html",
    "https://docs.scenic-lang.org/en/latest/reference/sensors.html",
    "https://docs.scenic-lang.org/en/latest/reference/specifiers.html",
    "https://docs.scenic-lang.org/en/latest/reference/operators.html",
    "https://docs.scenic-lang.org/en/latest/reference/functions.html",
    "https://docs.scenic-lang.org/en/latest/reference/visibility.html",
    "https://docs.scenic-lang.org/en/latest/reference/scene_generation.html",
    "https://docs.scenic-lang.org/en/latest/reference/dynamic_scenarios.html",
]

def scrape_url(url: str, output_dir: Path) -> bool:
    try:
        print(f"Fetching: {url}")
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        main_content = None
        for selector in ['div.document', 'div[role="main"]', 'main', 'article', 'div.body']:
            main_content = soup.select_one(selector)
            if main_content:
                break
        if not main_content:
            main_content = soup.find('body') or soup
        parsed = urlparse(url)
        path_parts = parsed.path.strip('/').split('/')
        if len(path_parts) >= 2:
            filename = f"{path_parts[-2]}_{path_parts[-1]}"
        else:
            filename = path_parts[-1] if path_parts else "index.html"
        if filename.endswith('.html'):
            filename = filename[:-5]
        filename = f"{filename}.html"
        output_file = output_dir / filename
        output_file.write_text(str(main_content), encoding='utf-8')
        return True
        
    except requests.exceptions.RequestException as e:
        print(f"✗ Error fetching {url}: {e}")
        return False
    except Exception as e:
        print(f"✗ Error processing {url}: {e}")
        return False


def main():
    output_dir = Path(__file__).parent.parent / "data" / "html"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    success_count = 0
    failure_count = 0
    
    for i, url in enumerate(URLS, 1):
        print(f"[{i}/{len(URLS)}] ", end="")
        
        if scrape_url(url, output_dir):
            success_count += 1
        else:
            failure_count += 1
        
        if i < len(URLS):
            time.sleep(1)
        
        print()

if __name__ == "__main__":
    main()
