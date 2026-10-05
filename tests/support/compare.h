/*
 * Golden-image comparison engine for the wxlunasvg test suite (plan Phase 3).
 *
 * Replaces the out-of-tree prototype's byte-exact comparePNGs (plan sections 4
 * and 9, which name it as the root cause of cross-platform flakiness). PNG
 * files are decoded to straight (non-premultiplied) RGBA and compared
 * pixel-by-pixel, mirroring the semantics of wxWidgets'
 * RGBSimilarTo / RGBASimilarTo matchers in tests/testimage.h:
 *
 *   - the two images must have identical dimensions;
 *   - a checked channel is "equal" when abs(expected - actual) <= tolerance;
 *   - the first pixel that breaches the tolerance is reported the way wx
 *     reports it: "first mismatch is at (x, y) which has value 0x... instead
 *     of the expected 0x...".
 *
 * Beyond wx's matcher this engine adds two knobs so anti-aliased edges can be
 * tolerated without hiding a whole-region regression:
 *
 *   - max_delta: a hard cap on the worst per-channel delta among differing
 *     pixels (default 255, i.e. disabled);
 *   - max_differing_pixel_ratio: the largest fraction of differing pixels
 *     that still counts as a match (default 0.0, i.e. the wx behaviour).
 *
 * The tolerance policy used by the corpus - exact for flat fills and geometry,
 * a small tolerance for anti-aliased edges - is recorded in
 * tests/data/manifest.json and tests/README.md.
 *
 * This header is C++17 (the suite is pinned to cxx_std_17 so a Phase 7 port
 * into wxWidgets' Catch2 v2.13.10 harness stays a one-line include change), so
 * it deliberately avoids C++20/23 library facilities.
 */

#ifndef WXLUNASVG_TEST_COMPARE_H
#define WXLUNASVG_TEST_COMPARE_H

#include <cstddef>
#include <cstdint>
#include <filesystem>
#include <string>
#include <vector>

namespace wxlunasvg {
namespace test {

/*
 * A decoded image in straight (non-premultiplied) RGBA order: r, g, b, a.
 * This matches what wxImage holds and what the PNG encoder emits, so no
 * premultiplication rounding leaks into the comparison.
 */
struct Image {
    int width{0};
    int height{0};
    std::vector<std::uint8_t> pixels;

    // True when the dimensions are positive and the buffer has exactly
    // width * height * 4 bytes.
    bool IsValid() const;

    // The pixel at (pixel_x, pixel_y) as 0xRRGGBBAA. Callers must keep the
    // coordinates in range.
    std::uint32_t PixelAt(int pixel_x, int pixel_y) const;
};

/*
 * tolerance            - per-channel absolute delta at or below which a channel
 *                        is considered equal (wx's RGBSimilarTo tolerance).
 * check_alpha          - false compares RGB only (RGBSimilarTo); true compares
 *                        RGB + A (RGBASimilarTo).
 * max_delta            - hard cap on the worst per-channel delta among
 *                        differing pixels.
 * max_differing_pixel_ratio - largest fraction of differing pixels tolerated.
 */
struct CompareOptions {
    int tolerance{0};
    bool check_alpha{true};
    int max_delta{255};
    double max_differing_pixel_ratio{0.0};
};

// Detail of the first pixel that breached the tolerance.
struct PixelMismatch {
    int x{0};
    int y{0};
    std::uint32_t expected{0}; // 0xRRGGBBAA
    std::uint32_t actual{0};   // 0xRRGGBBAA
    int delta{0};              // worst checked-channel delta at this pixel
};

struct CompareResult {
    bool passed{false};
    bool size_mismatch{false};
    int expected_width{0};
    int expected_height{0};
    int actual_width{0};
    int actual_height{0};
    std::size_t total_pixels{0};
    std::size_t differing_pixels{0};
    double differing_pixel_ratio{0.0};
    int max_delta{0}; // worst per-channel delta seen at any differing pixel
    bool has_first_mismatch{false};
    PixelMismatch first_mismatch{};
    CompareOptions options{};

    // wx-style "first mismatch ..." line plus a summary, or the size-mismatch
    // / success message.
    std::string Describe() const;
};

// Compares two decoded images. Both must be valid (IsValid()); an invalid
// input is reported as a size mismatch so the caller never reads out of bounds.
CompareResult CompareImages(const Image& expected, const Image& actual, const CompareOptions& options);

struct LoadResult {
    bool ok{false};
    std::string error;
    Image image;
};

// Decodes a PNG file to straight RGBA. On failure ok is false and error is set.
LoadResult LoadPng(const std::filesystem::path& path);

struct FileCompareResult {
    bool ok{false}; // false => an input could not be loaded/decoded
    std::string error;
    CompareResult comparison{};
    bool diff_written{false};
    std::string diff_path;
};

// The plan's comparePng(a, b, tolerance), extended to files and options: loads
// both PNGs and compares decoded pixels. On failure - and only on failure - a
// diff PNG is written when diff_path is non-empty.
FileCompareResult ComparePng(const std::filesystem::path& expected_path,
                             const std::filesystem::path& actual_path,
                             const CompareOptions& options,
                             const std::filesystem::path& diff_path = std::filesystem::path());

// Writes a reviewable diff visualisation: a dimmed luminance rendering of the
// expected image with every differing pixel marked red. The two images must
// have matching, valid dimensions. Returns false and sets error on failure.
bool WriteDiffPng(const std::filesystem::path& output_path,
                  const Image& expected,
                  const Image& actual,
                  const CompareOptions& options,
                  std::string& error);

} // namespace test
} // namespace wxlunasvg

#endif // WXLUNASVG_TEST_COMPARE_H
