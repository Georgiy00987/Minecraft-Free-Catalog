import io
import json
import uuid
import zipfile
from dataclasses import dataclass
from typing import Optional


@dataclass
class TexturePackMeta:
    name: str
    description: str
    author: str
    version: tuple[int, int, int] = (1, 0, 0)


class MinecraftTexturePackCreator:
    """
    Асинхронный класс для создания Minecraft Bedrock texture pack в памяти.
    Не создаёт никаких файлов локально — всё хранится в BytesIO.
    """

    FORMAT_VERSION = 2
    MIN_ENGINE_VERSION = [1, 16, 0]

    def _build_manifest(self, meta: TexturePackMeta) -> dict:
        """Создаёт структуру manifest.json для Bedrock ресурспака."""
        return {
            "format_version": self.FORMAT_VERSION,
            "header": {
                "name": meta.name,
                "description": f"{meta.description}\n§7Author: {meta.author}",
                "uuid": str(uuid.uuid4()),
                "version": list(meta.version),
                "min_engine_version": self.MIN_ENGINE_VERSION,
            },
            "modules": [
                {
                    "type": "resources",
                    "uuid": str(uuid.uuid4()),
                    "version": list(meta.version),
                }
            ],
            "metadata": {
                "authors": [meta.author],
            },
        }

    async def create_pack(
        self,
        meta: TexturePackMeta,
        icon_bytes: Optional[bytes] = None,
    ) -> io.BytesIO:
        """
        Создаёт ZIP-архив текстурпака в памяти.

        Args:
            meta: метаданные пака (имя, описание, автор)
            icon_bytes: байты PNG-изображения для иконки (необязательно)

        Returns:
            io.BytesIO — готовый ZIP-архив, позиция сброшена в начало
        """
        buffer = io.BytesIO()

        with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
            # --- manifest.json ---
            manifest = self._build_manifest(meta)
            zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))

            # --- pack_icon.png ---
            if icon_bytes:
                zf.writestr("pack_icon.png", icon_bytes)

        buffer.seek(0)
        return buffer

    @staticmethod
    def get_zip_filename(meta: TexturePackMeta) -> str:
        """Возвращает безопасное имя файла для отправки пользователю."""
        safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in meta.name)
        return f"{safe_name}_texture_pack.mcpack"
