import os
import argparse
import subprocess
from pathlib import Path

def join_audio_files(book_name, ext=".mp3"):
    """
    여러 오디오 파일을 ffmpeg를 사용하여 하나로 합치는 스크립트입니다.
    output/[book_name]/audio/ 폴더의 모든 오디오 파일을 읽어
    output/[book_name]/audiobook.mp3 파일로 저장합니다.
    """
    project_root = Path(__file__).resolve().parent
    book_dir = project_root / "output" / book_name
    input_path = book_dir / "audio"
    output_path = book_dir / "audiobook.mp3"
    
    if not input_path.exists() or not input_path.is_dir():
        print(f"오류: 텍스트 및 오디오 폴더 구조를 찾을 수 없습니다.")
        print(f"경로: '{input_path}' 생성 또는 확인이 필요합니다.")
        print(f"먼저 추출된 텍스트로 오디오 파일을 생성하여 위 경로에 넣어주세요.")
        return

    # 지정된 확장자를 가진 파일 검색
    audio_files = list(input_path.glob(f"*{ext}"))
    if not audio_files:
        print(f"'{input_path}' 폴더에 '{ext}' 확장자를 가진 오디오 파일이 없습니다.")
        return

    # 파일명을 기준으로 1차 정렬 (01_xxx, 02_xxx 형식일 경우 순서대로 정렬됨)
    audio_files.sort()
    
    # 만약 사용자가 지정한 순서 파일(order.txt)이 있다면 그 순서를 우선합니다.
    order_file = input_path / "order.txt"
    if order_file.exists():
        print(f"'{order_file.name}' 파일이 발견되었습니다. 지정된 순서대로 병합합니다.")
        with open(order_file, "r", encoding="utf-8") as f:
            # 빈 줄과 주석 제외하고 파일명만 추출
            ordered_names = [line.strip() for line in f if line.strip() and not line.startswith("#")]
            
        ordered_files = []
        for name in ordered_names:
            file_path = input_path / name
            if file_path in audio_files:
                ordered_files.append(file_path)
            else:
                print(f"경고: order.txt에 적힌 '{name}' 파일을 찾을 수 없어 건너뜁니다.")
                
        # order.txt에 포함되지 않은 나머지 파일들을 뒤에 추가
        remaining = [f for f in audio_files if f not in ordered_files]
        audio_files = ordered_files + remaining
    else:
        # order.txt가 없을 때 생성 안내 및 자동 생성
        print(f"'{order_file.name}' 가 없습니다. 이름순 정렬을 사용합니다.")
        with open(order_file, "w", encoding="utf-8") as f:
            f.write("# 이 파일은 오디오 병합 순서를 결정합니다.\n")
            f.write("# 파일명의 순서를 위아래로 자유롭게 바꿔서 저장한 뒤 이 스크립트를 다시 실행하세요.\n\n")
            for audio_file in audio_files:
                f.write(f"{audio_file.name}\n")
        print(f"참고: 순서를 마음대로 바꾸고 싶다면 {order_file} 파일의 텍스트 줄 순서를 수정한 뒤 다시 실행하세요.\n")

    
    # ffmpeg concat demuxer를 위한 리스트 텍스트 파일 생성
    list_file_path = input_path / "concat_list.txt"
    with open(list_file_path, "w", encoding="utf-8") as f:
        for audio_file in audio_files:
            # ffmpeg 규칙에 따라 "file '파일명'" 형태로 작성 (상대 경로 사용)
            escaped_name = audio_file.name.replace("'", "'\\''")  # 작은따옴표 이스케이프
            f.write(f"file '{escaped_name}'\n")
            print(f"병합 대기: {audio_file.name}")

    print(f"\n총 {len(audio_files)}개의 파일을 합칩니다...")

    # ffmpeg 명령어 구성
    cmd = [
        "ffmpeg",
        "-y",               # 덮어쓰기 허용
        "-f", "concat",
        "-safe", "0",
        "-i", str(list_file_path),
        "-c", "copy",
        str(output_path)
    ]

    try:
        # ffmpeg 실행 (cwd를 input_path로 설정하여 상대경로 인식)
        subprocess.run(cmd, cwd=input_path, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
        print(f"\n성공! 오디오가 병합되었습니다.")
        print(f"병합된 오디오북 저장 경로: {output_path}")
    except subprocess.CalledProcessError as e:
        print(f"\n오류: ffmpeg 실행 중 문제가 발생했습니다.")
        print("파일들의 샘플레이트나 비트레이트가 다를 경우 '-c copy' 대신 재인코딩이 필요할 수 있습니다.")
    except FileNotFoundError:
        print("\n오류: 시스템에 'ffmpeg'가 설치되어 있지 않습니다. Homebrew 등으로 설치해주세요.")
    finally:
        # 임시 리스트 파일 삭제
        if list_file_path.exists():
            list_file_path.unlink()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="output 폴더 구조에 맞춰 오디오 파일들을 하나로 자동 병합합니다.")
    parser.add_argument("book_name", help="합칠 오디오가 있는 책 이름 (예: 'Guns, Germs, and Steel - The Fates of Human Societies. (Jared Diamond)')")
    parser.add_argument("--ext", default=".mp3", help="병합할 파일들의 확장자 (기본값: .mp3)")

    args = parser.parse_args()
    join_audio_files(args.book_name, args.ext)
