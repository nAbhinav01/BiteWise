Sample nutrition-label images for testing (PHASE 9).

Contents
  *_clean.png      12 synthetic, flat, well-lit labels
  *_photo.jpg      the same 12 labels degraded to look like a phone photo
  ground_truth.csv the correct nutrient values + expected verdict per image

Regenerate:   python generate_sample_images.py
Measure:      python evaluate.py        (writes data/evaluation_report.md)
Test:         python -m pytest -q

These are SYNTHETIC labels with typical values - not photos of real brands.
Add your own REAL photos here and test them manually (see TESTING.md).

Tips for good photos: straight-on, good light, no glare, table fills the frame.
