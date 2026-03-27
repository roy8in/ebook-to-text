import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup, NavigableString
import re
from pathlib import Path

# 블록 요소 목록 (줄바꿈을 넣어야 하는 태그)
BLOCK_ELEMENTS = {
    'p', 'div', 'section', 'article', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    'blockquote', 'pre', 'ul', 'ol', 'li', 'table', 'tr', 'td', 'th',
    'dl', 'dt', 'dd', 'figure', 'figcaption', 'br', 'hr',
}

# 짧은 페이지 판정 기준 (공백 제외 글자 수)
SHORT_PAGE_THRESHOLD = 500


class EpubExtractor:
    def __init__(self, epub_path):
        self.epub_path = Path(epub_path).resolve()
        self.book = epub.read_epub(str(self.epub_path))
        self.toc_map = {}  # {href_without_anchor: title} or {href: title}
        
        # 파일 저장 구조: 프로젝트루트/output/책이름/text/
        project_root = Path(__file__).resolve().parent
        self.output_dir = project_root / "output" / self.epub_path.stem / "text"
        self.book_title = self._get_book_title()

    def _get_book_title(self):
        """EPUB 메타데이터에서 책 제목 추출"""
        title = self.book.get_metadata('DC', 'title')
        if title:
            return title[0][0].strip()
        return None

    def _parse_toc(self, toc_list):
        """TOC를 재귀적으로 순회하며 href와 제목 매핑 (단순화된 평면 구조 생성)"""
        for item in toc_list:
            if isinstance(item, tuple):
                self._parse_toc(item[1])
            elif isinstance(item, epub.Link):
                # href에서 앵커(#) 제거 전후 모두 저장하여 매핑 확률 높임
                base_href = item.href.split('#')[0]
                if base_href not in self.toc_map:
                    self.toc_map[base_href] = item.title
                self.toc_map[item.href] = item.title

    def load_toc(self):
        """Phase 1: TOC 데이터를 추출하여 챕터 제목 매핑"""
        self._parse_toc(self.book.toc)
        print(f"Mapped {len(self.toc_map)} TOC entries.")

    def sanitize_filename(self, filename):
        """파일명에 사용할 수 없는 특수문자 제거"""
        return re.sub(r'[\\/*?:"<>|]', '_', filename).strip()

    def _remove_footnote_refs(self, soup):
        """각주 참조 태그 완전 제거"""
        # 1) <span class="SUP"> 안의 <a epub:type="noteref"> 패턴
        for span in soup.find_all('span', class_='SUP'):
            span.decompose()

        # 2) 각주 백링크 (<a class="_idFootnoteLink">) 및 관련 wrapper
        for a_tag in soup.find_all('a', class_='_idFootnoteLink'):
            # 상위 wrapper span들도 제거
            parent = a_tag.parent
            while parent and parent.name == 'span' and not parent.get('class'):
                grandparent = parent.parent
                parent.decompose()
                parent = grandparent
                break
            else:
                a_tag.decompose()

        # 3) 남은 독립적 <sup> 태그 (쉼표 등 구분자 포함) 제거
        for sup in soup.find_all('sup'):
            text = sup.get_text(strip=True)
            # 숫자, 로마자, 쉼표 등 각주 참조 패턴만 제거
            if re.match(r'^[ivxlcdm0-9,.\s]*$', text, re.IGNORECASE):
                sup.decompose()

        # 4) 페이지 하단 각주 본문 (div class containing "footnote") 제거
        for div in soup.find_all('div', class_=re.compile(r'footnote', re.IGNORECASE)):
            div.decompose()

    def _extract_text_block_aware(self, element):
        """블록 요소에만 줄바꿈을 넣고, 인라인 요소는 텍스트를 이어붙이는 재귀 추출"""
        parts = []
        for child in element.children:
            if isinstance(child, NavigableString):
                text = str(child)
                # 줄바꿈/탭을 공백으로
                text = re.sub(r'[\n\t\r]+', ' ', text)
                parts.append(text)
            elif child.name in BLOCK_ELEMENTS:
                # 블록 요소 전후에 줄바꿈 삽입
                parts.append('\n')
                parts.append(self._extract_text_block_aware(child))
                parts.append('\n')
            elif child.name == 'br':
                parts.append('\n')
            else:
                # 인라인 요소 (<span>, <em>, <i>, <a>, <b>, <strong> 등) → 줄바꿈 없이 이어붙임
                parts.append(self._extract_text_block_aware(child))
        return ''.join(parts)

    def _dehyphenate(self, text):
        """OCR 하이픈 단어 분리 병합: 줄 끝 하이픈 + 다음 줄 소문자 시작 → 합침"""
        # 패턴: 영문자-\n소문자 → 합침 (self-esteem 등 정상 하이픈 복합어는 줄바꿈 없으므로 안전)
        return re.sub(r'(\w)-\n([a-z])', r'\1\2', text)

    def _remove_book_title_header(self, text):
        """반복되는 책 제목 헤더 제거"""
        if not self.book_title:
            return text
        lines = text.split('\n')
        cleaned = []
        for line in lines:
            # 책 제목 (대소문자, 부분 일치) - 짧은 줄이 책 제목과 유사하면 제거
            stripped = line.strip()
            if stripped and self._is_title_match(stripped):
                continue
            cleaned.append(line)
        return '\n'.join(cleaned)

    def _is_title_match(self, line):
        """줄이 책 제목과 일치하는지 판정"""
        if not self.book_title:
            return False
        # 정규화: 소문자, 구두점 제거
        normalize = lambda s: re.sub(r'[^a-z0-9]', '', s.lower())
        line_norm = normalize(line)
        title_norm = normalize(self.book_title)
        # 완전 일치 (구두점 무시)
        if line_norm == title_norm:
            return True
        # 줄이 제목의 부분집합인 경우 (축약된 헤더)
        if line_norm and title_norm.startswith(line_norm):
            return True
        # 줄이 50자 이하이고, 줄의 단어 대부분이 제목에 포함
        if len(line) <= 50:
            normalize_word = lambda w: re.sub(r'[^a-z0-9]', '', w.lower())
            title_words = set(normalize_word(w) for w in self.book_title.split() if normalize_word(w))
            line_words = set(normalize_word(w) for w in line.split() if normalize_word(w))
            if line_words and len(line_words & title_words) / len(line_words) >= 0.8:
                return True
        return False

    def _fix_spaced_capitals(self, text):
        """OCR 스캔의 대문자 간격 축약: 'A L T H O U G H' → 'ALTHOUGH'"""
        def fix_match(m):
            spaced_part = m.group(2).replace(' ', '')
            return m.group(1) + spaced_part + ' '
        # 줄 시작에서 단일 대문자+공백이 3회 이상 연속되는 패턴 + 마지막 대문자
        return re.sub(r'(^|\n)((?:[A-Z] ){3,}[A-Z])\s', fix_match, text)

    def _remove_page_numbers(self, text):
        """본문에 혼입된 페이지 번호 + 섹션명 패턴 제거"""
        # 패턴: 숫자(또는 OCR 오류) + 섹션명 (예: '1O PREFACE', 'I 6 PROLOGUE', '2 6 I')
        section_names = r'(?:PREFACE|PROLOGUE|EPILOGUE|CHAPTER\s+\d+|FROM EDEN TO CAJAMARCA)'
        # "숫자/문자 공백" 조합 + 섹션명이 문장 중간에 나타나는 패턴
        text = re.sub(r'\s+[\dIOl]\s*[\dIOl\s]*\s+' + section_names + r'\s+', ' ', text)
        return text

    def _remove_figure_refs(self, text):
        """Figure 참조 및 캡션 제거"""
        # 패턴 1: 'Figure X.X.' 뒤에 이어지는 캡션 문장 (마침표까지)
        text = re.sub(r'Figure\s+\d+\.\d+\.\s*[^.\n]+\.?', '', text)
        # 패턴 2: 홀로 남는 'Figure X.X' (참조만 있는 경우) + 주변 괄호
        text = re.sub(r'\((?:see\s+)?Figure\s+\d+\.\d+\)', '', text, flags=re.IGNORECASE)
        # 패턴 3: '(page NNN)' 패턴 제거
        text = re.sub(r'\(page\s+\d+\)', '', text, flags=re.IGNORECASE)
        return text

    def _extract_title_from_text(self, text):
        """텍스트 내용에서 챕터 제목 추출 (fallback)"""
        lines = text.strip().split('\n')
        for line in lines[:5]:  # 처음 5줄만 검사
            stripped = line.strip()
            if not stripped:
                continue
            # CHAPTER N + 부제 패턴
            m = re.match(r'(CHAPTER\s+\d+)\s*(.*)', stripped, re.IGNORECASE)
            if m:
                title = m.group(1)
                subtitle = m.group(2).strip()
                if subtitle:
                    title += ' ' + subtitle
                return title[:80]  # 파일명 길이 제한
            # PROLOGUE, EPILOGUE, PREFACE 등 섹션명
            if re.match(r'^(PROLOGUE|EPILOGUE|PREFACE|INTRODUCTION|AFTERWORD|ACKNOWLEDGMENTS)', stripped, re.IGNORECASE):
                return stripped[:80]
        return None

    def clean_html(self, content):
        """Phase 2: HTML 정제 및 텍스트 추출 (개선)"""
        soup = BeautifulSoup(content, 'html.parser')

        # 불필요한 태그 제거
        for tag in soup(['script', 'style', 'nav', 'aside', 'footer', 'header']):
            tag.decompose()

        # 각주 참조 태그 제거
        self._remove_footnote_refs(soup)

        # 블록 요소 인식 텍스트 추출 (인라인 요소 줄바꿈 방지)
        body = soup.find('body')
        if body:
            text = self._extract_text_block_aware(body)
        else:
            text = self._extract_text_block_aware(soup)

        # 연속된 줄바꿈 및 공백 정리
        text = re.sub(r'[^\S\n]+', ' ', text)       # 줄바꿈 이외 연속 공백 → 단일 공백
        text = re.sub(r' *\n *', '\n', text)         # 줄바꿈 주변 공백 제거
        text = re.sub(r'\n{2,}', '\n', text)         # 연속 줄바꿈 → 단일 줄바꿈

        # 추가 후처리
        text = self._dehyphenate(text)                # OCR 하이픈 분리 병합
        text = self._remove_book_title_header(text)   # 책 제목 반복 헤더 제거
        text = self._fix_spaced_capitals(text)        # 대문자 간격 축약
        text = self._remove_page_numbers(text)        # 페이지 번호 혼입 제거
        text = self._remove_figure_refs(text)         # Figure 캡션/참조 제거

        # 후처리 후 다시 정리
        text = re.sub(r'  +', ' ', text)              # 다중 공백 정리
        text = re.sub(r'\n{2,}', '\n', text)         # 빈 줄 정리
        return text.strip()

    def _is_short_page(self, text):
        """비본문/짧은 페이지 여부 판정"""
        no_space_count = len(re.sub(r'\s', '', text))
        return no_space_count < SHORT_PAGE_THRESHOLD

    def extract_chapters(self):
        """Phase 2 & 3: Spine 순서대로 텍스트 추출 및 저장 (짧은 페이지 병합)"""
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # 1단계: 모든 페이지를 수집
        pages = []
        processed_hrefs = set()

        for item_ref in self.book.spine:
            item = self.book.get_item_with_id(item_ref[0])

            if item.get_type() != ebooklib.ITEM_DOCUMENT:
                continue

            href = item.get_name()
            if href in processed_hrefs:
                continue

            # TOC에서 제목 찾기
            title = self.toc_map.get(href)

            # 텍스트 정제
            raw_content = item.get_content().decode('utf-8')
            clean_text = self.clean_html(raw_content)

            if not clean_text:
                processed_hrefs.add(href)
                continue

            pages.append({
                'href': href,
                'title': title,
                'text': clean_text,
                'is_short': self._is_short_page(clean_text),
            })
            processed_hrefs.add(href)

        # 2단계: 짧은 페이지를 다음 챕터에 병합
        merged_chapters = []
        pending_text = []  # 다음 챕터에 병합될 짧은 페이지 텍스트
        pending_titles = []  # 병합 대기 중인 짧은 페이지 제목들

        for page in pages:
            if page['is_short']:
                pending_text.append(page['text'])
                if page['title']:
                    pending_titles.append(page['title'])
                print(f"  Merged short page: {page['title'] or page['href']} ({len(re.sub(r'\\s', '', page['text']))} chars)")
            else:
                # 본문 챕터: 대기 중인 짧은 페이지 텍스트를 앞에 병합
                combined = '\n'.join(pending_text + [page['text']])
                # 제목 결정: TOC 제목 → 병합된 짧은 페이지 제목 → 텍스트에서 추출
                title = page['title']
                if not title and pending_titles:
                    title = pending_titles[-1]  # 마지막 짧은 페이지 제목 사용
                if not title:
                    title = self._extract_title_from_text(combined)
                pending_text = []
                pending_titles = []
                merged_chapters.append({
                    'title': title,
                    'text': combined,
                })

        # 마지막에 남은 짧은 페이지가 있으면 마지막 챕터에 병합
        if pending_text and merged_chapters:
            merged_chapters[-1]['text'] += '\n' + '\n'.join(pending_text)
        elif pending_text:
            # 모든 페이지가 짧은 경우 (극히 드문 케이스)
            merged_chapters.append({
                'title': 'Combined',
                'text': '\n'.join(pending_text),
            })

        # 3단계: 파일 저장
        for idx, chapter in enumerate(merged_chapters, 1):
            title = chapter['title'] or f"Chapter_{idx}"
            safe_title = self.sanitize_filename(title)
            file_name = f"{idx:02d}_{safe_title}.txt"
            file_path = self.output_dir / file_name

            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(chapter['text'])

            char_count = len(chapter['text'])
            no_space_count = len(re.sub(r'\s', '', chapter['text']))
            print(f"Saved: {file_name} ({char_count} chars, {no_space_count} without spaces)")

        print(f"\nExtraction complete. {len(merged_chapters)} files saved in: {self.output_dir}")

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python extractor.py <path_to_epub>")
    else:
        epub_file = sys.argv[1]
        extractor = EpubExtractor(epub_file)
        extractor.load_toc()
        extractor.extract_chapters()
