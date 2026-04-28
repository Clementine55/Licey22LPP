import os
import uuid
import httpx
import jwt
import pypdf
import logging
import asyncio
import aiofiles

from dotenv import load_dotenv

logger = logging.getLogger("PrintPortal")
load_dotenv()

ONLYOFFICE_URL = os.getenv("ONLYOFFICE_URL")
ONLYOFFICE_JWT_SECRET = os.getenv("ONLYOFFICE_JWT_SECRET")

if not ONLYOFFICE_URL or not ONLYOFFICE_JWT_SECRET:
    logger.error("ВНИМАНИЕ: Не заданы настройки OnlyOffice в файле .env!")

class PDFService:
    @staticmethod
    async def extract_pages(input_pdf: str, pages_str: str, output_pdf: str) -> str:
        def _extract():
            if not pages_str or pages_str.lower() in ["all", "все", ""]:
                return input_pdf
                
            try:
                reader = pypdf.PdfReader(input_pdf)
                writer = pypdf.PdfWriter()
                total_pages = len(reader.pages)
                
                pages_to_keep = set()
                for part in pages_str.replace(" ", "").split(","):
                    if "-" in part:
                        try:
                            start, end = map(int, part.split("-"))
                            pages_to_keep.update(range(start - 1, end))
                        except ValueError: pass
                    elif part.isdigit():
                        pages_to_keep.add(int(part) - 1)
                        
                valid_pages = sorted([p for p in pages_to_keep if 0 <= p < total_pages])
                if not valid_pages: return input_pdf
                    
                for p in valid_pages: writer.add_page(reader.pages[p])
                with open(output_pdf, "wb") as f: writer.write(f)
                return output_pdf
            except Exception as e:
                logger.error(f"Ошибка при обрезке PDF: {e}")
                return input_pdf
        # Выполняем тяжелую нарезку PDF в фоновом потоке
        return await asyncio.to_thread(_extract)

class OnlyOfficeService:
    @staticmethod
    async def convert(download_url: str, file_name: str, orientation: str, margins: str, scale: str, paper_size: str, output_dir: str, retry=False) -> str:
        ext = os.path.splitext(file_name)[1].lower().strip('.')
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            if ext in ['pdf', 'jpg', 'jpeg', 'png', 'webp']:
                save_path = os.path.join(output_dir, f"{uuid.uuid4().hex}.{ext}")
                resp = await client.get(download_url)
                async with aiofiles.open(save_path, 'wb') as f: 
                    await f.write(resp.content)
                return save_path

            payload = {
                "async": False, "filetype": ext, "outputtype": "pdf",
                "key": uuid.uuid4().hex[:20], "title": f"converted_{uuid.uuid4().hex[:5]}.pdf",
                "url": download_url
            }

            if ext in ['xls', 'xlsx', 'ods', 'csv'] and not retry:
                layout = {"orientation": "landscape" if orientation == "landscape" else "portrait"}
                
                margin_presets = {
                    "none": {"top": "0mm", "bottom": "0mm", "left": "0mm", "right": "0mm"},
                    "narrow": {"top": "19.1mm", "bottom": "19.1mm", "left": "6.4mm", "right": "6.4mm"},
                    "normal": {"top": "19.1mm", "bottom": "19.1mm", "left": "17.8mm", "right": "17.8mm"},
                    "wide": {"top": "25.4mm", "bottom": "25.4mm", "left": "25.4mm", "right": "25.4mm"}
                }
                layout["margins"] = margin_presets.get(margins, margin_presets["normal"])

                paper_presets = {
                    "a4": {"width": "210mm", "height": "297mm"},
                    "a3": {"width": "297mm", "height": "420mm"},
                    "letter": {"width": "215.9mm", "height": "279.4mm"}
                }
                if paper_size in paper_presets:
                    layout["pageSize"] = paper_presets[paper_size]

                if scale == "fit":
                    layout["fitToWidth"] = 1
                    layout["fitToHeight"] = 1
                elif scale.isdigit():
                    layout["scale"] = int(scale)

                payload["spreadsheetLayout"] = layout

            token = jwt.encode(payload, ONLYOFFICE_JWT_SECRET, algorithm="HS256")
            payload["token"] = token.decode('utf-8') if isinstance(token, bytes) else token

            headers = {
                "Authorization": f"Bearer {payload['token']}", 
                "Content-Type": "application/json",
                "Accept": "application/json"
            }
            
            resp = await client.post(f"{ONLYOFFICE_URL}/ConvertService.ashx", json=payload, headers=headers)
            
            try:
                data = resp.json()
            except Exception:
                raise Exception("Неверный ответ от сервера конвертации OnlyOffice")

            if data.get("error") == -3 and not retry:
                return await OnlyOfficeService.convert(download_url, file_name, orientation, "default", "100", paper_size, output_dir, retry=True)

            if "error" in data:
                raise Exception(f"Ошибка конвертации OnlyOffice (код {data['error']})")

            pdf_resp = await client.get(data.get("fileUrl"))
            save_path = os.path.join(output_dir, f"{uuid.uuid4().hex}.pdf")
            async with aiofiles.open(save_path, 'wb') as f: 
                await f.write(pdf_resp.content)
            return save_path

async def cleanup_temp_files(*file_paths):
    for path in file_paths:
        try: 
            if os.path.exists(path): 
                await asyncio.to_thread(os.remove, path)
        except Exception: pass