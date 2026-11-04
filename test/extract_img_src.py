import os
import re
import sys
import html
import argparse
import urllib.request
from urllib.parse import urlparse

# Windows 콘솔 인코딩 대응
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

def extract_img_sources(html_content: str) -> list[str]:
    """
    HTML 문자열에서 <img ... src="..." ...>의 src 값을 정규식으로 추출하고,
    HTML 엔티티(&amp; 등)를 디코딩하여 반환합니다.
    """
    pattern = re.compile(r'<img\s+[^>]*?src=["\']([^"\']+)["\']', re.IGNORECASE)
    raw_urls = pattern.findall(html_content)
    
    clean_urls = [html.unescape(url.strip()) for url in raw_urls if url.strip()]
    return clean_urls

def save_urls_to_file(urls: list[str], output_path: str):
    """추출된 URL들을 텍스트 파일로 저장합니다."""
    with open(output_path, "w", encoding="utf-8") as f:
        for url in urls:
            f.write(url + "\n")
    print(f"[OK] 총 {len(urls)}개의 이미지 URL을 '{output_path}' 파일에 저장했습니다.")

def download_images(urls: list[str], download_dir: str):
    """추출된 URL에서 이미지를 직접 다운로드합니다."""
    os.makedirs(download_dir, exist_ok=True)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://jcomic.net/"
    }
    
    total = len(urls)
    print(f"\n[+] 총 {total}개의 이미지를 '{download_dir}' 폴더에 다운로드 시작...")
    
    success_count = 0
    forbidden_count = 0
    
    for idx, url in enumerate(urls, start=1):
        try:
            parsed_path = urlparse(url).path
            base_filename = os.path.basename(parsed_path)
            
            if not base_filename or "." not in base_filename:
                filename = f"{idx:03d}.jpg"
            else:
                filename = f"{idx:03d}_{base_filename}"
                
            save_path = os.path.join(download_dir, filename)
            
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = resp.read()
                with open(save_path, "wb") as img_file:
                    img_file.write(data)
                    
            print(f"  [{idx}/{total}] 완료: {filename}")
            success_count += 1
        except urllib.error.HTTPError as e:
            if e.code == 403:
                forbidden_count += 1
                if forbidden_count == 1:
                    print(f"\n[!] 403 Forbidden 발생 원인:")
                    print(f"    1) Cloudflare 보안 차단 (봇 감지)")
                    print(f"    2) AWS S3 서명 만료 (X-Amz-Expires=60 으로 60초가 지나면 만료됨)")
                    print(f"    -> 브라우저(F12 콘솔) 다운로드 스크립트를 사용하면 차단 없이 즉시 저장 가능합니다.\n")
            print(f"  [{idx}/{total}] HTTP {e.code} 에러: {filename}")
        except Exception as e:
            print(f"  [{idx}/{total}] 실패: {e}")

def main():
    parser = argparse.ArgumentParser(
        description="HTML에서 img src를 추출하여 파일로 저장하는 CLI 도구"
    )
    parser.add_argument(
        "input",
        nargs="?",
        default=None,
        help="입력 HTML 파일 경로 (지정하지 않으면 표준 입력(stdin)에서 읽음)"
    )
    parser.add_argument(
        "-o", "--output",
        default="img_urls.txt",
        help="추출된 URL 목록을 저장할 파일명 (기본값: img_urls.txt)"
    )
    parser.add_argument(
        "-d", "--download",
        metavar="FOLDER",
        nargs="?",
        const="downloaded_images",
        default=None,
        help="실제 이미지 파일까지 다운로드하여 저장할 폴더명 (기본 폴더: downloaded_images)"
    )
    
    args = parser.parse_args()
    
    if args.input:
        if not os.path.exists(args.input):
            print(f"[!] 오류: 파일 '{args.input}'을 찾을 수 없습니다.", file=sys.stderr)
            sys.exit(1)
        with open(args.input, "r", encoding="utf-8", errors="ignore") as f:
            html_text = f.read()
    else:
        if not sys.stdin.isatty():
            html_text = sys.stdin.read()
        else:
            parser.print_help()
            sys.exit(0)
            
    urls = extract_img_sources(html_text)
    if not urls:
        print("[!] <img> 태그에서 src 속성을 찾지 못했습니다.")
        sys.exit(0)
        
    print(f"[+] {len(urls)}개의 이미지 링크를 발견했습니다.")
    save_urls_to_file(urls, args.output)
    
    if args.download:
        download_images(urls, args.download)

if __name__ == "__main__":
    main()
