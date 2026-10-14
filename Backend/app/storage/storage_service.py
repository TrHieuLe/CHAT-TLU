from pathlib import Path
import shutil
import unicodedata
from typing import BinaryIO

from fastapi import UploadFile


class LocalStorageService:
    def __init__(self, base_dir: str = "data/storage"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.upload_dir = Path(__file__).resolve().parents[2] / "data"

    def upload(self, path: str, file: str) -> str:
        src = Path(file)
        if not src.exists():
            raise FileNotFoundError(f"File không tồn tại: {file}")

        dest_dir = Path(path)
        if not dest_dir.is_absolute():
            dest_dir = self.base_dir / dest_dir

        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / src.name
        shutil.copy2(src, dest)
        return str(dest)

    def _resolve_source(self, path: str) -> Path:
        """
        Ưu tiên file local thật trước.
        Nếu không có thì mới fallback sang storage base_dir.
        """
        p = Path(path)

        if p.is_absolute() and p.exists():
            return p

        if p.exists():
            return p.resolve()

        storage_p = self.base_dir / p
        if storage_p.exists():
            return storage_p.resolve()

        raise FileNotFoundError(f"File không tồn tại trong storage: {storage_p}")

    def download(self, path: str, local_path: str | None = None):
        src = self._resolve_source(path)

        if local_path:
            dest = Path(local_path)
            if dest.exists() and dest.is_dir():
                dest = dest / src.name
            elif str(local_path).endswith("/") or (not dest.suffix and not dest.exists()):
                dest.mkdir(parents=True, exist_ok=True)
                dest = dest / src.name

            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
            return open(dest, "rb")

        return open(src, "rb")

    def exists(self, name: str) -> bool:
        try:
            self._resolve_source(name)
            return True
        except FileNotFoundError:
            return False

    def path(self, name: str) -> str:
        return str(self._resolve_source(name))

    def upload_v2(self, path: Path | str, file: UploadFile) -> Path | None:
        full_path = self.upload_dir / path
        directory = full_path.parent
        directory.mkdir(parents=True, exist_ok=True)

        try:
            with open(full_path, "wb") as f:
                shutil.copyfileobj(file.file, f)
            return full_path
        except Exception as e:
            return None
        finally:
            file.file.close()

    @staticmethod
    def _normalize_name(name: str) -> str:
        name = unicodedata.normalize("NFC", name).lower()
        return name.replace(" ", "").replace("_", "").replace("-", "")

    @staticmethod
    def _inside(path: Path, root: Path) -> Path | None:
        """Trả về path đã resolve nếu nó là file nằm trong root (chặn ../ và đường dẫn tuyệt đối)."""
        try:
            resolved = path.resolve()
            if resolved.is_file() and resolved.is_relative_to(root.resolve()):
                return resolved
        except (OSError, ValueError):
            pass
        return None

    def find_file(self, path: Path | str, fuzzy: bool = True) -> Path | None:
        """
        Tìm kiếm file trong upload_dir (Backend/data) và các thư mục con (bỏ qua images/):
        1. Đường dẫn trực tiếp (chỉ nhận nếu nằm trong upload_dir / base_dir).
        2. Khớp tên đầy đủ, rồi khớp stem (không phân biệt hoa thường, khoảng trắng, NFC/NFD).
        3. Nếu fuzzy: khớp một phần, chọn ứng viên có độ dài stem gần với query nhất.
        """
        query_str = unicodedata.normalize("NFC", str(path).strip())
        if not query_str:
            return None

        for root in (self.upload_dir, self.base_dir):
            direct = self._inside(root / query_str, root)
            if direct:
                return direct

        query_name = self._normalize_name(Path(query_str).name)
        query_stem = self._normalize_name(Path(query_str).stem)

        stem_match: Path | None = None
        fuzzy_match: Path | None = None
        fuzzy_gap: int | None = None

        for candidate in self.upload_dir.rglob("*"):
            if not candidate.is_file():
                continue
            rel_parts = candidate.relative_to(self.upload_dir).parts
            if "images" in rel_parts:
                continue
            cand_name = self._normalize_name(candidate.name)
            cand_stem = self._normalize_name(candidate.stem)

            if cand_name == query_name:
                return candidate

            if stem_match is None and cand_stem == query_stem:
                stem_match = candidate
                continue

            if (
                fuzzy
                and len(query_stem) >= 6
                and len(cand_stem) >= 6
                and (query_stem in cand_stem or cand_stem in query_stem)
            ):
                gap = abs(len(cand_stem) - len(query_stem))
                if fuzzy_gap is None or gap < fuzzy_gap:
                    fuzzy_match, fuzzy_gap = candidate, gap

        return stem_match or fuzzy_match

    def download_v2(self, path: Path | str):
        target = self.find_file(path)
        if not target or not target.is_file():
            return None
        try:
            return open(target, 'rb')
        except Exception:
            return None

    def delete_v2(self, path: Path | str) -> bool:
        # Không dùng khớp mờ khi xóa để tránh xóa nhầm file khác
        target = self.find_file(path, fuzzy=False)
        if target and target.is_file():
            try:
                target.unlink()
                return True
            except Exception:
                pass
        return False


_storage = LocalStorageService()


def get_storage() -> LocalStorageService:
    return _storage