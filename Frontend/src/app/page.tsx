'use client';

import React, { useRef, useEffect, useMemo, useState } from 'react';
import Image from 'next/image';
import Link from 'next/link';
import { useChat } from '@/hooks/useChat';
import MessageBubble from '@/components/chat/MessageBubble';
import ChatInput from '@/components/chat/ChatInput';
import DocPreviewModal from '@/components/chat/DocPreviewModal';
import {
  createSession,
  getSessions,
  getHistory,
  deleteSession,
  renameSession,
  getSessionExportUrl,
} from '@/lib/api';
import {
  Plus,
  MessageSquare,
  Menu,
  Loader2,
  PanelLeft,
  Trash2,
  Edit2,
  Check,
  X,
  Download,
  Database,
  Search,
  GraduationCap,
  Award,
  FileText,
  Languages,
} from 'lucide-react';

const TOPICS = [
  { label: 'Tốt nghiệp', icon: GraduationCap, question: 'Điều kiện xét tốt nghiệp gồm những gì?' },
  { label: 'Học bổng', icon: Award, question: 'Điều kiện để được xét học bổng khuyến khích học tập?' },
  { label: 'Học vụ', icon: FileText, question: 'Quy chế thi lại, học lại như thế nào?' },
  { label: 'Tiếng Anh', icon: Languages, question: 'Chuẩn đầu ra Tiếng Anh quy định như thế nào?' },
];

const QUICK_TOPICS = [
  { label: 'Điểm chuẩn', question: 'Điểm chuẩn ngành Công nghệ thông tin là bao nhiêu?' },
  { label: 'Học phí', question: 'Học phí ngành Công nghệ thông tin là bao nhiêu?' },
  { label: 'Điểm rèn luyện', question: 'Quy chế về điểm rèn luyện là như thế nào?' },
  { label: 'Chuẩn đầu ra CNTT', question: 'Có bao nhiêu module MOS cần đạt để được miễn thi CĐR CNTT?' },
  { label: 'Wifi & thư viện', question: 'Cho tôi một vài thông tin về thư viện Đại học Thủy lợi' },
];

type HistoryItem = {
  id: string;
  title?: string;
  updated_at?: string;
};

function groupHistory(items: HistoryItem[]) {
  const now = new Date();
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  const weekAgo = startOfToday - 6 * 24 * 60 * 60 * 1000;
  const groups: { label: string; items: HistoryItem[] }[] = [
    { label: 'Hôm nay', items: [] },
    { label: '7 ngày qua', items: [] },
    { label: 'Cũ hơn', items: [] },
  ];
  for (const it of items) {
    // updated_at từ backend là UTC không kèm múi giờ
    const raw = it.updated_at;
    const t = raw ? new Date(/[zZ]|[+-]\d\d:?\d\d$/.test(raw) ? raw : raw + 'Z').getTime() : NaN;
    if (!Number.isFinite(t) || t >= startOfToday) groups[0].items.push(it);
    else if (t >= weekAgo) groups[1].items.push(it);
    else groups[2].items.push(it);
  }
  return groups.filter((g) => g.items.length > 0);
}

export default function Home() {
  const [sessionId, setSessionId] = useState('');
  const { messages, send, sendImage, regenerate, loading, clear, load } = useChat(sessionId);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const [isMobileSidebarOpen, setIsMobileSidebarOpen] = useState(false);
  const [isDesktopSidebarOpen, setIsDesktopSidebarOpen] = useState(true);

  const [isLoadingHistory, setIsLoadingHistory] = useState(false);
  const [chatHistory, setChatHistory] = useState<HistoryItem[]>([]);
  const [historyQuery, setHistoryQuery] = useState('');
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const [editingId, setEditingId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState('');
  const [previewDoc, setPreviewDoc] = useState<{ isOpen: boolean; url: string; title: string }>({
    isOpen: false,
    url: '',
    title: '',
  });

  useEffect(() => {
    handleNewChat();
  }, []);

  useEffect(() => {
    if (messages.length > 0 && messages.length <= 2 && !loading) {
      fetchSessions();
    }
  }, [messages.length, loading]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  const fetchSessions = async () => {
    try {
      const data = await getSessions();
      setChatHistory(data);
    } catch (error) {
      console.error('Không thể kết nối đến Backend để lấy lịch sử:', error);
    }
  };

  const handleNewChat = async () => {
    clear();
    setIsMobileSidebarOpen(false);

    try {
      const data = await createSession();
      setSessionId(data.id);
    } catch (error) {
      console.error('Lỗi tạo session:', error);
      setSessionId('session-' + Math.random().toString(36).substring(7));
    }

    fetchSessions();
  };

  const handleSelectHistory = async (id: string) => {
    setIsMobileSidebarOpen(false);
    if (id === sessionId) return;

    setIsLoadingHistory(true);
    try {
      const pastMessages = await getHistory(id);
      setSessionId(id);
      load(pastMessages);
    } catch (error) {
      console.error('Lỗi khi lấy tin nhắn:', error);
    } finally {
      setIsLoadingHistory(false);
    }
  };

  const handleDeleteChat = async (
    id: string,
    e: React.MouseEvent<HTMLButtonElement>
  ) => {
    e.stopPropagation();

    setDeletingId(id);
    try {
      await deleteSession(id);
      if (id === sessionId) {
        await handleNewChat();
      } else {
        await fetchSessions();
      }
    } catch (error) {
      console.error('Lỗi khi xóa cuộc trò chuyện:', error);
      alert('Không thể xóa cuộc trò chuyện. Vui lòng thử lại.');
    } finally {
      setDeletingId(null);
    }
  };

  const handleStartRename = (id: string, currentTitle: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setEditingId(id);
    setEditTitle(currentTitle || '');
  };

  const handleSaveRename = async (id: string, e?: React.FormEvent) => {
    if (e) e.preventDefault();
    const cleanTitle = editTitle.trim();
    if (!cleanTitle) {
      setEditingId(null);
      return;
    }
    try {
      await renameSession(id, cleanTitle);
      setChatHistory((prev) =>
        prev.map((c) => (c.id === id ? { ...c, title: cleanTitle } : c))
      );
    } catch (error) {
      console.error('Lỗi khi đổi tên cuộc trò chuyện:', error);
    } finally {
      setEditingId(null);
    }
  };

  const handlePreviewDoc = (url: string, title: string) => {
    setPreviewDoc({
      isOpen: true,
      url,
      title,
    });
  };

  const handleSuggestionClick = (text: string) => {
    send(text);
  };

  const historyGroups = useMemo(() => {
    const q = historyQuery.trim().toLowerCase();
    const filtered = q
      ? chatHistory.filter((c) => (c.title || 'Trò chuyện mới').toLowerCase().includes(q))
      : chatHistory;
    return groupHistory(filtered);
  }, [chatHistory, historyQuery]);

  const currentTitle =
    chatHistory.find((c) => c.id === sessionId)?.title ||
    (messages.length > 0 ? 'Cuộc trò chuyện' : 'Đoạn chat mới');

  // Sidebar thu gọn chỉ áp dụng trên desktop; trên điện thoại luôn hiện đầy đủ khi mở
  const collapsed = !isDesktopSidebarOpen && !isMobileSidebarOpen;

  const renderThinkingBubble = () => (
    <div className="flex w-full justify-start gap-3 animate-fade-up">
      <div className="flex-shrink-0 w-10 h-10 rounded-xl bg-white border border-tlu-tint-2 flex items-center justify-center">
        <Image src="/logo-tlu.png" alt="" width={22} height={29} />
      </div>
      <div className="flex items-center gap-3 text-tlu-blue text-sm bg-white px-5 py-3 rounded-2xl rounded-tl-sm border border-tlu-border">
        <div className="flex gap-1.5" aria-hidden="true">
          <div className="w-2 h-2 bg-tlu-blue rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
          <div className="w-2 h-2 bg-tlu-blue rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
          <div className="w-2 h-2 bg-tlu-red rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
        </div>
        <span className="font-medium">StudyBot đang tra cứu văn bản…</span>
      </div>
    </div>
  );

  return (
    <div className="h-screen bg-tlu-ground text-tlu-ink flex overflow-hidden">
      {isMobileSidebarOpen && (
        <div
          className="fixed inset-0 bg-tlu-navy/50 backdrop-blur-sm z-40 lg:hidden"
          onClick={() => setIsMobileSidebarOpen(false)}
        />
      )}

      <aside
        className={`
          fixed lg:static inset-y-0 left-0 z-50
          ${isDesktopSidebarOpen ? 'w-[300px]' : 'w-[300px] lg:w-[84px]'}
          ${isMobileSidebarOpen ? 'translate-x-0' : '-translate-x-full'}
          lg:translate-x-0
          transition-all duration-300 ease-in-out
          bg-tlu-navy text-tlu-on-navy flex flex-col shadow-2xl lg:shadow-none
          overflow-hidden
        `}
        aria-label="Thanh bên"
      >
        <div className={`flex items-center gap-3 px-4 pt-5 pb-4 ${collapsed ? 'lg:justify-center lg:px-0' : ''}`}>
          <div className="w-12 h-12 rounded-xl bg-white flex items-center justify-center flex-shrink-0">
            <Image src="/logo-tlu.png" alt="Logo Trường Đại học Thủy lợi" width={30} height={39} priority />
          </div>
          <div className={`flex flex-col min-w-0 ${collapsed ? 'lg:hidden' : ''}`}>
            <span className="text-[17px] font-bold text-white tracking-tight leading-tight">StudyBot TLU</span>
            <span className="text-xs text-tlu-on-navy-2">Trợ lý học vụ · ĐH Thủy lợi</span>
          </div>
          <button
            onClick={() => setIsMobileSidebarOpen(false)}
            className="lg:hidden ml-auto w-10 h-10 rounded-lg flex items-center justify-center text-tlu-on-navy-2 hover:bg-tlu-navy-2 hover:text-white"
            aria-label="Đóng thanh bên"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className={`px-4 space-y-3 ${collapsed ? 'lg:px-0 lg:flex lg:flex-col lg:items-center' : ''}`}>
          <button
            onClick={handleNewChat}
            className={`flex items-center justify-center gap-2 h-11 rounded-xl bg-white text-tlu-blue font-semibold text-sm hover:bg-tlu-tint transition-colors ${
              collapsed ? 'w-full lg:w-11' : 'w-full'
            }`}
            title="Đoạn chat mới"
          >
            <Plus className="w-[18px] h-[18px]" />
            <span className={collapsed ? 'lg:hidden' : ''}>Đoạn chat mới</span>
          </button>

          <label className={`flex items-center gap-2 h-10 px-3 rounded-[10px] bg-tlu-navy-2 text-tlu-on-navy-2 ${collapsed ? 'lg:hidden' : ''}`}>
            <Search className="w-4 h-4 flex-shrink-0" aria-hidden="true" />
            <span className="sr-only">Tìm trong lịch sử</span>
            <input
              type="search"
              value={historyQuery}
              onChange={(e) => setHistoryQuery(e.target.value)}
              placeholder="Tìm trong lịch sử…"
              className="flex-1 min-w-0 bg-transparent border-0 outline-none text-sm text-white placeholder:text-tlu-on-navy-3"
            />
          </label>
        </div>

        <nav
          aria-label="Lịch sử trò chuyện"
          className={`flex-1 overflow-y-auto scrollbar-navy px-3 pt-3 pb-2 ${collapsed ? 'lg:hidden' : ''}`}
        >
          {chatHistory.length === 0 ? (
            <p className="text-xs text-center text-tlu-on-navy-3 mt-6">Chưa có cuộc trò chuyện nào</p>
          ) : historyGroups.length === 0 ? (
            <p className="text-xs text-center text-tlu-on-navy-3 mt-6">Không tìm thấy “{historyQuery}”</p>
          ) : (
            historyGroups.map((group) => (
              <div key={group.label} className="mb-2">
                <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-tlu-on-navy-3 px-2 pt-3 pb-1.5">
                  {group.label}
                </p>
                {group.items.map((chat) => {
                  const active = sessionId === chat.id;
                  return (
                    <div
                      key={chat.id}
                      onClick={() => handleSelectHistory(chat.id)}
                      className={`w-full flex items-center gap-2.5 px-2.5 py-2.5 rounded-[10px] transition-colors group cursor-pointer ${
                        active ? 'bg-tlu-navy-3 text-white' : 'text-tlu-on-navy hover:bg-tlu-navy-2 hover:text-white'
                      } ${deletingId === chat.id ? 'opacity-60 pointer-events-none' : ''}`}
                    >
                      <MessageSquare className={`w-4 h-4 flex-shrink-0 ${active ? '' : 'opacity-70'}`} />

                      {editingId === chat.id ? (
                        <form
                          onSubmit={(e) => handleSaveRename(chat.id, e)}
                          className="flex-1 flex items-center gap-1 min-w-0"
                          onClick={(e) => e.stopPropagation()}
                        >
                          <input
                            type="text"
                            value={editTitle}
                            onChange={(e) => setEditTitle(e.target.value)}
                            autoFocus
                            aria-label="Tên cuộc trò chuyện"
                            className="w-full text-sm px-2 py-1 rounded-md bg-white text-tlu-ink outline-none"
                          />
                          <button type="submit" className="p-1 text-white hover:bg-tlu-navy-line rounded" aria-label="Lưu tên">
                            <Check className="w-4 h-4" />
                          </button>
                          <button
                            type="button"
                            onClick={() => setEditingId(null)}
                            className="p-1 text-tlu-on-navy-2 hover:bg-tlu-navy-line rounded"
                            aria-label="Hủy đổi tên"
                          >
                            <X className="w-4 h-4" />
                          </button>
                        </form>
                      ) : (
                        <>
                          <span className="text-sm truncate flex-1">{chat.title || 'Trò chuyện mới'}</span>
                          {active && <span className="w-1.5 h-1.5 rounded-full bg-tlu-red-soft flex-shrink-0 group-hover:hidden" />}

                          <div className="hidden group-hover:flex items-center gap-0.5">
                            <button
                              onClick={(e) => handleStartRename(chat.id, chat.title || '', e)}
                              title="Đổi tên cuộc trò chuyện"
                              aria-label="Đổi tên cuộc trò chuyện"
                              className="p-1 rounded-md text-tlu-on-navy-2 hover:text-white hover:bg-tlu-navy-line"
                            >
                              <Edit2 className="w-3.5 h-3.5" />
                            </button>
                            <a
                              href={getSessionExportUrl(chat.id, 'markdown')}
                              download
                              onClick={(e) => e.stopPropagation()}
                              title="Tải về cuộc trò chuyện (.md)"
                              aria-label="Tải về cuộc trò chuyện"
                              className="p-1 rounded-md text-tlu-on-navy-2 hover:text-white hover:bg-tlu-navy-line"
                            >
                              <Download className="w-3.5 h-3.5" />
                            </a>
                            <button
                              onClick={(e) => handleDeleteChat(chat.id, e)}
                              disabled={deletingId === chat.id}
                              title="Xóa cuộc trò chuyện"
                              aria-label="Xóa cuộc trò chuyện"
                              className="p-1 rounded-md text-tlu-on-navy-2 hover:text-white hover:bg-tlu-red disabled:opacity-50"
                            >
                              {deletingId === chat.id ? (
                                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                              ) : (
                                <Trash2 className="w-3.5 h-3.5" />
                              )}
                            </button>
                          </div>
                        </>
                      )}
                    </div>
                  );
                })}
              </div>
            ))
          )}
        </nav>
        {collapsed && <div className="hidden lg:block flex-1" />}

        <div className={`border-t border-tlu-navy-line px-3 py-3 space-y-1 ${collapsed ? 'lg:px-0 lg:flex lg:flex-col lg:items-center' : ''}`}>
          <Link
            href="/admin"
            className="flex items-center gap-2.5 px-2.5 py-2.5 rounded-[10px] text-sm text-tlu-on-navy hover:bg-tlu-navy-2 hover:text-white transition-colors"
            title="Quản trị tri thức"
          >
            <Database className="w-4 h-4 flex-shrink-0" />
            <span className={collapsed ? 'lg:hidden' : ''}>Quản trị tri thức</span>
          </Link>
          <div className="flex items-center gap-2.5 px-2.5 py-2">
            <span className="w-8 h-8 rounded-full bg-tlu-blue text-white text-xs font-bold flex items-center justify-center flex-shrink-0">
              SV
            </span>
            <div className={`flex flex-col min-w-0 ${collapsed ? 'lg:hidden' : ''}`}>
              <span className="text-sm font-semibold text-white truncate">Sinh viên TLU</span>
              <span className="text-xs text-tlu-on-navy-2 truncate">Khách · lưu trên thiết bị này</span>
            </div>
          </div>
        </div>
      </aside>

      <div className="flex-1 flex flex-col min-w-0 relative">
        <header className="flex items-center justify-between gap-3 px-3 md:px-6 py-3 bg-white border-b border-tlu-border z-10 lg:bg-white max-lg:bg-tlu-navy max-lg:border-b-[3px] max-lg:border-tlu-red">
          <div className="flex items-center gap-2 md:gap-3 min-w-0">
            <button
              onClick={() => setIsMobileSidebarOpen(true)}
              className="lg:hidden w-11 h-11 rounded-xl flex items-center justify-center bg-tlu-navy-2 text-white"
              aria-label="Mở lịch sử trò chuyện"
            >
              <Menu className="w-5 h-5" />
            </button>
            <button
              onClick={() => setIsDesktopSidebarOpen(!isDesktopSidebarOpen)}
              className="hidden lg:flex w-10 h-10 rounded-lg items-center justify-center text-tlu-muted hover:text-tlu-blue hover:bg-tlu-tint transition-colors"
              aria-label={isDesktopSidebarOpen ? 'Thu gọn thanh bên' : 'Mở rộng thanh bên'}
              title={isDesktopSidebarOpen ? 'Thu gọn thanh bên' : 'Mở rộng thanh bên'}
            >
              <PanelLeft className="w-5 h-5" />
            </button>

            {/* Điện thoại: logo + tên trên nền xanh đậm */}
            <div className="lg:hidden flex items-center gap-2.5 min-w-0">
              <div className="w-9 h-9 rounded-[10px] bg-white flex items-center justify-center flex-shrink-0">
                <Image src="/logo-tlu.png" alt="Logo Trường Đại học Thủy lợi" width={22} height={29} />
              </div>
              <div className="flex flex-col min-w-0">
                <span className="text-[15px] font-bold text-white leading-tight">StudyBot TLU</span>
                <span className="text-[11px] text-tlu-on-navy-2 truncate">Trợ lý học vụ · ĐH Thủy lợi</span>
              </div>
            </div>

            {/* Desktop: tên cuộc trò chuyện + phạm vi dữ liệu */}
            <div className="hidden lg:flex items-center gap-3 min-w-0">
              <span className="text-base font-semibold truncate">{currentTitle}</span>
              <span className="hidden xl:inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-tlu-tint text-tlu-blue text-xs font-semibold whitespace-nowrap">
                <span className="w-1.5 h-1.5 rounded-full bg-tlu-blue" />
                Tra cứu trên văn bản quy chế của trường
              </span>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <a
              href="https://tlu.edu.vn"
              target="_blank"
              rel="noopener noreferrer"
              className="hidden lg:inline text-sm font-medium text-tlu-blue hover:text-tlu-blue-dark"
            >
              tlu.edu.vn
            </a>
            <button
              onClick={handleNewChat}
              className="lg:hidden w-11 h-11 rounded-xl flex items-center justify-center bg-white text-tlu-blue"
              aria-label="Đoạn chat mới"
            >
              <Plus className="w-5 h-5" />
            </button>
          </div>
        </header>

        <main className="flex-1 overflow-y-auto px-4 md:px-6 py-6 md:py-8 scroll-smooth">
          <div className="flex flex-col gap-7 pb-6 max-w-[820px] mx-auto">
            {isLoadingHistory ? (
              <div className="flex flex-col items-center justify-center mt-32 text-tlu-muted">
                <Loader2 className="w-8 h-8 animate-spin mb-4 text-tlu-blue" />
                <p>Đang tải cuộc trò chuyện…</p>
              </div>
            ) : messages.length === 0 ? (
              <div className="flex flex-col items-center gap-8 mt-4 md:mt-10 animate-fade-in">
                <section className="flex flex-col items-center text-center gap-3.5">
                  <Image
                    src="/logo-tlu-full.png"
                    alt="Trường Đại học Thủy lợi – Thuyloi University"
                    width={300}
                    height={99}
                    priority
                    className="w-[240px] md:w-[300px] h-auto"
                  />
                  <h1 className="mt-2 text-[26px] md:text-[34px] leading-tight font-bold tracking-tight text-tlu-navy">
                    Xin chào, sinh viên <span className="text-tlu-red whitespace-nowrap">Thủy Lợi</span>
                  </h1>
                  <p className="max-w-[560px] text-[15px] md:text-base leading-relaxed text-slate-600">
                    Hỏi về quy chế đào tạo, học bổng, học phí, chuẩn đầu ra… Mỗi câu trả lời đều kèm văn bản gốc để bạn đối chiếu.
                  </p>
                  <svg width="220" height="14" viewBox="0 0 220 14" fill="none" aria-hidden="true">
                    <path
                      d="M2 7c18 0 18-5 36-5s18 10 36 10 18-10 36-10 18 10 36 10 18-10 36-10 18 5 36 5"
                      stroke="#B6C8E7"
                      strokeWidth="2"
                      strokeLinecap="round"
                    />
                  </svg>
                </section>

                <section aria-label="Câu hỏi gợi ý" className="w-full grid grid-cols-1 sm:grid-cols-2 gap-3.5">
                  {TOPICS.map(({ label, icon: Icon, question }) => (
                    <button
                      key={label}
                      onClick={() => handleSuggestionClick(question)}
                      className="flex flex-col items-start gap-2.5 text-left p-[18px] min-h-[112px] rounded-2xl border border-tlu-border bg-white hover:border-tlu-line hover:shadow-[0_6px_20px_rgba(14,42,94,0.08)] transition-all"
                    >
                      <span className="inline-flex items-center gap-2 text-xs font-semibold text-tlu-blue">
                        <Icon className="w-[18px] h-[18px]" aria-hidden="true" />
                        {label}
                      </span>
                      <span className="text-[15px] leading-snug font-medium text-tlu-ink">{question}</span>
                    </button>
                  ))}
                </section>

                <section aria-label="Chủ đề nhanh" className="flex flex-wrap justify-center gap-2">
                  {QUICK_TOPICS.map(({ label, question }) => (
                    <button
                      key={label}
                      onClick={() => handleSuggestionClick(question)}
                      className="h-9 px-3.5 rounded-full border border-tlu-tint-2 bg-tlu-tint text-tlu-blue-dark text-[13px] font-medium hover:bg-tlu-tint-2 transition-colors"
                    >
                      {label}
                    </button>
                  ))}
                </section>
              </div>
            ) : (
              messages.map((msg, index) => {
                const isLast = index === messages.length - 1;
                const showThinkingAfterThis = loading && isLast && msg.role === 'user';

                return (
                  <React.Fragment key={index}>
                    <div
                      className={`flex w-full ${
                        msg.role === 'user' ? 'justify-end' : 'justify-start'
                      }`}
                    >
                      <MessageBubble
                        msg={msg}
                        question={
                          msg.role === 'model' && messages[index - 1]?.role === 'user'
                            ? messages[index - 1].content
                            : undefined
                        }
                        sessionId={sessionId}
                        isLast={isLast}
                        onRegenerate={regenerate}
                        onSuggestionClick={handleSuggestionClick}
                        onPreviewDocument={handlePreviewDoc}
                      />
                    </div>

                    {showThinkingAfterThis && renderThinkingBubble()}
                  </React.Fragment>
                );
              })
            )}

            <div ref={messagesEndRef} />
          </div>
        </main>

        <footer className="px-3 md:px-6 pt-2 pb-3 md:pb-5 bg-tlu-ground">
          <div className="max-w-[820px] mx-auto space-y-2">
            <ChatInput
              onSend={send}
              onSendImage={sendImage}
              loading={loading}
              hasDocs={true}
            />
            <p className="text-center text-xs text-tlu-muted">
              StudyBot có thể nhầm. Hãy đối chiếu văn bản gốc hoặc liên hệ Phòng Đào tạo (024.38522201).
            </p>
          </div>
        </footer>
      </div>

      <DocPreviewModal
        isOpen={previewDoc.isOpen}
        onClose={() => setPreviewDoc(prev => ({ ...prev, isOpen: false }))}
        title={previewDoc.title}
        docUrl={previewDoc.url}
      />
    </div>
  );
}
