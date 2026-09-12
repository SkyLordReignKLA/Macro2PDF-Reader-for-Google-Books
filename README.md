# Macro2PDF Reader


This project addresses a specific challenge a lot of users face - getting Google Books documents on a local device. Many users are unable progress using ACSM keys. I hope this benefits someone the way it benefit me. It requires MacOS and a screen recording process. This code works best for black and white (B&W) books.


The way it starts is simple - you need to use an online reader (this code is designed for Google Books) on full screen mode, recommended one-page layout and Fit-to-Screen Zoom. I was able to achieve working results at a recording rate of 20 pages per minute. I think that it is possible to do 1 page per second.

Instructions for how to record your Macro with Screen Recording:

  Turn through the pages that you want in the PDF. Use Record Selection to record the pages as you want them to     
  appear on PDF. I recommend using a Macro tool like Apple Shortcuts. It can be powerful to program efficiency. This 
  code slows down your screen recording for transcription, so you can easily record at 1 page per second. Don't ever 
  go backwards, because this code only checks the previous page for duplicates.


Now that you have screen-recorded your entire book, you are entirely ready to create a PDF. Before running the script, you need to install a few Python imports: "pip install opencv-python numpy PyMuPDF img2pdf ocrmac"

Enter your .mov filename and path into video_file, and choose a selected path for raw_pdf_path and final_pdf_path raw and final outputs. I recommend check for inconsistencies using these documents.


This code uniquely leverages OpenCV, NumPy, PyMuPDF (fitz), OCR (Native 2 Mac), and img2pdf to transform the screen recording into a PDF. The while loop reads video frames using cv2, tracking stability and filtering out loading spinners using numpy color arrays. Static frames are written and bound into raw PDF with img2pdf. A for loop using fitz renders high-res pixmaps, extracting semantic content with ocrmac. We use it to evaluate similarity with difflib.

A collection of if-statements checks two pages exceeding semantic similarity 80% (a ratio which can be changed) based on the OCR assessment. A tiebreaker automatically discards the page with higher blue-pixel count. This logic specifically benefits from the blue loading wheel to identify duplicates. I found that was often the cause of duplication.


I tested this code on B&W books; however, I believe it will still work on color based on if blue is not the dominant color. This script provides document metrics including the highest similarity score kept in the final PDF. The code produces logs that can be helpful for troubleshooting.

If you encounter a duplicate page, I recommend changing the ratio to a percentage below the highest similarity score. Some books with low word counts have artificially high similarity rates on non-duplicates. If you encounter this, just do the opposite - turn up the rate. If you are really struggling, contact me.


Please let me know how it goes, especially with blue picture books. I would really like to hear your feedback on that one! Thank you!!
