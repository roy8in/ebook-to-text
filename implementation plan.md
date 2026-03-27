# Implementation Plan: EPUB Chapter-to-Text Extractor for NotebookLM

## 1. 기술 스택 (Technical Stack)
* **언어**: Python 3.10+
* **라이브러리**:
    * `ebooklib`: EPUB 구조 분석 및 데이터 추출
    * `beautifulsoup4`: HTML 파싱 및 텍스트 정제
    * `pathlib`: 경로 및 파일 시스템 관리
    * `re`: 파일명 정제 (Sanitization)

---

## 2. 개발 단계 및 로직 (Development Logic)

### Phase 1: 데이터 로드 및 매핑
1.  `ebooklib`을 사용하여 `.epub` 파일을 로드.
2.  `TOC(Table of Contents)` 데이터를 추출하여 각 챕터 제목과 내부 소스 파일(`.xhtml`)의 연결 정보를 딕셔너리 형태로 생성.
3.  EPUB의 `Spine` 정보를 기반으로 실제 독서 순서를 정의.

### Phase 2: 텍스트 추출 및 정제
1.  `ITEM_DOCUMENT` 타입의 파일만 순회하며 바이너리 데이터를 읽음.
2.  `BeautifulSoup`을 사용하여 다음 요소를 제거:
    * `<script>`, `<style>`, `<nav>`, `<aside>`
    * HTML 주석 및 비텍스트 메타데이터
3.  목차(TOC)에서 제공하는 앵커(`#`) 정보를 참조하여, 하나의 HTML 파일 내에 여러 챕터가 포함된 경우 이를 물리적으로 분할.
4.  연속된 줄바꿈을 단일 줄바꿈으로 축소하고 앞뒤 공백 제거.

### Phase 3: 파일 출력 (Output)
1.  출력 폴더 생성: `{파일명}_extracted_chapters/`
2.  파일명 규칙: `[번호]_[챕터명].txt` (특수문자는 `_`로 치환)
3.  인코딩: `UTF-8`

### Phase 4: 메타데이터 요약
1.  각 추출된 텍스트 파일의 **글자 수(Character Count)** 및 **공백 제외 글자 수** 출력.
2.  NotebookLM의 입력 용량 제한 확인용 로그 생성.


## 3. 기대 결과물
* 각 챕터가 독립된 `.txt` 파일로 분할되어 저장됨.