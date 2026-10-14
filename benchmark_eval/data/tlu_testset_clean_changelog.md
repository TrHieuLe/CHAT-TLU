# Changelog bộ test sạch `tlu_testset_clean.json`

Sinh tự động bởi `benchmark_eval/scripts/build_clean_testset.py` từ `tlu_testset_246.json`.

- Bộ gốc: 236 câu, 162 câu khác nhau sau chuẩn hóa (bỏ 74 bản trùng).
- Loại: 42 câu (tính theo câu khác nhau).
- Bộ sạch: 120 câu (0 câu từ feedback_candidates.jsonl).

Nguyên tắc gán nhãn: ground_truth chỉ gồm tài liệu **có trong index** và **chứa câu trả lời**.
Các nhãn cũ lấy từ nguồn hệ thống cũ trả về nên thường kèm tài liệu không liên quan
(ChiTieu.txt, CauLacBo.txt, KyTucXa.txt...) và file không được index
(SuKienSinhVien.txt, anhtruong.docx, toa.docx, table_docx_*.png).
`TA.docx` và `QĐ về tiếng anh CTTT...1315.docx` có nội dung giống hệt nhau nên luôn đi cùng nhau.

## Câu bị loại

| id gốc | Câu hỏi | Lý do |
|---|---|---|
| 40 | đưa ra ví dụ cụ thể đi | câu hỏi nối tiếp, không tự đứng được nếu thiếu lượt hội thoại trước |
| 44 | Ngành trí tuệ nhân tạo thì sao | câu hỏi nối tiếp, không tự đứng được nếu thiếu lượt hội thoại trước |
| 46 | Hãy in lại cho tôi ảnh tôi vừa gửi bạn | yêu cầu in lại ảnh người dùng gửi, không phải truy xuất tài liệu |
| 47 | Bạn in ra được logo của trường đại học thủy lợi không | yêu cầu in ảnh trường/logo; ảnh (anhtruong.docx) không có trong index |
| 54 | hãy thay số cụ thể cho tôi | câu hỏi nối tiếp, không tự đứng được nếu thiếu lượt hội thoại trước |
| 59 | Giả thích cho tôi ý 1 đi | câu hỏi nối tiếp, không tự đứng được nếu thiếu lượt hội thoại trước |
| 65 | Giải thích cho tôi về cái đầu đi | câu hỏi nối tiếp, không tự đứng được nếu thiếu lượt hội thoại trước |
| 67 | Giải thích cho tôi ý đầu đi | câu hỏi nối tiếp, không tự đứng được nếu thiếu lượt hội thoại trước |
| 69, 180, 182, 184, 190, 193 | Giải thích cho tôi ý 1 đi | câu hỏi nối tiếp, không tự đứng được nếu thiếu lượt hội thoại trước |
| 70 | Vậy nếu tôi học lực khá thì sẽ không bị điều kiện này hạ bằng à | câu hỏi nối tiếp, không tự đứng được nếu thiếu lượt hội thoại trước |
| 73 | Vậy nếu tôi được các tín còn lại đều điểm B thì có bị xuống dưới 3.0 không | câu hỏi nối tiếp, không tự đứng được nếu thiếu lượt hội thoại trước |
| 74 | bị full C thì sao | câu hỏi nối tiếp, không tự đứng được nếu thiếu lượt hội thoại trước |
| 75 | Làm sao để học tốt tại trường đại học thủy lợi | câu hỏi chung chung/xin lời khuyên, không có tài liệu đích |
| 149 | đưa ví dụ cụ thể dễ hiểu đi | câu hỏi nối tiếp, không tự đứng được nếu thiếu lượt hội thoại trước |
| 159 | giải thích cho tôi ý số 1 đi | câu hỏi nối tiếp, không tự đứng được nếu thiếu lượt hội thoại trước |
| 165 | giải thích cho tôi trường hợp 1 đi | câu hỏi nối tiếp, không tự đứng được nếu thiếu lượt hội thoại trước |
| 167 | giải thích cho tôi trường hợp đầu tiên đi | câu hỏi nối tiếp, không tự đứng được nếu thiếu lượt hội thoại trước |
| 168 | giải thích cho tôi trường hợp thứ 2 đi | câu hỏi nối tiếp, không tự đứng được nếu thiếu lượt hội thoại trước |
| 171 | Tôi học 20 tín ngành công nghệ thông tin thì được bao nhiêu | câu hỏi nối tiếp, không tự đứng được nếu thiếu lượt hội thoại trước |
| 172 | vậy nếu tôi được học bổng loại xuất sắc thì sao | câu hỏi nối tiếp, không tự đứng được nếu thiếu lượt hội thoại trước |
| 173 | vậy loại khá | câu hỏi nối tiếp, không tự đứng được nếu thiếu lượt hội thoại trước |
| 176 | Giải thích cho tôi trường hợp đầu đi | câu hỏi nối tiếp, không tự đứng được nếu thiếu lượt hội thoại trước |
| 178 | Giải thích chi tiết cho tôi ý 1 | câu hỏi nối tiếp, không tự đứng được nếu thiếu lượt hội thoại trước |
| 187 | vậy hãy cho tôi điểm của khoa công nghệ thông tin đi | câu hỏi nối tiếp, không tự đứng được nếu thiếu lượt hội thoại trước |
| 194 | Vậy là sinh viên loại Khá học lại cũng không sao à | câu hỏi nối tiếp, không tự đứng được nếu thiếu lượt hội thoại trước |
| 202 | Cho tôi ảnh trường đại học thủy lợi đi | yêu cầu in ảnh trường/logo; ảnh (anhtruong.docx) không có trong index |
| 203, 216, 234 | cho tôi ảnh trường đại học thủy lợi | yêu cầu in ảnh trường/logo; ảnh (anhtruong.docx) không có trong index |
| 204 | cho tôi ảnh trường đại học phenika | ngoài phạm vi (trường khác) |
| 205 | Trường đại học bách khoa Hà NỘi | ngoài phạm vi (trường khác) |
| 206 | in cho tôi ảnh trường đại học thủy lợi | yêu cầu in ảnh trường/logo; ảnh (anhtruong.docx) không có trong index |
| 207 | hãy cho tôi ảnh trường đại học bách khoa | ngoài phạm vi (trường khác) |
| 208 | cho tôi ảnh của trường đại học thủy lợi | yêu cầu in ảnh trường/logo; ảnh (anhtruong.docx) không có trong index |
| 209 | ảnh khác đi | câu hỏi nối tiếp, không tự đứng được nếu thiếu lượt hội thoại trước |
| 210 | hãy in cho tôi ảnh trường đại học bách khoa Hà NỘi | ngoài phạm vi (trường khác) |
| 211 | in cho tôi ảnh đại học phenila | ngoài phạm vi (trường khác) |
| 212 | phenika mà | câu hỏi nối tiếp, không tự đứng được nếu thiếu lượt hội thoại trước |
| 214 | cho tôi ảnh đại học thủy lợi | yêu cầu in ảnh trường/logo; ảnh (anhtruong.docx) không có trong index |
| 224 | tòa nhà c1 ở đâu | không có tài liệu nào trong index trả lời (toa.docx chưa được index) |
| 225 | tòa nhà c2 ở đâu | không có tài liệu nào trong index trả lời (toa.docx chưa được index) |
| 226 | ẢNh trường đại học thủy lợi đâu | yêu cầu in ảnh trường/logo; ảnh (anhtruong.docx) không có trong index |
| 227 | ảnh trường phenika | ngoài phạm vi (trường khác) |
| 228 | tòa c1 ở đâu | không có tài liệu nào trong index trả lời (toa.docx chưa được index) |

## Câu đổi nhãn hoặc gộp bản trùng

| id gốc | Câu hỏi | Nhãn cũ (hợp các bản) | Nhãn mới | Ghi chú |
|---|---|---|---|---|
| 1, 7, 12, 25, 45, 49, 57, 60, 78 | Học phí trường là bao nhiêu? | ChiTieu.txt<br>KyTucXa.txt<br>QĐ ve HBKKHT, HBCS .docx<br>QĐ về Học phí final (25-10-2021).docx<br>TATC.docx | HocPhi.txt<br>QĐ về Học phí final (25-10-2021).docx | mức thu theo tín chỉ chỉ có trong HocPhi.txt; gộp 9 bản |
| 2, 9, 13, 17, 20, 50 | Các chứng chỉ ngoại ngữ được tham chiếu có trình độ tương đương | ChiTieu.txt<br>DiemChuan.txt<br>QD411_QD_DHTL-Chuan_Dau_Ra_CNTT.pdf<br>QĐ về tiếng anh CTTT.300921.QD.1315.docx<br>QĐ-1226-Quy che dao tao dai hoc-DHTL .docx<br>TA.docx<br>TATC.docx | TATC.docx | bảng chứng chỉ tham chiếu tương đương nằm trong TATC.docx; gộp 6 bản |
| 3, 10, 14, 16, 19 | Các cơ sở tổ chức cấp chứng chỉ tiếng Anh quốc tế được công nhận | ChiTieu.txt<br>DiemChuan.txt<br>QĐ về tiếng anh CTTT.300921.QD.1315.docx<br>QĐ-1226-Quy che dao tao dai hoc-DHTL .docx<br>TATC.docx<br>introduce.txt | TATC.docx | danh sách tổ chức cấp chứng chỉ (IIG, British Council, IDP) nằm trong TATC.docx; gộp 5 bản |
| 4, 6 | In ra bảng Các chứng chỉ ngoại ngữ được tham chiếu có trình độ tương đương đi | ChiTieu.txt<br>QĐ về tiếng anh CTTT.300921.QD.1315.docx<br>QĐ-1226-Quy che dao tao dai hoc-DHTL .docx | TATC.docx | gộp 2 bản |
| 5 | in ra bảng Các cơ sở tổ chức cấp chứng chỉ tiếng Anh quốc tế được công nhận đi | DangKyTinChi.txt<br>QĐ về tiếng anh CTTT.300921.QD.1315.docx<br>QĐ-1226-Quy che dao tao dai hoc-DHTL .docx<br>introduce.txt | TATC.docx |  |
| 8 | hocj phí trường là bao nhiêu | TATC.docx | HocPhi.txt<br>QĐ về Học phí final (25-10-2021).docx | nhãn cũ TATC.docx (học phí tiếng Anh tăng cường) sai |
| 11 | Học phí ngành công nghệ thông tin trường đại học thủy lợi là bao nhiêu | TATC.docx | HocPhi.txt | nhãn cũ TATC.docx sai; mức 420.000đ/tín chỉ ngành CNTT nằm trong HocPhi.txt |
| 18, 48 | Điều kiện tốt nghiệp gồm những gì? | DangKyTinChi.txt<br>QĐ-1226-Quy che dao tao dai hoc-DHTL .docx<br>SuKienSinhVien.txt | QĐ-1226-Quy che dao tao dai hoc-DHTL .docx<br>QuyDinhHocTap.txt | bỏ SuKienSinhVien.txt (không có trong index); gộp 2 bản |
| 21 | TRường đại học thủy lợi thành lập năm bao nhiêu | CauLacBo.txt<br>QĐ về Học phí final (25-10-2021).docx<br>SuKienSinhVien.txt<br>TATC.docx<br>introduce.txt | introduce.txt |  |
| 22 | tRƯỜNG có bao nhiêu cơ sở | ChiTieu.txt<br>TATC.docx<br>introduce.txt | introduce.txt |  |
| 23 | Trường có bao nhiêu cơ sở ý | KyTucXa.txt<br>TATC.docx<br>introduce.txt | introduce.txt |  |
| 24 | Tôi học ngành công nghệ thông tin và được học bổng loại giỏi với 20 tín chỉ thì tôi được bao nhiêu tiền | QĐ ve HBKKHT, HBCS .docx<br>QĐ về Học phí final (25-10-2021).docx | QĐ ve HBKKHT, HBCS .docx<br>HocBong.txt<br>HocPhi.txt | cần mức học bổng (% học phí) và đơn giá tín chỉ CNTT |
| 27 | quy đổi điểm từ các chứng chỉ Tiếng Anh quốc tế | TA.docx<br>TATC.docx | TA.docx<br>QĐ về tiếng anh CTTT.300921.QD.1315.docx | bảng quy đổi điểm IELTS/TOEIC nằm trong QĐ 1315 (TA.docx) |
| 28 | Chỉ tiêu của trường đại học thủy lợi | CauLacBo.txt<br>ChiTieu.txt<br>QĐ về Học phí final (25-10-2021).docx | ChiTieu.txt |  |
| 29 | Chỉ tiêu của trường đại học thủy lợi khoa công nghệ thông tin | CauLacBo.txt<br>ChiTieu.txt<br>QĐ về Học phí final (25-10-2021).docx | ChiTieu.txt |  |
| 30 | Yêu cầu về trình độ tiếng Anh của sinh viên sau khi kết thúc năm học thứ nhất và năm học thứ hai | TA.docx<br>TATC.docx | TA.docx<br>QĐ về tiếng anh CTTT.300921.QD.1315.docx |  |
| 31, 162, 229 | Trường đại học thủy lợi có bao nhiêu cơ sở | CauLacBo.txt<br>KyTucXa.txt<br>QĐ về Học phí final (25-10-2021).docx<br>QĐ-1226-Quy che dao tao dai hoc-DHTL .docx<br>anhtruong.docx<br>introduce.txt | introduce.txt | bỏ anhtruong.docx (không có trong index); gộp 3 bản |
| 32 | Cho tôi 1 vài thông tin về thư viện đại học thủy lợi | CauLacBo.txt<br>QĐ về Học phí final (25-10-2021).docx<br>ThuVien.txt | ThuVien.txt |  |
| 33 | Mật khẩu wifi thư viện đại học thủy lợi là gì | TATC.docx<br>ThuVien.txt<br>Wifi.txt | Wifi.txt |  |
| 34 | Mật khẩu wifi tầng 2 tòa B5 là gì | KyTucXa.txt<br>TATC.docx<br>Wifi.txt | Wifi.txt |  |
| 35 | Cho tôi quy tắc cộng điểm rèn luyện của đại học thủy lợi | DangKyTinChi.txt<br>QĐ đánh giá KQRL .docx | QĐ đánh giá KQRL .docx |  |
| 36 | Cho tôi quy chế tính điểm bằng chữ | QĐ đánh giá KQRL .docx<br>QĐ-1226-Quy che dao tao dai hoc-DHTL .docx | QĐ-1226-Quy che dao tao dai hoc-DHTL .docx<br>QuyDinhHocTap.txt |  |
| 37 | Cho tôi chỉ tiêu tất cả các ngành của trường đại học thủy lợi đi | ChiTieu.txt<br>QĐ về Học phí final (25-10-2021).docx<br>introduce.txt | ChiTieu.txt |  |
| 38 | Tôi được 5 môn A 3 tín và 2 môn B 3 tín thì GPA của tôi là bao nhiêu | QĐ-1226-Quy che dao tao dai hoc-DHTL .docx | QĐ-1226-Quy che dao tao dai hoc-DHTL .docx<br>QuyDinhHocTap.txt |  |
| 39 | Tiêu chí lấy điểm để xét học bổng của trường đại học thủy lợi là như nào | DangKyTinChi.txt<br>QĐ ve HBKKHT, HBCS .docx<br>TA.docx | QĐ ve HBKKHT, HBCS .docx<br>HocBong.txt |  |
| 41 | ví dụ cụ thể tính điểm xét học bổng cơ mà | QĐ ve HBKKHT, HBCS .docx<br>QĐ-1226-Quy che dao tao dai hoc-DHTL .docx | QĐ ve HBKKHT, HBCS .docx<br>HocBong.txt |  |
| 51 | ĐIểm gpa bao nhiêu thì mới đươc xuất sắc | QĐ ve HBKKHT, HBCS .docx<br>QĐ-1226-Quy che dao tao dai hoc-DHTL .docx | QĐ-1226-Quy che dao tao dai hoc-DHTL .docx<br>QuyDinhHocTap.txt<br>QĐ ve HBKKHT, HBCS .docx<br>HocBong.txt |  |
| 52 | Quy đổi điểm chứng chỉ tiếng anh quốc tế | TA.docx<br>TATC.docx | TA.docx<br>QĐ về tiếng anh CTTT.300921.QD.1315.docx |  |
| 53 | in ảnh Quy đổi điểm các chứng chỉ tiếng Anh quốc tế sang thang điểm 10 | TA.docx<br>TATC.docx | TA.docx<br>QĐ về tiếng anh CTTT.300921.QD.1315.docx |  |
| 55 | QUy đổi diểm tiếng anh quốc tế | TA.docx<br>TATC.docx | TA.docx<br>QĐ về tiếng anh CTTT.300921.QD.1315.docx |  |
| 56 | cho tôi biết thông tin về trường Đại học Thủy Lợi | CauLacBo.txt<br>ThuVien.txt<br>introduce.txt | introduce.txt |  |
| 58, 66, 68 | Trường hợp nào thì sinh viên bị hạ bằng | QĐ đánh giá KQRL .docx<br>QĐ-1226-Quy che dao tao dai hoc-DHTL .docx<br>SuKienSinhVien.txt | QĐ-1226-Quy che dao tao dai hoc-DHTL .docx<br>QuyDinhHocTap.txt | bỏ SuKienSinhVien.txt (không có trong index); gộp 3 bản |
| 61 | Khoa nào là học phí rẻ nhất | ChiTieu.txt<br>DiemChuan.txt<br>QĐ về Học phí final (25-10-2021).docx<br>TATC.docx | HocPhi.txt | so sánh mức học phí giữa các khối ngành chỉ có trong HocPhi.txt |
| 62 | Ý là khối ngành nào có học phí rẻ nhất trường ý | ChiTieu.txt<br>DiemChuan.txt<br>QĐ về Học phí final (25-10-2021).docx | HocPhi.txt |  |
| 63 | Khối ngành KInh tế-quản lý có bao nhiêu ngành | ChiTieu.txt<br>DiemChuan.txt<br>QD411_QD_DHTL-Chuan_Dau_Ra_CNTT.pdf | HocPhi.txt | danh sách ngành theo khối Kinh tế – Quản lý nằm trong HocPhi.txt |
| 64 | Khi nào thì sinh viên bị hạ bằng | QĐ đánh giá KQRL .docx<br>QĐ-1226-Quy che dao tao dai hoc-DHTL .docx<br>SuKienSinhVien.txt | QĐ-1226-Quy che dao tao dai hoc-DHTL .docx<br>QuyDinhHocTap.txt |  |
| 71 | Vậy làm sao để được Gpa xuất sắc giờ | QĐ ve HBKKHT, HBCS .docx<br>QĐ-1226-Quy che dao tao dai hoc-DHTL .docx | QĐ-1226-Quy che dao tao dai hoc-DHTL .docx<br>QuyDinhHocTap.txt |  |
| 72 | Gpa hiện tại của tôi là 3.16 tôi đã học 120/140 tín thì tôi có khả năng được tốt nghiệp loại xuất sắc không | ChiTieu.txt<br>QĐ ve HBKKHT, HBCS .docx<br>QĐ-1226-Quy che dao tao dai hoc-DHTL .docx | QĐ-1226-Quy che dao tao dai hoc-DHTL .docx<br>QuyDinhHocTap.txt |  |
| 76 | Hãy cho tôi điểm chuẩn ngành công nghệ thông tin đi | DiemChuan.txt<br>QĐ về Học phí final (25-10-2021).docx | DiemChuan.txt |  |
| 77, 104 | Quy chế về điểm rèn luyện là như thế nào ? | QĐ ve HBKKHT, HBCS .docx<br>QĐ đánh giá KQRL .docx<br>QĐ-1226-Quy che dao tao dai hoc-DHTL .docx | QĐ đánh giá KQRL .docx | gộp 2 bản |
| 79 | Giới hạn khối lượng học tập tối thiểu của sinh viên trong một học kỳ là bao nhiêu? | QĐ ve HBKKHT, HBCS .docx<br>QĐ đánh giá KQRL .docx<br>QĐ-1226-Quy che dao tao dai hoc-DHTL .docx<br>TATC.docx | QĐ-1226-Quy che dao tao dai hoc-DHTL .docx<br>DangKyTinChi.txt | giới hạn tín chỉ/học kỳ ở Điều 8 QĐ 1226 và DangKyTinChi.txt |
| 80 | Khối lượng học tập tối đa sinh viên được đăng ký trong một học kỳ là bao nhiêu? | DangKyTinChi.txt<br>QĐ ve HBKKHT, HBCS .docx<br>QĐ về Học phí final (25-10-2021).docx<br>QĐ đánh giá KQRL .docx | QĐ-1226-Quy che dao tao dai hoc-DHTL .docx<br>DangKyTinChi.txt |  |
| 81 | Điểm chữ A tương ứng với thang điểm 10 là bao nhiêu? | DiemChuan.txt<br>QĐ-1226-Quy che dao tao dai hoc-DHTL .docx<br>TA.docx | QĐ-1226-Quy che dao tao dai hoc-DHTL .docx<br>QuyDinhHocTap.txt |  |
| 82 | Điểm chữ D tương ứng với thang điểm 10 là bao nhiêu? | DiemChuan.txt<br>QĐ đánh giá KQRL .docx<br>QĐ-1226-Quy che dao tao dai hoc-DHTL .docx | QĐ-1226-Quy che dao tao dai hoc-DHTL .docx<br>QuyDinhHocTap.txt |  |
| 83 | Điểm F tương ứng với mức điểm nào? | QĐ đánh giá KQRL .docx<br>QĐ-1226-Quy che dao tao dai hoc-DHTL .docx<br>TA.docx | QĐ-1226-Quy che dao tao dai hoc-DHTL .docx<br>QuyDinhHocTap.txt |  |
| 84 | Sinh viên xếp loại học lực 'Giỏi' khi có điểm trung bình tích lũy hệ 4 là bao nhiêu? | QĐ ve HBKKHT, HBCS .docx<br>QĐ-1226-Quy che dao tao dai hoc-DHTL .docx | QĐ-1226-Quy che dao tao dai hoc-DHTL .docx<br>QuyDinhHocTap.txt |  |
| 85 | Sinh viên bị buộc thôi học khi nhận cảnh báo học tập mức mấy? | QĐ ve HBKKHT, HBCS .docx<br>QĐ đánh giá KQRL .docx<br>QĐ-1226-Quy che dao tao dai hoc-DHTL .docx | QĐ-1226-Quy che dao tao dai hoc-DHTL .docx<br>QuyDinhHocTap.txt |  |
| 86 | Tổng số tín chỉ F tồn đọng vượt quá bao nhiêu thì bị cảnh báo học tập? | QĐ ve HBKKHT, HBCS .docx<br>QĐ-1226-Quy che dao tao dai hoc-DHTL .docx | QĐ-1226-Quy che dao tao dai hoc-DHTL .docx<br>QuyDinhHocTap.txt |  |
| 87 | Điều kiện về điểm trung bình tích lũy để xét tốt nghiệp là bao nhiêu? | QĐ-1226-Quy che dao tao dai hoc-DHTL .docx | QĐ-1226-Quy che dao tao dai hoc-DHTL .docx<br>QuyDinhHocTap.txt |  |
| 88 | Hạng tốt nghiệp bị giảm đi một mức nếu số tín chỉ học lại vượt quá bao nhiêu %? | QĐ đánh giá KQRL .docx<br>QĐ-1226-Quy che dao tao dai hoc-DHTL .docx | QĐ-1226-Quy che dao tao dai hoc-DHTL .docx<br>QuyDinhHocTap.txt |  |
| 89 | Quy định trình độ tiếng Anh tại QĐ 1315 áp dụng cho đối tượng nào? | TA.docx<br>TATC.docx | TA.docx<br>QĐ về tiếng anh CTTT.300921.QD.1315.docx |  |
| 90 | Sinh viên có IELTS bao nhiêu thì được miễn học tất cả học phần tiếng Anh năm thứ nhất? | TA.docx<br>TATC.docx | TA.docx<br>QĐ về tiếng anh CTTT.300921.QD.1315.docx |  |
| 91 | Mức điểm IELTS 4.5 tương đương bao nhiêu điểm cho kỹ năng nâng cao 1? | QĐ về tiếng anh CTTT.300921.QD.1315.docx<br>TA.docx<br>TATC.docx | TA.docx<br>QĐ về tiếng anh CTTT.300921.QD.1315.docx |  |
| 92 | Yêu cầu trình độ tiếng Anh khi kết thúc năm học thứ nhất của SV chương trình tiên tiến là gì? | TA.docx | TA.docx<br>QĐ về tiếng anh CTTT.300921.QD.1315.docx |  |
| 93 | Yêu cầu trình độ tiếng Anh khi kết thúc năm học thứ hai của SV chương trình tiên tiến là gì? | TA.docx | TA.docx<br>QĐ về tiếng anh CTTT.300921.QD.1315.docx |  |
| 94 | Chứng chỉ TOEIC 480 tương đương với bao nhiêu điểm cho kỹ năng nâng cao 1? | QĐ về tiếng anh CTTT.300921.QD.1315.docx<br>TA.docx<br>TATC.docx | TA.docx<br>QĐ về tiếng anh CTTT.300921.QD.1315.docx |  |
| 95 | Nếu sinh viên có IELTS 4.0 thì có được miễn học phần tiếng Anh nào không? | TA.docx<br>TATC.docx | TA.docx<br>QĐ về tiếng anh CTTT.300921.QD.1315.docx |  |
| 96 | Học phần Giáo dục thể chất có tính vào điểm trung bình tích lũy không? | QĐ ve HBKKHT, HBCS .docx<br>QĐ đánh giá KQRL .docx<br>QĐ-1226-Quy che dao tao dai hoc-DHTL .docx | QĐ-1226-Quy che dao tao dai hoc-DHTL .docx<br>QD_1038_16.07.2021_GDTC.docx |  |
| 97 | Sinh viên tốt nghiệp sau 3 tháng kể từ khi đủ điều kiện có được nhận bằng không? | DangKyTinChi.txt<br>QĐ-1226-Quy che dao tao dai hoc-DHTL .docx<br>SuKienSinhVien.txt<br>TA.docx | QĐ-1226-Quy che dao tao dai hoc-DHTL .docx |  |
| 98, 132, 133, 134, 135, 136, 137, 138, 139, 140, 141, 142, 143, 144 | Có cần chứng chỉ Công nghệ thông tin để tốt nghiệp không? | ChiTieu.txt<br>QuyDinh_Ve_CDR_CNTT_Ban_hanh_theo_QD411-06-4-2022.pdf<br>QĐ về Học phí final (25-10-2021).docx<br>QĐ-1226-Quy che dao tao dai hoc-DHTL .docx | QuyDinh_Ve_CDR_CNTT_Ban_hanh_theo_QD411-06-4-2022.pdf<br>QD411_QD_DHTL-Chuan_Dau_Ra_CNTT.pdf | nhãn cũ của id 98 (học phí, chỉ tiêu) sai; 13 bản sao còn lại đã gán đúng; gộp 14 bản |
| 99, 131 | Sinh viên có được học 3 chương trình cùng lúc không? | DangKyTinChi.txt<br>QuyDinh_Ve_CDR_CNTT_Ban_hanh_theo_QD411-06-4-2022.pdf<br>QĐ 1089 thi OLP môn học .docx<br>QĐ ve HBKKHT, HBCS .docx<br>QĐ-1226-Quy che dao tao dai hoc-DHTL .docx<br>TATC.docx | QĐ-1226-Quy che dao tao dai hoc-DHTL .docx | học cùng lúc hai chương trình: Điều 17 QĐ 1226; gộp 2 bản |
| 100, 130 | GPA 3.65 xếp hạng tốt nghiệp loại gì? | QĐ-1226-Quy che dao tao dai hoc-DHTL .docx | QĐ-1226-Quy che dao tao dai hoc-DHTL .docx<br>QuyDinhHocTap.txt | gộp 2 bản |
| 101, 129 | Điểm chữ I là gì? | QĐ đánh giá KQRL .docx<br>QĐ-1226-Quy che dao tao dai hoc-DHTL .docx<br>TA.docx | QĐ-1226-Quy che dao tao dai hoc-DHTL .docx<br>QuyDinhHocTap.txt | gộp 2 bản |
| 102, 128 | Học phần thực hành có cần thi kết thúc học phần không? | DangKyTinChi.txt<br>QĐ ve HBKKHT, HBCS .docx<br>QĐ-1226-Quy che dao tao dai hoc-DHTL .docx<br>TATC.docx | QĐ-1226-Quy che dao tao dai hoc-DHTL .docx<br>QuyDinhHocTap.txt | gộp 2 bản |
| 103, 126 | Học lực yếu có bị buộc thôi học không? | QĐ Khen thưởng - KL .docx<br>QĐ ve HBKKHT, HBCS .docx<br>QĐ đánh giá KQRL .docx<br>QĐ-1226-Quy che dao tao dai hoc-DHTL .docx<br>TATC.docx | QĐ-1226-Quy che dao tao dai hoc-DHTL .docx<br>QuyDinhHocTap.txt | nhãn cũ (học bổng, rèn luyện, TATC) sai; buộc thôi học do học lực ở QĐ 1226; gộp 2 bản |
| 105 | Sinh viên đạt Giải Nhì Olympic Quốc gia được công nhận bao nhiêu điểm thi kết thúc học phần? | QĐ 1089 thi OLP môn học .docx<br>QĐ đánh giá KQRL .docx | QĐ 1089 thi OLP môn học .docx |  |
| 106 | Kết quả giải Olympic được sử dụng để xét học bổng cho kỳ nào? | QĐ 1089 thi OLP môn học .docx<br>QĐ đánh giá KQRL .docx | QĐ 1089 thi OLP môn học .docx |  |
| 107, 108 | Sinh viên thuộc hộ cận nghèo là người dân tộc thiểu số được miễn hay giảm học phí? | KyTucXa.txt<br>QĐ 1089 thi OLP môn học .docx<br>QĐ ve HBKKHT, HBCS .docx<br>QĐ về Học phí final (25-10-2021).docx<br>TATC.docx | QĐ về Học phí final (25-10-2021).docx | miễn giảm học phí cho SV dân tộc thiểu số / cận nghèo ở QĐ học phí; gộp 2 bản |
| 109 | Sinh viên nộp bằng tốt nghiệp Trung cấp ngành CNTT được công nhận bao nhiêu điểm Tin học cơ bản? | QuyDinh_Ve_CDR_CNTT_Ban_hanh_theo_QD411-06-4-2022.pdf<br>QĐ-1226-Quy che dao tao dai hoc-DHTL .docx | QuyDinh_Ve_CDR_CNTT_Ban_hanh_theo_QD411-06-4-2022.pdf<br>QD411_QD_DHTL-Chuan_Dau_Ra_CNTT.pdf |  |
| 110 | Nếu nộp chứng chỉ MOS, điểm môn Tin học cơ bản được công nhận là bao nhiêu? | QuyDinh_Ve_CDR_CNTT_Ban_hanh_theo_QD411-06-4-2022.pdf<br>QĐ 1089 thi OLP môn học .docx | QuyDinh_Ve_CDR_CNTT_Ban_hanh_theo_QD411-06-4-2022.pdf<br>QD411_QD_DHTL-Chuan_Dau_Ra_CNTT.pdf |  |
| 111 | Có bao nhiêu module MOS cần đạt để được miễn thi CĐR CNTT? | QuyDinh_Ve_CDR_CNTT_Ban_hanh_theo_QD411-06-4-2022.pdf | QuyDinh_Ve_CDR_CNTT_Ban_hanh_theo_QD411-06-4-2022.pdf<br>QD411_QD_DHTL-Chuan_Dau_Ra_CNTT.pdf |  |
| 113 | Sinh viên đạt Giải Nhì và Ba Olympic cấp trường được bao nhiêu điểm quá trình? | QĐ 1089 thi OLP môn học .docx<br>QĐ đánh giá KQRL .docx | QĐ 1089 thi OLP môn học .docx |  |
| 114 | Học bổng loại Giỏi có giá trị bằng bao nhiêu % học phí? | QĐ ve HBKKHT, HBCS .docx<br>QĐ về Học phí final (25-10-2021).docx | QĐ ve HBKKHT, HBCS .docx<br>HocBong.txt |  |
| 115 | Điểm GPA bao nhiêu được coi là học lực loại Giỏi để xét học bổng? | QĐ ve HBKKHT, HBCS .docx<br>QĐ-1226-Quy che dao tao dai hoc-DHTL .docx | QĐ ve HBKKHT, HBCS .docx<br>HocBong.txt |  |
| 116 | Sinh viên học văn bằng hai có được xét học bổng KKHT không? | QĐ ve HBKKHT, HBCS .docx | QĐ ve HBKKHT, HBCS .docx<br>HocBong.txt |  |
| 117 | Công thức tính Điểm xét học bổng KKHT là gì? | QĐ ve HBKKHT, HBCS .docx | QĐ ve HBKKHT, HBCS .docx<br>HocBong.txt |  |
| 118 | Giá trị học bổng loại Xuất sắc bằng bao nhiêu % mức học phí? | QĐ ve HBKKHT, HBCS .docx<br>QĐ-1226-Quy che dao tao dai hoc-DHTL .docx | QĐ ve HBKKHT, HBCS .docx<br>HocBong.txt |  |
| 119 | Học bổng Khuyến khích học tập (KKHT) có mấy mức? | QĐ ve HBKKHT, HBCS .docx | QĐ ve HBKKHT, HBCS .docx<br>HocBong.txt |  |
| 120 | Các môn học nào không được tính vào điểm trung bình để xét khen thưởng? | QĐ 1089 thi OLP môn học .docx<br>QĐ Khen thưởng - KL .docx<br>QĐ ve HBKKHT, HBCS .docx<br>QĐ-1226-Quy che dao tao dai hoc-DHTL .docx | QĐ Khen thưởng - KL .docx |  |
| 121 | Số tín chỉ tối thiểu để xét khen thưởng trong một học kỳ là bao nhiêu? | QĐ Khen thưởng - KL .docx<br>QĐ ve HBKKHT, HBCS .docx | QĐ Khen thưởng - KL .docx |  |
| 123 | Tổng khối lượng của học phần Tiếng Anh tăng cường là bao nhiêu tín chỉ? | QĐ-1226-Quy che dao tao dai hoc-DHTL .docx<br>TATC.docx | TATC.docx |  |
| 124 | Đối tượng nào bắt buộc phải học Tiếng Anh tăng cường (TATC)? | QĐ về tiếng anh CTTT.300921.QD.1315.docx<br>TATC.docx | TATC.docx |  |
| 125 | Cần bao nhiêu tín chỉ tích lũy để lên năm thứ hai nhóm ngành Kỹ thuật? | ChiTieu.txt<br>QĐ-1226-Quy che dao tao dai hoc-DHTL .docx | QĐ-1226-Quy che dao tao dai hoc-DHTL .docx | bảng xếp trình độ năm học theo tín chỉ ở QĐ 1226 |
| 145 | Điểm chuẩn của trường là bao nhiêu? | DiemChuan.txt<br>QĐ Khen thưởng - KL .docx | DiemChuan.txt |  |
| 146 | Cho tôi điểm chuẩn của khoa công nghệ thông tin đi | QD411_QD_DHTL-Chuan_Dau_Ra_CNTT.pdf<br>QuyDinh_Ve_CDR_CNTT_Ban_hanh_theo_QD411-06-4-2022.pdf | DiemChuan.txt | nhãn cũ (2 file CĐR CNTT) sai |
| 147 | Quy định về học bổng trường là gì? | QĐ ve HBKKHT, HBCS .docx | QĐ ve HBKKHT, HBCS .docx<br>HocBong.txt |  |
| 148, 150, 151, 161, 169, 185, 195, 232, 235 | Điều kiện để được xét học bổng khuyến khích học tập? | QĐ ve HBKKHT, HBCS .docx<br>QĐ về Học phí final (25-10-2021).docx | QĐ ve HBKKHT, HBCS .docx<br>HocBong.txt | gộp 9 bản |
| 152, 160, 177, 189, 223, 231, 233 | Quy chế thi lại, học lại như thế nào? | QĐ-1226-Quy che dao tao dai hoc-DHTL .docx | QĐ-1226-Quy che dao tao dai hoc-DHTL .docx<br>QuyDinhHocTap.txt<br>DangKyTinChi.txt | gộp 7 bản |
| 153 | Cho tôi điểm chuẩn khoa kinh tế đi | DiemChuan.txt<br>QĐ-1226-Quy che dao tao dai hoc-DHTL .docx | DiemChuan.txt |  |
| 154 | Hướng dẫn cách kết nối Wifi của trường? | DangKyTinChi.txt<br>Mục lục Sổ tay sinh viên .docx<br>QĐ đánh giá KQRL .docx<br>QĐ-1226-Quy che dao tao dai hoc-DHTL .docx<br>Wifi.txt | Wifi.txt |  |
| 155 | Cho tôi điểm đầu vào của khoa công nghệ thông tin đi | DiemChuan.txt<br>QD411_QD_DHTL-Chuan_Dau_Ra_CNTT.pdf<br>QuyDinh_Ve_CDR_CNTT_Ban_hanh_theo_QD411-06-4-2022.pdf | DiemChuan.txt |  |
| 156 | Cho tôi điểm đầu vào của khoa kinh tế đi | ChiTieu.txt<br>DiemChuan.txt<br>QĐ 1089 thi OLP môn học .docx | DiemChuan.txt |  |
| 157 | sinh viên sẽ bị hạ bằng khi nào | Quy định về tổ chức thi trực tuyến.docx<br>QuyDinh_Ve_CDR_CNTT_Ban_hanh_theo_QD411-06-4-2022.pdf<br>QĐ Khen thưởng - KL .docx | QĐ-1226-Quy che dao tao dai hoc-DHTL .docx<br>QuyDinhHocTap.txt | nhãn cũ (thi trực tuyến, CĐR CNTT, khen thưởng) không chứa điều kiện hạ bằng |
| 158, 164, 166, 179, 181, 183, 192 | sinh viên bị hạ bằng tốt nghiệp khi nào | QuyDinh_Ve_CDR_CNTT_Ban_hanh_theo_QD411-06-4-2022.pdf<br>QĐ-1226-Quy che dao tao dai hoc-DHTL .docx | QĐ-1226-Quy che dao tao dai hoc-DHTL .docx<br>QuyDinhHocTap.txt | bỏ CĐR CNTT; gộp 7 bản |
| 163 | TRường có những thành tựu nào | ChiTieu.txt<br>QD_1038_16.07.2021_GDTC.docx<br>QĐ-1226-Quy che dao tao dai hoc-DHTL .docx<br>introduce.txt | introduce.txt |  |
| 170 | Vậy nếu học bổng loại giỏi thì được bao nhiêu | QĐ ve HBKKHT, HBCS .docx<br>QĐ-1226-Quy che dao tao dai hoc-DHTL .docx | QĐ ve HBKKHT, HBCS .docx<br>HocBong.txt |  |
| 174 | Vậy học phí trường có tăng theo năm không | QĐ về Học phí final (25-10-2021).docx<br>TATC.docx | HocPhi.txt<br>QĐ về Học phí final (25-10-2021).docx |  |
| 175, 236 | Chuẩn đầu ra Tiếng Anh quy định như thế nào? | QD411_QD_DHTL-Chuan_Dau_Ra_CNTT.pdf<br>QuyDinh_Ve_CDR_CNTT_Ban_hanh_theo_QD411-06-4-2022.pdf<br>QĐ về tiếng anh CTTT.300921.QD.1315.docx<br>TA.docx<br>table_docx_61140543_3_156c1610.png | TA.docx<br>QĐ về tiếng anh CTTT.300921.QD.1315.docx<br>TATC.docx<br>QĐ-1226-Quy che dao tao dai hoc-DHTL .docx | bỏ ảnh table_docx_*.png; bỏ CĐR CNTT (không phải tiếng Anh); gộp 2 bản |
| 186 | sinh viên chất lượng tiên tiến không được xét hocj bổng à | QĐ Khen thưởng - KL .docx<br>QĐ ve HBKKHT, HBCS .docx<br>QĐ-1226-Quy che dao tao dai hoc-DHTL .docx | QĐ ve HBKKHT, HBCS .docx<br>HocBong.txt |  |
| 188 | hãy cho tôi quy đổi điểm tiếng anh quốc tế đi | QĐ 1089 thi OLP môn học .docx<br>QĐ về tiếng anh CTTT.300921.QD.1315.docx<br>TA.docx | TA.docx<br>QĐ về tiếng anh CTTT.300921.QD.1315.docx |  |
| 191 | hãy cho tôi điểm đầu vào của khoa công nghệ thông tin đi | DiemChuan.txt<br>QD411_QD_DHTL-Chuan_Dau_Ra_CNTT.pdf<br>QuyDinh_Ve_CDR_CNTT_Ban_hanh_theo_QD411-06-4-2022.pdf | DiemChuan.txt |  |
| 196 | Cho tôi điểm đầu vào của khoa kinh tế | ChiTieu.txt<br>DiemChuan.txt<br>QĐ 1089 thi OLP môn học .docx | DiemChuan.txt |  |
| 197 | Ngành nào có điểm đầu vào cao nhất khoa kinh tế | ChiTieu.txt<br>DiemChuan.txt<br>QĐ 1089 thi OLP môn học .docx | DiemChuan.txt |  |
| 198 | quy đổi điểm tiếng anh quốc tế | QĐ về tiếng anh CTTT.300921.QD.1315.docx<br>table_docx_8815c2f8_3_1d2d6ca9.png<br>table_docx_98e7b276_3_b2a0572e.png<br>table_docx_c7bba307_3_3b229c78.png | TA.docx<br>QĐ về tiếng anh CTTT.300921.QD.1315.docx | bỏ các file ảnh table_docx_*.png (không có trong index) |
| 199 | Miễn học, miễn thi và công nhận điểm đối với học phần Tin học cơ bản | QuyDinh_Ve_CDR_CNTT_Ban_hanh_theo_QD411-06-4-2022.pdf | QuyDinh_Ve_CDR_CNTT_Ban_hanh_theo_QD411-06-4-2022.pdf<br>QD411_QD_DHTL-Chuan_Dau_Ra_CNTT.pdf |  |
| 200 | Sinh viên đủ điều kiện miễn thi chuẩn đầu ra công nghệ thông tin (như quy định tại
Điều 3) hoặc đạt chuẩn đầu ra công nghệ thông tin do Trường Đại học Thủy lợi tổ
1chức sát hạch sẽ được Nhà trường xem xét miễn học, miễn thi, chuyển và công nhận
điểm đối với học phần Tin học cơ bản trong chương trình đào tạo, cụ thể như nào | QuyDinh_Ve_CDR_CNTT_Ban_hanh_theo_QD411-06-4-2022.pdf | QuyDinh_Ve_CDR_CNTT_Ban_hanh_theo_QD411-06-4-2022.pdf<br>QD411_QD_DHTL-Chuan_Dau_Ra_CNTT.pdf |  |
| 201 | Trường đại học thủy lợi | CauLacBo.txt<br>anhtruong.docx<br>introduce.txt | introduce.txt | bỏ anhtruong.docx |
| 213 | cho tôi bảng quy đổi điểm tiếng anh quốc tế | QĐ về tiếng anh CTTT.300921.QD.1315.docx<br>table_docx_8815c2f8_3_1d2d6ca9.png<br>table_docx_98e7b276_3_b2a0572e.png<br>table_docx_cd9e6e84_3_99ff145b.png | TA.docx<br>QĐ về tiếng anh CTTT.300921.QD.1315.docx | bỏ các file ảnh table_docx_*.png (không có trong index) |
| 215 | đại học thủy lợi | CauLacBo.txt<br>QĐ về Học phí final (25-10-2021).docx<br>anhtruong.docx<br>introduce.txt | introduce.txt | bỏ anhtruong.docx |
| 217, 218, 219, 220 | Cho tôi thông tin về đại học thủy lợi | Mục lục Sổ tay sinh viên .docx<br>QĐ về Học phí final (25-10-2021).docx<br>anhtruong.docx<br>introduce.txt | introduce.txt | bỏ anhtruong.docx; gộp 4 bản |
| 221 | cho tôi thông tin về trường | QĐ Khen thưởng - KL .docx<br>QĐ về Học phí final (25-10-2021).docx | introduce.txt | nhãn cũ (khen thưởng, học phí) sai |
| 222 | cho tôi thông tin về trường đại học thủy lợi | Mục lục Sổ tay sinh viên .docx<br>QĐ về Học phí final (25-10-2021).docx<br>anhtruong.docx<br>introduce.txt | introduce.txt | bỏ anhtruong.docx |
| 230 | Cách tính điểm xét học bổng như thế nào | QĐ ve HBKKHT, HBCS .docx | QĐ ve HBKKHT, HBCS .docx<br>HocBong.txt |  |

## Câu thêm từ phản hồi người dùng

Chưa có (`feedback_candidates.jsonl` chưa tồn tại hoặc chưa có câu nào được điền ground_truth).
