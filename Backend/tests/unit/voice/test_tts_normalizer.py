from app.voice.tts_normalizer import TABLE_SKIP_TEXT, normalize_for_speech, truncate_at_sentence


def test_strips_markdown_links_and_citations():
    out = normalize_for_speech("## Tiêu đề\n**Đậm** và *nghiêng* [1], xem [trang](https://tlu.edu.vn) `mã`")
    assert "#" not in out and "*" not in out and "[" not in out
    assert "https" not in out
    assert "Tiêu đề." in out and "Đậm và nghiêng" in out and "trang" in out and "mã" in out


def test_percent_currency_and_units():
    out = normalize_for_speech("Lãi 6,10%/năm, học phí 450.000đ/tín chỉ, phí 20 USD, 100 VNĐ")
    assert "6 phẩy 10 phần trăm một năm" in out
    assert "450.000 đồng một tín chỉ" in out
    assert "20 đô la Mỹ" in out
    assert "100 đồng" in out


def test_dates_and_scores():
    out = normalize_for_speech("Hạn 15/9/2026. Khai giảng ngày 5/10. Điểm 8/10.")
    assert "ngày 15 tháng 9 năm 2026" in out
    assert "ngày 5 tháng 10" in out
    assert "8/10" in out  # không đọc nhầm điểm thành ngày


def test_ranges_but_not_phone_numbers():
    out = normalize_for_speech("Khoảng 7-8 điểm, gọi 024-3852-2201")
    assert "7 đến 8" in out
    assert "024-3852-2201" in out


def test_abbreviations_without_duplicate_word():
    out = normalize_for_speech("Điểm ĐRL cao, liên hệ PĐT. CPA tối thiểu 2.0")
    assert "Điểm rèn luyện" in out and "điểm điểm" not in out.lower()
    assert "phòng đào tạo" in out
    assert "CPA" in out  # mục có nghĩa chứa chính từ viết tắt được giữ nguyên


def test_small_table_read_row_by_row():
    md = "| Ngành | Điểm chuẩn |\n|---|---|\n| Kỹ thuật | 24 |\n| Kinh tế | 23,5 |"
    out = normalize_for_speech(md)
    assert "Kỹ thuật, Điểm chuẩn: 24" in out
    assert "Kinh tế, Điểm chuẩn: 23,5" in out
    assert "|" not in out


def test_large_table_is_skipped():
    rows = "\n".join(f"| Ngành {i} | {20 + i} |" for i in range(10))
    out = normalize_for_speech("Bảng điểm:\n| Ngành | Điểm |\n|---|---|\n" + rows)
    assert TABLE_SKIP_TEXT in out
    assert "Ngành 9" not in out


def test_latex_block_replaced():
    out = normalize_for_speech("Công thức: $$CPA = \\frac{\\sum a}{n}$$ xong")
    assert "frac" not in out and "$" not in out
    assert "xem trên màn hình" in out


def test_truncate_at_sentence():
    out = truncate_at_sentence("Câu một. Câu hai dài hơn. Câu ba.", 20)
    assert out.startswith("Câu một.")
    assert "Câu ba" not in out


def test_empty():
    assert normalize_for_speech("") == ""
    assert normalize_for_speech("   ") == ""
