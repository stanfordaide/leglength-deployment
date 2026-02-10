#!/bin/bash

# Define folders
BEFORE_FOLDER="/dataNAS/people/arogya/projects/mercure-pediatric-leglength/output-n361-old"
AFTER_FOLDER="/dataNAS/people/arogya/projects/mercure-pediatric-leglength/output-ensemble-chosen"
OUTPUT_FOLDER="/dataNAS/people/arogya/projects/mercure-pediatric-leglength/david-reversal"

# Create output folder if it doesn't exist
mkdir -p "$OUTPUT_FOLDER"

# List of IDs
IDS=(
    "AY649da02-AY8c9896c"
    "AY649e69b-AY8c905d0"
    "AY64a3543-AY8c8cd3f"
    "AY64a3a57-AY8c943a7"
    "AY8c8c5fa-AY8c8c965"
    "AY8c8cc71-AY8c916f1"
    "AY8c8d142-AY8c8d3c6"
    "AY8c8ec1b-AY8c8effe"
    "AY8c90ece-AY8c97f7c"
    "AY8c941b4-AY8c94491"
    "AY8c98d1b-AY8c98f98"
)

# Copy files for each ID
for ID in "${IDS[@]}"; do
    echo "Processing $ID..."
    
    # Create subfolder for this ID
    ID_FOLDER="$OUTPUT_FOLDER/$ID"
    mkdir -p "$ID_FOLDER"
    
    # Copy QA table images
    if [ -f "$BEFORE_FOLDER/${ID}_qa_table_output.jpg" ]; then
        cp "$BEFORE_FOLDER/${ID}_qa_table_output.jpg" "$ID_FOLDER/${ID}_qa_table_BEFORE.jpg"
        echo "  ✓ Copied BEFORE qa_table"
    else
        echo "  ✗ Missing BEFORE qa_table"
    fi
    
    if [ -f "$AFTER_FOLDER/${ID}_qa_table_output.jpg" ]; then
        cp "$AFTER_FOLDER/${ID}_qa_table_output.jpg" "$ID_FOLDER/${ID}_qa_table_AFTER.jpg"
        echo "  ✓ Copied AFTER qa_table"
    else
        echo "  ✗ Missing AFTER qa_table"
    fi
    
    # Copy debug QA images
    if [ -f "$BEFORE_FOLDER/${ID}_debug_qa_image.png" ]; then
        cp "$BEFORE_FOLDER/${ID}_debug_qa_image.png" "$ID_FOLDER/${ID}_debug_qa_BEFORE.png"
        echo "  ✓ Copied BEFORE debug_qa"
    else
        echo "  ✗ Missing BEFORE debug_qa"
    fi
    
    if [ -f "$AFTER_FOLDER/${ID}_debug_qa_image.png" ]; then
        cp "$AFTER_FOLDER/${ID}_debug_qa_image.png" "$ID_FOLDER/${ID}_debug_qa_AFTER.png"
        echo "  ✓ Copied AFTER debug_qa"
    else
        echo "  ✗ Missing AFTER debug_qa"
    fi
    
    # Also copy the full QA output DICOM if available
    if [ -f "$BEFORE_FOLDER/${ID}_qa_output.dcm" ]; then
        cp "$BEFORE_FOLDER/${ID}_qa_output.dcm" "$ID_FOLDER/${ID}_qa_output_BEFORE.dcm"
        echo "  ✓ Copied BEFORE qa_output.dcm"
    fi
    
    if [ -f "$AFTER_FOLDER/${ID}_qa_output.dcm" ]; then
        cp "$AFTER_FOLDER/${ID}_qa_output.dcm" "$ID_FOLDER/${ID}_qa_output_AFTER.dcm"
        echo "  ✓ Copied AFTER qa_output.dcm"
    fi
    
    echo ""
done

echo "✅ Done! Files copied to: $OUTPUT_FOLDER"
echo ""
echo "Structure:"
echo "  $OUTPUT_FOLDER/"
echo "    ├── {ID}/"
echo "    │   ├── {ID}_qa_table_BEFORE.jpg"
echo "    │   ├── {ID}_qa_table_AFTER.jpg"
echo "    │   ├── {ID}_debug_qa_BEFORE.png"
echo "    │   └── {ID}_debug_qa_AFTER.png"
