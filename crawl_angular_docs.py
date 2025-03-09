import asyncio
from urllib.parse import urlparse

from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode, CrawlerMonitor, DisplayMode, RateLimiter
from crawl4ai.async_dispatcher import SemaphoreDispatcher
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator

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
    urls_file = "angular-docs-sitemap/angular-docs-urls.txt"
    batch_size = 5  # Start with a conservative batch size
    
    all_urls = read_urls_from_file(urls_file)
    
    test_size = 20  # Uncomment for testing
    test_urls = all_urls[:test_size]  # Uncomment for testing
    print(f"Found {len(all_urls)} total URLs. Processing {test_size} for testing.")
    
    # Crawl the URLs
    await crawl_batch(test_urls, batch_size=batch_size)  # Uncomment for testing
    # await crawl_angular_docs_batch(all_urls, output_dir, batch_size=batch_size)  # For production

if __name__ == "__main__":
    asyncio.run(main())