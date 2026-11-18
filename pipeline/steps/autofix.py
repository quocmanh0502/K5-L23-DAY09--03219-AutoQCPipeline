"""BƯỚC 2/4 — Sửa tự động những lỗi bắt buộc mà máy sửa được AN TOÀN.   ★★

Test:  pytest tests/test_autofix.py -q

`fix(ds, issues, cfg) -> list[dict]`: duyệt `issues` (chỉ lỗi severity ERROR), sửa thẳng vào thư mục `ds`,
và trả về danh sách thay đổi; mỗi phần tử có khoá: image, line, action, before, after
(đây chính là file `03_fixes.csv` — bằng chứng pipeline đã làm gì, người có thể kiểm lại).

| code lỗi                                       | cách sửa                                    | action           |
|------------------------------------------------|---------------------------------------------|------------------|
| BAD_FORMAT, BAD_CLASS_ID, BOX_ZERO, DUP_BOX    | xoá dòng đó khỏi file nhãn                  | "drop_line"      |
| BOX_OUT_OF_IMAGE                               | cắt box về trong [0,1] (giữ nguyên lớp)     | "clip_box"       |
| MISSING_LABEL_FILE                             | KHÔNG sửa file (máy không thể bịa nhãn): ghi 1 dòng fix, before="(không có file)", after="chuyển người gán" | "needs_label" |
| BAD_CLASS_NAME                                 | ghi lại `names` trong data.yaml đúng `cfg["classes"]` | "rename_classes" |
| DUP_IMAGE_*, LEAK_TEST, CORRUPT_IMAGE, BAD_SIZE| xoá ảnh + nhãn khỏi `ds`                    | "remove_image"   |

Bẫy cần nghĩ tới (có test cho từng cái)
- Một file có NHIỀU dòng lỗi: số dòng trong `issues` là số dòng GỐC. Nếu xoá từng dòng một thì số dòng lệch.
  Gom theo file, rồi ghi lại MỘT lần.
- Sau khi cắt, box có thể không còn diện tích (nằm hẳn ngoài ảnh): lúc đó xoá dòng thay vì ghi box rỗng.
- Một dòng có 2 lỗi (vd. BOX_OUT_OF_IMAGE + DUP_BOX): xoá dòng thắng, chỉ ghi 1 fix `drop_line`, không ghi thêm `clip_box`. Dòng trống ở giữa file vẫn đếm vào số dòng gốc.
- Ảnh vừa bị xoá (DUP_IMAGE_*...) mà còn issue dòng của chính nó: bỏ qua êm, không được báo lỗi/chết.
- Không động tới lỗi WARN (cảnh báo là việc của người). Không sửa file ở `data/raw/` — chỉ sửa `ds`.
- Chạy lần 2 trên dữ liệu đã sửa phải không làm gì thêm (idempotent) — NGOẠI LỆ duy nhất: `needs_label` được ghi lại mỗi lần còn lỗi `MISSING_LABEL_FILE` (vì ảnh vẫn chưa có nhãn).

- `needs_label` KHÔNG tạo file nhãn rỗng (rỗng = "ảnh nền", khác với "chưa gán"). `review_queue` sẽ đẩy ảnh này lên đầu hàng đợi cho người.

Gợi ý: `yaml.safe_load / safe_dump`.
"""
from collections import defaultdict

import yaml

from ..common import ERROR, parse_yolo_line

DROP = {"BAD_FORMAT", "BAD_CLASS_ID", "BOX_ZERO", "DUP_BOX"}       # sửa bằng cách xoá dòng
REMOVE = {"LEAK_TEST", "CORRUPT_IMAGE", "BAD_SIZE"}              # xoá ảnh (cộng thêm mọi DUP_IMAGE_*)


def _fix(image, line, action, before, after):
    return {"image": image, "line": line, "action": action, "before": before, "after": after}


def fix(ds, issues, cfg):
    fixes = []
    errs = [i for i in issues if i.severity == ERROR]             # cảnh báo (WARN) là việc của người: không đụng

    # 1) Xoá ảnh hỏng / trùng / rò rỉ test (cả ảnh lẫn file nhãn)
    removed = set()
    for i in errs:
        if (i.code in REMOVE or i.code.startswith("DUP_IMAGE_")) and i.image not in removed:
            p = ds.image_path(i.image)
            if p is None:
                continue
            p.unlink()
            ds.label_path(i.image).unlink(missing_ok=True)
            removed.add(i.image)
            fixes.append(_fix(i.image, "", "remove_image", p.name, "(đã xoá)"))

    # 2) Thiếu file nhãn: máy không bịa nhãn, KHÔNG tạo file rỗng (rỗng = "ảnh nền"), chỉ ghi lại để chuyển người
    # 3) Tên lớp sai trong data.yaml: ghi lại đúng cfg["classes"]
    for i in errs:
        if i.code == "MISSING_LABEL_FILE" and i.image not in removed:
            fixes.append(_fix(i.image, "", "needs_label", "(không có file)", "chuyển người gán"))
        elif i.code == "BAD_CLASS_NAME" and ds.yaml_path.exists():
            d = yaml.safe_load(ds.yaml_path.read_text(encoding="utf-8")) or {}
            before = d.get("names")
            d["names"] = list(cfg["classes"])
            ds.yaml_path.write_text(yaml.safe_dump(d, allow_unicode=True, sort_keys=False), encoding="utf-8")
            fixes.append(_fix(i.image, "", "rename_classes", str(before), str(d["names"])))

    # 4) Lỗi theo dòng: gom theo file -> {số dòng gốc: {mã lỗi}}, rồi ghi lại file MỘT lần (xoá từng dòng sẽ lệch số dòng)
    by_file = defaultdict(lambda: defaultdict(set))
    for i in errs:
        if i.line is not None and (i.code in DROP or i.code == "BOX_OUT_OF_IMAGE"):
            by_file[i.image][i.line].add(i.code)

    for stem, line_codes in by_file.items():
        lp = ds.label_path(stem)
        if stem in removed or not lp.exists():                    # ảnh vừa bị xoá: bỏ qua êm
            continue
        out = []
        # enumerate trên file gốc, GIỮ dòng trống -> `no` khớp đúng số dòng trong issue
        for no, text in enumerate(lp.read_text(encoding="utf-8").splitlines(), 1):
            codes = line_codes.get(no, set())
            if codes & DROP:                                      # xoá dòng thắng clip: chỉ 1 fix drop_line
                fixes.append(_fix(stem, no, "drop_line", text, ""))
                continue
            if "BOX_OUT_OF_IMAGE" in codes:
                c, x, y, w, h = parse_yolo_line(text)
                x1, y1 = max(0.0, x - w / 2), max(0.0, y - h / 2)    # cắt 4 mép về [0, 1]
                x2, y2 = min(1.0, x + w / 2), min(1.0, y + h / 2)
                if x2 <= x1 or y2 <= y1:                          # box nằm hẳn ngoài ảnh: không còn gì để giữ
                    fixes.append(_fix(stem, no, "drop_line", text, ""))
                    continue
                new = f"{c} {(x1 + x2) / 2:.6f} {(y1 + y2) / 2:.6f} {x2 - x1:.6f} {y2 - y1:.6f}"
                fixes.append(_fix(stem, no, "clip_box", text, new))
                text = new
            out.append(text)
        lp.write_text("".join(l + "\n" for l in out), encoding="utf-8")
    return fixes
