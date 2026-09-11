import cv2
import numpy
import img2pdf
import os
import shutil
import fitz  # PyMuPDF
import time
from difflib import SequenceMatcher
from ocrmac import ocrmac

def run_phase1_extraction(video_path, new_output, settle_frames=10, threshold=1.0, slow_down=10):
    """Phase 1: Extracts frames from the screen recording and outputs a raw PDF."""
    start_time = time.time()
    temporary_video_directory = "temp_video_pages"
    os.makedirs(temporary_video_directory, exist_ok=True)
    
    cap = cv2.VideoCapture(video_path)
    previous_grayscale = None
    last_saved_page_grayscale = None
    static_frame_count = 0
    page_saved_flag = False
    extracted_video_frames = []
    actual_frame_identifier = 0

    lower_blue = numpy.array([100, 150, 0])
    upper_blue = numpy.array([140, 255, 255])

    print(f"\n--- PHASE 1: VIDEO EXTRACTION ---")
    print(f"Analyzing {video_path}...")

    while cap.isOpened():
        frame_read, frame = cap.read()
        if not frame_read:
            break
            
        for slowdown_cycle in range(slow_down):
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            if previous_grayscale is not None:
                frame_difference = cv2.absdiff(gray, previous_grayscale)
                mean_difference = numpy.mean(frame_difference)
                
                if mean_difference > threshold:
                    static_frame_count = 0
                    page_saved_flag = False
                else:
                    static_frame_count += 1
                    
                if static_frame_count == settle_frames and not page_saved_flag:
                    height, width = gray.shape
                    ymin, ymax = int(height * 0.3), int(height * 0.7)
                    xmin, xmax = int(width * 0.3), int(width * 0.7)
                    center_crop = frame[ymin:ymax, xmin:xmax]
                    
                    hsv_crop = cv2.cvtColor(center_crop, cv2.COLOR_BGR2HSV)
                    blue_mask = cv2.inRange(hsv_crop, lower_blue, upper_blue)
                    blue_pixels = cv2.countNonZero(blue_mask)
                    
                    if blue_pixels < 800:
                        is_new_page = False
                        if last_saved_page_grayscale is None:
                            is_new_page = True
                        else:
                            page_difference = cv2.absdiff(gray, last_saved_page_grayscale)
                            _, page_difference_cap = cv2.threshold(page_difference, 20, 255, cv2.THRESH_BINARY)
                            if cv2.countNonZero(page_difference_cap) > 3000:
                                is_new_page = True
                                
                        if is_new_page:
                            image_path = os.path.join(temporary_video_directory, f"page_{len(extracted_video_frames):04d}.png")
                            cv2.imwrite(image_path, frame)
                            extracted_video_frames.append(image_path)
                            last_saved_page_grayscale = gray
                            page_saved_flag = True
                            print(f"Extracted Page {len(extracted_video_frames)} (Frame {actual_frame_identifier})")
                    else:
                        static_frame_count = 0
            
            previous_grayscale = gray
        actual_frame_identifier += 1
        
    cap.release()
    
    if extracted_video_frames:
        print(f"Binding raw PDF with {len(extracted_video_frames)} pages...")
        with open(new_output, "wb") as file_object:
            file_object.write(img2pdf.convert(extracted_video_frames))
            
    shutil.rmtree(temporary_video_directory)
    elapsed_time = time.time() - start_time
    print(f"Phase 1 complete in {elapsed_time:.2f} seconds. Raw file output to: {new_output}")
    return new_output


def run_phase2_cleaning(input_pdf_path, output_pdf_path):
    """Phase 2: Lexical deduplication, blue-tiebreaker evaluation, rich telemetry, and automatic finalization."""
    start_time = time.time()
    temporary_cleaning_directory = "temp_cleaning"
    os.makedirs(temporary_cleaning_directory, exist_ok=True)
    
    document = fitz.open(input_pdf_path)
    final_clean_pages = []
    
    lower_blue_bound = numpy.array([100, 150, 0])
    upper_blue_bound = numpy.array([140, 255, 255])
    
    previous_page_text = None
    previous_blue_pixels = 0
    
    pipeline_statistics = {
        "total_processed": 0,
        "duplicates_dropped": 0,
        "reverts_performed": 0
    }
    
    surviving_metadata = []
    
    print(f"\n--- PHASE 2: LEXICAL DEDUPLICATION & TELEMETRY ---")
    print(f"Opening {input_pdf_path} for processing...")
    
    for page_number in range(len(document)):
        page = document.load_page(page_number)
        pipeline_statistics["total_processed"] += 1
        
        pixmap_image = page.get_pixmap(dpi=150)
        temporary_file_path = os.path.join(temporary_cleaning_directory, f"page_{page_number:04d}.png")
        pixmap_image.save(temporary_file_path)
        
        image_array = numpy.frombuffer(pixmap_image.tobytes("png"), numpy.uint8)
        image_decoded = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
        
        conversion_matrix = cv2.cvtColor(image_decoded, cv2.COLOR_BGR2HSV)
        blue_mask = cv2.inRange(conversion_matrix, lower_blue_bound, upper_blue_bound)
        blue_pixel_count = cv2.countNonZero(blue_mask)
        
        annotations = ocrmac.OCR(temporary_file_path).recognize()
        current_text = " ".join([result[0] for result in annotations]) if annotations else ""
        
        is_duplicate = False
        lexical_similarity = 0.0
        
        if previous_page_text is not None:
            lexical_similarity = SequenceMatcher(None, previous_page_text, current_text).ratio()
            if lexical_similarity > 0.80:
                is_duplicate = True
                
        print(f"Page {page_number+1:03d} | Similarity: {lexical_similarity:^7.2%} | Blue Pixels: {blue_pixel_count:04d}")
        
        if is_duplicate:
            if blue_pixel_count > previous_blue_pixels:
                print(f" ↳ Purging current page duplicate. Relative Blue Pixels: {blue_pixel_count} > {previous_blue_pixels}.")
                os.remove(temporary_file_path)
                pipeline_statistics["duplicates_dropped"] += 1
                continue
            elif previous_blue_pixels > blue_pixel_count:
                print(f" ↳ Purging previous page. Relative Blue Pixels: {previous_blue_pixels} > {blue_pixel_count}.")
                if final_clean_pages:
                    old_image = final_clean_pages.pop()
                    if os.path.exists(old_image):
                        os.remove(old_image)
                    if surviving_metadata:
                        surviving_metadata.pop()
                final_clean_pages.append(temporary_file_path)
                surviving_metadata.append((page_number + 1, temporary_file_path, blue_pixel_count, current_text))
                previous_page_text = current_text
                previous_blue_pixels = blue_pixel_count
                pipeline_statistics["reverts_performed"] += 1
            else:
                os.remove(temporary_file_path)
                pipeline_statistics["duplicates_dropped"] += 1
                continue
        else:
            final_clean_pages.append(temporary_file_path)
            surviving_metadata.append((page_number + 1, temporary_file_path, blue_pixel_count, current_text))
            previous_page_text = current_text
            previous_blue_pixels = blue_pixel_count

    document.close()
    
    # Extended Statistical analysis on surviving pages
    maximum_blue_page = None
    highest_blue_value = -1
    maximum_similarity_pair = (None, None, 0.0)
    total_blue_pixels = 0
    total_similarity = 0.0
    similarity_comparisons = 0
    
    for index, (saved_page_number, saved_path, saved_blue_count, saved_text) in enumerate(surviving_metadata):
        total_blue_pixels += saved_blue_count
        if saved_blue_count > highest_blue_value:
            highest_blue_value = saved_blue_count
            maximum_blue_page = saved_page_number
            
        if index > 0:
            previous_text = surviving_metadata[index-1][3]
            current_similarity = SequenceMatcher(None, previous_text, saved_text).ratio()
            total_similarity += current_similarity
            similarity_comparisons += 1
            if current_similarity > maximum_similarity_pair[2]:
                maximum_similarity_pair = (surviving_metadata[index-1][0], saved_page_number, current_similarity)

    # Calculate final averages and execution time
    average_blue_pixels = total_blue_pixels / len(final_clean_pages) if final_clean_pages else 0
    average_lexical_similarity = total_similarity / similarity_comparisons if similarity_comparisons > 0 else 0
    retention_rate = (len(final_clean_pages) / pipeline_statistics['total_processed']) * 100 if pipeline_statistics['total_processed'] > 0 else 0
    elapsed_time = time.time() - start_time

    print("\n" + "="*50)
    print("PIPELINE: FINAL SURVIVING STATISTICS")
    print("="*50)
    print(f"Total Processing Time:       {elapsed_time:.2f} seconds")
    print(f"Original Pages Scanned:      {pipeline_statistics['total_processed']}")
    print(f"Final Clean Pages:           {len(final_clean_pages)}")
    print(f"Total Purged/Reverted:       {pipeline_statistics['duplicates_dropped'] + pipeline_statistics['reverts_performed']}")
    print(f"Document Retention Rate:     {retention_rate:.1f}%")
    print("-" * 50)
    print(f"Highest Blue Remaining:      Page {maximum_blue_page} ({highest_blue_value} pixels)")
    print(f"Average Blue Per Page:       {average_blue_pixels:.1f} pixels")
    print(f"Highest Similarity Found:    Pages {maximum_similarity_pair[0]} & {maximum_similarity_pair[1]} ({maximum_similarity_pair[2]:.2%})")
    print(f"Average Doc Similarity:      {average_lexical_similarity:.2%}")
    print("="*50)

    # Automatic finalization & cleanup
    print(f"\nBinding final pristine document automatically...")
    with open(output_pdf_path, "wb") as file_object:
        file_object.write(img2pdf.convert(final_clean_pages))
        

    print(f"Success! Final clean book saved to: {output_pdf_path}")
    shutil.rmtree(temporary_cleaning_directory)

# ==========================================
# EXECUTION WORKFLOW
# ==========================================
video_file = "screen_recording.mov" #Insert your .mov screen recording file and path here
raw_pdf_path = "output_RAW.pdf" #Create a path for the RAW data so you can analyze it
final_pdf_path = "output.FINAL" #I recommend 

# Step 1: Execute extraction to generate the raw file
run_phase1_extraction(video_file, raw_pdf_path)

# Step 2: Execute cleaning, telemetry, and automatic finalization
run_phase2_cleaning(raw_pdf_path, final_pdf_path)