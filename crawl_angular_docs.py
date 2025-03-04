import asyncio
import os
import json
import re
import argparse
from datetime import datetime
from urllib.parse import urlparse
from bs4 import BeautifulSoup

from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode

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

# Extract content type from URL
def get_content_type(url):
    url_path = url.lower()
    if '/api/' in url_path:
        return "api"
    elif '/guide/' in url_path:
        return "guide"
    elif '/tutorial' in url_path:
        return "tutorial"
    elif '/components/' in url_path:
        return "component"
    elif '/tools/' in url_path:
        return "tools"
    else:
        return "other"

# Process HTML content for RAG
def process_content_for_rag(html, url):
    soup = BeautifulSoup(html, 'html.parser')
    
    # Extract title - try different possible elements
    title = None
    # Try the page title first
    if soup.title:
        title = soup.title.string
    
    # Try h1 elements
    if not title and soup.h1:
        title = soup.h1.get_text(strip=True)
    
    # Fall back to URL-based title if nothing else works
    if not title:
        path_parts = urlparse(url).path.strip('/').split('/')
        if path_parts:
            # Convert path to title case for readability
            title = ' '.join(word.capitalize() for word in path_parts[-1].replace('-', ' ').replace('_', ' ').split())
        else:
            title = "Angular Documentation"
    
    # Clean up the title
    if title:
        # Remove "Angular" prefix if it exists
        title = re.sub(r'^Angular\s+[|-]\s+', '', title)
        title = title.strip()
    
    # Get the document type from URL
    doc_type = get_content_type(url)
    
    # Find the main content
    main_content = None
    for selector in ['main', 'article', '.content', '.doc-content', 'body']:
        main_content = soup.select_one(selector)
        if main_content:
            break
    
    if not main_content:
        main_content = soup.body
    
    # Extract chunks of content 
    chunks = []
    
    # Process by headings to create logical chunks
    current_heading = None
    current_texts = []
    current_code_blocks = []
    
    # Function to store the current chunk and start a new one
    def save_current_chunk():
        if not current_texts and not current_code_blocks:
            return
        
        chunk = {
            "heading": current_heading,
            "text": "\n".join(current_texts) if current_texts else "",
            "code": current_code_blocks.copy() if current_code_blocks else []
        }
        chunks.append(chunk)
    
    if main_content:
        # For each child of the main content
        for element in main_content.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'div', 'pre', 'code', 'ul', 'ol', 'li', 'table']):
            # If it's a heading, save the current chunk and start a new one
            if element.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                save_current_chunk()
                current_heading = element.get_text(strip=True)
                current_texts = []
                current_code_blocks = []
            
            # If it's a code block
            elif element.name in ['pre', 'code']:
                code_text = element.get_text(strip=True)
                if code_text:
                    # Try to detect language
                    language = "typescript"  # Default for Angular docs
                    
                    # Check for language hints in class attributes
                    if element.get('class'):
                        for cls in element.get('class'):
                            if cls.startswith(('language-', 'lang-')):
                                language = cls.split('-', 1)[1]
                                break
                    
                    current_code_blocks.append({
                        "language": language,
                        "content": code_text
                    })
            
            # If it's text content
            elif element.name in ['p', 'li', 'div']:
                text = element.get_text(strip=True)
                if text and element.name != 'div' or (element.name == 'div' and not element.find(['div', 'p'])):
                    current_texts.append(text)
            
            # Handle lists
            elif element.name in ['ul', 'ol']:
                # Extract list items
                list_items = element.find_all('li')
                if list_items:
                    list_type = "• " if element.name == 'ul' else "1. "
                    for i, item in enumerate(list_items):
                        prefix = list_type
                        if element.name == 'ol':
                            prefix = f"{i+1}. "
                        current_texts.append(f"{prefix}{item.get_text(strip=True)}")
            
            # Handle tables
            elif element.name == 'table':
                current_texts.append("Table: " + ' | '.join([th.get_text(strip=True) for th in element.find_all('th')]))
                for row in element.find_all('tr'):
                    if not row.find('th'):  # Skip header row
                        current_texts.append(' | '.join([td.get_text(strip=True) for td in row.find_all('td')]))
        
        # Save the last chunk
        save_current_chunk()
    
    # Extract links to related documentation
    related_links = []
    for link in soup.find_all('a', href=True):
        href = link.get('href')
        # Only consider Angular documentation links
        if href.startswith(('/', 'https://angular.dev')):
            text = link.get_text(strip=True)
            if text:
                full_url = href if href.startswith('http') else 'https://angular.dev' + href
                related_links.append({
                    "text": text,
                    "url": full_url
                })
    
    # Create the result object
    result = {
        "url": url,
        "title": title,
        "doc_type": doc_type,
        "crawl_time": datetime.now().isoformat(),
        "chunks": chunks,
        "related_links": related_links[:10]  # Limit to avoid too many links
    }
    
    return result

# Process a batch of URLs
async def process_url_batch(urls, output_dir, start_index=0):
    os.makedirs(output_dir, exist_ok=True)
    
    # Basic configuration for the crawler
    browser_config = BrowserConfig(
        headless=True,
        verbose=False  # Set to True for more detailed logs
    )
    
    run_config = CrawlerRunConfig(
        cache_mode=CacheMode.ENABLED,
        check_robots_txt=True
    )
    
    async with AsyncWebCrawler(config=browser_config) as crawler:
        for i, url in enumerate(urls):
            global_index = start_index + i
            print(f"Processing {global_index+1}/{start_index+len(urls)} ({i+1}/{len(urls)} in current batch): {url}")
            
            try:
                # Check if file already exists (to support resuming)
                output_file = os.path.join(output_dir, url_to_filename(url))
                if os.path.exists(output_file):
                    print(f"  Skipping: Already processed")
                    continue
                
                # Crawl a single URL
                result = await crawler.arun(url=url, config=run_config)
                
                if not result.success:
                    print(f"  Failed: {result.error_message}")
                    with open(os.path.join(output_dir, "failed_urls.txt"), 'a') as f:
                        f.write(f"{url}\n")
                    continue
                
                # Process the HTML content for RAG
                processed_content = process_content_for_rag(result.html, url)
                
                # Save to JSON file
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(processed_content, f, ensure_ascii=False, indent=2)
                
                print(f"  Success: {len(processed_content['chunks'])} chunks extracted")
                
            except Exception as e:
                print(f"  Error processing {url}: {str(e)}")
                # Log error to file
                with open(os.path.join(output_dir, "errors.log"), 'a') as f:
                    f.write(f"{url}: {str(e)}\n")
                with open(os.path.join(output_dir, "failed_urls.txt"), 'a') as f:
                    f.write(f"{url}\n")

async def main():
    parser = argparse.ArgumentParser(description='Crawl Angular documentation for RAG system')
    parser.add_argument('--urls-file', default="angular-docs-sitemap/angular-docs-urls.txt", help='File containing URLs to crawl')
    parser.add_argument('--output-dir', default="angular-docs-data", help='Directory to store output files')
    parser.add_argument('--batch-size', type=int, default=20, help='Number of URLs to process in each batch')
    parser.add_argument('--test-mode', action='store_true', help='Run only on a small test batch')
    parser.add_argument('--test-size', type=int, default=5, help='Number of URLs to process in test mode')
    parser.add_argument('--resume', action='store_true', help='Resume from previous run by skipping already processed URLs')
    args = parser.parse_args()
    
    # Read all URLs
    all_urls = read_urls_from_file(args.urls_file)
    print(f"Found {len(all_urls)} URLs to process")
    
    if args.test_mode:
        # Process only a small test batch
        test_urls = all_urls[:args.test_size]
        print(f"\nRunning in test mode: Processing {len(test_urls)} URLs...")
        output_dir = os.path.join(args.output_dir, "test_batch")
        await process_url_batch(test_urls, output_dir)
        print("\nTest completed. Examine the results in the output directory.")
    else:
        # Process the full set in batches
        print(f"\nProcessing all URLs in batches of {args.batch_size}...")
        
        # Track progress for resuming
        processed_urls = set()
        if args.resume:
            # Check output directory for already processed files
            if os.path.exists(args.output_dir):
                for file in os.listdir(args.output_dir):
                    if file.endswith('.json'):
                        # Crude way to extract URL from filename
                        parts = file.split('_')
                        if len(parts) >= 2:
                            domain = parts[0]
                            path = '_'.join(parts[1:]).replace('.json', '')
                            url = f"https://{domain}/{path.replace('_', '/')}"
                            processed_urls.add(url)
            
            print(f"Resuming from previous run: {len(processed_urls)} URLs already processed")
        
        batch_size = args.batch_size
        for i in range(0, len(all_urls), batch_size):
            batch_urls = all_urls[i:i+batch_size]
            
            # Filter out already processed URLs if resuming
            if args.resume:
                batch_urls = [url for url in batch_urls if url not in processed_urls]
                if not batch_urls:
                    print(f"Skipping batch {i//batch_size + 1}: All URLs already processed")
                    continue
            
            batch_num = i // batch_size + 1
            total_batches = (len(all_urls) + batch_size - 1) // batch_size
            
            print(f"\nBatch {batch_num}/{total_batches}: Processing {len(batch_urls)}/{batch_size} URLs...")
            await process_url_batch(batch_urls, args.output_dir, start_index=i)
            
            print(f"Batch {batch_num} completed.")
        
        print("\nAll batches processed successfully.")
        
        # Report on any failed URLs
        failed_urls_file = os.path.join(args.output_dir, "failed_urls.txt")
        if os.path.exists(failed_urls_file):
            with open(failed_urls_file, 'r') as f:
                failed_urls = f.read().splitlines()
            
            if failed_urls:
                print(f"\n{len(failed_urls)} URLs failed to process. See {failed_urls_file} for details.")
            else:
                print("\nAll URLs processed successfully!")
        else:
            print("\nAll URLs processed successfully!")

if __name__ == "__main__":
    asyncio.run(main())