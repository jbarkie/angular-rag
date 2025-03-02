const fs = require('fs');
const { DOMParser } = require('xmldom');

// Read the sitemap file
const sitemap = fs.readFileSync('sitemap.xml', 'utf8');
const parser = new DOMParser();
const xmlDoc = parser.parseFromString(sitemap, 'text/xml');

// Extract all URLs
const urlNodes = xmlDoc.getElementsByTagName('loc');
const urls = [];
for (let i = 0; i < urlNodes.length; i++) {
  urls.push(urlNodes[i].textContent);
}

// Write to a file
fs.writeFileSync('angular-docs-urls.txt', urls.join('\n'));
console.log(`Extracted ${urls.length} URLs from the sitemap`);