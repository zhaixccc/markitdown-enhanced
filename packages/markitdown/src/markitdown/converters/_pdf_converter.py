import sys
import io
import base64
import mimetypes

from typing import BinaryIO, Any, Union

from ._llm_caption import llm_caption
from .._base_converter import DocumentConverter, DocumentConverterResult
from .._stream_info import StreamInfo
from .._exceptions import MissingDependencyException, MISSING_DEPENDENCY_MESSAGE


# Try loading optional (but in this case, required) dependencies
# Save reporting of any exceptions for later
_dependency_exc_info = None
try:
    import pdfminer
    import pdfminer.high_level
except ImportError:
    # Preserve the error and stack trace for later
    _dependency_exc_info = sys.exc_info()

# Try loading PyMuPDF for image extraction (optional)
_pymupdf_dependency_exc_info = None
try:
    import fitz  # PyMuPDF
except ImportError:
    # Preserve the error and stack trace for later
    _pymupdf_dependency_exc_info = sys.exc_info()


ACCEPTED_MIME_TYPE_PREFIXES = [
    "application/pdf",
    "application/x-pdf",
]

ACCEPTED_FILE_EXTENSIONS = [".pdf"]


class PdfConverter(DocumentConverter):
    """
    Converts PDFs to Markdown. Most style information is ignored, so the results are essentially plain-text.

    If llm_client and llm_model are provided, images in the PDF will be extracted and described using the LLM.
    """

    def accepts(
        self,
        file_stream: BinaryIO,
        stream_info: StreamInfo,
        **kwargs: Any,  # Options to pass to the converter
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
        **kwargs: Any,  # Options to pass to the converter
    ) -> DocumentConverterResult:
        # Check the dependencies
        if _dependency_exc_info is not None:
            raise MissingDependencyException(
                MISSING_DEPENDENCY_MESSAGE.format(
                    converter=type(self).__name__,
                    extension=".pdf",
                    feature="pdf",
                )
            ) from _dependency_exc_info[
                1
            ].with_traceback(  # type: ignore[union-attr]
                _dependency_exc_info[2]
            )

        assert isinstance(file_stream, io.IOBase)  # for mypy

        # Extract text using pdfminer
        text_content = pdfminer.high_level.extract_text(file_stream)

        # Check if LLM image description is requested
        llm_client = kwargs.get("llm_client")
        llm_model = kwargs.get("llm_model")

        if llm_client is not None and llm_model is not None:
            # First, check if PDF contains any images
            has_images = self._check_pdf_has_images(file_stream)

            if has_images:
                # Only extract and describe images if they exist
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

        return DocumentConverterResult(markdown=text_content)

    def _check_pdf_has_images(self, file_stream: BinaryIO) -> bool:
        """
        Check if PDF contains any images without extracting them.

        Returns:
            True if PDF contains images, False otherwise
        """
        # Check if PyMuPDF is available
        if _pymupdf_dependency_exc_info is not None:
            # PyMuPDF not available, assume no images
            return False

        try:
            # Reset file stream position
            file_stream.seek(0)

            # Open PDF with PyMuPDF
            pdf_data = file_stream.read()
            pdf_document = fitz.open(stream=pdf_data, filetype="pdf")

            # Check each page for images
            for page_num in range(len(pdf_document)):
                page = pdf_document.load_page(page_num)
                image_list = page.get_images()

                # Check if there are any images that meet our criteria
                for img in image_list:
                    try:
                        # Get image dimensions
                        xref = img[0]
                        pix = fitz.Pixmap(pdf_document, xref)

                        # Check if image is large enough (not decorative)
                        if pix.width >= 50 and pix.height >= 50:
                            pix = None
                            pdf_document.close()
                            return True

                        pix = None

                    except Exception:
                        # Skip this image if there's an error
                        continue

            pdf_document.close()
            return False

        except Exception:
            # If there's any error, assume no images
            return False
        finally:
            # Reset file stream position
            file_stream.seek(0)

    def _extract_and_describe_images(
        self,
        file_stream: BinaryIO,
        **kwargs: Any,
    ) -> list[str]:
        """
        Extract images from PDF and generate descriptions using LLM.

        Returns:
            List of image descriptions
        """
        # Get LLM client and model from kwargs
        llm_client = kwargs.get("llm_client")
        llm_model = kwargs.get("llm_model")

        if llm_client is None or llm_model is None:
            return []

        # Check if PyMuPDF is available
        if _pymupdf_dependency_exc_info is not None:
            # PyMuPDF not available, skip image extraction
            return []

        descriptions = []

        try:
            # Reset file stream position
            file_stream.seek(0)

            # Open PDF with PyMuPDF
            pdf_data = file_stream.read()
            pdf_document = fitz.open(stream=pdf_data, filetype="pdf")

            # Extract images from each page
            for page_num in range(len(pdf_document)):
                page = pdf_document.load_page(page_num)
                image_list = page.get_images()

                for img_index, img in enumerate(image_list):
                    try:
                        # Get image data
                        xref = img[0]
                        pix = fitz.Pixmap(pdf_document, xref)

                        # Skip if image is too small (likely decorative)
                        if pix.width < 50 or pix.height < 50:
                            pix = None
                            continue

                        # Convert to PNG if not already
                        if pix.n - pix.alpha < 4:  # GRAY or RGB
                            img_data = pix.tobytes("png")
                        else:  # CMYK: convert to RGB first
                            pix1 = fitz.Pixmap(fitz.csRGB, pix)
                            img_data = pix1.tobytes("png")
                            pix1 = None

                        pix = None

                        # Create stream info for the image
                        image_stream = io.BytesIO(img_data)
                        image_stream_info = StreamInfo(
                            mimetype="image/png",
                            extension=".png",
                            filename=f"pdf_image_page{page_num+1}_{img_index+1}.png",
                        )

                        # Generate description using LLM
                        description = llm_caption(
                            image_stream,
                            image_stream_info,
                            client=llm_client,
                            model=llm_model,
                            prompt=kwargs.get("llm_prompt"),
                        )

                        if description:
                            descriptions.append(
                                f"**Page {page_num + 1}, Image {img_index + 1}:**\n{description}"
                            )

                    except Exception as e:
                        # Skip this image if there's an error
                        continue

            pdf_document.close()

        except Exception as e:
            # If there's any error with image extraction, just return empty list
            pass
        finally:
            # Reset file stream position
            file_stream.seek(0)

        return descriptions
