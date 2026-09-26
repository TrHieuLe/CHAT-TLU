from pathlib import Path
import shutil
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

    def find_file(self, path: Path | str) -> Path | None:
        """
        Tìm kiếm file trong upload_dir (Backend/data) và các thư mục con:
        1. Khớp chính xác tên file hoặc đường dẫn.
        2. Khớp theo stem (tên không đuôi).
        3. Khớp không phân biệt hoa thường hoặc khoảng trắng.
        """
        query_str = str(path).strip()
        if not query_str:
            return None

        # 1. Thử đường dẫn trực tiếp
        direct = self.upload_dir / query_str
        if direct.is_file():
            return direct

        # 2. Thử tìm kiếm trong base_dir (data/storage)
        storage_direct = self.base_dir / query_str
        if storage_direct.is_file():
            return storage_direct

        query_clean = query_str.lower().replace(" ", "").replace("_", "").replace("-", "")
        query_stem = Path(query_str).stem.lower().replace(" ", "").replace("_", "").replace("-", "")

        # 3. Quét đệ quy trong thư mục data/
        for candidate in self.upload_dir.rglob("*"):
            if not candidate.is_file():
                continue
            cand_name = candidate.name.lower().replace(" ", "").replace("_", "").replace("-", "")
            cand_stem = candidate.stem.lower().replace(" ", "").replace("_", "").replace("-", "")

            # Khớp tên đầy đủ
            if cand_name == query_clean:
                return candidate

            # Khớp tên gốc (bỏ đuôi)
            if cand_stem == query_stem:
                return candidate

            # Khớp một phần nếu query đủ dài (> 6 ký tự)
            if len(query_stem) >= 6 and (query_stem in cand_stem or cand_stem in query_stem):
                return candidate

        return None

    def download_v2(self, path: Path | str):
        target = self.find_file(path)
        if not target or not target.is_file():
            return None
        try:
            return open(target, 'rb')
        except Exception:
            return None

    def delete_v2(self, path: Path | str) -> bool:
        target = self.find_file(path)
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