import asyncio
import argparse
import os
import re
from urllib.parse import urlparse

from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode, CrawlerMonitor, DisplayMode, RateLimiter
from crawl4ai.async_dispatcher import SemaphoreDispatcher
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator

# Parse command line arguments
def parse_args():
    parser = argparse.ArgumentParser(
        prog="crawl_angular_docs",
        description="Crawl Angular docs and convert to an LLM-friendly Markdown format to assist in building a RAG system that optimizes for Angular development."
    )
    parser.add_argument("--filename", default="angular-docs-sitemap/angular-docs-urls.txt", help="Path to the file containing URLs to crawl.")
    parser.add_argument("--output_dir", default="angular-docs-data/", help="Path to the output directory to save the Markdown content.")
    args = parser.parse_args()
    return args

# Read URLs of Angular docs given file path 
def read_urls_from_file(file_path):
    with open(file_path, 'r') as file:
        urls = [line.strip() for line in file.readlines() if line.strip()]
    return urls

async def process_result(result, output_dir):
    os.makedirs(output_dir, exist_ok=True)

    crawled_url = result.url
    # Parse the URL to create a more friendly filename structure
    parsed_url = urlparse(crawled_url)
    path = parsed_url.netloc + parsed_url.path
    
    # Create filename from path, replacing special characters
    filename = path.replace('/', '-').replace('.', '-')
    filename = re.sub(r'[^a-zA-Z0-9-_]', '', filename)
    filename = f"{filename}.md"
    filepath = os.path.join(output_dir, filename)

    # Write the markdown content to file
    with open(filepath, 'w', encoding='utf-8') as f:
        # Add URL as reference at the top of the file
        f.write(f"Source: {result.url}\n\n")
        f.write(result.markdown)
    
    print(f"Saved markdown to {filepath}")

    html = result.html
    html_filepath = filepath.replace(".md", ".html")
    with open(html_filepath, 'w', encoding='utf-8') as f:
        f.write(html) 

    print(f"Saved HTML to {filepath}")

# Main crawling function with improved memory handling
async def crawl_batch(urls, output_dir, batch_size=10):
    browser_config = BrowserConfig(
        headless=True,
        verbose=True,
    )

    md_generator = DefaultMarkdownGenerator(
        options={
            "ignore_links": True,       # Remove hyperlinks from final markdown
            "ignore_images": True,      # Remove image references 
            "escape_html": False        # Preserve HTML entities
        }
    )

    # Advanced run configuration
    run_config = CrawlerRunConfig(
        markdown_generator=md_generator,  # Convert final HTML into markdown at the end of each crawl 
        cache_mode=CacheMode.BYPASS,       
        check_robots_txt=True,             # Respect robots.txt rules
        word_count_threshold=10,            # Minimum words to keep a section
        stream=False                         # Get all results at once
    )

    dispatcher = SemaphoreDispatcher(
        max_session_permit=20,          # Maximum concurrent tasks
        rate_limiter=RateLimiter(      
            base_delay=(0.5, 1.0),      # Delay between requests
            max_delay=10.0              # Max allowable delay when rate-limiting errors occur
        ),
        monitor=CrawlerMonitor(        
            max_visible_rows=15,
            display_mode=DisplayMode.DETAILED   # Show individual task status, memory usage, and timing
        )
    )

    async with AsyncWebCrawler(config=browser_config) as crawler:
        results = await crawler.arun_many(
            urls=urls,
            config=run_config,
            dispatcher=dispatcher,
        )

        for result in results:
            if result.success:
                await process_result(result, output_dir)
            else:
                print(f"Error processing {result.url}: {result.error_message}") 

async def main():
    # Configuration
    args = parse_args()
    urls_file = "angular-docs-sitemap/angular-docs-urls.txt" if not args.filename else args.filename
    output_dir = "angular-docs-data" if not args.output_dir else args.output_dir
    batch_size = 5  # Start with a conservative batch size
    
    
    urls = read_urls_from_file(urls_file)
    print(f"Found {len(urls)} total URLs. Processing...")
    
    # Crawl the URLs
    await crawl_batch(urls, output_dir, batch_size=batch_size)  

if __name__ == "__main__":
    asyncio.run(main())