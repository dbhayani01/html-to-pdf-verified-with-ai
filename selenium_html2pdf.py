import argparse
import base64
import os
from pathlib import Path
import time

from groq import Groq
import pymupdf
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

"""
Standalone HTML -> PDF -> PNG -> Groq verification pipeline.

This version uses the Headless Chrome (Selenium) backend to support JavaScript graphs.

Usage:
  python selenium_html2pdf.py sample.html
"""

# Correct model string for the Groq vision endpoint
GROQ_VISION_MODEL = "qwen/qwen3.8-27b"

def html_to_pdf_selenium(html_path: Path, pdf_path: Path) -> None:
    """Convert HTML -> PDF using headless Chrome via Selenium, allowing JS to execute."""
    # 1. Configure Chrome options for a headless environment
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")  # Run without a GUI
    chrome_options.add_argument("--no-sandbox")     # Required for running as root/containers in Linux
    chrome_options.add_argument("--disable-dev-shm-usage")

    # 2. Initialize the Chrome driver automatically
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)

    try:
        # 3. Open the local HTML file (must use absolute path)
        file_url = f"file://{html_path.resolve()}"
        driver.get(file_url)

        # 4. CRITICAL: Wait for JavaScript graphs and animations to render completely
        time.sleep(3)  # Adjust this if your charts take longer to load

        # 5. Print the page to a PDF using Chrome's native print settings
        print_options = {
            "printBackground": True,  # Corrected key parameter for Chromium CDP printing
            "orientation": "portrait",
            "scale": 1.0,
        }
        
        # Base64 encoded PDF string from Chrome
        pdf_data = driver.execute_cdp_cmd("Page.printToPDF", print_options)

        # 6. Save the raw bytes to your target PDF path
        pdf_path.write_bytes(base64.b64decode(pdf_data['data']))

    finally:
        # Clean up and close the browser process
        driver.quit()


def pdf_to_page_images(pdf_path: Path, out_dir: Path, dpi: int = 150) -> list[Path]:
    """Rasterize each PDF page to a PNG."""
    out_dir.mkdir(parents=True, exist_ok=True)
    doc = pymupdf.open(str(pdf_path))
    image_paths = []
    for page_index, page in enumerate(doc):
        pix = page.get_pixmap(dpi=dpi)
        img_path = out_dir / f"page_{page_index + 1}.png"
        pix.save(str(img_path))
        image_paths.append(img_path)
    doc.close()
    return image_paths


def verify_page_with_groq(image_path: Path, prompt: str, client: Groq) -> str:
    """Send one rendered page image to Groq's Qwen vision model with a request timeout."""
    b64 = base64.b64encode(image_path.read_bytes()).decode("utf-8")
    
    completion = client.chat.completions.create(
        model=GROQ_VISION_MODEL,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                ],
            }
        ],
        temperature=0.2,
        max_completion_tokens=1024,
        timeout=45.0,  
    )
    return completion.choices[0].message.content


def run_pipeline(html_path: Path, engine: str, dpi: int, prompt: str) -> None:
    html_path = html_path.resolve()
    if not html_path.is_file():
        raise FileNotFoundError(f"HTML file not found: {html_path}")
    if dpi <= 0:
        raise ValueError("DPI must be greater than zero.")

    work_dir = html_path.parent
    pdf_path = work_dir / f"{html_path.stem}_{engine}.pdf"
    img_dir = work_dir / f"{html_path.stem}_{engine}_pages"

    print(f"[1/3] Converting {html_path.name} -> {pdf_path.name} via {engine} ...")
    html_to_pdf_selenium(html_path, pdf_path)

    print(f"[2/3] Rasterizing pages at {dpi} DPI ...")
    image_paths = pdf_to_page_images(pdf_path, img_dir, dpi=dpi)
    print(f"       {len(image_paths)} page image(s) written to {img_dir}")

    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        print("[3/3] Skipping Groq verification because GROQ_API_KEY is not set.")
        return

    print(f"[3/3] Verifying each page with Groq model ({GROQ_VISION_MODEL}) ...")
    client = Groq(api_key=api_key)
    for img_path in image_paths:
        try:
            verdict = verify_page_with_groq(img_path, prompt, client)
            print(f"\n--- {img_path.name} ---\n{verdict}\n")
        except Exception as e:
            print(f"\n--- {img_path.name} ---\n[Error during verification]: {e}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="HTML -> PDF -> page images -> Groq verification")
    parser.add_argument("html_file", type=Path)
    parser.add_argument("--dpi", type=int, default=150)
    parser.add_argument(
        "--prompt",
        default=(
            "You are verifying a rendered PDF page for layout bugs. Check for: overlapping elements, "
            "text overflow/clipping, broken tables, missing backgrounds/colors, or misaligned grids. "
            "Reply with 'OK' if it looks correct, otherwise describe the specific issue and where it is."
        ),
    )
    args = parser.parse_args()
    
    try:
        run_pipeline(args.html_file, "selenium", args.dpi, args.prompt)
    except (FileNotFoundError, RuntimeError, ValueError) as error:
        parser.error(str(error))
