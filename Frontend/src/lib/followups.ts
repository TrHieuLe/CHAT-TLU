// Gợi ý câu hỏi tiếp theo cho câu trả lời của bot.
//
// Chủ đề được xác định từ CÂU HỎI của người dùng (trọng số cao nhất) và tên
// tài liệu nguồn; câu trả lời chỉ dùng khi hai tín hiệu trên không khớp chủ đề
// nào. Mọi câu gợi ý đều lấy từ benchmark_eval/data/tlu_testset_clean.json
// (câu đã có đáp án trong kho tài liệu; chỉ sửa chính tả/viết hoa), để bấm vào
// không bị từ chối.

interface FollowupTopic {
  /** Từ khóa (chữ thường) tìm trong câu hỏi / câu trả lời */
  keywords: string[];
  /** Đoạn tên file nguồn (chữ thường) thuộc chủ đề này */
  sources: string[];
  questions: string[];
}

const TOPICS: FollowupTopic[] = [
  {
    keywords: ["học bổng", "kkht", "hbkkht"],
    sources: ["hocbong", "hbkkht"],
    questions: [
      "Công thức tính Điểm xét học bổng KKHT là gì?",
      "Học bổng loại Giỏi có giá trị bằng bao nhiêu % học phí?",
      "Sinh viên học văn bằng hai có được xét học bổng KKHT không?",
    ],
  },
  {
    keywords: ["tốt nghiệp", "hạ bằng", "hạng bằng"],
    sources: [],
    questions: [
      "Điều kiện về điểm trung bình tích lũy để xét tốt nghiệp là bao nhiêu?",
      "Hạng tốt nghiệp bị giảm đi một mức nếu số tín chỉ học lại vượt quá bao nhiêu %?",
      "GPA 3.65 xếp hạng tốt nghiệp loại gì?",
    ],
  },
  {
    keywords: ["cảnh báo", "thôi học", "học vụ"],
    sources: [],
    questions: [
      "Sinh viên bị buộc thôi học khi nhận cảnh báo học tập mức mấy?",
      "Tổng số tín chỉ F tồn đọng vượt quá bao nhiêu thì bị cảnh báo học tập?",
      "Học lực yếu có bị buộc thôi học không?",
    ],
  },
  {
    keywords: ["điểm chữ", "thang điểm", "gpa", "cpa", "điểm trung bình", "xếp loại", "học lực"],
    sources: [],
    questions: [
      "Điểm chữ A tương ứng với thang điểm 10 là bao nhiêu?",
      "Sinh viên xếp loại học lực 'Giỏi' khi có điểm trung bình tích lũy hệ 4 là bao nhiêu?",
      "Học phần Giáo dục thể chất có tính vào điểm trung bình tích lũy không?",
    ],
  },
  {
    keywords: ["thi lại", "học lại", "cải thiện", "đăng ký học", "đăng ký tín chỉ", "khối lượng học tập"],
    sources: ["dangkytinchi", "quydinhhoctap", "quy che dao tao"],
    questions: [
      "Khối lượng học tập tối đa sinh viên được đăng ký trong một học kỳ là bao nhiêu?",
      "Giới hạn khối lượng học tập tối thiểu của sinh viên trong một học kỳ là bao nhiêu?",
      "Quy chế thi lại, học lại như thế nào?",
    ],
  },
  {
    keywords: ["tiếng anh", "ielts", "toeic", "ngoại ngữ", "tatc", "tiên tiến"],
    sources: ["ta.docx", "tatc", "1315"],
    questions: [
      "Sinh viên có IELTS bao nhiêu thì được miễn học tất cả học phần tiếng Anh năm thứ nhất?",
      "Chứng chỉ TOEIC 480 tương đương với bao nhiêu điểm cho kỹ năng nâng cao 1?",
      "Đối tượng nào bắt buộc phải học Tiếng Anh tăng cường (TATC)?",
    ],
  },
  {
    keywords: ["mos", "tin học", "cđr cntt", "chuẩn đầu ra cntt", "chuẩn đầu ra công nghệ thông tin"],
    sources: ["cdr_cntt", "qd411"],
    questions: [
      "Có bao nhiêu module MOS cần đạt để được miễn thi CĐR CNTT?",
      "Nếu nộp chứng chỉ MOS, điểm môn Tin học cơ bản được công nhận là bao nhiêu?",
      "Sinh viên ngành nào không phải thực hiện quy định về CĐR CNTT này?",
    ],
  },
  {
    keywords: ["học phí", "miễn giảm", "miễn học phí", "giảm học phí"],
    sources: ["hocphi", "học phí"],
    questions: [
      "Học phí ngành Công nghệ thông tin là bao nhiêu?",
      "Khối ngành nào có học phí rẻ nhất trường?",
      "Sinh viên thuộc hộ cận nghèo là người dân tộc thiểu số được miễn hay giảm học phí?",
    ],
  },
  {
    keywords: ["điểm chuẩn", "điểm đầu vào", "tuyển sinh", "chỉ tiêu", "xét tuyển"],
    sources: ["diemchuan", "chitieu"],
    questions: [
      "Điểm chuẩn ngành Công nghệ thông tin là bao nhiêu điểm?",
      "Ngành nào có điểm đầu vào cao nhất khoa Kinh tế?",
      "Chỉ tiêu tuyển sinh của Trường Đại học Thủy lợi?",
    ],
  },
  {
    keywords: ["rèn luyện"],
    sources: ["kqrl"],
    questions: [
      "Quy chế về điểm rèn luyện là như thế nào?",
      "Quy tắc cộng điểm rèn luyện của trường như thế nào?",
    ],
  },
  {
    keywords: ["khen thưởng", "danh hiệu", "kỷ luật"],
    sources: ["khen thưởng"],
    questions: [
      "Có bao nhiêu loại danh hiệu khen thưởng định kỳ cuối năm học cho cá nhân?",
      "Số tín chỉ tối thiểu để xét khen thưởng trong một học kỳ là bao nhiêu?",
    ],
  },
  {
    keywords: ["olympic"],
    sources: ["olp", "olympic"],
    questions: [
      "Sinh viên đạt Giải Nhì Olympic Quốc gia được công nhận bao nhiêu điểm thi kết thúc học phần?",
      "Kết quả giải Olympic được sử dụng để xét học bổng cho kỳ nào?",
    ],
  },
  {
    keywords: ["wifi", "thư viện"],
    sources: ["wifi", "thuvien"],
    questions: [
      "Hướng dẫn cách kết nối Wifi của trường?",
      "Cho tôi vài thông tin về thư viện Đại học Thủy lợi",
    ],
  },
  {
    keywords: ["thành lập", "cơ sở", "thành tựu", "thông tin về trường", "giới thiệu"],
    sources: ["introduce"],
    questions: [
      "Trường Đại học Thủy lợi có bao nhiêu cơ sở?",
      "Trường Đại học Thủy lợi thành lập năm nào?",
      "Trường có những thành tựu nào?",
    ],
  },
];

const DEFAULT_QUESTIONS = [
  "Quy chế thi lại, học lại như thế nào?",
  "Chuẩn đầu ra Tiếng Anh quy định như thế nào?",
];

const normalize = (s: string) =>
  s.toLowerCase().normalize("NFC").replace(/[?.!\s]+/g, " ").trim();

function countHits(text: string, needles: string[]): number {
  if (!text) return 0;
  return needles.reduce((n, kw) => (text.includes(kw) ? n + 1 : n), 0);
}

export function getSmartFollowups(
  answer: string,
  question = "",
  sourceTitles: string[] = [],
  limit = 2
): string[] {
  if (!answer) return [];

  const q = question.toLowerCase().normalize("NFC");
  const src = sourceTitles.join(" | ").toLowerCase().normalize("NFC");
  const ans = answer.toLowerCase().normalize("NFC");

  let scored = TOPICS.map((topic, idx) => ({
    topic,
    idx,
    // Câu hỏi luôn thắng: retriever hay kéo thêm tài liệu lệch chủ đề (vd hỏi tốt
    // nghiệp nhưng nguồn là TA.docx), nên nguồn chỉ phân xử khi câu hỏi hòa điểm.
    score: 100 * countHits(q, topic.keywords) + countHits(src, topic.sources),
  })).filter((t) => t.score > 0);

  // Câu hỏi nối tiếp kiểu "vậy thì sao?" không có từ khóa: dựa vào câu trả lời
  if (scored.length === 0) {
    scored = TOPICS.map((topic, idx) => ({ topic, idx, score: countHits(ans, topic.keywords) }))
      .filter((t) => t.score > 0);
  }

  scored.sort((a, b) => b.score - a.score || a.idx - b.idx);

  const asked = normalize(question);
  const seen = new Set<string>();
  const result: string[] = [];
  const pool = [...scored.flatMap((t) => t.topic.questions), ...DEFAULT_QUESTIONS];

  for (const s of pool) {
    const key = normalize(s);
    if (key === asked || seen.has(key)) continue;
    seen.add(key);
    result.push(s);
    if (result.length >= limit) break;
  }
  return result;
}
