import requests
from bs4 import BeautifulSoup
import re
from typing import List
from pathlib import Path
import json

#jvndb_ids = load_jvndb_ids("/content/drive/MyDrive/annjvns.txt")
# 対象のJVNDB ID一覧
#jvndb_ids = [
# "JVNDB-2025-018963",
#]

base_url = "https://jvndb.jvn.jp/ja/contents/2025/"
# 検索するセクション見出しの候補（ページによって表現が異なることがあるため複数用意）
section_titles = [
    "影響を受けるシステム",
    "影響を受ける製品",
]

TARGET = "1809"  # 大文字小文字を区別して検索（ここは数字なので大小は関係しません）
START_TOKENS = ["マイクロソフト", "Microsoft"]  # この語の出現位置以降から検索する
SUMMARY_TOKEN = "概要"  # search_text に '概要' が含まれていればその位置以降から検索
def load_jvndb_ids(path) -> List[str]:
    """
    Load a list of JVNDB IDs from a file.
    - If the file suffix is .json, it will be parsed as a JSON list.
    - Otherwise the file is read as text: one ID per line. Blank lines and lines
      starting with '#' are ignored.
    Returns a list of strings.
    """
    p = Path(path) # Convert string to Path object
    if not p.exists():
        raise FileNotFoundError(f"File not found: {p}")

    if p.suffix.lower() == ".json":
        with p.open("r", encoding="utf-8") as f:
            data = json.load(f)
            if not isinstance(data, list):
                raise ValueError("JSON file must contain a list of IDs")
            return [str(x).strip() for x in data if str(x).strip()]

    # fallback: plain text, one ID per line
    ids: List[str] = []
    with p.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            ids.append(line)
    return ids
 
def extract_section_text(soup, title_candidates):
    """
    指定した見出し候補のうち最初にヒットする見出しを探し、
    その見出しの次に続く段落・リスト等のテキストを結合して返す。
    見出しが見つからなければ None を返す。
    """
    for tag in soup.find_all(re.compile("^h[1-6]$")):
        txt = tag.get_text(strip=True)
        for cand in title_candidates:
            if cand in txt:
                parts = []
                for sib in tag.find_next_siblings():
                    if sib.name and re.match(r"^h[1-6]$", sib.name):
                        break
                    parts.append(sib.get_text(" ", strip=True))
                section_text = "\n".join(p for p in parts if p)
                return section_text if section_text else None
    return None

def find_start_index_after_tokens(text, tokens):
    """
    tokens に含まれる語のうち最初に現れる位置を返す。
    見つからなければ -1 を返す。
    """
    indices = [text.find(t) for t in tokens if text.find(t) != -1]
    return min(indices) if indices else -1

def find_target_snippets(text, target, context=60):
    """
    target（厳密一致）を含むスニペット（前後 context 文字）を取得して返す。
    """
    snippets = []
    pattern = re.compile(r".{0,%d}%s.{0,%d}" % (context, re.escape(target), context))
    for m in pattern.finditer(text):
        snippets.append(m.group().strip())
    return snippets

def extract_from_start_to_cvs(search_text, cvs_token="CVS"):
    """
    search_text の先頭（開始位置）から最初に現れる cvs_token の直前までを返す。
    - まず大文字の cvs_token を探す
    - 見つからなければ小文字で探す
    - 見つからなければ search_text 全体を返す
    戻り値は切り出した文字列（空の場合は空文字列）
    """
    if not search_text:
        return ""
    idx = search_text.find(cvs_token)
    if idx == -1:
        # 小文字でのフォールバック
        idx = search_text.lower().find(cvs_token.lower())
    if idx == -1:
        return search_text.strip()
    return search_text[:idx].strip()

results = {}
jvndb_ids = load_jvndb_ids("/content/drive/MyDrive/annjvn.txt")

for jvndb_id in jvndb_ids:
    url = f"{base_url}{jvndb_id}.html"
    try:
        res = requests.get(url, timeout=15)
        res.encoding = res.apparent_encoding or 'utf-8'
        soup = BeautifulSoup(res.text, 'html.parser')

        section_text = extract_section_text(soup, section_titles)
        found = False
        snippets = []
        extracted_text = None

        if section_text:
            # セクション内で "マイクロソフト" または "Microsoft" の最初の出現位置を探す
            start_idx = find_start_index_after_tokens(section_text, START_TOKENS)
            if start_idx != -1:
                # 見つかった位置以降だけを検索対象にする
                search_text = section_text[start_idx:]
            else:
                # トークンが見つからない場合はセクション全体を検索対象にする
                search_text = section_text

            # search_text に '概要' が含まれていればその位置以降だけを検索対象とする
            if SUMMARY_TOKEN in search_text:
                search_text = search_text[search_text.find(SUMMARY_TOKEN):]

        else:
            # セクションが見つからない場合、ページ全体をフォールバック検索
            full_text = soup.get_text(" ", strip=True)
            start_idx = find_start_index_after_tokens(full_text, START_TOKENS)
            if start_idx != -1:
                search_text = full_text[start_idx:]
            else:
                search_text = full_text

            # ここでも search_text に '概要' が含まれていればその位置以降だけを検索対象とする
            if SUMMARY_TOKEN in search_text:
                search_text = search_text[search_text.find(SUMMARY_TOKEN):]

        # ここまでで search_text が定義されているはず
        # TARGET が見つかったら、開始位置から 'CVS' の直前までを切り出して返す
        if TARGET in search_text:
            found = True
            snippets = find_target_snippets(search_text, TARGET)
            extracted_text = extract_from_start_to_cvs(search_text, cvs_token="対策")
            influed_text = extract_from_start_to_cvs(search_text, cvs_token="CVS")
        #Summary_token=影響
            extracted_text = search_text[search_text.find("される影響"):]
            append_text = extract_from_start_to_cvs(extracted_text, cvs_token="対策")            
        else:
            found = False
            snippets = []
            extracted_text = None
            append_text = None
        if found:
            results[jvndb_id] = {
                "url": url,
                "found": True,
                "snippets": snippets or ["(見つかりましたがスニペット抽出に失敗しました)"],
                "extracted": influed_text or "",
                "appended": append_text or ""
            }
        else:
            results[jvndb_id] = {
                "url": url,
                "found": False,
                "snippets": [],
                "extracted": ""
            }
            # デバッグ出力（必要なければ削除可）
            print(f"{jvndb_id}: Not found")

    except Exception as e:
        results[jvndb_id] = {"url": url, "error": str(e)}

# 結果表示
for k, v in results.items():
    print("----")
    print(k)
    if "error" in v:
        print("取得失敗:", v["error"])
        continue
    print("URL:", v["url"])
    if v["found"]:
        print(f"検出: '{TARGET}' が見つかりました。マッチしたスニペット:")
        for s in v["snippets"]:
            print("-", s)
        print("抽出（開始位置から 'CVS' の直前まで）:")
        print(v["extracted"])
        print("----")
        print(v["appended"])
    else:
        print(f"未検出: '{TARGET}' は見つかりませんでした。")
print("ZZ")
