# Angular Docs Sitemap 

The purpose of this Node.js project is to generate a sitemap of the Angular docs using the npm package `sitemap-generator`. The resulting sitemap will be used to systematically fetch and process the Angular documentation such that a RAG system can be built to optimize an LLM for the development of Angular projects. 

## generate-sitemap.js

This file is responsible for instantiating a `SitemapGenerator`, and registering event listeners that will log any errors, ignored URLs, or URLs that are successfully added to the sitemap. 