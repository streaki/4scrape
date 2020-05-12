# 4scrape
A script for scraping images off 4chan threads. Not a *real* scraper, because it uses the API instead of scraping the human-readable site.

Looks for threads in the catalog whose subject or comment text matches the supplied regular expression and downloads media files posted in them. Respects the "1 request per second" rule from 4chan API documentation.

It has two ways of dealing with duplicate media:
- metafiles tracking the last checked post in a given thread
- option to store md5 hashes of media that already have been downloaded - globally, not per thread

Requires the **requests** package to work.

Uses the **getopt** package, which means POSIX-style options don't work like you'd expect them to, e.g. *-mi* doesn't work, *-m -i* does.

Run with the **-h** option (or without necessary parameters) to display a help text.

Designed to run from cron, with recurring threads and generals in mind.
