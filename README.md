structor
========

I had an out-of-copyright book that I wanted to read. I also wanted to make it easy 
for other people to read it. Simple solution: scan each page, use OCR to convert
it to text, then format it as an ebook. Except there were a whole pile of OCR transcription
errors, and Tesseract wasn't very good at detecting and retaining the page structure.

Enter python and openCV. I wrote a script that takes an image and uses computer vision 
magick to determine the page's structure. So far, my script can detect and locate:

* lines of text,
* paragraphs,
* section titles,
* images and their associated captions,
* boilerplate like page numbers, and
* chapter titles.

Ain't it grand?
