# PPT Design System - Usage Guide

## Overview

The NeuraDeck PPT generation system has been refactored to use a **consulting-grade design system** that ensures consistent, professional slides with proper alignment, spacing, typography, and overflow protection.

## Architecture

### Core Components

1. **`design_system.py`** - Design tokens, grid system, typography, validation
2. **`theme_config.json`** - Theme configuration (colors, fonts, spacing)
3. **`ppt_builder_v2.py`** - Refactored builder using design system
4. **`ppt_builder.py`** - Legacy builder (maintained for compatibility)

### Design System Features

- ✅ **Grid System**: 12-column grid for consistent alignment
- ✅ **Typography Scale**: H1-H4, body sizes, consistent line heights
- ✅ **Spacing Scale**: 4pt base unit (4, 8, 12, 16, 24, 32, 48pt)
- ✅ **Text Fitting**: Auto-reduce font size, wrap text, prevent overflow
- ✅ **Validation**: WCAG contrast checks, bounds validation, overflow detection
- ✅ **Theme Tokens**: Centralized colors, fonts, spacing

## How to Use

### Basic Usage (Backward Compatible)

```python
from app.ppt_builder import build_ppt

# Works exactly as before
output_path = build_ppt(
    outline=outline_data,
    chart_paths=chart_paths,
    output_path=Path("output.pptx"),
    user_prompt="Tesla Research",
    template_id="builtin_1",
    brand_color="#2563eb"
)
```

### Using V2 Builder (With Validation)

```python
from app.ppt_builder_v2 import build_ppt

# Returns (path, formatting_report)
output_path, report = build_ppt(
    outline=outline_data,
    chart_paths=chart_paths,
    output_path=Path("output.pptx"),
    user_prompt="Tesla Research",
    template_id="builtin_1",
    brand_color="#2563eb",
    validate=True  # Enable validation
)

# Check formatting quality
if report and report.has_errors:
    print("⚠️ Formatting errors detected:")
    print(report.summary())
```

## Changing Themes

### Method 1: Edit `theme_config.json`

Edit `backend/app/theme_config.json` to modify colors, fonts, or add new themes:

```json
{
  "templates": {
    "my_custom_theme": {
      "name": "My Custom Theme",
      "colors": {
        "bg": "#ffffff",
        "bg_mid": "#f0f0f0",
        "accent": "#0066cc",
        "text_primary": "#000000",
        "text_secondary": "#333333"
      },
      "fonts": {
        "title": "Arial",
        "body": "Arial"
      }
    }
  }
}
```

### Method 2: Programmatic Override

```python
from app.design_system import ColorPalette, FontConfig
from pptx.dml.color import RGBColor

# Create custom color palette
custom_colors = ColorPalette(
    bg=RGBColor(255, 255, 255),
    bg_mid=RGBColor(240, 240, 240),
    accent=RGBColor(0, 102, 204),
    text_primary=RGBColor(0, 0, 0),
    text_secondary=RGBColor(51, 51, 51)
)
```

## Adding a New Slide Type

### Step 1: Create Component Class

```python
from app.design_system import SlideComponent, LayoutBuilder, TypographyScale, ColorPalette, FontConfig

class MyCustomSlide(SlideComponent):
    """Custom slide component."""
    
    def add(self, prs: Presentation, data: str) -> List[ValidationResult]:
        """Add custom slide."""
        slide = prs.slides.add_slide(prs.slide_layouts[6])
        
        # Use layout builder for positioning
        content_area = self.layout.content_area(start_row=1.0, height=5.0)
        
        # Use typography scale
        title_size = self.typography.H2
        
        # Use colors
        slide.background.fill.solid()
        slide.background.fill.fore_color.rgb = self.colors.bg
        
        # Use fonts
        text_box = slide.shapes.add_textbox(
            Inches(content_area.x), Inches(content_area.y),
            Inches(content_area.width), Inches(content_area.height)
        )
        p = text_box.text_frame.paragraphs[0]
        p.text = data
        p.font.name = self.fonts.body_font
        p.font.size = Pt(self.typography.BODY)
        p.font.color.rgb = self.colors.text_primary
        
        # Validate
        results = []
        results.append(self.validator.validate_bounds(content_area))
        results.append(self.validator.validate_contrast(
            self.colors.text_primary,
            self.colors.bg
        ))
        
        return results
```

### Step 2: Use in Builder

```python
# In build_ppt function
custom_component = MyCustomSlide(layout_builder, typography, colors, fonts)
results = custom_component.add(prs, "Custom data")
all_results.extend(results)
```

## Validation System

### What Gets Validated

1. **Bounds Checking**: Elements within slide dimensions
2. **Margin Compliance**: Elements within safe margins
3. **Contrast**: WCAG AA compliance (4.5:1 for normal text, 3:0 for large)
4. **Text Overflow**: Estimated text width vs available space
5. **Font Usage**: Consistent typography tokens

### Validation Report

```python
report = FormattingReport(
    total_slides=10,
    errors=[...],      # Critical issues
    warnings=[...],    # Potential issues
    info=[...]         # Informational
)

print(report.summary())
# Output:
# Formatting Report: 10 slides
#   Errors: 0
#   Warnings: 2
#   Info: 15
```

### Custom Validation

```python
from app.design_system import SlideValidator, ValidationResult

validator = SlideValidator(grid, slide_dims, colors)

# Check bounds
bounds = LayoutBounds(0, 0, 10, 7.5)
results = validator.validate_bounds(bounds)

# Check contrast
contrast_result = validator.validate_contrast(
    text_color, bg_color, is_large_text=True
)

# Check text overflow
overflow_result = validator.validate_text_overflow(
    "Long text...", bounds, font_size=20, font_name="Calibri"
)
```

## Text Fitting

### Automatic Fitting

The system automatically fits text to available width:

```python
from app.design_system import TextFitter

# Fit text to width
fitted_text, font_size = TextFitter.fit_text_to_width(
    text="Very long text that might overflow",
    max_width_pt=500,  # Points
    min_font_size=14,
    max_font_size=36,
    initial_font_size=20,
    font_name="Calibri"
)
```

### Text Wrapping

```python
# Wrap text into lines
lines = TextFitter.wrap_text_lines(
    text="Long text to wrap",
    max_width_pt=400,
    font_size_pt=20,
    font_name="Calibri",
    max_lines=5
)
```

## Grid System

### Using the Grid

```python
from app.design_system import GridSystem, SlideDimensions

grid = GridSystem(
    columns=12,
    gutter=0.25,  # inches
    margin_left=0.75,
    margin_right=0.75,
    margin_top=0.5,
    margin_bottom=0.5
)

slide_dims = SlideDimensions(width=10, height=7.5)

# Get column position (col 0-11, span 1-12)
x, width = grid.column_position(slide_dims.width, col=0, span=6)  # Left half
x2, width2 = grid.column_position(slide_dims.width, col=6, span=6)  # Right half
```

### Layout Builder Helpers

```python
from app.design_system import LayoutBuilder

layout = LayoutBuilder(grid, slide_dims)

# Title area
title_area = layout.title_area(row=0, height=1.0)

# Content area
content_area = layout.content_area(start_row=2, height=5.0)

# Two columns
left_col, right_col = layout.two_column(start_row=2, height=5.0)

# Chart area
chart_area = layout.chart_area(start_row=2, height=4.5)
```

## Spacing Scale

Use semantic spacing constants:

```python
from app.design_system import Spacing

# Use spacing tokens
p.space_after = Spacing.LG      # 16pt
p.space_before = Spacing.MD     # 12pt
title_box.text_frame.margin_top = Spacing.XL  # 24pt
```

## Typography Scale

Use typography hierarchy:

```python
from app.design_system import TypographyScale

typo = TypographyScale()

# Title sizes
p_title.font.size = Pt(typo.H1)  # 56pt
p_title.font.size = Pt(typo.H2)  # 36pt
p_title.font.size = Pt(typo.H3)  # 32pt

# Body sizes
p_body.font.size = Pt(typo.BODY_LARGE)  # 24pt
p_body.font.size = Pt(typo.BODY)        # 20pt
p_body.font.size = Pt(typo.CAPTION)     # 14pt

# Line heights
p.line_spacing = typo.LINE_HEIGHT_NORMAL  # 1.35
```

## Configuration

### `theme_config.json` Structure

```json
{
  "templates": {
    "template_id": {
      "name": "Template Name",
      "colors": {
        "bg": "#ffffff",
        "bg_mid": "#f0f0f0",
        "accent": "#0066cc",
        "accent_glow": "#3399ff",  // Optional
        "text_primary": "#000000",
        "text_secondary": "#333333"
      },
      "fonts": {
        "title": "Font Name",
        "body": "Font Name"
      }
    }
  },
  "typography": {
    "h1": 56,
    "h2": 36,
    "body": 20,
    // ...
  },
  "layout": {
    "grid_columns": 12,
    "gutter": 0.25,
    "margins": {
      "left": 0.75,
      "right": 0.75,
      "top": 0.5,
      "bottom": 0.5
    }
  },
  "validation": {
    "min_font_size": 14,
    "max_font_size": 56,
    "max_bullet_lines": 7,
    "require_wcag_aa": true
  }
}
```

## Migration Guide

### From Legacy Builder

The legacy `ppt_builder.py` remains functional. To migrate:

1. **No changes needed** - Legacy builder still works
2. **Optional**: Switch to `ppt_builder_v2` for validation
3. **Gradual**: Migrate slide types one at a time

### Testing

```python
# Test with validation
output_path, report = build_ppt(..., validate=True)

if report.has_errors:
    # Handle errors
    pass

if report.has_warnings:
    # Review warnings
    print(report.summary())
```

## Limitations

### PowerPoint Library Constraints

1. **No True Glow Effects**: Simulated with lighter accent colors
2. **Font Fallbacks**: PowerPoint may substitute fonts silently
3. **Text Measurement**: Estimated (not pixel-perfect)
4. **No Gradient Backgrounds**: Solid colors only (can be extended)
5. **Limited Shape Effects**: Basic shapes only

### Known Issues

1. **Font Availability**: Custom fonts may not be installed
2. **Text Wrapping**: PowerPoint handles wrapping, our estimates are approximate
3. **Chart Styling**: External chart images not styled by our system

## Best Practices

1. **Always Use Design Tokens**: Never hardcode `Pt(20)` or `Inches(0.8)`
2. **Validate Output**: Enable validation in production
3. **Test Edge Cases**: Long text, many bullets, small slides
4. **Use Grid System**: Always position elements via grid
5. **Check Contrast**: Ensure WCAG AA compliance
6. **Review Reports**: Check formatting reports for issues

## Examples

See `tests/test_templates.py` for usage examples.

## Support

For issues or questions:
1. Check `DIAGNOSIS.md` for known issues
2. Review validation reports
3. Test with different templates
4. Check `theme_config.json` for configuration
