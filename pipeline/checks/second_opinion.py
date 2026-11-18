"""CHECK 6 — Ý kiến thứ hai: so nhãn với một model LỚN HƠN (yolo26l).   ★★★ (khó nhất, đáng điểm nhất)

Test:  pytest tests/test_second_opinion.py -q

Máy kiểm quy tắc, người kiểm ý nghĩa (slide). Các lỗi như thiếu nhãn / gán nhầm lớp hợp lệ / box lỏng
KHÔNG bắt được bằng quy tắc cú pháp. Ta nhờ một model mạnh hơn "nhìn lại" và CHỈ CẢNH BÁO (model cũng có thể sai):
những ảnh bị cờ sẽ vào hàng đợi cho NGƯỜI duyệt.

`preds[stem]` = list `[id_lớp, conf, cx, cy, w, h]` của model (lấy qua `get_preds(ds, cfg, "checker")` nếu preds=None).
`L = ds.valid_boxes(stem)` = list `(id_lớp, cx, cy, w, h)` của nhãn (đã bỏ dòng hỏng).
Ngưỡng ở `cfg["second_opinion"]`: conf, min_area_px, fp_conf, iou_missing, iou_match, iou_loose.

Thuật toán gợi ý, với từng ảnh (bỏ qua ảnh không có trong preds hoặc không có file nhãn):
  P = dự đoán có conf >= conf  VÀ diện tích px (w*W * h*H) >= min_area_px
  Với mỗi dự đoán r trong P: lấy các nhãn có IoU(r, nhãn) >= iou_missing  (cands)
   - không có cands                            -> POSSIBLE_MISSING     (model thấy vật mà nhãn không có box)
   - có cands cùng lớp, tốt nhất IoU < iou_loose -> POSSIBLE_LOOSE_BOX  (đúng vật, box lỏng/lệch)
   - không có cands cùng lớp, nhưng cands tốt nhất IoU >= iou_match (khác lớp) -> POSSIBLE_WRONG_CLASS
  Với mỗi dòng nhãn hợp lệ: nếu IoU với MỌI dự đoán (conf >= fp_conf, không lọc diện tích) đều < iou_missing
                                             -> POSSIBLE_FALSE_POS  (box nhãn không khớp vật nào model thấy; Issue.line = số dòng)

Chi tiết các ca biên (test kiểm đúng các ca này)
- `cands` gồm nhãn MỌI lớp có IoU >= iou_missing; "tốt nhất cùng lớp" = cands cùng lớp có IoU lớn nhất; "tốt nhất khác lớp" tương tự với cands khác lớp.
- Thứ tự quyết định cho mỗi dự đoán: (1) cands rỗng -> MISSING. (2) có cands cùng lớp: IoU tốt nhất < iou_loose -> LOOSE_BOX, ngược lại KHÔNG cờ
  (nhãn đúng lớp đã phủ vật này, kể cả khi còn nhãn khác lớp chồng lên). (3) không có cands cùng lớp: nếu IoU tốt nhất khác lớp >= iou_match -> WRONG_CLASS;
  nếu chỉ có khác lớp với IoU trong [iou_missing, iou_match) -> không cờ gì (mơ hồ: để cho FALSE_POS / lần duyệt khác).
- Một dự đoán sinh tối đa MỘT issue (MISSING / LOOSE_BOX / WRONG_CLASS); một ảnh có thể có nhiều issue.
- Thứ tự issue: theo `ds.image_files()` rồi theo thứ tự dự đoán trong `preds[stem]`, cuối cùng là các FALSE_POS theo số dòng; `Issue.image` = stem, `Issue.line` chỉ đặt cho FALSE_POS.

Lưu ý số dòng: dùng `ds.read_label_lines(stem)` (giữ số dòng gốc, kể cả dòng hỏng/trống) để lấy `Issue.line`; `valid_boxes` KHÔNG giữ số dòng.

Tất cả severity WARN; `Issue.extra` nên có {"conf": ...} hoặc {"iou": ...} (hàng đợi duyệt dùng conf để xếp ưu tiên).

Gợi ý
- `iou_xywh` có sẵn. Dòng nhãn hỏng không được làm script chết (dùng `ds.valid_boxes` và `parse_yolo_line` trong try).
- Kết quả phụ thuộc mạnh vào ngưỡng: calibrate chúng ở Bước 3 thay vì đoán.
"""
from ..common import WARN, Issue, iou_xywh, parse_yolo_line
from ..model_cache import get_preds


def _warn(code, stem, msg, line=None, **extra):
    return Issue("second_opinion", WARN, code, stem, msg, line, extra)


def run(ds, cfg, preds=None):
    c = cfg["second_opinion"]
    if preds is None:
        preds = get_preds(ds, cfg, "checker")
    issues = []
    for p in ds.image_files():                                    # thứ tự issue: theo ảnh
        stem = p.stem
        lines = ds.read_label_lines(stem)
        size = ds.image_size(stem)
        if stem not in preds or lines is None or size is None:    # không có dự đoán / file nhãn / ảnh hỏng
            continue
        W, H = size

        # nhãn hợp lệ KÈM số dòng gốc (valid_boxes làm mất số dòng, mà FALSE_POS cần nó)
        labels = []
        for no, text in lines:
            try:
                cls, x, y, w, h = parse_yolo_line(text)
            except ValueError:
                continue                                          # dòng hỏng: label_format đã báo
            if 0 <= cls < len(ds.classes):
                labels.append((no, cls, (x, y, w, h)))

        # A) với từng dự đoán đáng tin: MISSING / LOOSE_BOX / WRONG_CLASS (tối đa 1 issue mỗi dự đoán)
        for r in preds[stem]:
            pc, conf, box = int(r[0]), r[1], tuple(r[2:6])       # r = [lớp, conf, cx, cy, w, h]
            if conf < c["conf"] or box[2] * W * box[3] * H < c["min_area_px"]:
                continue
            cands = [(iou_xywh(box, lb), lc) for _, lc, lb in labels]
            cands = [(iou, lc) for iou, lc in cands if iou >= c["iou_missing"]]
            same = [iou for iou, lc in cands if lc == pc]
            other = [iou for iou, lc in cands if lc != pc]
            name = ds.classes[pc] if 0 <= pc < len(ds.classes) else pc
            if not cands:
                issues.append(_warn("POSSIBLE_MISSING", stem, f"model thấy {name} (conf {conf:.2f}) mà nhãn không có box",
                                    conf=conf, box=list(box)))    # box của model: để người/công cụ biết vật ở đâu
            elif same:                                            # có nhãn cùng lớp: chỉ cờ khi ôm lệch
                if max(same) < c["iou_loose"]:
                    issues.append(_warn("POSSIBLE_LOOSE_BOX", stem, f"box {name} lệch/lỏng (IoU {max(same):.2f})",
                                        conf=conf, iou=round(max(same), 4), box=list(box)))
            elif max(other) >= c["iou_match"]:                    # chỉ có nhãn khác lớp, chồng rõ
                issues.append(_warn("POSSIBLE_WRONG_CLASS", stem, f"model nói {name} (conf {conf:.2f}), nhãn ghi lớp khác",
                                    conf=conf, iou=round(max(other), 4), box=list(box)))
            # còn lại (khác lớp, IoU trong [iou_missing, iou_match)): mơ hồ, không cờ

        # B) nhãn không khớp vật nào model thấy (conf >= fp_conf, KHÔNG lọc diện tích)
        fp = [tuple(r[2:6]) for r in preds[stem] if r[1] >= c["fp_conf"]]
        for no, lc, lb in labels:
            if all(iou_xywh(lb, b) < c["iou_missing"] for b in fp):
                issues.append(_warn("POSSIBLE_FALSE_POS", stem, f"box {ds.classes[lc]} không khớp vật nào model thấy",
                                    no, iou=0.0))
    return issues
