"""BƯỚC 4 — Cửa chặn: quyết định Release / Hold / Rework.   ★

Test:  pytest tests/test_gate.py -q

Cây quyết định Day 07 (slide Day 09: "Lỗi bắt buộc chặn pipeline; lỗi cảnh báo chuyển người xem"):

  còn ≥ 1 lỗi bắt buộc (severity ERROR)                          -> "Rework"
  không còn lỗi bắt buộc, nhưng tỉ lệ ẢNH còn cảnh báo
      >= cfg["gate"]["warn_ratio_hold"]                          -> "Hold"
  còn lại                                                        -> "Release"

Tỉ lệ cảnh báo = (số ẢNH khác nhau có ≥ 1 cảnh báo) / (tổng số ảnh).  Chú ý:
- chỉ đếm issue có `image` nằm trong `image_stems` (bỏ "<dataset>", "data.yaml");
- bỏ qua ảnh nằm trong `reviewed` (người đã xem, cảnh báo của ảnh đó coi như đã xử lý) — nhưng LỖI BẮT BUỘC thì không bao giờ được bỏ qua;
- mẫu số là số ảnh, không phải số issue.

Trả về dict: decision, n_errors, n_warn_images, n_images, warn_ratio (làm tròn 4 chữ số), reasons (list[str], giải thích bằng tiếng Việt, có số liệu).
"""
from ..common import ERROR, WARN


def decide(issues, image_stems, cfg, reviewed=frozenset()):
    stems = set(image_stems)
    # lỗi bắt buộc: đếm TẤT CẢ, không lọc theo `reviewed` (người duyệt không được "che" lỗi bắt buộc)
    n_err = sum(1 for i in issues if i.severity == ERROR)
    # cảnh báo: gom theo ẢNH (set), chỉ ảnh còn trong dataset và chưa được người duyệt
    warn_imgs = {i.image for i in issues
                 if i.severity == WARN and i.image in stems and i.image not in reviewed}
    n = len(stems)
    ratio = round(len(warn_imgs) / n, 4) if n else 0        # dataset rỗng: tránh chia cho 0
    limit = cfg["gate"]["warn_ratio_hold"]

    if n_err:
        decision = "Rework"
        reasons = [f"Còn {n_err} lỗi bắt buộc chưa sửa"]
    elif ratio >= limit:                                    # đúng bằng ngưỡng vẫn là Hold
        decision = "Hold"
        reasons = [f"{len(warn_imgs)}/{n} ảnh ({ratio:.1%}) còn cảnh báo chưa duyệt, >= ngưỡng {limit:.0%}"]
    else:
        decision = "Release"
        reasons = [f"Không còn lỗi bắt buộc; {len(warn_imgs)}/{n} ảnh ({ratio:.1%}) còn cảnh báo, < ngưỡng {limit:.0%}"]

    return {"decision": decision, "n_errors": n_err, "n_warn_images": len(warn_imgs),
            "n_images": n, "warn_ratio": ratio, "reasons": reasons}
