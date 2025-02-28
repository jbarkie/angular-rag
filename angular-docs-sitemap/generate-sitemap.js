const SitemapGenerator = require('sitemap-generator');

// create generator
const generator = SitemapGenerator('https://angular.dev', {
  stripQuerystring: false
});

// register event listeners
// log all URLs
generator.on('add', (url) => {
    console.log(`Added: ${url}`);
  });
  
  generator.on('ignore', (url) => {
    console.log(`Ignored: ${url}`);
  });
  
  generator.on('error', (error) => {
    console.log(`Error: ${error.url} (${error.code})`);
  });
  
  generator.on('done', () => {
    console.log('Sitemap generation completed!');
  });  

// start the crawler
generator.start();