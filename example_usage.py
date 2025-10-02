#!/usr/bin/env python3
"""
Example usage of text area detection functions.
"""

from image_processor import (
    detect_text_areas, 
    detect_text_areas_advanced, 
    visualize_text_areas,
    process_image_and_extract_text
)

def example_usage():
    """Example of how to use the text area detection functions."""
    
    image_path = "uploads/hoa_don.jpg"
    
    print("=== Text Area Detection Example ===\n")
    
    # 2. Advanced detection with morphological operations
    print("\n2. Advanced morphological detection:")
    areas_advanced = detect_text_areas_advanced(image_path, method="morphology")
    print(f"   Found {len(areas_advanced)} text areas")
    
    # 3. Visualize the results
    print("\n3. Saving visualization:")
    visualize_text_areas(image_path, areas_advanced, "uploads/result_visualization.jpg")
    print("   Saved to: uploads/result_visualization.jpg")
    
    # 4. Extract text from detected areas (optional)
    print("\n4. Extracting text from the entire image:")
    extracted_text = process_image_and_extract_text(image_path)
    print(f"   Extracted text preview: {extracted_text[:100]}...")
    
    print("\n=== Example completed ===")

if __name__ == "__main__":
    example_usage()