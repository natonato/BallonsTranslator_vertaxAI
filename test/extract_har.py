import os
import sys
import json
import base64
import argparse

# Windows 콘솔 인코딩 대응
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

def extract_images_from_har(har_path: str, output_dir: str):
    """
    브라우저에서 저장한 .har (Save all as HAR with content) 파일에서
    이미지 바이너리를 디코딩하여 파일로 저장합니다.
    CORS, Cloudflare 403, AWS 만료 제약 없이 100% 추출 가능합니다.
    """
    if not os.path.exists(har_path):
        print(f"[!] 오류: '{har_path}' 파일을 찾을 수 없습니다.", file=sys.stderr)
        return

    os.makedirs(output_dir, exist_ok=True)

    print(f"[*] HAR 파일 읽는 중: {har_path}...")
    with open(har_path, "r", encoding="utf-8", errors="ignore") as f:
        data = json.load(f)

    entries = data.get("log", {}).get("entries", [])
    print(f"[*] 총 {len(entries)}개의 네트워크 요청 기록을 분석합니다.")

    saved_count = 0
    for entry in entries:
        req_url = entry.get("request", {}).get("url", "")
        resp = entry.get("response", {})
        content = resp.get("content", {})
        mime_type = content.get("mimeType", "")
        text_data = content.get("text", "")
        encoding = content.get("encoding", "")

        # 이미지 타입이거나 URL에 .jpg, .png, .webp 등이 포함된 경우
        is_image = mime_type.startswith("image/") or any(ext in req_url.lower() for ext in [".jpg", ".jpeg", ".png", ".webp"])
        
        # comic-img / jcomic 이미지 위주 필터링 (필요시 전체 이미지 대상)
        if is_image and text_data:
            saved_count += 1
            # URL에서 파일명 추정
            clean_url = req_url.split("?")[0]
            base_name = os.path.basename(clean_url)
            
            ext = ".jpg"
            if "png" in mime_type:
                ext = ".png"
            elif "webp" in mime_type:
                ext = ".webp"
                
            if not base_name or "." not in base_name:
                filename = f"{saved_count:03d}{ext}"
            else:
                filename = f"{saved_count:03d}_{base_name}"
                
            out_file = os.path.join(output_dir, filename)

            try:
                if encoding == "base64":
                    img_bytes = base64.b64decode(text_data)
                else:
                    img_bytes = text_data.encode("latin1")

                with open(out_file, "wb") as img_f:
                    img_f.write(img_bytes)
                print(f"  [{saved_count}] 저장 완료: {filename} ({len(img_bytes):,} bytes)")
            except Exception as e:
                print(f"  [{saved_count}] 저장 실패: {e}")

    if saved_count > 0:
        print(f"\n[OK] 총 {saved_count}개의 이미지를 '{output_dir}' 폴더에 성공적으로 저장했습니다!")
    else:
        print("\n[!] HAR 파일 내에서 이미지 본문 데이터를 찾지 못했습니다.")
        print("    저장 시 반드시 'Save all as HAR with content'를 선택했는지 확인해주세요.")

def main():
    parser = argparse.ArgumentParser(
        description="브라우저에서 저장한 HAR 파일에서 이미지 파일들을 추출하는 도구"
    )
    parser.add_argument("har_file", help="브라우저에서 저장한 .har 파일 경로")
    parser.add_argument("-o", "--output", default="extracted_images", help="이미지를 저장할 폴더명 (기본: extracted_images)")

    args = parser.parse_args()
    extract_images_from_har(args.har_file, args.output)

if __name__ == "__main__":
    main()
