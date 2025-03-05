import asyncio
import os
import json
from datetime import datetime
from urllib.parse import urlparse

from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
from crawl4ai.async_dispatcher import SemaphoreDispatcher
from crawl4ai.content_filter_strategy import PruningContentFilter
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator

# Function to read URLs from the file
def read_urls_from_file(file_path):
    with open(file_path, 'r') as file:
        urls = [line.strip() for line in file.readlines() if line.strip()]
    return urls

# Generate a safe filename from URL
def url_to_filename(url):
    parsed = urlparse(url)
    path = parsed.path.strip('/')
    if not path:
        path = 'index'
    safe_path = path.replace('/', '_')
    return f"{parsed.netloc}_{safe_path}.json"

# Determine document type based on URL
def determine_doc_type(url):
    url_path = url.lower()
    if '/api/' in url_path:
        return "api"
    elif '/guide/' in url_path:
        return "guide"
    elif '/tutorial' in url_path:
        return "tutorial"
    elif '/reference/' in url_path:
        return "reference"
    elif '/cli/' in url_path:
        return "cli"
    else:
        return "other"

# The original HTML processing function
def process_html_for_rag(html, url):
    # Extract title (simple approach)
    title_start = html.find("<title>")
    title_end = html.find("</title>")
    if title_start > -1 and title_end > -1:
        title = html[title_start + 7:title_end].strip()
    else:
        # Fallback title from URL
        path_parts = urlparse(url).path.strip('/').split('/')
        title = path_parts[-1].replace('-', ' ').replace('_', ' ').title() if path_parts else "Angular Documentation"
    
    # Determine document type based on URL
    doc_type = determine_doc_type(url)
    
    # Basic content chunking (very simplified)
    chunks = []
    current_heading = None
    current_text = ""
    current_code = []
    
    # Very simple HTML chunking by h1-h6 tags
    for tag_level in range(1, 7):
        heading_tag = f"<h{tag_level}"
        heading_end_tag = f"</h{tag_level}>"
        
        start_pos = 0
        while True:
            # Find the next heading
            heading_start = html.find(heading_tag, start_pos)
            if heading_start == -1:
                break
                
            # If we have accumulated content, save it as a chunk
            if current_text or current_code:
                chunks.append({
                    "heading": current_heading,
                    "text": current_text.strip(),
                    "code": current_code
                })
                current_text = ""
                current_code = []
            
            # Extract the heading text
            content_start = html.find(">", heading_start) + 1
            content_end = html.find(heading_end_tag, content_start)
            if content_start > 0 and content_end > 0:
                current_heading = html[content_start:content_end].strip()
                
                # Basic HTML tag stripping for the heading
                current_heading = current_heading.replace("<strong>", "").replace("</strong>", "")
                current_heading = current_heading.replace("<em>", "").replace("</em>", "")
            
            # Find the content until the next heading
            next_heading_start = html.find(heading_tag, content_end)
            if next_heading_start == -1:
                next_heading_start = len(html)
                
            # Extract content between headings
            content_block = html[content_end + len(heading_end_tag):next_heading_start]
            
            # Very simple content extraction
            in_tag = False
            for char in content_block:
                if char == '<':
                    in_tag = True
                elif char == '>':
                    in_tag = False
                elif not in_tag:
                    current_text += char
            
            # Move to the next position
            start_pos = next_heading_start if next_heading_start < len(html) else len(html)
    
    # Add the final chunk if we have content
    if current_text or current_code:
        chunks.append({
            "heading": current_heading,
            "text": current_text.strip(),
            "code": current_code
        })
    
    # Simple document structure
    return {
        "url": url,
        "title": title,
        "doc_type": doc_type,
        "crawl_time": datetime.now().isoformat(),
        "chunks": chunks,
        "related_links": []
    }

# Process results function
async def process_result(result, output_dir):
    if not result.success:
        print(f"Error crawling {result.url}: {result.error_message}")
        return
    
    try:
        # Process the HTML content
        processed_content = process_html_for_rag(result.html, result.url)
        
        # Save to JSON file
        output_file = os.path.join(output_dir, url_to_filename(result.url))
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(processed_content, f, ensure_ascii=False, indent=2)
        
        print(f"Successfully processed {result.url}")
        
    except Exception as e:
        print(f"Exception while processing {result.url}: {str(e)}")
        # Log the exception
        with open(os.path.join(output_dir, "error_log.txt"), "a") as f:
            f.write(f"{result.url}: {str(e)}\n")

# Main crawling function using a simpler approach
async def crawl_angular_docs_batch(urls, output_dir, batch_size=5):
    os.makedirs(output_dir, exist_ok=True)
    print(f"Starting batch crawl of {len(urls)} URLs...")
    
    # Very basic configuration
    browser_config = BrowserConfig(
        headless=True,
        verbose=False 
    )
    
    run_config = CrawlerRunConfig(
        cache_mode=CacheMode.ENABLED,  # Use cache when available
        check_robots_txt=False        # Skip robots.txt for testing
    )
    
    # Simple semaphore-based dispatcher
    dispatcher = SemaphoreDispatcher(
        max_session_permit=batch_size  # Control concurrent requests
    )
    
    # Create the crawler with browser config
    async with AsyncWebCrawler(config=browser_config) as crawler:
        # Process URLs in smaller batches to better manage memory
        for i in range(0, len(urls), batch_size):
            batch = urls[i:i + batch_size]
            print(f"Processing batch {i//batch_size + 1}/{(len(urls) + batch_size - 1)//batch_size} ({len(batch)} URLs)")
            
            # Use stream=False to get all results at once
            results = await crawler.arun_many(
                urls=batch,
                config=run_config,
                dispatcher=dispatcher,
                stream=False  # Get all results at once
            )
            
            print(f"Got {len(results)} results, now processing batch {i//batch_size + 1}...")
            
            # Process all results sequentially
            for result in results:
                await process_result(result, output_dir)
            
            print(f"Completed batch {i//batch_size + 1}")

# Main execution function
async def main():
    # Configuration
    urls_file = "angular-docs-sitemap/angular-docs-urls.txt"
    output_dir = "angular_docs_rag"
    
    # Read URLs from file
    all_urls = read_urls_from_file(urls_file)
    
    # For testing, use a small subset
    test_size = 20
    test_urls = all_urls[:test_size]
    print(f"Found {len(all_urls)} total URLs. Processing {test_size} for testing.")
    
    # Crawl the test URLs using the simplified approach
    await crawl_angular_docs_batch(test_urls, output_dir, batch_size=5)
    
    print("\nBatch crawling completed. Check the output directory for results.")

if __name__ == "__main__":
    asyncio.run(main())