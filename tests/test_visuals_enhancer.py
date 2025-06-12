import os
import sys
import traceback  # Import traceback module for detailed error information
from pathlib import Path

# Add the project root to the Python path to allow importing app modules
sys.path.append(str(Path(__file__).parent.parent))

# Import the enhance_report function from the visuals_enhancer module
from app.utils.visuals_enhancer import enhance_report

def main():
    # Path to the sample markdown file
    sample_md_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'reports', 'outputs', 'CHANGE_TO_REPORT_NAME.md')
    
    # Verify the file exists
    if not os.path.exists(sample_md_path):
        print(f"Error: Sample markdown file not found at {sample_md_path}")
        return
    
    print(f"\nTesting visuals_enhancer with sample file: {sample_md_path}\n")
    print("-" * 80)
    
    # Call the enhance_report function
    try:
        print("Calling enhance_report function...")
        result = enhance_report(sample_md_path)
        print("enhance_report function completed successfully")
        
        # Verify the output files were created
        pdf_path = result.get("pdf_path")
        web_html_path = result.get("web_html_path")
        
        if os.path.exists(pdf_path) and os.path.exists(web_html_path):
            print("\n✅ Test successful! Both PDF and Web HTML files were created.")
            print(f"\nSeverity counts extracted from report:")
            print(f"  - High: {result['severity_counts']['high']}")
            print(f"  - Medium: {result['severity_counts']['medium']}")
            print(f"  - Low: {result['severity_counts']['low']}")
            print(f"\nOutput files: ")
            print(f"  - PDF: {pdf_path}")
            print(f"  - Web HTML: {web_html_path}")
        else:
            print("\n❌ Test failed! One or more output files were not created.")
            if not os.path.exists(pdf_path):
                print(f"  - PDF file not found: {pdf_path}")
            if not os.path.exists(web_html_path):
                print(f"  - Web HTML file not found: {web_html_path}")
    
    except Exception as e:
        print(f"\n❌ Error during test: {e}")
        print("\nDetailed traceback:")
        traceback.print_exc()  # Print the full traceback for better debugging

if __name__ == "__main__":
    main()
