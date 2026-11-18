# Báo cáo Day 09 — Hoàng Quốc Mạnh, 03219

> Báo cáo đã tích hợp từ mẫu `REPORT.md` và số liệu/bằng chứng trong `Day09_BangChung_BaoCao(1).md`. Các mục có dữ liệu được điền theo bằng chứng; không tự bổ sung những quan sát hình ảnh chưa được ghi nhận.

> Cấu hình: `duplicates.phash_dist = 10`, `second_opinion.conf = 0.6` (config_sha1 `931de84d…`, review_sim_sha1 `7988ca22…`). Mọi số khớp `08_summary.json`.

## 1. Kết luận trước
**Hold** (mã thoát 10). Quét 224 ảnh, nhận 202/224 (loại 22 ở cửa vào); dataset xuất 202 ảnh dưới dạng **bản nháp** (`submission/export/clean_v1`, chưa phát hành).
Lý do: không còn lỗi bắt buộc (0), nhưng 38/202 ảnh (18,8%) còn cảnh báo chưa người duyệt, vượt ngưỡng Hold 10%. Hàng đợi 125 ảnh > ngân sách duyệt 80 ảnh, nên 45 ảnh không ai xem — và 38 ảnh còn cảnh báo đều nằm trong 45 ảnh đó.

| Trường (`08_summary.json`) | Giá trị |
|---|---|
| decision | Hold |
| n_errors | 0 |
| n_warn_images / n_images | 38 / 202 |
| warn_ratio | 0.1881 |
| reviewed / budget | 80 / 80 |

## 2. Lỗi và phân việc
Lô 224 ảnh; 202 ảnh qua cửa vào. Danh sách lỗi TRƯỚC khi sửa (`02_error_list_v1`): 211 dòng.

| Mã lỗi | Số ảnh/dòng | Ai sửa | Vì sao |
|---|---:|---|---|
| DUP_IMAGE_EXACT | 8 ảnh | máy (loại ở cửa vào) | md5 trùng từng byte → chắc chắn 100%, không cần người |
| DUP_IMAGE_NEAR | 4 ảnh | máy (loại) | phash ≤ 10; đã mở xem cả 4 cặp (dist 0, 0, 6, 10) đều trùng thật |
| LEAK_TEST | 5 ảnh | máy (loại) | ảnh có trong kho test/val → giữ lại sẽ làm mAP ảo |
| BAD_SIZE | 3 ảnh | máy (loại) | cạnh ngắn 180–226 px < 250 px, quy tắc cứng của dự án |
| CORRUPT_IMAGE | 2 ảnh | máy (loại) | không `load()` được thì không train được, không có gì để sửa |
| BAD_CLASS_ID | 6 dòng / 6 ảnh | máy (xoá dòng) | id ngoài 0..3 (vd. 93, 7, -1) → không suy ra được lớp đúng, giữ lại là nhãn rác |
| BAD_FORMAT | 3 dòng / 3 ảnh | máy (xoá dòng) | thiếu cột / `nan` → không parse được |
| BOX_ZERO | 4 dòng / 4 ảnh | máy (xoá dòng) | w hoặc h = 0, box không diện tích |
| DUP_BOX | 7 dòng / 7 ảnh | máy (xoá dòng sau) | cùng lớp, IoU > 0.9 → bản sao, xoá 1 dòng không mất thông tin |
| BOX_OUT_OF_IMAGE | 8 dòng / 8 ảnh | máy (cắt box) | chỉ tràn mép ít, cắt về [0,1] giữ nguyên lớp và vị trí → an toàn |
| BAD_CLASS_NAME | 2 dòng / data.yaml | máy (đổi tên lớp) | `Person`/`Bus` → chuẩn hoá theo `classes` của dự án |
| MISSING_LABEL_FILE | 6 ảnh | **người** | máy không được bịa nhãn → đánh dấu NEEDS_LABEL |
| POSSIBLE_MISSING | 53 dòng / 52 ảnh | **người** | chỉ là ý kiến model lớn, precision 0.57 trên calib → gần nửa là báo nhầm |
| POSSIBLE_LOOSE_BOX | 28 dòng / 24 ảnh | **người** | sửa mép box cần nhìn ảnh; máy tự chỉnh dễ làm tệ hơn |
| POSSIBLE_FALSE_POS | 29 dòng / 27 ảnh | **người** | box nhãn không khớp vật model thấy; precision chỉ 0.31 → không thể tự xoá |
| POSSIBLE_WRONG_CLASS | 18 ảnh | **người** | nhầm giữa các lớp hợp lệ (car/truck/bus/person), máy không biết bên nào đúng |
| EMPTY_LABEL | 12 ảnh | **người** | không phân biệt được ảnh nền thật hay quên gán nhãn |
| BOX_TINY | 6 dòng / 4 ảnh | người | dưới 12 px theo quy tắc dự án — có thể là vật xa thật |
| BOX_HUGE | 3 ảnh | người | box gần phủ cả ảnh, có thể đúng (vật cận cảnh) hoặc sai |
| CLASS_RARE | 4 dòng | người | lớp ít mẫu, chỉ cần người biết để cân nhắc thu thêm |

Máy tự sửa (`03_fixes.csv`, 36 dòng): `drop_line` 20 · `clip_box` 8 · `needs_label` 6 · `rename_classes` 2. Cửa vào loại 22 ảnh (`01_intake`). Nguyên tắc: máy chỉ sửa khi phép sửa **xác định được và không bịa thông tin**; mọi thứ cần “đoán” vật trong ảnh đều chuyển người.

**Hàng đợi** (`05_review_queue.csv`, 125 ảnh) xếp theo `priority` = tổng trọng số `review.weights` (NEEDS_LABEL 10, WRONG_CLASS 3, MISSING/FALSE_POS/FIXED_DROP_LINE 2, LOOSE_BOX 1.5…) có xét conf. Lý do: ảnh thiếu nhãn là **lỗi bắt buộc** (chưa xử lý thì Rework) nên phải lên đầu; nhầm lớp/sót vật làm hỏng nhãn nặng hơn box lỏng vài pixel. Ảnh #1 `img_0020` (11.52) gộp 3 vấn đề: bị xoá dòng id 93, model thấy thêm vật và nghi nhầm lớp; #2–7 là 6 ảnh NEEDS_LABEL (10.0).

Ngân sách 80 ảnh cắt hàng đợi ở priority 3.34 (ảnh #81 là 3.33). Trong 80 ảnh được duyệt có **74 ảnh mang cảnh báo ngữ nghĩa** (trên tổng 107/125 ảnh có cảnh báo ngữ nghĩa), gồm 18/18 WRONG_CLASS, 50/52 MISSING, 12/23 FALSE_POS, 11/15 EMPTY_LABEL nhưng chỉ 8/24 LOOSE_BOX (trọng số thấp nhất) → 33 ảnh có cảnh báo ngữ nghĩa nằm ngoài ngân sách.

Trước → sau duyệt (số ảnh, `04_error_list_v2` → `07_error_list_v3`):

| Mã | v2 (trước duyệt) | v3 (sau duyệt) |
|---|---:|---:|
| MISSING_LABEL_FILE (lỗi bắt buộc) | 6 | 0 |
| POSSIBLE_MISSING | 52 | 12 |
| POSSIBLE_WRONG_CLASS | 18 | 3 |
| POSSIBLE_LOOSE_BOX | 24 | 20 |
| POSSIBLE_FALSE_POS | 23 | 21 |
| EMPTY_LABEL | 15 | 4 |

LOOSE_BOX và FALSE_POS gần như không giảm — đúng như thứ tự ưu tiên: các ảnh đó nằm cuối hàng đợi.

## 3. Calibration (2 ngưỡng)
Sweep chạy trên tập calib 39 ảnh có đáp án (`calibration_report.md`), rồi kiểm lại trên raw bằng mắt.

| Tham số | Khởi đầu | Đã chọn | Precision / Recall (trước → sau) | Lý do (đánh đổi) |
|---|---|---|---|---|
| `duplicates.phash_dist` | 2 | 10 | DUP_IMAGE_NEAR: P 1.00 → 1.00, R 0.50 → 0.67 (EXACT giữ 1.00/1.00) | Đây là ngưỡng **xoá ảnh** → ưu tiên precision (cờ sai = mất ảnh tốt). 4–14 cho cùng P=1.00/R=0.67 trên calib; trên raw, 10 bắt thêm cặp `img_0186`/`img_0061` (ghế đá, cắt lệch, dist 10) là trùng thật. Không lên 16 dù F1 cao nhất (0.91) vì trên raw xoá nhầm ảnh (xem dưới). |
| `second_opinion.conf` | 0.25 | 0.6 | WRONG_CLASS: P 0.56 → 0.62, R 0.83 → 0.83 · MISSING: P 0.50 → 0.57, R 1.00 → 1.00 · LOOSE_BOX: P 0.29 → 0.20, R 0.40 → 0.20 · FALSE_POS: 0.31/1.00 không đổi (dùng `fp_conf` riêng) | Đây là cảnh báo **cho người xem** → ưu tiên recall. Lên 0.6 giữ nguyên recall của hai mã quan trọng nhất (MISSING, WRONG_CLASS) mà bớt báo nhầm, hàng đợi 143 → 125 ảnh. Đánh đổi thật: recall LOOSE_BOX mất 0.40 → 0.20 (từ conf 0.4). Không chọn 0.8 dù gate ra Release (16/202 = 7,9%): recall MISSING rơi còn 0.75 → “Release giả” vì checker mù bớt, không phải vì data sạch hơn. |

Gate trên raw theo conf (phash_dist = 10): 0.25 → Hold 58/202 · 0.5 → Hold 44/202 · **0.6 → Hold 38/202** · 0.7 → Hold 29/202 · 0.8 → Release 16/202.

**Calibration có thể đánh lừa:** trên calib, `phash_dist = 16` là tốt nhất (DUP_IMAGE_NEAR F1 0.91, P vẫn 1.00). Nhưng chạy trên raw, số ảnh bị loại vì LEAK_TEST nhảy 5 → 11 và DUP_IMAGE_NEAR 4 → 7; mở xem các cặp ở dist 16 thì `img_0011`/`img_0008` (tennis vs trượt tuyết) và `img_0177`/`img_0113` (lướt sóng vs người đàn ông) **khác hẳn nhau** — precision thật trên raw < 1.00, tức là sẽ xoá nhầm ảnh tốt. Calib chỉ có 39 ảnh, 6 cặp near-dup nên không chứa loại “ảnh khác nhưng phash gần” này. Tương tự, LOOSE_BOX chỉ có 5 lỗi chèn nên P/R nhảy từng bậc 20% — một box thay đổi kết luận.

## 4. Cửa chặn và điều pipeline KHÔNG bắt được
**(a) Gate chặn đúng.** Lệnh: `python -m pipeline.run --budget 0 --reports work/rep_nb --export-dir work/exp_nb`
```
[17:40:54]           kết luận: REWORK — Còn 6 lỗi bắt buộc chưa sửa
[17:40:54] Bước 5/5  KHÔNG xuất: còn lỗi bắt buộc (Rework) — trả về bước 3
exit=20
ls work/exp_nb  ->  No such file or directory
```
Kết quả: **Rework**, mã thoát **20**, thư mục `work/exp_nb` **không được tạo** (không xuất dataset). Lý do: không có người duyệt → 6 ảnh `MISSING_LABEL_FILE` (`img_0031`, `img_0053`, `img_0126`, `img_0135`, `img_0170`, `img_0219`) vẫn chưa có nhãn → còn lỗi bắt buộc. Máy không được tự sinh nhãn, nên pipeline đúng là phải dừng chứ không “sửa cho qua”.

**(b) Điểm mù:**
1. **Box lỏng/hụt nhẹ không bị cờ.** LOOSE_BOX chỉ cờ khi IoU < 0.5; recall trên calib chỉ 0.20 (bắt 1/5 lỗi chèn). Box lệch vài pixel hoặc không ôm hết vật gần như luôn lọt. Thêm vào đó, LOOSE_BOX có trọng số thấp nhất nên trên raw chỉ 8/24 ảnh được người xem, v3 còn 20 ảnh.
2. **Ảnh gần trùng bị biến đổi mạnh.** DUP_IMAGE_NEAR recall 0.67 trên calib ở phash 10 (sót 2/6). Muốn bắt thêm phải tăng ngưỡng, nhưng ở 16 đã xoá nhầm ảnh khác hẳn (mục 3) → không thể chỉnh ngưỡng để vừa đủ.
3. **Nhầm lớp mà model lớn cũng nhầm.** WRONG_CLASS recall 0.83 (sót 1/6). Lỗi chèn trên calib chủ yếu person→car, còn raw nghiêng car/truck/bus — đúng nhóm model dễ nhầm, nên recall thật trên raw có thể thấp hơn.
4. **Ảnh không ai duyệt.** 45/125 ảnh vượt ngân sách 80; cả 38 ảnh còn cảnh báo ở v3 đều thuộc 45 ảnh này.

**Lỗi tự nhìn thấy khi xem ảnh:** cặp `img_0011`/`img_0008` và `img_0177`/`img_0113` (bị phash 16 coi là trùng nhưng khác cảnh); cặp `img_0186`/`img_0061` trùng thật ở dist 10. <!-- Thay/bổ sung tên ảnh bạn tự mở xem nếu khác -->

**Ghi chú về ví dụ ảnh quan sát thủ công:** bằng chứng hiện có nêu rõ các cặp `img_0011`/`img_0008` và `img_0177`/`img_0113` bị coi là near-duplicate ở ngưỡng 16 nhưng thực tế khác cảnh; cặp `img_0186`/`img_0061` là trùng thật ở khoảng cách 10. Chưa có mã ảnh được ghi riêng cho ba ví dụ “thiếu box người”, “gán sai lớp” và “box không ôm hết vật”, nên không suy đoán mã ảnh cho các trường hợp này.

## 5. Train: raw vs clean (tùy chọn, chấm riêng)
**Cấu hình (công bằng):** yolo26n, 20 epoch, imgsz 640, batch 16, seed 0 và 1 cho mỗi biến thể; cùng val (`gold_val`), cùng test (100 ảnh), cùng siêu tham số. Train trên **máy local RTX 3050 Laptop 4 GB** (~100–125 s mỗi lần), không dùng Colab. `clean` = `export/clean_v1` khi pipeline kết luận **Hold** (bản nháp, 38/202 ảnh còn cảnh báo chưa duyệt).

| biến thể | #ảnh train | số seed | map50 (TB ± độ lệch) | map50_95 (TB ± độ lệch) | precision (TB ± độ lệch) | recall (TB ± độ lệch) |
|---|---|---|---|---|---|---|
| raw | 224 | 2 | 0.728 ± 0.008 | 0.524 ± 0.004 | 0.855 ± 0.004 | 0.582 ± 0.007 |
| clean | 202 | 2 | 0.734 ± 0.014 | 0.510 ± 0.003 | 0.771 ± 0.010 | 0.638 ± 0.020 |

**So với nhiễu:** chênh mAP50 (clean − raw) = **+0.006**, nhỏ hơn độ lệch giữa 2 seed (0.008 ở raw, 0.014 ở clean) → **nằm trong nhiễu, chưa kết luận được clean tốt hơn**. Các chỉ số khác lệch rõ hơn nhiễu nhưng ngược chiều nhau: mAP50-95 −0.014, precision −0.084, recall +0.056. Tức là clean **không tốt hơn tổng thể**, mà đổi precision lấy recall. AP50 theo lớp cũng dao động mạnh giữa 2 seed (vd. truck ở raw: 0.73 vs 0.60), nên chỉ 2 seed là quá ít.

**Giả thuyết và cách kiểm:**
1. *Raw được lợi nhờ rò rỉ test:* raw còn 5 ảnh `LEAK_TEST` và 12 ảnh trùng (`01_intake`); model raw đã "thấy" một phần test → điểm raw bị đẩy lên. Kiểm: train lại raw sau khi chỉ bỏ 5 ảnh rò rỉ, so mAP50 với raw gốc.
2. *Recall clean tăng vì nhãn người thêm vật bị sót:* người duyệt (mô phỏng) giảm `POSSIBLE_MISSING` 52 → 12 ảnh, nên clean có thêm box cho vật trước đó bị bỏ → recall tăng. Kiểm: đếm box mỗi biến thể từ `class_stats.csv` / thư mục train, so recall theo lớp.
3. *Precision clean giảm vì clean vẫn là bản nháp:* 38 ảnh còn cảnh báo chưa duyệt (FALSE_POS 21, LOOSE_BOX 20 ở v3) và clean ít hơn 22 ảnh. Kiểm: duyệt hết 45 ảnh còn lại rồi train lại.
4. *Đo quá nhỏ:* test chỉ 100 ảnh (387 box), 2 seed. Kiểm: chạy 3–5 seed, báo khoảng tin cậy.

**Kết luận trung thực:** với 2 seed và test 100 ảnh, **không đủ bằng chứng nói clean tốt hơn raw** về mAP50; clean cho recall cao hơn nhưng precision và mAP50-95 thấp hơn. **Việc tiếp:** loại ảnh rò rỉ khỏi raw (giả thuyết 1), duyệt nốt hàng đợi để có clean đạt Release, rồi train lại với ≥ 3 seed.

## 6. Quyết định và ghi chú AI
(a) **Hold.** Để thành Release: tỉ lệ ảnh còn cảnh báo phải < 10%, tức ≤ 20/202 ảnh (9,9%). Hiện còn 38 → người phải duyệt thêm ≥ 18 trong 45 ảnh chưa xem (cả 38 ảnh còn cảnh báo đều nằm trong 45 ảnh đó), hoặc cấp thêm ngân sách duyệt cho lô này. Không đổi `review.budget_images` trong config và không nâng `conf` lên 0.8 để “ép” Release — đó là Release giả.

(b) AI:
- Prompt chính: nhờ Claude viết 4 module `label_format`, `gate`, `autofix`, `second_opinion` theo docstring và test có sẵn, sau đó hỏi cách đọc sweep để chọn ngưỡng.
- Cách kiểm: chạy `pytest` (79/79 passed) và từng file test riêng; chạy `python -m pipeline.run` trên raw và đối chiếu `08_summary.json`; mở xem bằng mắt các cặp ảnh trùng ở dist 6/10/16.
- Một lần AI sai: lúc chọn conf 0.6, AI nói “recall không giảm chút nào”, nhưng bảng sweep cho thấy recall LOOSE_BOX giảm 0.40 → 0.20 — chỉ MISSING và WRONG_CLASS là giữ nguyên.
