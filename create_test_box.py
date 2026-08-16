import cadquery as cq

# Create a simple box
result = cq.Workplane("XY").box(10, 10, 10)

# Export to STEP
cq.exporters.export(result, "sample_parts/test_box.step")
print("Successfully generated sample_parts/test_box.step")
