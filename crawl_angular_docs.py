import asyncio
import argparse

from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode, CrawlerMonitor, DisplayMode, RateLimiter
from crawl4ai.async_dispatcher import SemaphoreDispatcher
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator

def parse_args():
    parser = argparse.ArgumentParser(
        prog="crawl_angular_docs",
        description="Crawl Angular docs and convert to an LLM-friendly Markdown format to assist in building a RAG system that optimizes for Angular development."
    )
    parser.add_argument('--filename', help="Path to the file containing URLs to crawl.")
    args = parser.parse_args()
    return args

# Read URLs of Angular docs given file path 
def read_urls_from_file(file_path):
    with open(file_path, 'r') as file:
        urls = [line.strip() for line in file.readlines() if line.strip()]
    return urls

async def process_result(result):
    print(f"Markdown for {result.url}:\n", result.markdown[:500])

# Main crawling function with improved memory handling
async def crawl_batch(urls, batch_size=10):
    browser_config = BrowserConfig(
        headless=True,
        verbose=True,
    )

    md_generator = DefaultMarkdownGenerator(
        options={
            "ignore_links": True,
            "ignore_images": True,
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
                await process_result(result)
            else:
                print(f"Error processing {result.url}: {result.error_message}") 

async def main():
    # Configuration
    args = parse_args()
    urls_file = "angular-docs-sitemap/angular-docs-urls.txt" if not args.filename else args.filename
    batch_size = 5  # Start with a conservative batch size
    
    
    urls = read_urls_from_file(urls_file)
    print(f"Found {len(urls)} total URLs. Processing...")
    
    # Crawl the URLs
    await crawl_batch(urls, batch_size=batch_size)  

if __name__ == "__main__":
    asyncio.run(main())