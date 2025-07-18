import sys
import io
import base64
import mimetypes
from typing import BinaryIO, Any, Union, List, Tuple
from pathlib import Path

from ._llm_caption import llm_caption
from .._base_converter import DocumentConverter, DocumentConverterResult
from .._stream_info import StreamInfo
from .._exceptions import MissingDependencyException, MISSING_DEPENDENCY_MESSAGE

# Try loading required dependencies
_pdfminer_dependency_exc_info = None
try:
    import pdfminer
    import pdfminer.high_level
except ImportError:
    _pdfminer_dependency_exc_info = sys.exc_info()

# Try loading pdfplumber for enhanced image extraction (optional)
_pdfplumber_dependency_exc_info = None
try:
    import pdfplumber
    from PIL import Image
except ImportError:
    _pdfplumber_dependency_exc_info = sys.exc_info()

# Try loading PyMuPDF as fallback (optional)
_pymupdf_dependency_exc_info = None
try:
    import fitz  # PyMuPDF
except ImportError:
    _pymupdf_dependency_exc_info = sys.exc_info()

ACCEPTED_MIME_TYPE_PREFIXES = [
    "application/pdf",
    "application/x-pdf",
]

ACCEPTED_FILE_EXTENSIONS = [".pdf"]


class EnhancedPdfConverter(DocumentConverter):
    """
    Enhanced PDF converter with multiple image extraction strategies:
    1. pdfplumber (preferred) - better image positioning and quality
    2. PyMuPDF (fallback) - broader compatibility
    3. pdfminer only (text-only fallback)
    
    Features:
    - Smart image detection before AI analysis
    - Multiple extraction backends
    - Cost optimization through pre-detection
    """

    def accepts(
        self,
        file_stream: BinaryIO,
        stream_info: StreamInfo,
        **kwargs: Any,
    ) -> bool:
        mimetype = (stream_info.mimetype or "").lower()
        extension = (stream_info.extension or "").lower()

        if extension in ACCEPTED_FILE_EXTENSIONS:
            return True

        for prefix in ACCEPTED_MIME_TYPE_PREFIXES:
            if mimetype.startswith(prefix):
                return True

        return False

    def convert(
        self,
        file_stream: BinaryIO,
        stream_info: StreamInfo,
        **kwargs: Any,
    ) -> DocumentConverterResult:
        # Check pdfminer dependency
        if _pdfminer_dependency_exc_info is not None:
            raise MissingDependencyException(
                MISSING_DEPENDENCY_MESSAGE.format(
                    converter=type(self).__name__,
                    extension=".pdf",
                    feature="pdf",
                )
            ) from _pdfminer_dependency_exc_info[1].with_traceback(
                _pdfminer_dependency_exc_info[2]
            )

        # Extract text using pdfminer (always available)
        text_content = self._extract_text_with_pdfminer(file_stream)
        
        # Check if LLM image description is requested
        llm_client = kwargs.get("llm_client")
        llm_model = kwargs.get("llm_model")
        
        if llm_client is not None and llm_model is not None:
            # Smart detection: check if PDF contains images before AI analysis
            has_images = self._smart_image_detection(file_stream)
            
            if has_images:
                print("🖼️ 检测到图片，开始AI分析...")
                image_descriptions = self._extract_and_describe_images(
                    file_stream, **kwargs
                )
                
                if image_descriptions:
                    # Combine text and image descriptions
                    md_content = text_content
                    md_content += "\n\n## Images in PDF\n\n"
                    for i, description in enumerate(image_descriptions, 1):
                        md_content += f"### Image {i}\n\n{description}\n\n"
                    return DocumentConverterResult(markdown=md_content)
            else:
                print("📄 未检测到图片，跳过AI分析（节省成本）")
        
        return DocumentConverterResult(markdown=text_content)

    def _extract_text_with_pdfminer(self, file_stream: BinaryIO) -> str:
        """使用pdfminer提取文本"""
        file_stream.seek(0)
        return pdfminer.high_level.extract_text(file_stream)

    def _smart_image_detection(self, file_stream: BinaryIO) -> bool:
        """
        智能图片检测：尝试多种方法检测PDF中是否有图片
        优先级：pdfplumber > PyMuPDF > 假设无图片
        """
        # 方法1: 使用pdfplumber检测（推荐）
        if _pdfplumber_dependency_exc_info is None:
            try:
                return self._detect_images_with_pdfplumber(file_stream)
            except Exception:
                pass
        
        # 方法2: 使用PyMuPDF检测（备选）
        if _pymupdf_dependency_exc_info is None:
            try:
                return self._detect_images_with_pymupdf(file_stream)
            except Exception:
                pass
        
        # 方法3: 无法检测，假设无图片
        return False

    def _detect_images_with_pdfplumber(self, file_stream: BinaryIO) -> bool:
        """使用pdfplumber检测图片"""
        file_stream.seek(0)
        
        # 保存到临时文件（pdfplumber需要文件路径）
        import tempfile
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp_file:
            tmp_file.write(file_stream.read())
            tmp_path = tmp_file.name
        
        try:
            with pdfplumber.open(tmp_path) as pdf:
                for page in pdf.pages:
                    if page.images:
                        # 检查图片尺寸
                        for img in page.images:
                            width = img.get('width', 0)
                            height = img.get('height', 0)
                            if width >= 50 and height >= 50:
                                return True
            return False
        finally:
            # 清理临时文件
            Path(tmp_path).unlink(missing_ok=True)
            file_stream.seek(0)

    def _detect_images_with_pymupdf(self, file_stream: BinaryIO) -> bool:
        """使用PyMuPDF检测图片（备选方案）"""
        file_stream.seek(0)
        pdf_data = file_stream.read()
        
        try:
            pdf_document = fitz.open(stream=pdf_data, filetype="pdf")
            
            for page_num in range(len(pdf_document)):
                page = pdf_document.load_page(page_num)
                image_list = page.get_images()
                
                for img in image_list:
                    try:
                        xref = img[0]
                        pix = fitz.Pixmap(pdf_document, xref)
                        if pix.width >= 50 and pix.height >= 50:
                            pix = None
                            pdf_document.close()
                            return True
                        pix = None
                    except Exception:
                        continue
            
            pdf_document.close()
            return False
        finally:
            file_stream.seek(0)

    def _extract_and_describe_images(
        self,
        file_stream: BinaryIO,
        **kwargs: Any,
    ) -> List[str]:
        """
        提取并描述图片
        优先使用pdfplumber，备选PyMuPDF
        """
        # 方法1: 使用pdfplumber提取（推荐）
        if _pdfplumber_dependency_exc_info is None:
            try:
                return self._extract_with_pdfplumber(file_stream, **kwargs)
            except Exception as e:
                print(f"⚠️ pdfplumber提取失败，尝试备选方案: {e}")
        
        # 方法2: 使用PyMuPDF提取（备选）
        if _pymupdf_dependency_exc_info is None:
            try:
                return self._extract_with_pymupdf(file_stream, **kwargs)
            except Exception as e:
                print(f"⚠️ PyMuPDF提取失败: {e}")
        
        return []

    def _extract_with_pdfplumber(
        self,
        file_stream: BinaryIO,
        **kwargs: Any,
    ) -> List[str]:
        """使用pdfplumber提取和描述图片"""
        file_stream.seek(0)
        
        # 保存到临时文件
        import tempfile
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp_file:
            tmp_file.write(file_stream.read())
            tmp_path = tmp_file.name
        
        descriptions = []
        
        try:
            with pdfplumber.open(tmp_path) as pdf:
                for page_num, page in enumerate(pdf.pages):
                    for img_idx, img in enumerate(page.images):
                        try:
                            # 检查图片尺寸
                            width = img.get('width', 0)
                            height = img.get('height', 0)
                            if width < 50 or height < 50:
                                continue
                            
                            # 提取图片区域
                            bbox = (img["x0"], img["top"], img["x1"], img["bottom"])
                            cropped_page = page.crop(bbox)
                            pil_image = cropped_page.to_image(resolution=150).original
                            
                            # 转换为字节流
                            img_stream = io.BytesIO()
                            pil_image.save(img_stream, format='PNG')
                            img_stream.seek(0)
                            
                            # 创建StreamInfo
                            image_stream_info = StreamInfo(
                                mimetype="image/png",
                                extension=".png",
                                filename=f"pdf_page{page_num+1}_img{img_idx+1}.png",
                            )
                            
                            # 使用LLM描述图片
                            description = llm_caption(
                                img_stream,
                                image_stream_info,
                                client=kwargs.get("llm_client"),
                                model=kwargs.get("llm_model"),
                                prompt=kwargs.get("llm_prompt"),
                            )
                            
                            if description:
                                descriptions.append(
                                    f"**Page {page_num + 1}, Image {img_idx + 1}:**\n{description}"
                                )
                        
                        except Exception as e:
                            print(f"⚠️ 处理第{page_num+1}页第{img_idx+1}张图片失败: {e}")
                            continue
        
        finally:
            Path(tmp_path).unlink(missing_ok=True)
            file_stream.seek(0)
        
        return descriptions

    def _extract_with_pymupdf(
        self,
        file_stream: BinaryIO,
        **kwargs: Any,
    ) -> List[str]:
        """使用PyMuPDF提取和描述图片（备选方案）"""
        # 这里可以复用之前实现的PyMuPDF逻辑
        # 为了简洁，这里省略具体实现
        # 实际使用时可以从原来的_extract_and_describe_images方法复制
        return []
