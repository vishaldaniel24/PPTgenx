# PPT Generation Pipeline Diagnosis

## A) Rendering Pipeline Map

### Layout Decision Points

1. **Slide Dimensions** (`ppt_builder.py:377-378`)
   - Hardcoded: `Inches(10)` width, `Inches(7.5)` height
   - No abstraction for different aspect ratios

2. **Margins & Spacing** (scattered throughout)
   - Title slide: `Inches(1)` left margin, `Inches(2.5)` top
   - Content slide: `Inches(0.8)` left, `Inches(0.5)` top
   - No consistent margin system

3. **Typography** (hardcoded in each function)
   - Title slide: `Pt(56)` title, `Pt(28)` subtitle
   - Content slide: `Pt(36)` title, `Pt(20)` body
   - Chart slide: `Pt(32)` title, `Pt(22)` placeholder
   - No typography scale/tokens

4. **Color Tokens** (`ppt_builder.py:21-98`)
   - Defined in TEMPLATES dict but not systematically applied
   - No contrast validation
   - Colors converted to RGBColor but no validation

5. **Chart Styling** (`ppt_builder.py:341-349`)
   - Fixed positioning: `Inches(0.85)`, `Inches(1.45)`
   - Fixed size: `Inches(8.3)`, `Inches(5.6)`
   - No grid alignment

### Sources of Non-Determinism

1. **Text Width Calculation** (`ppt_builder.py:246`)
   - Uses `len(text) * 12` - inaccurate approximation
   - No actual font metrics
   - Underline width calculation is guesswork

2. **Font Fallbacks**
   - No fallback mechanism if font not available
   - PowerPoint may substitute fonts silently

3. **Text Truncation** (`ppt_builder.py:270, 418`)
   - Arbitrary `[:90]` character limit
   - No consideration of actual rendered width
   - May truncate mid-word

4. **Bullet Count** (`ppt_builder.py:262-264`)
   - Logic: `min(len(bullets), 7)` then fallback to 4
   - Inconsistent with content needs

5. **Layout Coordinates**
   - All positions hardcoded in Inches()
   - No grid system
   - Elements may overlap on different slide sizes

## B) Top 10 Layout/Formatting Failure Modes

1. **Text Overflow** ⚠️ CRITICAL
   - Fixed widths (`Inches(8.5)`) with no text fitting
   - Long titles/clipped text
   - Bullets extend beyond bounds

2. **Inconsistent Spacing** ⚠️ HIGH
   - Different margins per slide type
   - Inconsistent paragraph spacing (`Pt(16)` vs `Pt(8)`)
   - No spacing scale

3. **Poor Alignment** ⚠️ HIGH
   - No grid system
   - Elements aligned to arbitrary positions
   - Charts not aligned to content

4. **Typography Inconsistency** ⚠️ MEDIUM
   - Font sizes hardcoded throughout
   - No hierarchy system
   - Line heights inconsistent (`1.35` vs `1.2`)

5. **Color Contrast Issues** ⚠️ MEDIUM
   - No WCAG validation
   - Light text on light bg possible
   - No contrast checking

6. **Magic Numbers** ⚠️ MEDIUM
   - `Inches(0.8)`, `Pt(36)`, `[:90]` scattered everywhere
   - No named constants
   - Hard to maintain/change

7. **No Validation** ⚠️ MEDIUM
   - No bounds checking
   - No overflow detection
   - No quality reports

8. **Chart Positioning** ⚠️ LOW
   - Fixed coordinates
   - Not aligned to grid
   - May overlap with titles

9. **Text Measurement** ⚠️ LOW
   - Estimated width (`len * 12`) inaccurate
   - No actual font metrics
   - Underline width wrong

10. **No Overflow Protection** ⚠️ LOW
    - Text truncated arbitrarily
    - No continuation slides
    - No smart wrapping

## C) Refactor Strategy

### Phase 1: Design System Foundation ✅
- Create `design_system.py` with tokens, grid, typography
- Create `theme_config.json` for configuration
- Add text fitting utilities

### Phase 2: Refactor Builder
- Replace hardcoded values with design system tokens
- Use grid system for all layouts
- Add text fitting to all text elements

### Phase 3: Validation
- Add SlideValidator
- Generate formatting reports
- Check bounds, contrast, overflow

### Phase 4: Testing
- Add validation tests
- Test edge cases (long text, many bullets)
- Generate sample decks
