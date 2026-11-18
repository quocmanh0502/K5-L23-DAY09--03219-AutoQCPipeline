"""CHECK 2 — Dòng nhãn YOLO: sai định dạng, ID lớp lạ, box tràn ảnh, box rỗng, box lặp.   (Script 2 trong slide)   ★★

Test:  pytest tests/test_label_format.py -q

Mỗi dòng nhãn: `id cx cy w h` (5 số, toạ độ 0–1). Trả về list[Issue]; `Issue.line` = số dòng (đếm từ 1).

| code             | severity | khi nào                                                                  |
|------------------|----------|--------------------------------------------------------------------------|
| BAD_FORMAT       | ERROR    | không đúng 5 cột số (dùng `parse_yolo_line`, bắt `ValueError`)           |
| BAD_CLASS_ID     | ERROR    | id lớp ngoài 0..len(ds.classes)-1                                        |
| BOX_ZERO         | ERROR    | w <= 0 hoặc h <= 0                                                       |
| BOX_OUT_OF_IMAGE | ERROR    | mép box vượt [0,1] quá `cfg["label_format"]["overflow_tol"]`; extra={"overflow": mức tràn} |
| DUP_BOX          | ERROR    | cùng lớp với một dòng TRƯỚC ĐÓ và IoU > `dup_box_iou`; báo ở dòng SAU    |
| BOX_TINY         | WARN     | cạnh ngắn của box (px) < `min_box_px`  (cần `ds.image_size(stem)`)       |
| BOX_HUGE         | WARN     | w*h > `max_box_frac`                                                     |

Gợi ý
- Mép trái = x - w/2, mép phải = x + w/2 (xem câu hỏi "dòng YOLO nào lỗi?" trong slide).
- Một dòng hỏng (BAD_FORMAT, BAD_CLASS_ID, BOX_ZERO) thì `continue`, đừng kiểm tiếp hình học của dòng đó.
- Dòng thiếu cột làm script của slide dừng giữa chừng: đây là lý do phải `try/except`.
- `iou_xywh(a, b)` có sẵn trong common.py.
- Ngưỡng nằm trong `cfg["label_format"]` — đừng viết cứng số vào code.
"""
from ..common import ERROR, WARN, Issue, iou_xywh, parse_yolo_line


def run(ds, cfg):
    c = cfg["label_format"]                  # mọi ngưỡng lấy từ config, không viết cứng
    n_cls = len(ds.classes)
    issues = []

    def add(sev, code, stem, msg, line, **extra):
        issues.append(Issue("label_format", sev, code, stem, msg, line, extra))

    for lp in ds.label_files():
        stem = lp.stem
        size = ds.image_size(stem) if ds.image_path(stem) else None   # (rộng, cao) px; None nếu không có ảnh
        seen = []                            # box hợp lệ ở các dòng TRƯỚC, để bắt DUP_BOX
        for no, text in ds.read_label_lines(stem) or []:              # `no` = số dòng gốc (giữ cả dòng trống)
            try:
                cls, x, y, w, h = parse_yolo_line(text)
            except ValueError as e:          # dòng hỏng không được làm script chết
                add(ERROR, "BAD_FORMAT", stem, f"dòng hỏng: {e}", no)
                continue
            if not 0 <= cls < n_cls:
                add(ERROR, "BAD_CLASS_ID", stem, f"id lớp {cls} ngoài 0..{n_cls - 1}", no)
                continue
            if w <= 0 or h <= 0:
                add(ERROR, "BOX_ZERO", stem, f"box rỗng w={w} h={h}", no)
                continue

            # mức tràn lớn nhất của 4 mép (trái, phải, trên, dưới) ra ngoài [0, 1]
            over = max(-(x - w / 2), (x + w / 2) - 1, -(y - h / 2), (y + h / 2) - 1)
            if over > c["overflow_tol"]:
                add(ERROR, "BOX_OUT_OF_IMAGE", stem, f"box tràn ảnh {over:.4f}", no, overflow=round(over, 6))

            box = (x, y, w, h)
            if any(sc == cls and iou_xywh(sb, box) > c["dup_box_iou"] for sc, sb in seen):
                add(ERROR, "DUP_BOX", stem, "box trùng (cùng lớp) với một dòng trước", no)
            seen.append((cls, box))

            if size:
                short = min(w * size[0], h * size[1])                 # cạnh ngắn tính bằng pixel
                if short < c["min_box_px"]:
                    add(WARN, "BOX_TINY", stem, f"cạnh ngắn {short:.1f}px < {c['min_box_px']}px", no)
            if w * h > c["max_box_frac"]:
                add(WARN, "BOX_HUGE", stem, f"box chiếm {w * h:.0%} ảnh", no)
    return issues
