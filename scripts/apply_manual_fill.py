"""manual_fill.json 내용을 restaurants.json / cafe.json에 반영

사용법:
  1. data/manual_fill.json 에서 각 항목의 별점, 리뷰수, 사진목록 직접 입력
  2. cd backend && python scripts/apply_manual_fill.py
"""
import json, os, sys

sys.stdout.reconfigure(encoding="utf-8")

base = os.path.join(os.path.dirname(__file__), "..", "data")
fill_path = os.path.join(base, "manual_fill.json")

with open(fill_path, encoding="utf-8") as f:
    fills = json.load(f)

# 파일별로 묶기
from collections import defaultdict
by_file = defaultdict(list)
for item in fills:
    by_file[item["file"]].append(item)

updated_total = 0

for fpath_rel, items in by_file.items():
    fpath = os.path.join(os.path.dirname(__file__), "..", fpath_rel)
    with open(fpath, encoding="utf-8") as f:
        data = json.load(f)

    updated = 0
    for fill in items:
        idx = fill["idx"]
        target = data[idx]

        # 이름 검증
        if target["이름"] != fill["name"]:
            print(f"  [경고] idx={idx} 이름 불일치: {target['이름']} ≠ {fill['name']}, 건너뜀")
            continue

        changed = False
        if fill.get("별점") is not None and target.get("별점") != fill["별점"]:
            target["별점"] = fill["별점"]
            changed = True
        if fill.get("리뷰수") is not None and target.get("리뷰수") != fill["리뷰수"]:
            target["리뷰수"] = fill["리뷰수"]
            changed = True
        if fill.get("사진목록"):
            target["사진목록"] = fill["사진목록"]
            target["사진"] = fill["사진목록"][0]
            changed = True
        if fill.get("전화번호") and not target.get("전화번호"):
            target["전화번호"] = fill["전화번호"]
            changed = True
        if fill.get("운영시간") and not target.get("운영시간"):
            target["운영시간"] = fill["운영시간"]
            changed = True
        if fill.get("lat") is not None and fill.get("lng") is not None:
            target["lat"] = fill["lat"]
            target["lng"] = fill["lng"]
            changed = True

        if changed:
            updated += 1
            coord = f" 좌표:({fill.get('lat')},{fill.get('lng')})" if fill.get("lat") else ""
            print(f"  반영: {fill['name']} — 별점:{target.get('별점')} 사진:{len(target.get('사진목록') or [])}장{coord}")

    with open(fpath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"{fpath_rel}: {updated}/{len(items)}개 반영 완료\n")
    updated_total += updated

print(f"전체 {updated_total}개 반영 완료")
